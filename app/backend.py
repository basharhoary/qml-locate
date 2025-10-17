# app/backend.py
from __future__ import annotations

from typing import List, Tuple, Optional

from PySide6.QtCore import (
    QObject, Signal, Property, Slot, QTimer, QElapsedTimer, QUrl
)
from PySide6.QtPositioning import QGeoPositionInfoSource

from . import load_settings, get_user_agent
from .routing import RoutingClient  # you'll implement this next (async Qt networking)


class Backend(QObject):
    # ---- Signals for QML bindings
    latitudeChanged = Signal(float)
    longitudeChanged = Signal(float)
    statusChanged = Signal(str)
    isBusyChanged = Signal()

    routePointsChanged = Signal()         # QVariantList of [lat, lon]
    routeDistanceChanged = Signal(float)  # meters
    routeDurationChanged = Signal(float)  # seconds

    destinationChanged = Signal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        self._cfg = load_settings()
        self._user_agent = get_user_agent(contact_email="basharhoary@hotmail.com")

        # Location state
        self._lat: float = 52.3759  # Braunschweig defaults
        self._lon: float = 10.5268
        self._status: str = "Idle"
        self._isBusy: bool = False
        self._geo_src: Optional[QGeoPositionInfoSource] = None
        self._geo_timeout: Optional[QTimer] = None

        # Debounce
        self._lastRouteMs = QElapsedTimer()
        self._lastRouteMs.start()

        # Route state exposed to QML
        self._route_points: List[List[float]] = []  # [[lat, lon], ...]
        self._route_distance_m: float = 0.0
        self._route_duration_s: float = 0.0

        # Destination text (so QML can bind if desired)
        self._destination_text: str = ""

        # Networking client (Qt async via QNetworkAccessManager in routing.py)
        self._router = RoutingClient(
            user_agent=self._user_agent,
            timeouts_ms=self._cfg["network"]["timeouts"],
            retry_cfg=self._cfg["network"]["retry"],
            parent=self,
        )

    # ------------------ Properties (Location) ------------------
    def get_latitude(self) -> float: return self._lat
    def get_longitude(self) -> float: return self._lon
    def get_status(self) -> str: return self._status
    def get_isBusy(self) -> bool: return self._isBusy

    def _set_latitude(self, v: float):
        if v != self._lat:
            self._lat = v
            self.latitudeChanged.emit(self._lat)

    def _set_longitude(self, v: float):
        if v != self._lon:
            self._lon = v
            self.longitudeChanged.emit(self._lon)

    def _set_status(self, s: str):
        if s != self._status:
            self._status = s
            self.statusChanged.emit(self._status)

    def _set_busy(self, v: bool):
        if v != self._isBusy:
            self._isBusy = v
            self.isBusyChanged.emit()

    latitude  = Property(float, fget=get_latitude, notify=latitudeChanged)
    longitude = Property(float, fget=get_longitude, notify=longitudeChanged)
    status    = Property(str,   fget=get_status, notify=statusChanged)
    isBusy    = Property(bool,  fget=get_isBusy, notify=isBusyChanged)

    # ------------------ Properties (Route) ------------------
    def get_route_points(self): return self._route_points
    def get_route_distance(self) -> float: return self._route_distance_m
    def get_route_duration(self) -> float: return self._route_duration_s

    routePoints  = Property('QVariantList', fget=get_route_points, notify=routePointsChanged)
    routeDistance = Property(float, fget=get_route_distance, notify=routeDistanceChanged)
    routeDuration = Property(float, fget=get_route_duration, notify=routeDurationChanged)

    # Destination text (optional QML binding)
    def get_destination(self) -> str: return self._destination_text
    def set_destination(self, t: str):
        t = (t or "").strip()
        if t != self._destination_text:
            self._destination_text = t
            self.destinationChanged.emit(self._destination_text)

    destination = Property(str, fget=get_destination, fset=set_destination, notify=destinationChanged)

    # ------------------ Public Slots ------------------
    @Slot()
    def locate(self):
        """
        Try platform location (Windows Location / etc.).
        If it doesn't respond quickly, fall back to IP geolocation (async).
        """
        if self._isBusy:
            # Allow locate while busy with routing? Safer to block; keeps UI logic simple.
            return

        self._set_status("Locating…")
        self._cleanup_geosource()

        src = QGeoPositionInfoSource.createDefaultSource(self)
        if src is None:
            self._set_status("No system location provider. Using IP location…")
            self._fallback_ip_async()
            return

        self._geo_src = src

        def on_ok(posinfo):
            c = posinfo.coordinate()
            self._set_latitude(c.latitude())
            self._set_longitude(c.longitude())
            self._set_status("Got location from system services.")
            self._stop_geo_timeout()
            self._cleanup_geosource()

        src.positionUpdated.connect(on_ok)
        src.requestUpdate()

        # Timeout → IP fallback
        self._start_geo_timeout(
            self._cfg["network"]["timeouts"].get("geocode_ms", 10000) // 2,
            "Using approximate IP location…",
        )

    @Slot(str)
    def routeTo(self, destination_text: str):
        """
        Debounced, async: geocode → route. Updates route state on success.
        """
        if self._isBusy:
            return

        # Debounce rapid re-entry
        if self._lastRouteMs.elapsed() < int(self._cfg["ui"]["debounce_route_ms"]):
            return
        self._lastRouteMs.restart()

        dest = (destination_text or "").strip()
        self.set_destination(dest)
        if not dest:
            self._set_status("Enter a destination address.")
            return

        self._set_busy(True)
        self._set_status("Geocoding…")

        # 1) Geocode destination (async)
        def geo_ok(dlat: float, dlon: float):
            self._set_status("Requesting route…")
            # 2) Route (async)
            self._router.route_async(
                orig_lon=self._lon,
                orig_lat=self._lat,
                dest_lon=dlon,
                dest_lat=dlat,
                on_ok=route_ok,
                on_err=route_err,
            )

        def geo_err(msg: str):
            self._set_status(msg or "Destination not found.")
            self._set_busy(False)

        def route_ok(path_latlon: List[Tuple[float, float]], distance_m: float, duration_s: float):
            # OSRM returns [lon, lat]; routing client should already convert to [lat, lon] for QML
            self._route_points = [[float(lat), float(lon)] for (lat, lon) in path_latlon]
            self._route_distance_m = float(distance_m)
            self._route_duration_s = float(duration_s)

            self.routePointsChanged.emit()
            self.routeDistanceChanged.emit(self._route_distance_m)
            self.routeDurationChanged.emit(self._route_duration_s)

            self._set_status("Route ready.")
            self._set_busy(False)

        def route_err(msg: str):
            self._set_status(msg or "No route found.")
            self._set_busy(False)

        self._router.geocode_async(dest, on_ok=geo_ok, on_err=geo_err)

    @Slot()
    def clearRoute(self):
        """Clear current route."""
        self._route_points = []
        self._route_distance_m = 0.0
        self._route_duration_s = 0.0
        self.routePointsChanged.emit()
        self.routeDistanceChanged.emit(self._route_distance_m)
        self.routeDurationChanged.emit(self._route_duration_s)
        self._set_status("Route cleared.")

    # ------------------ Internal helpers ------------------
    def _start_geo_timeout(self, ms: int, msg_on_fire: str):
        self._stop_geo_timeout()
        t = QTimer(self)
        t.setSingleShot(True)

        def fire():
            self._set_status(msg_on_fire)
            self._cleanup_geosource()
            self._fallback_ip_async()

        t.timeout.connect(fire)
        t.start(ms)
        self._geo_timeout = t

    def _stop_geo_timeout(self):
        if self._geo_timeout:
            self._geo_timeout.stop()
            self._geo_timeout.deleteLater()
            self._geo_timeout = None

    def _cleanup_geosource(self):
        if self._geo_src:
            try:
                self._geo_src.positionUpdated.disconnect()
            except Exception:
                pass
            self._geo_src.deleteLater()
            self._geo_src = None

    # ---- Async IP fallback using the same RoutingClient's QNetworkAccessManager
    def _fallback_ip_async(self):
        """
        Try a couple of public IP geolocation endpoints asynchronously.
        Updates lat/lon on first success; sets a status on failure.
        """
        # Try in order; stop at first success.
        endpoints = [
            ("https://ipapi.co/json/", ("latitude", "longitude")),
            ("http://ip-api.com/json/", ("lat", "lon")),
        ]
        idx = 0

        def try_next():
            nonlocal idx
            if idx >= len(endpoints):
                self._set_status("Could not determine location.")
                return

            url, keys = endpoints[idx]
            idx += 1

            def ok_cb(js: dict):
                lat = js.get(keys[0])
                lon = js.get(keys[1])
                if lat is not None and lon is not None:
                    try:
                        self._set_latitude(float(lat))
                        self._set_longitude(float(lon))
                        self._set_status("Got approximate location from IP.")
                        return
                    except Exception:
                        pass
                # If parsing failed, move to next
                try_next()

            def err_cb(_msg: str):
                try_next()

            self._router.json_get_async(url, on_ok=ok_cb, on_err=err_cb)

        try_next()
