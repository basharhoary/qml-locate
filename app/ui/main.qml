import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtLocation
import QtPositioning

ApplicationWindow {
    id: win
    visible: true
    width: 960
    height: 640
    title: "Locate & Route — QML + PySide6  (v" + appVersion + ")"

    // ---------- OSM Plugin ----------
    Plugin {
        id: osm
        name: "osm"
        PluginParameter { name: "osm.mapping.providersrepository.disabled"; value: true }
        PluginParameter { name: "osm.mapping.host"; value: tileServerUrl }           // from context
        PluginParameter { name: "osm.mapping.highdpi_tiles"; value: tileHighDpi }    // from context
        PluginParameter { name: "osm.mapping.copyright"; value: tileCopyright }      // from context
        PluginParameter { name: "osm.mapping.cache.directory"; value: tileCacheDir } // from context
    }

    // ---------- Toast (lightweight) ----------
    Popup {
        id: toast
        x: (win.width - implicitWidth) / 2
        y: win.height - implicitHeight - 24
        padding: 10
        modal: false
        focus: false
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { radius: 6; color: "#333"; opacity: 0.92 }
        contentItem: Text {
            id: toastText
            text: ""
            color: "white"
            font.pixelSize: 14
            wrapMode: Text.WordWrap
        }
        Timer {
            id: toastTimer
            interval: 2200; running: false; repeat: false
            onTriggered: toast.close()
        }
        function show(msg) {
            toastText.text = msg
            if (!toast.visible) toast.open()
            toastTimer.restart()
        }
    }

    function showToast(msg) { toast.show(msg) }

    // ---------- Layout ----------
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8

        // --- TOP BAR: locate + destination + route ---
        RowLayout {
            spacing: 10
            Layout.fillWidth: true

            Timer {
                id: routeDebounce
                interval: 500  // ms
                repeat: false;
                running: false
            }

            Button {
                text: "Locate now"
                enabled: !backend.isBusy
                onClicked: backend.locate()
            }

            TextField {
                id: destField
                placeholderText: "Destination (street, number, city)…"
                Layout.fillWidth: true
                enabled: !backend.isBusy
                text: backend.destination
                onAccepted: routeBtn.clicked()
                onTextChanged: backend.destination = text
            }

            Button {
                id: routeBtn
                text: "Route"
                enabled: !backend.isBusy
                onClicked: {
                    if (routeDebounce.running) return
                    routeDebounce.start()
                    backend.routeTo(destField.text)
                }
            }

            Button {
                text: "Clear"
                enabled: !backend.isBusy && (map.routeCoords.length > 0)
                onClicked: backend.clearRoute()
            }

            BusyIndicator {
                running: backend.isBusy
                visible: running
                Layout.preferredWidth: 28
                Layout.preferredHeight: 28
            }
        }

        // --- INFO BAR ---
        RowLayout {
            spacing: 16
            Layout.fillWidth: true

            Text {
                text: backend.routeDistance > 0
                      ? ("Distance: " + (backend.routeDistance/1000).toFixed(1) + " km")
                      : "Distance: –"
            }
            Text {
                text: backend.routeDuration > 0
                      ? ("Duration: " + (backend.routeDuration/60).toFixed(0) + " min")
                      : "Duration: –"
            }
            Item { Layout.fillWidth: true } // spacer
            Text {
                text: backend.status
                opacity: 0.8
                elide: Text.ElideRight
                Layout.preferredWidth: 320
            }
        }

        // --- MAP ---
        Map {
            id: map
            Layout.fillWidth: true
            Layout.fillHeight: true
            plugin: osm
            copyrightsVisible: true
            zoomLevel: initialZoom

            // center follows current location
            center: QtPositioning.coordinate(backend.latitude, backend.longitude)

            // current location marker
            MapQuickItem {
                coordinate: QtPositioning.coordinate(backend.latitude, backend.longitude)
                anchorPoint.x: 10; anchorPoint.y: 10
                sourceItem: Rectangle {
                    width: 20; height: 20; radius: 10
                    border.width: 2; border.color: "black"; color: "white"
                }
            }

            // Prepare route coordinates when backend.routePoints changes
            property var routeCoords: (function() {
                var pts = backend.routePoints || []
                var out = []
                for (var i = 0; i < pts.length; ++i) {
                    out.push(QtPositioning.coordinate(pts[i][0], pts[i][1]))
                }
                // auto-fit after recompute
                if (out.length > 1) {
                    Qt.callLater(function(){ fitPath(out) })
                }
                return out
            })()

            MapPolyline {
                id: routeLine
                line.width: 5
                line.color: "#1976d2"
                path: map.routeCoords
                visible: path.length > 0
            }

            // --- Zoom controls (right-top) ---
            Column {
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 10
                spacing: 8
                property int size: 40

                Button {
                    text: "+"
                    width: parent.size; height: parent.size
                    onClicked: {
                        zoomAnimator.to = Math.min(map.maximumZoomLevel, map.zoomLevel + 1)
                        zoomAnimator.start()
                    }
                }
                Button {
                    text: "−"
                    width: parent.size; height: parent.size
                    onClicked: {
                        zoomAnimator.to = Math.max(map.minimumZoomLevel, map.zoomLevel - 1)
                        zoomAnimator.start()
                    }
                }
            }

            // --- Smooth zoom animation ---
            NumberAnimation on zoomLevel {
                id: zoomAnimator
                duration: zoomAnimMs   // from settings (mirrors ui.zoom_anim_ms)
                easing.type: Easing.InOutQuad
            }

            // --- Mouse wheel coalescing (throttle) ---
            property int pendingWheelSteps: 0
            Timer {
                id: wheelTimer
                interval: wheelThrottleMs  // mirrors ui.wheel_throttle_ms
                repeat: false
                onTriggered: {
                    var target = map.zoomLevel + map.pendingWheelSteps
                    zoomAnimator.to = Math.max(map.minimumZoomLevel, Math.min(map.maximumZoomLevel, target))
                    zoomAnimator.start()
                    map.pendingWheelSteps = 0
                }
            }

            WheelHandler {
                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                onWheel: function (event) {
                    map.pendingWheelSteps += (event.angleDelta.y > 0) ? 1 : -1
                    wheelTimer.restart()
                    event.accepted = true
                }
            }

            // --- Pinch-to-zoom around gesture focus ---
            PinchHandler {
                target: null // we handle manually
                onActiveChanged: if (!active) eventPoint1.accepted = true
                onScaleChanged: {
                    var desired = map.zoomLevel + (scale - 1) * 1.0
                    zoomAnimator.to = Math.max(map.minimumZoomLevel, Math.min(map.maximumZoomLevel, desired))
                    zoomAnimator.start()
                }
            }

            // Ensure we prefer an OSM map type if multiple exist
            Component.onCompleted: {
                for (var i = 0; i < supportedMapTypes.length; ++i) {
                    var t = supportedMapTypes[i];
                    var n = (t.name || "").toLowerCase();
                    var d = (t.description || "").toLowerCase();
                    if (n.indexOf("openstreetmap") !== -1 || d.indexOf("openstreetmap") !== -1) {
                        activeMapType = t;
                        break;
                    }
                }
            }

            function fitPath(coords) {
                if (!coords || coords.length < 2) return
                var minLat =  90, maxLat = -90, minLon =  180, maxLon = -180
                for (var i = 0; i < coords.length; ++i) {
                    var c = coords[i]
                    minLat = Math.min(minLat, c.latitude)
                    maxLat = Math.max(maxLat, c.latitude)
                    minLon = Math.min(minLon, c.longitude)
                    maxLon = Math.max(maxLon, c.longitude)
                }
                // center
                var cenLat = (minLat + maxLat) / 2.0
                var cenLon = (minLon + maxLon) / 2.0
                center = QtPositioning.coordinate(cenLat, cenLon)

                // choose a zoom that roughly fits (simple heuristic)
                // shrink until the span fits; each level ~ halves visible span in raster tiles
                var spanLat = Math.max(0.0001, maxLat - minLat)
                var spanLon = Math.max(0.0001, maxLon - minLon)
                var span = Math.max(spanLat, spanLon)
                var z = maximumZoomLevel
                while (z > minimumZoomLevel && span * Math.pow(2, z - maximumZoomLevel) > 0.002) { // heuristic
                    z -= 1
                }
                zoomAnimator.to = Math.max(minimumZoomLevel, Math.min(maximumZoomLevel, z))
                zoomAnimator.start()
            }

            // --- Keyboard shortcuts ---
            Keys.onReleased: (event) => {
                if (event.key === Qt.Key_Plus || event.key === Qt.Key_Equal) {
                    zoomAnimator.to = Math.min(map.maximumZoomLevel, map.zoomLevel + 1); zoomAnimator.start(); event.accepted = true
                } else if (event.key === Qt.Key_Minus) {
                    zoomAnimator.to = Math.max(map.minimumZoomLevel, map.zoomLevel - 1); zoomAnimator.start(); event.accepted = true
                } else if (event.key === Qt.Key_L && (event.modifiers & Qt.ControlModifier)) {
                    destField.forceActiveFocus(); destField.selectAll(); event.accepted = true
                }
            }
            focus: true
        }
    }

    // Example: show short toasts for certain statuses (optional)
    Connections {
        target: backend
        function onStatusChanged() {
            const s = (backend.status || "").toLowerCase()
            if (s.includes("error") || s.includes("failed") || s.includes("not found") || s.includes("rate limited")) {
                showToast(backend.status)
            }
        }
    }
}
