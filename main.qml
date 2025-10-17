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

        Map {
            id: map
            Layout.fillWidth: true
            Layout.fillHeight: true
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
    }
}
