import QtQuick
import QtQuick.Controls
import "../theme" as ThemeModule

Switch {
    id: control

    indicator: Rectangle {
        implicitWidth: ThemeModule.Theme.size.switchWidth
        implicitHeight: ThemeModule.Theme.size.switchHeight
        x: control.leftPadding
        y: parent.height / 2 - height / 2
        radius: height / 2
        color: control.checked ? ThemeModule.Theme.colors.switchOn : ThemeModule.Theme.colors.switchOff
        border.color: control.checked ? ThemeModule.Theme.colors.cyan : ThemeModule.Theme.colors.border

        Rectangle {
            x: control.checked ? parent.width - width - ThemeModule.Theme.spacing.xs : ThemeModule.Theme.spacing.xs
            y: ThemeModule.Theme.spacing.xs
            width: ThemeModule.Theme.size.switchKnob
            height: ThemeModule.Theme.size.switchKnob
            radius: ThemeModule.Theme.size.switchKnob / 2
            color: control.checked ? ThemeModule.Theme.colors.cyan : ThemeModule.Theme.colors.muted

            Behavior on x {
                NumberAnimation {
                    duration: ThemeModule.Theme.motion.fast
                }
            }
        }
    }

    contentItem: Text {
        text: control.text
        color: ThemeModule.Theme.colors.text
        font.pixelSize: ThemeModule.Theme.fonts.formText
        leftPadding: control.indicator.width + ThemeModule.Theme.spacing.md
        verticalAlignment: Text.AlignVCenter
    }
}
