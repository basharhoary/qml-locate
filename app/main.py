# app/main.py
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl, QTimer, QStandardPaths
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from . import APP_NAME, __version__, load_settings, project_path
from .backend import Backend

from . import APP_NAME, __version__, load_settings, project_path, init_logging

import logging
log = logging.getLogger(__name__)

def main() -> int:
    # --- Qt app ---
    app = QGuiApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)

    # --- Settings & cache paths ---
    cfg = load_settings()

    init_logging(cfg)

    cache_root = Path(QStandardPaths.writableLocation(QStandardPaths.CacheLocation))
    cache_root.mkdir(parents=True, exist_ok=True)

    tile_cache_dirname = cfg["maps"]["tile_cache_dirname"]
    tile_cache_dir = cache_root / tile_cache_dirname
    tile_cache_dir.mkdir(parents=True, exist_ok=True)

    # --- Backend & QML engine ---
    engine = QQmlApplicationEngine()
    backend = Backend()

    # Expose things QML needs
    ctx = engine.rootContext()
    ctx.setContextProperty("backend", backend)
    ctx.setContextProperty("tileCacheDir", str(tile_cache_dir))
    ctx.setContextProperty("tileServerUrl", cfg["maps"]["tile_server"])
    ctx.setContextProperty("tileHighDpi", bool(cfg["maps"]["high_dpi_tiles"]))
    ctx.setContextProperty("tileCopyright", cfg["maps"]["copyright"])
    ctx.setContextProperty("initialZoom", int(cfg["maps"]["initial_zoom"]))
    ctx.setContextProperty("appVersion", __version__)
    ctx.setContextProperty("zoomAnimMs", int(cfg["ui"]["zoom_anim_ms"]))
    ctx.setContextProperty("wheelThrottleMs", int(cfg["ui"]["wheel_throttle_ms"]))


    # Load QML
    qml_path = project_path("app", "ui", "main.qml")
    engine.load(QUrl.fromLocalFile(str(qml_path)))

    if not engine.rootObjects():
        print("Failed to load QML.", file=sys.stderr)
        return 1

    # Auto-locate shortly after startup (keeps UI responsive)
    QTimer.singleShot(300, backend.locate)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
