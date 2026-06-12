import QtQuick
import QtQuick.Controls
import "../theme" as ThemeModule

Button {
    id: control

    property string variant: "secondary"

    implicitWidth: ThemeModule.Theme.size.iconButton
    implicitHeight: ThemeModule.Theme.size.iconButton
    hoverEnabled: true

    contentItem: Text {
        text: control.text
        color: control.variant === "danger" && control.hovered
            ? ThemeModule.Theme.colors.text
            : control.variant === "danger"
                ? ThemeModule.Theme.colors.red
                : ThemeModule.Theme.colors.cyan
        font.family: ThemeModule.Theme.fonts.mono
        font.pixelSize: ThemeModule.Theme.fonts.sectionHeading
        font.bold: true
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        radius: ThemeModule.Theme.radius.sm
        color: control.variant === "danger" && control.hovered
            ? ThemeModule.Theme.colors.red
            : control.hovered
                ? ThemeModule.Theme.colors.buttonPrimaryFill
                : "transparent"
        border.color: control.hovered ? ThemeModule.Theme.colors.borderActive : "transparent"
        border.width: ThemeModule.Theme.border.thin
    }
}
