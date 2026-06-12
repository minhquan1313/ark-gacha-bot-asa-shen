import QtQuick
import QtQuick.Controls
import "../theme" as ThemeModule

TextField {
    id: control

    color: ThemeModule.Theme.colors.text
    placeholderTextColor: ThemeModule.Theme.colors.dim
    selectedTextColor: ThemeModule.Theme.colors.panelStrong
    selectionColor: ThemeModule.Theme.colors.cyan
    selectByMouse: true
    implicitHeight: ThemeModule.Theme.size.formFieldHeight
    padding: ThemeModule.Theme.spacing.sm
    font.pixelSize: ThemeModule.Theme.fonts.formText

    background: Rectangle {
        color: ThemeModule.Theme.colors.panelStrong
        border.color: control.activeFocus ? ThemeModule.Theme.colors.cyan : ThemeModule.Theme.colors.border
        border.width: ThemeModule.Theme.border.thin
        radius: ThemeModule.Theme.radius.sm
    }
}
