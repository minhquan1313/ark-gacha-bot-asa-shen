import QtQuick
import QtQuick.Layouts
import "../components"

BaseHelperWindow {
    helperTitle: "CROP PLOT FERTILIZER REFRESH"
    helperBody: controller && controller.running ? "" : "Aim at a crop plot and this tool opens its inventory, transfers everything to your player inventory, then transfers everything back into the crop plot."
    hotkeyHint: controller && controller.running ? "ALT + N stops this helper" : "ALT + N toggles START / STOP"
    statusText: controller ? controller.status : "Ready."
    running: controller ? controller.running : false
    compactWhenRunning: true
    showStatus: !(controller && controller.running)

    CyberButton {
        visible: controller && !controller.running
        text: controller ? controller.startStopText : "START"
        variant: controller ? controller.startStopVariant : "primary"
        Layout.fillWidth: true
        onClicked: controller.toggle()
    }
}
