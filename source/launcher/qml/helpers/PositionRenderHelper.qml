import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme" as ThemeModule

BaseHelperWindow {
    id: helper

    stopControllerOnClose: false

    width: ThemeModule.Theme.size.contentCardWidth
    minimumWidth: ThemeModule.Theme.size.contentCardWidth
    helperTitle: "POSITION / RENDER HELPER"
    helperBody: "Capture stores the current yaw only. View applies the saved yaw with pitch zero."
    statusText: controller ? controller.status : "Ready."
    property bool guideOpen: guideDialog.visible

    Component.onCompleted: Qt.callLater(guideDialog.showNearOwner)
    onClosing: guideDialog.close()

    RowLayout {
        Layout.fillWidth: true
        Item { Layout.fillWidth: true }
        CyberButton {
            objectName: "PositionGuideButton"
            text: "GUIDE"
            variant: "secondary"
            onClicked: guideDialog.showNearOwner()
        }
    }

    Panel {
        title: "STATION YAW"
        Layout.fillWidth: true
        RowLayout {
            Layout.fillWidth: true
            Text {
                text: controller ? controller.stationYaw : "0.0"
                color: ThemeModule.Theme.colors.text
                font.family: ThemeModule.Theme.fonts.mono
                Layout.fillWidth: true
            }
            CyberButton {
                text: "CAPTURE"
                enabled: controller && !controller.busy
                onClicked: controller.captureStationYaw()
            }
            CyberButton {
                text: "VIEW"
                enabled: controller && !controller.busy
                onClicked: controller.viewStationYaw()
            }
        }
    }

    HelperGuideWindow {
        id: guideDialog
        objectName: "PositionGuideDialog"
        ownerWindow: helper
        guideTitle: "POSITION / RENDER HELPER"

        Text {
            text: "Capture stores the current horizontal view for station_yaw. View applies the saved yaw with pitch zero. Press ALT + N to return to this helper."
            color: ThemeModule.Theme.colors.text
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        CyberButton {
            text: "OK"
            variant: "primary"
            Layout.alignment: Qt.AlignRight
            onClicked: guideDialog.close()
        }
    }
}
