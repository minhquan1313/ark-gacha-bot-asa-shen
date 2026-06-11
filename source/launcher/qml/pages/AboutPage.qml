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
            title: "ABOUT ME"
            Layout.fillWidth: true

            Image {
                source: assetPaths.logo
                fillMode: Image.PreserveAspectFit
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: ThemeModule.Theme.size.logoLarge
                Layout.preferredHeight: ThemeModule.Theme.size.logoLarge
            }
            Text {
                text: launcherController.appTitle + "\n" + launcherController.appVersion
                color: ThemeModule.Theme.colors.text
                font.pixelSize: ThemeModule.Theme.fonts.statValue
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                Layout.fillWidth: true
            }
            Text {
                text: "DEVELOPED BY\nShen\n\nCode. Automate. Dominate."
                color: ThemeModule.Theme.colors.muted
                horizontalAlignment: Text.AlignHCenter
                Layout.fillWidth: true
            }
        }
    }
}
