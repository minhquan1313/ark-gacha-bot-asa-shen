import QtQuick
import QtQuick.Layouts
import "../theme" as ThemeModule

Rectangle {
    id: panel

    property string title: ""
    property bool fillBody: false
    property bool requestedExpanded: true
    property int expandGeneration: 0
    property bool expanded: requestedExpanded
    default property alias content: body.data

    objectName: "CollapsiblePanel"
    implicitWidth: Math.max(header.implicitWidth, body.implicitWidth) + ThemeModule.Theme.spacing.lg * 2
    implicitHeight: column.implicitHeight + ThemeModule.Theme.spacing.lg * 2
    color: ThemeModule.Theme.colors.panelTranslucent
    border.color: ThemeModule.Theme.colors.border
    border.width: ThemeModule.Theme.border.thin
    radius: ThemeModule.Theme.radius.panel

    onExpandGenerationChanged: expanded = requestedExpanded

    ColumnLayout {
        id: column
        anchors.fill: parent
        anchors.margins: ThemeModule.Theme.spacing.lg
        spacing: ThemeModule.Theme.spacing.md

        RowLayout {
            id: header
            Layout.fillWidth: true
            spacing: ThemeModule.Theme.spacing.sm

            CyberButton {
                objectName: "CollapsiblePanelToggle"
                text: panel.expanded ? "v" : ">"
                variant: "secondary"
                onClicked: panel.expanded = !panel.expanded
            }
            Text {
                text: panel.title
                color: ThemeModule.Theme.colors.muted
                font.family: ThemeModule.Theme.fonts.body
                font.pixelSize: ThemeModule.Theme.fonts.panelTitle
                font.bold: true
                Layout.fillWidth: true
                elide: Text.ElideRight
            }
        }

        ColumnLayout {
            id: body
            visible: panel.expanded
            spacing: ThemeModule.Theme.spacing.md
            Layout.fillWidth: true
            Layout.fillHeight: panel.fillBody
        }
    }
}
