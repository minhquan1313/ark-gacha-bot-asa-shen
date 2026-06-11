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
            title: "CHECK UPDATE"
            Layout.fillWidth: true

            Text {
                text: "CURRENT VERSION\n" + launcherController.appVersion
                color: ThemeModule.Theme.colors.text
                horizontalAlignment: Text.AlignHCenter
                Layout.fillWidth: true
            }
            Text {
                text: "LATEST VERSION\nManual check required"
                color: ThemeModule.Theme.colors.green
                horizontalAlignment: Text.AlignHCenter
                Layout.fillWidth: true
            }
            CyberButton {
                text: "CHECK UPDATE"
                variant: "primary"
                Layout.alignment: Qt.AlignHCenter
                onClicked: toolsController.checkUpdates()
            }
        }
    }
}
