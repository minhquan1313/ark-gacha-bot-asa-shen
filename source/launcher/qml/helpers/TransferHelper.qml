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

    Flickable {
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
                            text: modelData.value
                            Layout.fillWidth: true
                            onEditingFinished: controller.updateSetting(modelData.key, text)
                        }
                        CyberButton {
                            visible: Boolean(modelData.capture)
                            text: "C"
                            variant: "secondary"
                            onClicked: controller.captureSettingYaw(modelData.key)
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
                                text: modelData.bedName
                                color: modelData.warning ? ThemeModule.Theme.colors.yellow : ThemeModule.Theme.colors.text
                                Layout.fillWidth: true
                                onEditingFinished: controller.updatePlayer("bed_name", modelData.index, text)
                            }
                            CyberButton { text: "C"; variant: "secondary"; onClicked: controller.copyPlayerName(modelData.index) }
                            CyberButton { text: "X"; variant: "danger"; onClicked: controller.removePlayer(modelData.index) }
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
                CyberButton { text: "ADD PLAYER"; variant: "secondary"; onClicked: controller.addPlayer() }
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
        text: controller ? controller.startStopText : "START"
        variant: controller ? controller.startStopVariant : "primary"
        Layout.fillWidth: true
        onClicked: controller.toggle()
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
                text: teleport
                Layout.fillWidth: true
                onEditingFinished: helper.controller.setTeleport(side, text)
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
                    CyberTextField { text: modelData.yaw; Layout.fillWidth: true; onEditingFinished: helper.controller.updateDedi(side, modelData.index, "yaw", text) }
                    Text { text: "Pitch"; color: ThemeModule.Theme.colors.muted }
                    CyberTextField { text: modelData.pitch; Layout.fillWidth: true; onEditingFinished: helper.controller.updateDedi(side, modelData.index, "pitch", text) }
                }
                CyberSwitch { text: "CROUCHED"; checked: modelData.crouched; onToggled: helper.controller.updateDedi(side, modelData.index, "crouched", checked) }
                RowLayout {
                    Layout.fillWidth: true
                    CyberButton { text: "CAPTURE"; onClicked: helper.controller.captureDedi(side, modelData.index) }
                    CyberButton { text: "VIEW"; onClicked: helper.controller.viewDedi(side, modelData.index) }
                    Item { Layout.fillWidth: true }
                    CyberButton { text: "REMOVE"; variant: "danger"; onClicked: helper.controller.removeDedi(side, modelData.index) }
                }
            }
        }
        CyberButton { text: "ADD DEDI"; variant: "secondary"; onClicked: helper.controller.addDedi(side) }
    }
}
