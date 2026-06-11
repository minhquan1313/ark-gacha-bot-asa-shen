import QtQuick
import QtQuick.Layouts
import "../theme" as ThemeModule

Rectangle {
    id: panel

    property string title: ""
    default property alias content: body.data

    color: "#EB0A1019"
    border.color: ThemeModule.Theme.colors.border
    border.width: ThemeModule.Theme.border.thin
    radius: ThemeModule.Theme.radius.panel

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: ThemeModule.Theme.spacing.lg
        spacing: ThemeModule.Theme.spacing.md

        Text {
            visible: panel.title.length > 0
            text: panel.title
            color: ThemeModule.Theme.colors.muted
            font.family: ThemeModule.Theme.fonts.body
            font.pixelSize: ThemeModule.Theme.fonts.panelTitle
            font.bold: true
            Layout.fillWidth: true
        }

        ColumnLayout {
            id: body
            spacing: ThemeModule.Theme.spacing.md
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
    }
}
