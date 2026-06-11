import QtQuick
import QtQuick.Controls
import "../theme" as ThemeModule

ScrollView {
    id: view

    property var lines: []

    clip: true
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

    TextArea {
        readOnly: true
        selectByMouse: true
        wrapMode: TextEdit.Wrap
        text: view.lines.join("")
        color: ThemeModule.Theme.colors.text
        font.family: ThemeModule.Theme.fonts.mono
        font.pixelSize: ThemeModule.Theme.fonts.consoleText
        background: Rectangle {
            color: ThemeModule.Theme.colors.panelStrong
            border.color: ThemeModule.Theme.colors.border
            border.width: ThemeModule.Theme.border.thin
            radius: ThemeModule.Theme.radius.sm
        }
    }
}
