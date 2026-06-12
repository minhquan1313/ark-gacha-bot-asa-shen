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
    property var activeHelperWindow: null

    Component.onCompleted: {
        launcherController.registerWindow(root);
        helperWindowController.registerWindow(root);
    }

    onClosing: {
        launcherController.persistWindowSize(width, height);
        helperWindowController.closeActiveHelper();
        helperWindowController.shutdown();
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
            helperWindowController.openHelper(helperName, {});
        }
    }

    Connections {
        target: helperWindowController
        function onCloseRequested() {
            if (root.activeHelperWindow) {
                root.activeHelperWindow.close();
                root.activeHelperWindow = null;
            }
        }
        function onHelperRequested(helperName, payload) {
            openHelper(helperName, payload);
        }
        function onToggleRequested(helperName) {
            var helper = root.activeHelperWindow;
            if (helper && helper.controller && helperWindowController.activeHelperName === helperName) {
                helper.controller.toggle();
            }
        }
        function onFocusRequested() {
            var helper = root.activeHelperWindow;
            if (helper) {
                helper.show();
                helper.raise();
                helper.requestActivate();
            }
        }
    }

    Component { id: autoJoinComponent; AutoJoinHelper {} }
    Component { id: transferComponent; TransferHelper {} }
    Component { id: fertilizerComponent; FertilizerRefreshHelper {} }
    Component { id: depositComponent; DepositRouteHelper {} }
    Component { id: positionComponent; PositionRenderHelper {} }

    function openHelper(helperName, payload) {
        var component = helperName === "autoJoin" ? autoJoinComponent : helperName === "transfer" ? transferComponent : helperName === "fertilizer" ? fertilizerComponent : helperName === "position" ? positionComponent : helperName === "deposit" ? depositComponent : null;
        var controller = helperName === "autoJoin" ? autoJoinHelperController : helperName === "transfer" ? transferHelperController : helperName === "fertilizer" ? fertilizerHelperController : helperName === "position" ? positionRenderHelperController : helperName === "deposit" ? depositRouteHelperController : null;
        if (!component || !controller) {
            return;
        }
        var helper = component.createObject(root, {"controller": controller});
        root.activeHelperWindow = helper;
        positionHelper(helper);
        helper.closing.connect(function() {
            if (root.activeHelperWindow === helper) {
                root.activeHelperWindow = null;
                helperWindowController.markClosed(helperName);
            }
        });
        helper.widthChanged.connect(function() {
            if (root.activeHelperWindow === helper) {
                positionHelper(helper);
            }
        });
        helper.heightChanged.connect(function() {
            if (root.activeHelperWindow === helper) {
                positionHelper(helper);
            }
        });
        helper.show();
        helper.raise();
        helper.requestActivate();
    }

    function positionHelper(helper) {
        helper.x = Math.max(root.x + ThemeModule.Theme.spacing.lg, root.x + root.width - helper.width - ThemeModule.Theme.spacing.lg);
        helper.y = Math.max(root.y + ThemeModule.Theme.spacing.lg, root.y + (root.height - helper.height) / 2);
    }
}
