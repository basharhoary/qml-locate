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
                onClicked: backend.routeTo(destField.text)
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
            // (For best performance later, you can move this mapping to Python once per route.)
            property var routeCoords: (backend.routePoints || []).map(function(p) {
                return QtPositioning.coordinate(p[0], p[1]);
            })

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
                duration: 150   // from settings (mirrors ui.zoom_anim_ms)
                easing.type: Easing.InOutQuad
            }

            // --- Mouse wheel coalescing (throttle) ---
            property int pendingWheelSteps: 0
            Timer {
                id: wheelTimer
                interval: 100  // mirrors ui.wheel_throttle_ms
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
    // Connections {
    //     target: backend
    //     onStatusChanged: {
    //         const s = backend.status.toLowerCase()
    //         if (s.includes("not found") || s.includes("error") || s.includes("failed") ) {
    //             showToast(backend.status)
    //         }
    //     }
    // }
}
