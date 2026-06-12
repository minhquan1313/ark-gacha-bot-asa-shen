import QtQuick
import "../theme" as ThemeModule

Rectangle {
    id: meter

    property real value: 0
    property color accent: ThemeModule.Theme.colors.green

    implicitHeight: ThemeModule.Theme.size.meterHeight
    radius: ThemeModule.Theme.radius.sm
    color: ThemeModule.Theme.colors.meterTrack
    clip: true

    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: parent.width * Math.max(0, Math.min(100, meter.value)) / 100
        radius: ThemeModule.Theme.radius.sm
        color: meter.value >= 80 ? ThemeModule.Theme.colors.yellow : meter.accent
    }
}
