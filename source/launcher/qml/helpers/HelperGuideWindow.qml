import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "../components"
import "../theme" as ThemeModule

Window {
    id: guide

    property var ownerWindow
    property string guideTitle: "HELPER GUIDE"
    default property alias content: guideBody.data

    width: ownerWindow ? Math.max(ownerWindow.width, ThemeModule.Theme.size.contentCardWidth) : ThemeModule.Theme.size.contentCardWidth
    height: Math.max(260, guideContent.implicitHeight + ThemeModule.Theme.spacing.xl * 2)
    minimumWidth: ThemeModule.Theme.size.contentCardWidth
    minimumHeight: 220
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    color: "transparent"

    function showNearOwner() {
        if (ownerWindow) {
            x = ownerWindow.x - width - ThemeModule.Theme.spacing.lg;
            if (x < Screen.virtualX + ThemeModule.Theme.spacing.lg) {
                x = ownerWindow.x;
                y = ownerWindow.y + ownerWindow.height + ThemeModule.Theme.spacing.md;
            } else {
                y = ownerWindow.y;
            }
        }
        show();
        raise();
        requestActivate();
    }

    Rectangle {
        anchors.fill: parent
        color: ThemeModule.Theme.colors.panelStrong
        border.color: ThemeModule.Theme.colors.borderActive
        border.width: ThemeModule.Theme.border.thin
        radius: ThemeModule.Theme.radius.md

        ColumnLayout {
            id: guideContent
            anchors.fill: parent
            anchors.margins: ThemeModule.Theme.spacing.lg
            spacing: ThemeModule.Theme.spacing.md

            Item {
                objectName: "HelperGuideHeader"
                Layout.fillWidth: true
                implicitHeight: Math.max(titleText.implicitHeight, closeButton.implicitHeight)

                MouseArea {
                    objectName: "HelperGuideDragArea"
                    anchors.left: parent.left
                    anchors.right: closeButton.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    acceptedButtons: Qt.LeftButton
                    onPressed: guide.startSystemMove()
                }

                Text {
                    id: titleText
                    text: guide.guideTitle
                    color: ThemeModule.Theme.colors.cyan
                    font.pixelSize: ThemeModule.Theme.fonts.sectionHeading
                    font.bold: true
                    anchors.left: parent.left
                    anchors.right: closeButton.left
                    anchors.verticalCenter: parent.verticalCenter
                    elide: Text.ElideRight
                }

                IconButton {
                    id: closeButton
                    objectName: "HelperGuideCloseButton"
                    text: "X"
                    variant: "danger"
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    onClicked: guide.close()
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: ThemeModule.Theme.border.thin
                color: ThemeModule.Theme.colors.border
            }

            ColumnLayout {
                id: guideBody
                Layout.fillWidth: true
                spacing: ThemeModule.Theme.spacing.md
            }
        }
    }
}
