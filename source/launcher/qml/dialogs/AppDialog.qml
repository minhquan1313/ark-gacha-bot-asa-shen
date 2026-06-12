import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme" as ThemeModule

Popup {
    id: dialog

    property string title: ""
    property string message: ""
    property string variant: "info"

    modal: true
    focus: true
    width: Math.min(
        parent ? parent.width - ThemeModule.Theme.spacing.xxl * 2 : ThemeModule.Theme.size.dialogWidth,
        ThemeModule.Theme.size.dialogWidth
    )
    height: dialogContent.implicitHeight + ThemeModule.Theme.spacing.xl * 2
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    background: Rectangle {
        color: ThemeModule.Theme.colors.panelStrong
        border.color: dialog.variant === "error" ? ThemeModule.Theme.colors.red
            : dialog.variant === "warning" ? ThemeModule.Theme.colors.yellow
            : ThemeModule.Theme.colors.cyan
        border.width: ThemeModule.Theme.border.thin
        radius: ThemeModule.Theme.radius.md
    }

    ColumnLayout {
        id: dialogContent
        anchors.fill: parent
        anchors.margins: ThemeModule.Theme.spacing.xl
        spacing: ThemeModule.Theme.spacing.lg

        Text {
            text: dialog.title.toUpperCase()
            color: dialog.variant === "error" ? ThemeModule.Theme.colors.red
                : dialog.variant === "warning" ? ThemeModule.Theme.colors.yellow
                : ThemeModule.Theme.colors.cyan
            font.pixelSize: ThemeModule.Theme.fonts.sectionHeading
            font.bold: true
            Layout.fillWidth: true
        }

        Text {
            text: dialog.message
            color: ThemeModule.Theme.colors.text
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            CyberButton {
                text: "OK"
                variant: "primary"
                onClicked: dialog.close()
            }
        }
    }
}
