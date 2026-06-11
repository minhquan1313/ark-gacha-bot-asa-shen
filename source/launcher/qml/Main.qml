import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "shell"
import "dialogs"
import "helpers"
import "theme" as ThemeModule

ApplicationWindow {
    id: root

    width: settingsController.launcherWidth
    height: settingsController.launcherHeight
    minimumWidth: ThemeModule.Theme.size.minimumWidth
    minimumHeight: ThemeModule.Theme.size.minimumHeight
    visible: true
    flags: Qt.FramelessWindowHint | Qt.Window
    color: ThemeModule.Theme.colors.bg
    title: launcherController.appName

    property bool narrow: width < ThemeModule.Theme.size.breakpointNarrow
    property var helperWindows: ({})

    Component.onCompleted: launcherController.registerWindow(root)

    onClosing: {
        launcherController.persistWindowSize(width, height);
        launcherController.shutdown();
    }

    Rectangle {
        anchors.fill: parent
        color: ThemeModule.Theme.colors.bg

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            TitleBar {
                window: root
                Layout.fillWidth: true
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                Sidebar {
                    narrow: root.narrow
                    Layout.fillHeight: true
                    Layout.preferredWidth: width
                }

                PageHost {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                }
            }
        }
    }

    AppDialog {
        id: appDialog
        x: (root.width - width) / 2
        y: (root.height - height) / 2
    }

    RunnerOverlay {
        id: runnerOverlay
        visible: launcherController.running
        x: root.x + root.width - width - ThemeModule.Theme.spacing.lg
        y: root.y + (root.height - height) / 2
    }

    Connections {
        target: launcherController
        function onDialogRequested(title, message, variant) {
            appDialog.title = title;
            appDialog.message = message;
            appDialog.variant = variant;
            appDialog.open();
        }
    }

    Connections {
        target: toolsController
        function onMessageRequested(title, message, variant) {
            appDialog.title = title;
            appDialog.message = message;
            appDialog.variant = variant;
            appDialog.open();
        }
        function onHelperRequested(helperName) {
            openHelper(helperName);
        }
    }

    Component {
        id: autoJoinComponent
        AutoJoinHelper {}
    }
    Component {
        id: transferComponent
        TransferHelper {}
    }
    Component {
        id: fertilizerComponent
        FertilizerRefreshHelper {}
    }
    Component {
        id: depositComponent
        DepositRouteHelper {}
    }
    Component {
        id: positionComponent
        PositionRenderHelper {}
    }

    function openHelper(helperName) {
        var existing = helperWindows[helperName];
        if (existing) {
            existing.show();
            existing.raise();
            existing.requestActivate();
            return;
        }

        var component = helperName === "transfer" ? transferComponent : helperName === "fertilizer" ? fertilizerComponent : helperName === "position" ? positionComponent : helperName === "deposit" ? depositComponent : autoJoinComponent;
        var helper = component.createObject(root);
        helperWindows[helperName] = helper;
        helper.closing.connect(function () {
            helperWindows[helperName] = null;
        });
        helper.show();
        helper.raise();
        helper.requestActivate();
    }
}
