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

        Panel {
            Layout.fillWidth: true
            Layout.fillHeight: true

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: ThemeModule.Theme.spacing.md

                ColumnLayout {
                    Layout.preferredWidth: ThemeModule.Theme.size.settingsTabsWidth
                    Layout.fillHeight: true
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

                Flickable {
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

                        Repeater {
                            model: settingsController.fields
                            delegate: RowLayout {
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
                                        : textEditor
                                }

                                Component {
                                    id: textEditor
                                    TextField {
                                        text: String(modelData.value)
                                        color: ThemeModule.Theme.colors.text
                                        selectByMouse: true
                                        background: Rectangle {
                                            color: ThemeModule.Theme.colors.panelStrong
                                            border.color: ThemeModule.Theme.colors.border
                                            radius: ThemeModule.Theme.radius.sm
                                        }
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
                                    id: summaryEditor
                                    Text {
                                        text: String(modelData.value)
                                        color: ThemeModule.Theme.colors.text
                                        wrapMode: Text.WordWrap
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
