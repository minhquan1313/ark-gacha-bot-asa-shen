import QtQuick
import QtQuick.Controls
import "../theme" as ThemeModule

Button {
    id: control

    property string variant: "secondary"
    property color normalBorder: variant === "primary" ? ThemeModule.Theme.colors.cyan
        : variant === "danger" ? ThemeModule.Theme.colors.red
        : ThemeModule.Theme.colors.border
    property color normalText: variant === "primary" ? ThemeModule.Theme.colors.cyan
        : variant === "danger" ? ThemeModule.Theme.colors.red
        : ThemeModule.Theme.colors.text
    property color normalFill: variant === "primary" ? "#2900D8FF"
        : variant === "danger" ? "#29FF4D6D"
        : "#8C121C2A"

    implicitHeight: ThemeModule.Theme.size.buttonHeight
    padding: ThemeModule.Theme.spacing.md
    leftPadding: ThemeModule.Theme.spacing.lg
    rightPadding: ThemeModule.Theme.spacing.lg
    hoverEnabled: true

    contentItem: Text {
        text: control.text
        color: control.hovered ? ThemeModule.Theme.colors.text : control.normalText
        font.family: ThemeModule.Theme.fonts.body
        font.pixelSize: ThemeModule.Theme.fonts.buttonText
        font.bold: true
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: ThemeModule.Theme.radius.sm
        color: control.down ? "#3311536B" : control.hovered ? "#42182B3A" : control.normalFill
        border.color: control.hovered ? ThemeModule.Theme.colors.borderActive : control.normalBorder
        border.width: ThemeModule.Theme.border.thin
    }
}
