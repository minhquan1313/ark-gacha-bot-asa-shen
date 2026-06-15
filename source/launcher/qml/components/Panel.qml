import QtQuick
import QtQuick.Layouts
import "../theme" as ThemeModule

Rectangle {
    id: panel

    property string title: ""
    property bool fillBody: false
    default property alias content: body.data

    implicitWidth: Math.max(header.implicitWidth, body.implicitWidth) + ThemeModule.Theme.spacing.lg * 2
    implicitHeight: column.implicitHeight + ThemeModule.Theme.spacing.lg * 2
    color: ThemeModule.Theme.colors.panelStrong
    border.color: ThemeModule.Theme.colors.borderSoft
    border.width: ThemeModule.Theme.border.thin
    radius: ThemeModule.Theme.radius.panel

    ColumnLayout {
        id: column
        anchors.fill: parent
        anchors.margins: ThemeModule.Theme.spacing.lg
        spacing: ThemeModule.Theme.spacing.md

        Rectangle {
            visible: panel.title.length > 0
            Layout.fillWidth: true
            implicitHeight: Math.max(header.implicitHeight + ThemeModule.Theme.spacing.sm, ThemeModule.Theme.size.formFieldHeight)
            color: ThemeModule.Theme.colors.panel
            border.color: ThemeModule.Theme.colors.border
            border.width: ThemeModule.Theme.border.thin
            radius: ThemeModule.Theme.radius.sm

            Text {
                id: header
                anchors.fill: parent
                anchors.leftMargin: ThemeModule.Theme.spacing.md
                anchors.rightMargin: ThemeModule.Theme.spacing.md
                text: panel.title
                color: ThemeModule.Theme.colors.cyan
                font.family: ThemeModule.Theme.fonts.body
                font.pixelSize: ThemeModule.Theme.fonts.panelTitle
                font.bold: true
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }
        }

        ColumnLayout {
            id: body
            spacing: ThemeModule.Theme.spacing.md
            Layout.fillWidth: true
            Layout.fillHeight: panel.fillBody
        }
    }
}
