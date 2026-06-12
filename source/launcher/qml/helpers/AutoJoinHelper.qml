import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme" as ThemeModule

BaseHelperWindow {
    helperTitle: "AUTO JOIN SERVER"
    helperBody: controller && controller.running ? "" : "Enter a server number and this tool will retry the existing join flow until the player is back in-server or you stop it."
    hotkeyHint: controller && controller.running ? "ALT + N stops this helper" : "ALT + N toggles START / STOP"
    statusText: controller ? controller.status : "Ready."
    running: controller ? controller.running : false
    compactWhenRunning: true
    showStatus: !(controller && controller.running)

    RowLayout {
        visible: controller && !controller.running
        Layout.fillWidth: true
        Text {
            text: "SERVER NUMBER"
            color: ThemeModule.Theme.colors.muted
            Layout.preferredWidth: ThemeModule.Theme.size.helperLabelWidth
        }
        CyberTextField {
            objectName: "AutoJoinServerInput"
            text: controller ? controller.serverNumber : ""
            enabled: controller && !controller.running
            Layout.fillWidth: true
            onEditingFinished: controller.setServerNumber(text)
            onAccepted: controller.start()
        }
    }

    CyberButton {
        objectName: "AutoJoinStartButton"
        visible: controller && !controller.running
        text: controller ? controller.startStopText : "START"
        variant: controller ? controller.startStopVariant : "primary"
        Layout.fillWidth: true
        onClicked: controller.toggle()
    }
}
