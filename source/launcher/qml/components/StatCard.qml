import QtQuick
import "../theme" as ThemeModule

Rectangle {
    id: card

    property string label: ""
    property string value: "0"
    property string sublabel: ""

    objectName: "StatCard"
    implicitHeight: ThemeModule.Theme.size.statCardHeight
    color: ThemeModule.Theme.colors.panelTranslucent
    border.color: ThemeModule.Theme.colors.border
    border.width: ThemeModule.Theme.border.thin
    radius: ThemeModule.Theme.radius.panel

    Column {
        anchors.centerIn: parent
        width: Math.max(0, parent.width - ThemeModule.Theme.spacing.lg * 2)
        spacing: ThemeModule.Theme.spacing.xs

        Text {
            objectName: "StatCardLabel"
            text: card.label
            color: ThemeModule.Theme.colors.muted
            font.pixelSize: ThemeModule.Theme.fonts.statLabel
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            width: parent.width
        }
        Text {
            objectName: "StatCardValue"
            text: card.value
            color: ThemeModule.Theme.colors.text
            font.pixelSize: ThemeModule.Theme.fonts.statValue
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            width: parent.width
        }
        Text {
            text: card.sublabel
            color: ThemeModule.Theme.colors.muted
            font.family: ThemeModule.Theme.fonts.mono
            font.pixelSize: ThemeModule.Theme.fonts.footer
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            width: parent.width
        }
    }
}
