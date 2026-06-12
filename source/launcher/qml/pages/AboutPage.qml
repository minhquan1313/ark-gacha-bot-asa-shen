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
            objectName: "AboutCard"
            title: "ABOUT ME"
            Layout.fillWidth: true
            Layout.preferredHeight: ThemeModule.Theme.size.aboutCardHeight

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
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: ThemeModule.Theme.spacing.sm

                CyberButton {
                    objectName: "AboutGithubButton"
                    text: "GITHUB"
                    variant: "secondary"
                    enabled: false
                }
                CyberButton {
                    objectName: "AboutWebsiteButton"
                    text: "WEBSITE"
                    variant: "secondary"
                    enabled: false
                }
            }
            Text {
                objectName: "AboutLinksStatus"
                text: "External links are not configured for this build."
                color: ThemeModule.Theme.colors.dim
                horizontalAlignment: Text.AlignHCenter
                Layout.fillWidth: true
            }
            Text {
                text: "SPECIAL THANKS TO\nYou, for using " + launcherController.appName
                color: ThemeModule.Theme.colors.muted
                horizontalAlignment: Text.AlignHCenter
                Layout.fillWidth: true
            }
        }
    }
}
