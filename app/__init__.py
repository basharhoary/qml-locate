# app/__init__.py
"""
App package bootstrap for qml-locate.

- Provides __version__ and APP_NAME.
- load_settings(): returns a dict merged from defaults + config/settings.json (if present).
- get_user_agent(): polite UA for Nominatim/OSRM requests.
- project_path(): convenience resolver for paths relative to repo root.

Keep this module side-effect free (no Qt imports).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

import logging
from logging.handlers import RotatingFileHandler

__all__ = [
    "APP_NAME",
    "__version__",
    "load_settings",
    "init_logging",
    "project_path",
    "get_user_agent",
]

APP_NAME = "qml-locate"
__version__ = "0.1.0"

# Paths
PKG_ROOT = Path(__file__).resolve().parent        # .../qml-locate/app
PROJECT_ROOT = PKG_ROOT.parent                    # .../qml-locate
CONFIG_PATH = PROJECT_ROOT / "config" / "settings.json"

# Defaults (safe, override via settings.json)
DEFAULT_SETTINGS: Dict[str, Any] = {
    "network": {
        "timeouts": {
            "geocode_ms": 10_000,
            "route_ms": 15_000,
        },
        "retry": {
            "enabled": True,
            "retries": 1,
            "backoff_ms": 600,
        },
        "headers": {
            # Filled by get_user_agent() at call site; keep as fallback:
            "User-Agent": f"{APP_NAME}/0.1 (+contact: you@example.com)"
        },
    },
    "maps": {
        "tile_server": "https://tile.openstreetmap.org/",
        "tile_cache_dirname": "qml-locate-tiles",
        "high_dpi_tiles": True,
        "copyright": "© OpenStreetMap contributors",
        "initial_zoom": 13,
    },
    "ui": {
        "wheel_throttle_ms": 100,
        "zoom_anim_ms": 150,
        "debounce_route_ms": 500,
    },
    "logging": {
        "level": "INFO",
        "dir": "logs",
        "filename": "app.log",
        "max_bytes": 1_000_000,
        "backup_count": 3,
    },
}

def init_logging(settings: Dict[str, Any]) -> None:
    lg = logging.getLogger()
    if lg.handlers:
        return  # already initialized
    level_name = settings["logging"].get("level", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    lg.setLevel(level)

    log_dir = project_path(settings["logging"]["dir"])
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / settings["logging"]["filename"]
    handler = RotatingFileHandler(
        log_file,
        maxBytes=int(settings["logging"]["max_bytes"]),
        backupCount=int(settings["logging"]["backup_count"])
    )
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(fmt)
    lg.addHandler(handler)

    # also echo to console
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    lg.addHandler(console)


def project_path(*parts: str) -> Path:
    """
    Resolve a path under the repository root (next to app/, config/, etc.).
    Example: project_path("assets", "screenshot.png")
    """
    return PROJECT_ROOT.joinpath(*parts)


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """Recursive dict merge: overlay values overwrite base."""
    out = dict(base)
    for k, v in (overlay or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings() -> Dict[str, Any]:
    """
    Load settings from DEFAULT_SETTINGS, then merge config/settings.json if present.
    You can also point to a custom config via env APP_SETTINGS=/path/to.json.
    """
    settings = dict(DEFAULT_SETTINGS)

    # Env override path
    env_path = os.getenv("APP_SETTINGS")
    cfg_path = Path(env_path).expanduser() if env_path else CONFIG_PATH

    if cfg_path.is_file():
        try:
            with cfg_path.open("r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            settings = _deep_merge(settings, user_cfg)
        except Exception:
            # Keep defaults on parse errors; avoid raising here
            pass

    return settings


def get_user_agent(contact_email: str | None = None, app_version: str | None = None) -> str:
    """
    Build a polite User-Agent for external services (Nominatim/OSRM).
    Include a way to contact you per their usage policy.
    """
    email = (contact_email or "you@example.com").strip()
    ver = (app_version or __version__).strip()
    return f"{APP_NAME}/{ver} (+contact: {email})"
