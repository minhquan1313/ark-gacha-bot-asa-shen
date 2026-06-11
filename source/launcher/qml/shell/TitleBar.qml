import QtQuick
import QtQuick.Layouts
import "../components"
import "../theme" as ThemeModule

Rectangle {
    id: bar

    property var window

    height: ThemeModule.Theme.size.titleBarHeight
    color: ThemeModule.Theme.colors.panelStrong
    border.color: ThemeModule.Theme.colors.border
    border.width: ThemeModule.Theme.border.thin

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        onPressed: if (bar.window) bar.window.startSystemMove()
        onDoubleClicked: if (bar.window) {
            bar.window.visibility = bar.window.visibility === Window.Maximized
                ? Window.Windowed
                : Window.Maximized
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: ThemeModule.Theme.spacing.lg
        spacing: ThemeModule.Theme.spacing.sm

        Text {
            text: launcherController.appTitle
            color: ThemeModule.Theme.colors.cyan
            font.pixelSize: ThemeModule.Theme.fonts.chromeTitle
            font.bold: true
        }

        Text {
            text: launcherController.appVersion
            color: ThemeModule.Theme.colors.muted
            font.family: ThemeModule.Theme.fonts.mono
        }

        Item { Layout.fillWidth: true }

        Text {
            text: "SYSTEM READY"
            color: ThemeModule.Theme.colors.green
            font.family: ThemeModule.Theme.fonts.mono
            font.bold: true
        }

        IconButton {
            text: "-"
            onClicked: if (bar.window) bar.window.showMinimized()
        }
        IconButton {
            text: bar.window && bar.window.visibility === Window.Maximized ? "[]" : "[ ]"
            onClicked: if (bar.window) {
                bar.window.visibility = bar.window.visibility === Window.Maximized
                    ? Window.Windowed
                    : Window.Maximized
            }
        }
        IconButton {
            text: "X"
            variant: "danger"
            onClicked: if (bar.window) bar.window.close()
        }
    }
}
