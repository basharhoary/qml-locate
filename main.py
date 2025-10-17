import sys
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Property, Slot, QUrl, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtPositioning import QGeoPositionInfoSource


class Backend(QObject):
    latitudeChanged = Signal(float)
    longitudeChanged = Signal(float)
    statusChanged = Signal(str)

    def __init__(self):
        super().__init__()
        self._lat = 52.3759   # default (Braunschweig)
        self._lon = 10.5268
        self._status = "Idle"
        self._timeout = None
        self._src = None

    # --- QML properties
    def get_lat(self) -> float: return self._lat
    def set_lat(self, v: float):
        if v != self._lat:
            self._lat = v
            self.latitudeChanged.emit(self._lat)

    def get_lon(self) -> float: return self._lon
    def set_lon(self, v: float):
        if v != self._lon:
            self._lon = v
            self.longitudeChanged.emit(self._lon)

    def get_status(self) -> str: return self._status
    def set_status(self, s: str):
        if s != self._status:
            self._status = s
            self.statusChanged.emit(self._status)

    latitude  = Property(float, get_lat, set_lat, notify=latitudeChanged)
    longitude = Property(float, get_lon, set_lon, notify=longitudeChanged)
    status    = Property(str,   get_status, set_status, notify=statusChanged)

    # --- public API
    @Slot()
    def locate(self):
        """Try Windows location; fall back to IP if it doesn't answer quickly."""
        self.set_status("Locating…")
        self._cleanup_source()

        src = QGeoPositionInfoSource.createDefaultSource(self)
        if src is None:
            self._fallback_ip()
            return

        self._src = src

        def on_ok(posinfo):
            c = posinfo.coordinate()
            self.set_lat(c.latitude())
            self.set_lon(c.longitude())
            self.set_status("Got location from Windows services.")
            self._stop_timeout()
            self._cleanup_source()

        self._start_timeout(3500, "Using approximate IP location.")
        src.positionUpdated.connect(on_ok)
        src.requestUpdate()

    # --- helpers
    def _start_timeout(self, ms: int, msg: str):
        self._stop_timeout()
        t = QTimer(self)
        t.setSingleShot(True)

        def fire():
            self.set_status(msg)
            self._cleanup_source()
            self._fallback_ip()

        t.timeout.connect(fire)
        t.start(ms)
        self._timeout = t

    def _stop_timeout(self):
        if self._timeout:
            self._timeout.stop()
            self._timeout.deleteLater()
            self._timeout = None

    def _cleanup_source(self):
        if self._src:
            self._src.deleteLater()
            self._src = None

    def _fallback_ip(self):
        """Simple best-effort IP geolocation."""
        try:
            import requests
            for url in ("https://ipapi.co/json/", "http://ip-api.com/json/"):
                r = requests.get(url, timeout=5)
                r.raise_for_status()
                data = r.json()
                lat = data.get("latitude") or data.get("lat")
                lon = data.get("longitude") or data.get("lon")
                if lat is not None and lon is not None:
                    self.set_lat(float(lat))
                    self.set_lon(float(lon))
                    self.set_status("Got approximate location from IP.")
                    return
            self.set_status("Could not determine location.")
        except Exception:
            self.set_status("Could not determine location.")

if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()

    backend = Backend()
    engine.rootContext().setContextProperty("backend", backend)

    qml_path = Path(__file__).with_name("main.qml")
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    if not engine.rootObjects():
        sys.exit("Failed to load QML.")

    # auto-locate shortly after start
    QTimer.singleShot(300, backend.locate)

    sys.exit(app.exec())
