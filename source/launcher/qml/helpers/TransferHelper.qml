import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme" as ThemeModule

BaseHelperWindow {
    id: helper

    width: ThemeModule.Theme.size.transferHelperWidth
    height: ThemeModule.Theme.size.depositHelperHeight
    minimumWidth: ThemeModule.Theme.size.transferHelperWidth
    minimumHeight: ThemeModule.Theme.size.helperHeight
    helperTitle: "SERVER TRANSFER HELPER"
    helperBody: ""
    contentFill: true
    statusText: controller ? controller.status : "Ready."
    running: controller ? controller.running : false
    property bool allExpanded: true
    property int expandGeneration: 0

    function setAllExpanded(expanded) {
        allExpanded = expanded;
        expandGeneration += 1;
    }

    function commitEditableFields(item) {
        if (!item) {
            return;
        }
        if (item.commitField) {
            item.commitField();
        }
        var childList = item.children || [];
        for (var i = 0; i < childList.length; ++i) {
            commitEditableFields(childList[i]);
        }
    }

    function commitFormEdits() {
        commitEditableFields(formColumn);
    }

    Flickable {
        objectName: "TransferFormScroll"
        visible: controller && !controller.running
        clip: true
        contentHeight: formColumn.implicitHeight
        Layout.fillWidth: true
        Layout.fillHeight: true

        ColumnLayout {
            id: formColumn
            width: parent.width
            spacing: ThemeModule.Theme.spacing.md

            RowLayout {
                Layout.fillWidth: true
                CyberButton {
                    objectName: "TransferCollapseAllButton"
                    text: "COLLAPSE ALL"
                    variant: "secondary"
                    onClicked: helper.setAllExpanded(false)
                }
                CyberButton {
                    objectName: "TransferExpandAllButton"
                    text: "EXPAND ALL"
                    variant: "secondary"
                    onClicked: helper.setAllExpanded(true)
                }
                Item { Layout.fillWidth: true }
            }

            CollapsiblePanel {
                objectName: "TransferSettingsPanel"
                title: "TRANSFER SETTINGS"
                requestedExpanded: helper.allExpanded
                expandGeneration: helper.expandGeneration
                Layout.fillWidth: true
                Repeater {
                    model: controller ? controller.settingRows : []
                    delegate: RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: modelData.label
                            color: ThemeModule.Theme.colors.muted
                            Layout.preferredWidth: ThemeModule.Theme.size.settingsLabelWidth
                        }
                        CyberTextField {
                            objectName: "TransferSettingField"
                            property string settingKey: modelData.key
                            text: modelData.value
                            Layout.fillWidth: true
                            function commitField() {
                                controller.updateSetting(settingKey, text);
                            }
                            onEditingFinished: commitField()
                        }
                        CyberButton {
                            visible: Boolean(modelData.capture)
                            property string settingKey: modelData.key
                            text: "C"
                            variant: "secondary"
                            onClicked: {
                                helper.commitFormEdits();
                                controller.captureSettingYaw(settingKey);
                            }
                        }
                    }
                }
                Text {
                    text: controller ? controller.loopHint : ""
                    color: ThemeModule.Theme.colors.muted
                    font.family: ThemeModule.Theme.fonts.mono
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }
            }

            CollapsiblePanel {
                objectName: "TransferPlayersPanel"
                title: "PLAYER SETTINGS"
                requestedExpanded: helper.allExpanded
                expandGeneration: helper.expandGeneration
                Layout.fillWidth: true
                Repeater {
                    model: controller ? controller.playerRows : []
                    delegate: ColumnLayout {
                        Layout.fillWidth: true
                        spacing: ThemeModule.Theme.spacing.xs

                        RowLayout {
                            Layout.fillWidth: true
                            Text { text: modelData.label; color: ThemeModule.Theme.colors.muted; Layout.preferredWidth: ThemeModule.Theme.size.playerLabelWidth }
                            CyberTextField {
                                objectName: "TransferPlayerField"
                                property int playerIndex: modelData.index
                                text: modelData.bedName
                                color: modelData.warning ? ThemeModule.Theme.colors.yellow : ThemeModule.Theme.colors.text
                                Layout.fillWidth: true
                                function commitField() {
                                    controller.updatePlayer("bed_name", playerIndex, text);
                                }
                                onEditingFinished: commitField()
                            }
                            CyberButton {
                                property int playerIndex: modelData.index
                                text: "C"
                                variant: "secondary"
                                onClicked: {
                                    helper.commitFormEdits();
                                    controller.copyPlayerName(playerIndex);
                                }
                            }
                            CyberButton {
                                property int playerIndex: modelData.index
                                text: "X"
                                variant: "danger"
                                onClicked: {
                                    helper.commitFormEdits();
                                    controller.removePlayer(playerIndex);
                                }
                            }
                        }
                        Text {
                            objectName: "TransferPlayerWarning"
                            visible: Boolean(modelData.warning)
                            text: modelData.warning
                            color: ThemeModule.Theme.colors.yellow
                            font.family: ThemeModule.Theme.fonts.mono
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                }
                CyberButton {
                    objectName: "TransferAddPlayerButton"
                    text: "ADD PLAYER"
                    variant: "secondary"
                    onClicked: {
                        helper.commitFormEdits();
                        controller.addPlayer();
                    }
                }
            }

            DediSection {
                title: "RESOURCE DEDIS"
                side: "resource"
                teleport: controller ? controller.resourceTeleport : ""
                rows: controller ? controller.resourceDedis : []
            }
            DediSection {
                title: "DESTINATION DEDIS"
                side: "destination"
                teleport: controller ? controller.destinationTeleport : ""
                rows: controller ? controller.destinationDedis : []
            }
        }
    }

    ConsoleView {
        visible: controller && controller.running
        lines: controller ? controller.runningLog : []
        Layout.fillWidth: true
        Layout.fillHeight: true
    }

    CyberButton {
        objectName: "TransferStartButton"
        text: controller ? controller.startStopText : "START"
        variant: controller ? controller.startStopVariant : "primary"
        Layout.fillWidth: true
        onClicked: {
            if (controller && !controller.running) {
                helper.commitFormEdits();
            }
            controller.toggle();
        }
    }

    component DediSection: CollapsiblePanel {
        required property string side
        property string teleport: ""
        property var rows: []

        requestedExpanded: helper.allExpanded
        expandGeneration: helper.expandGeneration
        Layout.fillWidth: true

        RowLayout {
            Layout.fillWidth: true
            Text { text: "TELEPORT"; color: ThemeModule.Theme.colors.muted; Layout.preferredWidth: ThemeModule.Theme.size.settingsLabelWidth }
            CyberTextField {
                objectName: "TransferTeleportField"
                text: teleport
                Layout.fillWidth: true
                function commitField() {
                    helper.controller.setTeleport(side, text);
                }
                onEditingFinished: commitField()
            }
        }

        Repeater {
            model: rows
            delegate: CollapsiblePanel {
                objectName: "TransferDediRow"
                title: modelData.label
                requestedExpanded: helper.allExpanded
                expandGeneration: helper.expandGeneration
                Layout.fillWidth: true
                GridLayout {
                    objectName: "TransferDediDetails"
                    columns: 2
                    Layout.fillWidth: true
                    Text { text: "Yaw"; color: ThemeModule.Theme.colors.muted }
                    CyberTextField {
                        objectName: "TransferDediValueField"
                        property int dediIndex: modelData.index
                        property string dediKey: "yaw"
                        text: modelData.yaw
                        Layout.fillWidth: true
                        function commitField() {
                            helper.controller.updateDedi(side, dediIndex, dediKey, text);
                        }
                        onEditingFinished: commitField()
                    }
                    Text { text: "Pitch"; color: ThemeModule.Theme.colors.muted }
                    CyberTextField {
                        objectName: "TransferDediValueField"
                        property int dediIndex: modelData.index
                        property string dediKey: "pitch"
                        text: modelData.pitch
                        Layout.fillWidth: true
                        function commitField() {
                            helper.controller.updateDedi(side, dediIndex, dediKey, text);
                        }
                        onEditingFinished: commitField()
                    }
                }
                CyberSwitch { text: "CROUCHED"; checked: modelData.crouched; onToggled: helper.controller.updateDedi(side, modelData.index, "crouched", checked) }
                RowLayout {
                    Layout.fillWidth: true
                    CyberButton {
                        property int dediIndex: modelData.index
                        text: "CAPTURE"
                        onClicked: {
                            helper.commitFormEdits();
                            helper.controller.captureDedi(side, dediIndex);
                        }
                    }
                    CyberButton {
                        objectName: "TransferDediViewButton"
                        property int dediIndex: modelData.index
                        text: "VIEW"
                        onClicked: {
                            helper.commitFormEdits();
                            helper.controller.viewDedi(side, dediIndex);
                        }
                    }
                    Item { Layout.fillWidth: true }
                    CyberButton {
                        property int dediIndex: modelData.index
                        text: "REMOVE"
                        variant: "danger"
                        onClicked: {
                            helper.commitFormEdits();
                            helper.controller.removeDedi(side, dediIndex);
                        }
                    }
                }
            }
        }
        CyberButton {
            text: "ADD DEDI"
            variant: "secondary"
            onClicked: {
                helper.commitFormEdits();
                helper.controller.addDedi(side);
            }
        }
    }
}
