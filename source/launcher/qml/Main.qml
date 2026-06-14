import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
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
    property string pendingHelperName: ""
    property var pendingHelperPayload: ({})
    property bool closeConfirmed: false
    property var pendingConfirmCallback: null

    Component.onCompleted: {
        launcherController.registerWindow(root);
        helperWindowController.registerWindow(root);
    }

    onClosing: {
        if (launcherController.running && !closeConfirmed) {
            close.accepted = false;
            showConfirmDialog(
                "Stop Program And Exit",
                "The automation is still running. Stop it and close the launcher?",
                "STOP AND EXIT",
                "CANCEL"
            );
            return;
        }
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
        objectName: "AppDialog"
        x: (root.width - width) / 2
        y: (root.height - height) / 2
        onConfirmed: {
            if (root.pendingConfirmCallback) {
                var callback = root.pendingConfirmCallback;
                root.pendingConfirmCallback = null;
                callback();
            }
        }
    }

    RunnerOverlay {
        id: runnerOverlay
        visible: launcherController.running
        x: Screen.virtualX + Screen.desktopAvailableWidth - width - ThemeModule.Theme.spacing.lg
        y: Screen.virtualY + (Screen.desktopAvailableHeight - height) / 2
    }

    Connections {
        target: launcherController
        function onDialogRequested(title, message, variant) {
            showMessageDialog(title, message, variant);
        }
    }

    Connections {
        target: settingsController
        function onFieldActionConfirmationRequested(title, message, confirmText, value) {
            showConfirmDialog(
                title,
                message,
                confirmText,
                "CANCEL",
                function() {
                    settingsController.confirmFieldAction("auto_fill_gacha_group", value);
                }
            );
        }
    }

    Connections {
        target: toolsController
        function onMessageRequested(title, message, variant) {
            showMessageDialog(title, message, variant);
        }
        function onHelperRequested(helperName) {
            requestHelperOpen(helperName, {});
        }
        function onHelperPayloadRequested(helperName, payload) {
            requestHelperOpen(helperName, payload || {});
        }
    }

    Connections {
        target: autoJoinHelperController
        function onDialogRequested(title, message, variant) {
            showMessageDialog(title, message, variant);
        }
    }

    Connections {
        target: fertilizerHelperController
        function onDialogRequested(title, message, variant) {
            showMessageDialog(title, message, variant);
        }
    }

    Connections {
        target: positionRenderHelperController
        function onDialogRequested(title, message, variant) {
            showMessageDialog(title, message, variant);
        }
    }

    Connections {
        target: depositRouteHelperController
        function onDialogRequested(title, message, variant) {
            showMessageDialog(title, message, variant);
        }
    }

    Connections {
        target: transferHelperController
        function onDialogRequested(title, message, variant) {
            showMessageDialog(title, message, variant);
        }
    }

    Connections {
        target: helperWindowController
        function onCloseRequested() {
            if (root.activeHelperWindow) {
                root.activeHelperWindow.close();
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

    function applyHelperPayload(helperName, controller, payload) {
        if (!payload) {
            return;
        }
        if (helperName === "deposit" && payload.routeKind !== undefined && payload.routeIndex !== undefined) {
            controller.selectRoute(String(payload.routeKind), Number(payload.routeIndex));
        }
    }

    function requestHelperOpen(helperName, payload) {
        if (launcherController.running || launcherController.programStopping) {
            showMessageDialog(
                "Stop Program First",
                "Stop the running automation before opening a setup helper.",
                "warning"
            );
            return;
        }
        helperWindowController.openHelper(helperName, payload || {});
    }

    function openHelper(helperName, payload) {
        var component = helperName === "autoJoin" ? autoJoinComponent : helperName === "transfer" ? transferComponent : helperName === "fertilizer" ? fertilizerComponent : helperName === "position" ? positionComponent : helperName === "deposit" ? depositComponent : null;
        var controller = helperName === "autoJoin" ? autoJoinHelperController : helperName === "transfer" ? transferHelperController : helperName === "fertilizer" ? fertilizerHelperController : helperName === "position" ? positionRenderHelperController : helperName === "deposit" ? depositRouteHelperController : null;
        if (!component || !controller) {
            return;
        }
        if (root.activeHelperWindow) {
            root.pendingHelperName = helperName;
            root.pendingHelperPayload = payload || {};
            root.activeHelperWindow.close();
            return;
        }
        applyHelperPayload(helperName, controller, payload);
        var helper = component.createObject(root, {
            "controller": controller,
            "ownerActive": Qt.binding(function() { return root.active; })
        });
        root.activeHelperWindow = helper;
        positionHelper(helper);
        helper.helperClosed.connect(function() {
            if (root.activeHelperWindow === helper) {
                root.activeHelperWindow = null;
                if (root.pendingHelperName.length > 0) {
                    var nextName = root.pendingHelperName;
                    var nextPayload = root.pendingHelperPayload;
                    root.pendingHelperName = "";
                    root.pendingHelperPayload = {};
                    openHelper(nextName, nextPayload);
                } else {
                    helperWindowController.markClosed(helperName);
                }
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
        helper.x = Screen.virtualX + Screen.desktopAvailableWidth - helper.width - ThemeModule.Theme.spacing.lg;
        helper.y = Screen.virtualY + (Screen.desktopAvailableHeight - helper.height) / 2;
    }

    function showMessageDialog(title, message, variant) {
        appDialog.confirmMode = false;
        appDialog.confirmText = "OK";
        appDialog.cancelText = "CANCEL";
        appDialog.title = title;
        appDialog.message = message;
        appDialog.variant = variant;
        appDialog.open();
    }

    function showConfirmDialog(title, message, confirmText, cancelText, callback) {
        appDialog.confirmMode = true;
        appDialog.confirmText = confirmText;
        appDialog.cancelText = cancelText;
        appDialog.title = title;
        appDialog.message = message;
        appDialog.variant = "confirm";
        root.pendingConfirmCallback = callback || function() {
            root.closeConfirmed = true;
            root.close();
        };
        appDialog.open();
    }
}
