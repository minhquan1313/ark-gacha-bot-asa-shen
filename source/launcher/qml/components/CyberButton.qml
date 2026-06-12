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
    property color normalFill: variant === "primary" ? ThemeModule.Theme.colors.buttonPrimaryFill
        : variant === "danger" ? ThemeModule.Theme.colors.buttonDangerFill
        : ThemeModule.Theme.colors.glass

    implicitHeight: ThemeModule.Theme.size.buttonHeight
    padding: ThemeModule.Theme.spacing.md
    leftPadding: ThemeModule.Theme.spacing.lg
    rightPadding: ThemeModule.Theme.spacing.lg
    hoverEnabled: true

    contentItem: Text {
        text: control.text
        color: !control.enabled ? ThemeModule.Theme.colors.dim
            : control.hovered ? ThemeModule.Theme.colors.text
            : control.normalText
        font.family: ThemeModule.Theme.fonts.body
        font.pixelSize: ThemeModule.Theme.fonts.buttonText
        font.bold: true
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: ThemeModule.Theme.radius.sm
        color: !control.enabled ? ThemeModule.Theme.colors.sidebar
            : control.down ? ThemeModule.Theme.colors.buttonDownFill
            : control.hovered ? ThemeModule.Theme.colors.buttonHoverFill
            : control.normalFill
        border.color: !control.enabled ? ThemeModule.Theme.colors.border
            : control.hovered ? ThemeModule.Theme.colors.borderActive
            : control.normalBorder
        border.width: ThemeModule.Theme.border.thin
    }
}
