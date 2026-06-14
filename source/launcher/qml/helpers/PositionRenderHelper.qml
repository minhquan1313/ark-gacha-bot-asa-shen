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
    property bool guideOpen: guideDialog.opened

    Component.onCompleted: Qt.callLater(guideDialog.open)

    RowLayout {
        Layout.fillWidth: true
        Item { Layout.fillWidth: true }
        CyberButton {
            objectName: "PositionGuideButton"
            text: "GUIDE"
            variant: "secondary"
            onClicked: guideDialog.open()
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

    Popup {
        id: guideDialog
        modal: true
        focus: true
        width: helper.width - ThemeModule.Theme.spacing.xxl
        height: guideContent.implicitHeight + ThemeModule.Theme.spacing.xl * 2
        x: (helper.width - width) / 2
        y: (helper.height - height) / 2
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle {
            color: ThemeModule.Theme.colors.panelStrong
            border.color: ThemeModule.Theme.colors.cyan
            border.width: ThemeModule.Theme.border.thin
            radius: ThemeModule.Theme.radius.md
        }

        ColumnLayout {
            id: guideContent
            anchors.fill: parent
            anchors.margins: ThemeModule.Theme.spacing.xl
            spacing: ThemeModule.Theme.spacing.md

            Text {
                text: "POSITION / RENDER HELPER"
                color: ThemeModule.Theme.colors.cyan
                font.pixelSize: ThemeModule.Theme.fonts.sectionHeading
                font.bold: true
                Layout.fillWidth: true
            }
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
}
