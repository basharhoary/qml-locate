# app/routing.py
from __future__ import annotations

import json
from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, QUrl, QUrlQuery, QTimer, QByteArray
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply


JsonDict = Dict[str, object]
LatLon = Tuple[float, float]  # (lat, lon)


class RoutingClient(QObject):
    """
    Async HTTP client for:
      - Nominatim geocoding
      - OSRM routing
      - Generic JSON GET (used for IP fallback)

    Features:
      - per-request timeout (ms)
      - one retry with backoff on 429/5xx/timeout
      - polite User-Agent (required by Nominatim)
    """

    def __init__(
        self,
        user_agent: str,
        timeouts_ms: Dict[str, int],
        retry_cfg: Dict[str, object],
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)

        self._ua = user_agent.strip() or "qml-locate/0.1 (+contact: you@example.com)"
        # Defaults if not provided
        self._geocode_timeout = int(timeouts_ms.get("geocode_ms", 10000))
        self._route_timeout = int(timeouts_ms.get("route_ms", 15000))

        self._retry_enabled = bool(retry_cfg.get("enabled", True))
        self._retries = int(retry_cfg.get("retries", 1))
        self._backoff_ms = int(retry_cfg.get("backoff_ms", 600))

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def geocode_async(
        self,
        text: str,
        on_ok: Callable[[float, float], None],
        on_err: Callable[[str], None],
    ) -> None:
        """
        Geocode a free-text query with Nominatim.
        Calls on_ok(lat, lon) on success.
        """
        if not text.strip():
            on_err("Destination not found.")
            return

        url = QUrl("https://nominatim.openstreetmap.org/search")
        q = QUrlQuery()
        q.addQueryItem("q", text)
        q.addQueryItem("format", "json")
        q.addQueryItem("limit", "1")
        url.setQuery(q)

        self._get_json_with_retry(
            url=url,
            timeout_ms=self._geocode_timeout,
            on_ok=lambda js: self._parse_nominatim(js, on_ok, on_err),
            on_err=lambda msg: on_err(msg or "Geocoding failed."),
        )

    def route_async(
        self,
        orig_lon: float,
        orig_lat: float,
        dest_lon: float,
        dest_lat: float,
        on_ok: Callable[[List[LatLon], float, float], None],
        on_err: Callable[[str], None],
    ) -> None:
        """
        Route via public OSRM demo server (driving).
        Returns:
          on_ok(path_latlon=[(lat,lon),...], distance_m, duration_s)
        """
        # OSRM expects "lon,lat;lon,lat"
        base = f"https://router.project-osrm.org/route/v1/driving/{orig_lon},{orig_lat};{dest_lon},{dest_lat}"
        url = QUrl(base)
        q = QUrlQuery()
        q.addQueryItem("overview", "full")
        q.addQueryItem("geometries", "geojson")
        url.setQuery(q)

        def parse_route(js: JsonDict):
            try:
                routes = js.get("routes") or []
                if not routes:
                    on_err("No route found.")
                    return
                route = routes[0]
                geom = route.get("geometry") or {}
                coords = geom.get("coordinates") or []  # [[lon, lat], ...]
                # Convert to [(lat, lon), ...] for QML
                path_latlon: List[LatLon] = [(float(lat), float(lon)) for lon, lat in coords]
                distance_m = float(route.get("distance", 0.0))
                duration_s = float(route.get("duration", 0.0))
                on_ok(path_latlon, distance_m, duration_s)
            except Exception:
                on_err("Failed to parse route.")

        self._get_json_with_retry(
            url=url,
            timeout_ms=self._route_timeout,
            on_ok=parse_route,
            on_err=lambda msg: on_err(msg or "Routing failed."),
        )

    def json_get_async(
        self,
        url: str,
        on_ok: Callable[[JsonDict], None],
        on_err: Callable[[str], None],
        timeout_ms: Optional[int] = None,
    ) -> None:
        """
        Generic JSON GET with timeout and retry.
        """
        self._get_json_with_retry(
            url=QUrl(url),
            timeout_ms=int(timeout_ms or self._geocode_timeout),
            on_ok=on_ok,
            on_err=on_err,
        )

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _parse_nominatim(
        self,
        js: JsonDict,
        on_ok: Callable[[float, float], None],
        on_err: Callable[[str], None],
    ) -> None:
        try:
            arr = js if isinstance(js, list) else []
            if not arr:
                on_err("Destination not found.")
                return
            dlat = float(arr[0]["lat"])
            dlon = float(arr[0]["lon"])
            on_ok(dlat, dlon)
        except Exception:
            on_err("Geocoding parse error.")

    # ---- Core GET with one retry & timeout -------------------------------- #

    def _get_json_with_retry(
        self,
        url: QUrl,
        timeout_ms: int,
        on_ok: Callable[[JsonDict], None],
        on_err: Callable[[str], None],
    ) -> None:
        """
        Issue a GET request; on transient failure (429/5xx/timeout), retry once with backoff if enabled.
        """
        attempts_left = 1 + (self._retries if self._retry_enabled else 0)

        def attempt():
            nonlocal attempts_left
            attempts_left -= 1
            self._single_json_get(
                url=url,
                timeout_ms=timeout_ms,
                on_ok=on_ok,
                on_err=lambda msg, status: self._maybe_retry(msg, status, attempt, on_err),
            )

        attempt()

    def _maybe_retry(
        self,
        msg: str,
        status: Optional[int],
        retry_fn: Callable[[], None],
        final_err: Callable[[str], None],
    ):
        # Retry on 0 (network/timeout) or 429 or 5xx
        transient = (status is None) or (status == 0) or (status == 429) or (500 <= status < 600)
        if transient and self._retry_enabled:
            # Backoff, then retry if we still have attempts (managed by _get_json_with_retry)
            t = QTimer(self)
            t.setSingleShot(True)

            def fire():
                t.deleteLater()
                retry_fn()

            t.timeout.connect(fire)
            t.start(self._backoff_ms)
        else:
            final_err(msg or "Network error.")

    def _single_json_get(
        self,
        url: QUrl,
        timeout_ms: int,
        on_ok: Callable[[JsonDict], None],
        on_err: Callable[[str, Optional[int]], None],
    ) -> None:
        req = QNetworkRequest(url)
        # Required: polite UA per Nominatim policy
        req.setRawHeader(b"User-Agent", QByteArray(self._ua.encode("utf-8")))
        req.setRawHeader(b"Accept", b"application/json")

        reply = self._nam.get(req)

        # Timeout handling
        timer = QTimer(self)
        timer.setSingleShot(True)

        def on_timeout():
            # Abort and signal timeout with status=None
            if reply.isRunning():
                reply.abort()
            cleanup()
            on_err("Request timed out.", None)

        timer.timeout.connect(on_timeout)
        timer.start(max(1, int(timeout_ms)))

        def finish():
            # Stop timeout timer
            if timer.isActive():
                timer.stop()
            cleanup()

            # Read status code
            status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
            status_code: Optional[int] = int(status) if status is not None else None

            if reply.error() != QNetworkReply.NetworkError.NoError:
                # Network-level error
                on_err(self._qt_error_string(reply), status_code)
                return

            try:
                raw = bytes(reply.readAll())
                js = json.loads(raw.decode("utf-8", errors="replace") or "{}")
            except Exception:
                on_err("Invalid JSON response.", status_code)
                return

            # Handle HTTP errors even if payload arrived
            if status_code is not None and not (200 <= status_code < 300):
                # Optionally read message from body
                msg = self._http_error_message(js, status_code)
                on_err(msg, status_code)
                return

            on_ok(js)

        def cleanup():
            try:
                reply.finished.disconnect(finish)
            except Exception:
                pass
            try:
                reply.errorOccurred.disconnect(error_occ)
            except Exception:
                pass
            timer.deleteLater()
            reply.deleteLater()

        def error_occ(_err):
            # Let 'finish' read the body if any; but ensure we don't double-signal
            # We rely on finished() to be emitted after errorOccurred in Qt.
            pass

        reply.finished.connect(finish)
        reply.errorOccurred.connect(error_occ)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _qt_error_string(reply: QNetworkReply) -> str:
        err = reply.error()
        # Map some common errors to friendlier text
        if err == QNetworkReply.NetworkError.OperationCanceledError:
            return "Request canceled."
        if err == QNetworkReply.NetworkError.ConnectionRefusedError:
            return "Connection refused."
        if err == QNetworkReply.NetworkError.HostNotFoundError:
            return "Host not found."
        if err == QNetworkReply.NetworkError.TimeoutError:
            return "Network timeout."
        return reply.errorString() or "Network error."

    @staticmethod
    def _http_error_message(js: JsonDict, status_code: int) -> str:
        # Try to extract a message from common JSON error shapes
        if isinstance(js, dict):
            for key in ("message", "error", "detail", "note"):
                val = js.get(key)
                if isinstance(val, str) and val.strip():
                    return f"{val} (HTTP {status_code})"
        return f"HTTP {status_code}"
