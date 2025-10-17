import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtLocation
import QtPositioning

ApplicationWindow {
    id: win
    visible: true
    width: 800
    height: 560
    title: "Locate Me — QML + PySide6"

    // Force free OSM tiles (no API key) and ignore provider repository.
    Plugin {
        id: osm
        name: "osm"
        PluginParameter { name: "osm.mapping.providersrepository.disabled"; value: true }
        PluginParameter { name: "osm.mapping.host"; value: "https://tile.openstreetmap.org/" }
        PluginParameter { name: "osm.mapping.highdpi_tiles"; value: true }
        PluginParameter { name: "osm.mapping.copyright"; value: "© OpenStreetMap contributors" }
        // NOTE: we deliberately do NOT set a custom cache directory to avoid
        //       "Failed to create cache directory" warnings.
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8

        RowLayout {
            spacing: 12

            Button { text: "Locate now"; onClicked: backend.locate() }

            Text { text: backend.status; elide: Text.ElideRight; Layout.fillWidth: true }
            Text { text: "Lat: " + backend.latitude.toFixed(5) }
            Text { text: "Lon: " + backend.longitude.toFixed(5) }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Map {
                id: map
                anchors.fill: parent
                plugin: osm
                zoomLevel: 13
                copyrightsVisible: true

                // center follows backend properties
                center: QtPositioning.coordinate(backend.latitude, backend.longitude)

                MapQuickItem {
                    coordinate: QtPositioning.coordinate(backend.latitude, backend.longitude)
                    anchorPoint.x: 10; anchorPoint.y: 10
                    sourceItem: Rectangle {
                        width: 20; height: 20; radius: 10
                        border.width: 2; border.color: "black"; color: "white"
                    }
                }

                WheelHandler {
                    id: mapWheelHandler
                    onWheel: {
                        var deltaSteps = wheel.angleDelta.y ? wheel.angleDelta.y / 120 : wheel.pixelDelta.y / 100;
                        if (!deltaSteps)
                            return;
                        var targetZoom = map.zoomLevel + deltaSteps;
                        targetZoom = Math.max(map.minimumZoomLevel, Math.min(map.maximumZoomLevel, targetZoom));
                        if (targetZoom !== map.zoomLevel) {
                            map.zoomLevel = targetZoom;
                            wheel.accepted = true;
                        }
                    }
                }

                // Ensure we pick an OpenStreetMap map type if multiple exist
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
            }

            Column {
                anchors {
                    right: parent.right
                    bottom: parent.bottom
                    margins: 16
                }
                spacing: 12
                property int controlSize: 52
                z: 1

                Button {
                    id: zoomInButton
                    width: controlSize
                    height: controlSize
                    text: "+"
                    font.pixelSize: 26
                    hoverEnabled: true
                    Accessible.name: "Zoom in"
                    onClicked: map.zoomLevel = Math.min(map.maximumZoomLevel, map.zoomLevel + 1)
                    background: Rectangle {
                        anchors.fill: parent
                        radius: width / 2
                        color: zoomInButton.down ? "#ddddddcc" : "#ffffffdd"
                        border.color: "#444"
                        border.width: 1
                    }
                    contentItem: Text {
                        text: zoomInButton.text
                        font: zoomInButton.font
                        color: "#222"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                Button {
                    id: zoomOutButton
                    width: controlSize
                    height: controlSize
                    text: "-"
                    font.pixelSize: 26
                    hoverEnabled: true
                    Accessible.name: "Zoom out"
                    onClicked: map.zoomLevel = Math.max(map.minimumZoomLevel, map.zoomLevel - 1)
                    background: Rectangle {
                        anchors.fill: parent
                        radius: width / 2
                        color: zoomOutButton.down ? "#ddddddcc" : "#ffffffdd"
                        border.color: "#444"
                        border.width: 1
                    }
                    contentItem: Text {
                        text: zoomOutButton.text
                        font: zoomOutButton.font
                        color: "#222"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }
        }
    }
}
