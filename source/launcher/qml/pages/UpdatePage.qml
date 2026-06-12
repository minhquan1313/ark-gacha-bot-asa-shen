import QtQuick
import QtQuick.Layouts
import "../components"
import "../theme" as ThemeModule

Item {
    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width - ThemeModule.Theme.spacing.xxl, ThemeModule.Theme.size.contentCardWidth)
        spacing: ThemeModule.Theme.spacing.md

        Panel {
            objectName: "UpdateCard"
            title: "CHECK UPDATE"
            Layout.fillWidth: true
            Layout.preferredHeight: ThemeModule.Theme.size.updateCardHeight

            Text {
                text: "CURRENT VERSION\n" + launcherController.appVersion
                color: ThemeModule.Theme.colors.text
                horizontalAlignment: Text.AlignHCenter
                Layout.fillWidth: true
            }
            Text {
                objectName: "UpdateLatest"
                text: "LATEST VERSION\n" + toolsController.latestVersion + "\n" + toolsController.updateStatus
                color: toolsController.updateAvailable ? ThemeModule.Theme.colors.yellow : ThemeModule.Theme.colors.green
                horizontalAlignment: Text.AlignHCenter
                Layout.fillWidth: true
            }
            Panel {
                title: "UPDATE STATUS"
                Layout.fillWidth: true

                Text {
                    objectName: "UpdateDetail"
                    text: toolsController.updateDetail
                    color: ThemeModule.Theme.colors.muted
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            }
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: ThemeModule.Theme.spacing.sm

                CyberButton {
                    text: "CHECK UPDATE"
                    variant: "primary"
                    onClicked: toolsController.checkUpdates()
                }
                CyberButton {
                    text: "OPEN DOWNLOAD PAGE"
                    variant: "secondary"
                    onClicked: toolsController.openDownloadPage()
                }
            }
        }
    }
}
