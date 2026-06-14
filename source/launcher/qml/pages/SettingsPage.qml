import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme" as ThemeModule

Item {
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: ThemeModule.Theme.spacing.lg
        spacing: ThemeModule.Theme.spacing.md

        Text {
            text: launcherController.appTitle + " - SETTINGS"
            color: ThemeModule.Theme.colors.cyan
            font.pixelSize: ThemeModule.Theme.fonts.pageTitle
            font.bold: true
        }

        Rectangle {
            objectName: "SettingsShell"
            color: ThemeModule.Theme.colors.panelTranslucent
            border.color: ThemeModule.Theme.colors.border
            border.width: ThemeModule.Theme.border.thin
            radius: ThemeModule.Theme.radius.panel
            Layout.fillWidth: true
            Layout.fillHeight: true

            RowLayout {
                anchors.fill: parent
                anchors.margins: ThemeModule.Theme.spacing.lg
                spacing: ThemeModule.Theme.spacing.md

                Flickable {
                    id: tabScroll
                    objectName: "SettingsTabs"
                    Layout.preferredWidth: ThemeModule.Theme.size.settingsTabsWidth
                    Layout.minimumWidth: ThemeModule.Theme.size.settingsTabsWidth
                    Layout.maximumWidth: ThemeModule.Theme.size.settingsTabsWidth
                    Layout.fillHeight: true
                    clip: true
                    contentHeight: tabsColumn.implicitHeight

                    ColumnLayout {
                        id: tabsColumn
                        width: tabScroll.width
                        spacing: ThemeModule.Theme.spacing.sm

                        Repeater {
                            model: settingsController.groups
                            delegate: CyberButton {
                                text: modelData
                                variant: settingsController.currentGroup === modelData ? "primary" : "secondary"
                                Layout.fillWidth: true
                                onClicked: settingsController.setGroup(modelData)
                            }
                        }
                        Item { Layout.fillHeight: true }
                    }
                }

                Flickable {
                    objectName: "SettingsContent"
                    clip: true
                    contentHeight: formColumn.implicitHeight
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    ColumnLayout {
                        id: formColumn
                        width: parent.width
                        spacing: ThemeModule.Theme.spacing.md

                        Text {
                            text: settingsController.currentGroup + " SETTINGS"
                            color: ThemeModule.Theme.colors.text
                            font.pixelSize: ThemeModule.Theme.fonts.sectionHeading
                            font.bold: true
                            Layout.fillWidth: true
                        }

                        Flow {
                            visible: settingsController.groupActions.length > 0
                            Layout.fillWidth: true
                            spacing: ThemeModule.Theme.spacing.sm

                            Repeater {
                                model: settingsController.groupActions
                                delegate: RowLayout {
                                    spacing: ThemeModule.Theme.spacing.sm
                                    CyberTextField {
                                        id: actionInput
                                        visible: Boolean(modelData.input)
                                        placeholderText: modelData.input || ""
                                        text: ""
                                        Layout.preferredWidth: ThemeModule.Theme.size.settingsActionInputWidth
                                    }
                                    CyberButton {
                                        objectName: "SettingsGroupActionButton"
                                        text: modelData.label
                                        variant: modelData.variant || "secondary"
                                        onClicked: {
                                            var actionKey = String(modelData.key);
                                            if (actionKey.indexOf("open_helper:") === 0) {
                                                toolsController.openHelper(actionKey.slice(String("open_helper:").length));
                                                return;
                                            }
                                            settingsController.runGroupAction(actionKey, actionInput.text);
                                        }
                                    }
                                }
                            }
                        }

                        Repeater {
                            model: settingsController.fields
                            delegate: RowLayout {
                                objectName: modelData.type === "options" ? "SettingsOptionRow" : "SettingsFieldRow"
                                Layout.fillWidth: true
                                spacing: ThemeModule.Theme.spacing.md

                                Text {
                                    text: modelData.label
                                    color: ThemeModule.Theme.colors.muted
                                    Layout.preferredWidth: ThemeModule.Theme.size.settingsLabelWidth
                                }

                                Loader {
                                    Layout.fillWidth: true
                                    sourceComponent: modelData.type === "bool" ? boolEditor
                                        : modelData.type === "summary" ? summaryEditor
                                        : modelData.type === "options" ? optionsEditor
                                        : textEditor
                                }

                                Repeater {
                                    model: modelData.actions || []
                                    delegate: CyberButton {
                                        objectName: "SettingsFieldActionButton"
                                        text: modelData.label || ""
                                        variant: modelData.variant || "secondary"
                                        onClicked: {
                                            var actionKey = String(modelData.key);
                                            if (actionKey.indexOf("open_helper:") === 0) {
                                                toolsController.openHelperPayload(actionKey.slice(String("open_helper:").length), modelData.value || {});
                                                return;
                                            }
                                            settingsController.runFieldAction(actionKey, modelData.value);
                                        }
                                    }
                                }

                                Component {
                                    id: textEditor
                                    CyberTextField {
                                        text: String(modelData.value)
                                        onEditingFinished: settingsController.setValue(modelData.key, text)
                                    }
                                }

                                Component {
                                    id: boolEditor
                                    CyberSwitch {
                                        checked: Boolean(modelData.value)
                                        onToggled: settingsController.setValue(modelData.key, checked)
                                    }
                                }

                                Component {
                                    id: optionsEditor
                                    CyberComboBox {
                                        objectName: "SettingsOptionEditor"
                                        model: modelData.options || []
                                        currentIndex: Math.max(0, (modelData.options || []).indexOf(String(modelData.value)))
                                        onActivated: settingsController.setValue(modelData.key, currentText)
                                    }
                                }

                                Component {
                                    id: summaryEditor
                                    ColumnLayout {
                                        spacing: ThemeModule.Theme.spacing.xs
                                        Text {
                                            text: String(modelData.value)
                                            color: ThemeModule.Theme.colors.text
                                            wrapMode: Text.WordWrap
                                            Layout.fillWidth: true
                                        }
                                        Text {
                                            objectName: "SettingsFieldWarning"
                                            visible: Boolean(modelData.warning)
                                            text: modelData.warning || ""
                                            color: ThemeModule.Theme.colors.yellow
                                            font.family: ThemeModule.Theme.fonts.mono
                                            wrapMode: Text.WordWrap
                                            Layout.fillWidth: true
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            CyberButton { text: "REFRESH"; variant: "secondary"; onClicked: settingsController.refresh() }
            CyberButton { text: "RESET"; variant: "danger"; onClicked: settingsController.resetVisible() }
        }
    }
}
