import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme" as ThemeModule

Item {
    function runGroupAction(action, inputText) {
        var actionKey = String(action.key);
        if (actionKey.indexOf("open_helper:") === 0) {
            toolsController.openHelper(actionKey.slice(String("open_helper:").length));
            return;
        }
        settingsController.runGroupAction(actionKey, inputText || "");
    }

    function runFieldAction(action) {
        var actionKey = String(action.key);
        if (actionKey.indexOf("open_helper:") === 0) {
            toolsController.openHelperPayload(
                actionKey.slice(String("open_helper:").length),
                action.value || {}
            );
            return;
        }
        settingsController.runFieldAction(actionKey, action.value);
    }

    function isConfigGroup() {
        return settingsController.currentGroup === "GACHA"
            || settingsController.currentGroup === "PEGO"
            || settingsController.currentGroup === "STORAGE";
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: ThemeModule.Theme.spacing.lg
        spacing: ThemeModule.Theme.spacing.md

        RowLayout {
            Layout.fillWidth: true
            spacing: ThemeModule.Theme.spacing.md
            Text {
                text: launcherController.appTitle + " - SETTINGS"
                color: ThemeModule.Theme.colors.cyan
                font.pixelSize: ThemeModule.Theme.fonts.pageTitle
                font.bold: true
                Layout.fillWidth: true
            }
            Text {
                text: settingsController.currentGroup
                color: ThemeModule.Theme.colors.green
                font.family: ThemeModule.Theme.fonts.mono
                font.pixelSize: ThemeModule.Theme.fonts.consoleText
            }
        }

        Rectangle {
            objectName: "SettingsShell"
            color: ThemeModule.Theme.colors.panelStrong
            border.color: ThemeModule.Theme.colors.borderActive
            border.width: ThemeModule.Theme.border.thin
            radius: ThemeModule.Theme.radius.panel
            Layout.fillWidth: true
            Layout.fillHeight: true

            RowLayout {
                anchors.fill: parent
                anchors.margins: ThemeModule.Theme.spacing.md
                spacing: 0

                Rectangle {
                    color: ThemeModule.Theme.colors.sidebar
                    border.color: ThemeModule.Theme.colors.border
                    border.width: ThemeModule.Theme.border.thin
                    radius: ThemeModule.Theme.radius.panel
                    Layout.preferredWidth: ThemeModule.Theme.size.settingsTabsWidth
                    Layout.minimumWidth: ThemeModule.Theme.size.settingsTabsWidth
                    Layout.maximumWidth: ThemeModule.Theme.size.settingsTabsWidth
                    Layout.fillHeight: true

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: ThemeModule.Theme.spacing.sm
                        spacing: ThemeModule.Theme.spacing.sm

                        Text {
                            text: "CONFIG INDEX"
                            color: ThemeModule.Theme.colors.cyan
                            font.family: ThemeModule.Theme.fonts.mono
                            font.pixelSize: ThemeModule.Theme.fonts.badge
                            font.bold: true
                            Layout.fillWidth: true
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: ThemeModule.Theme.border.thin
                            color: ThemeModule.Theme.colors.border
                        }

                        Flickable {
                            id: tabScroll
                            objectName: "SettingsTabs"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            contentHeight: tabsColumn.implicitHeight

                            ColumnLayout {
                                id: tabsColumn
                                width: tabScroll.width
                                spacing: ThemeModule.Theme.spacing.sm

                                Repeater {
                                    model: settingsController.groups
                                    delegate: Rectangle {
                                        Layout.fillWidth: true
                                        implicitHeight: ThemeModule.Theme.size.buttonHeight
                                        color: settingsController.currentGroup === modelData
                                            ? ThemeModule.Theme.colors.buttonPrimaryFill
                                            : ThemeModule.Theme.colors.glass
                                        border.color: settingsController.currentGroup === modelData
                                            ? ThemeModule.Theme.colors.cyan
                                            : ThemeModule.Theme.colors.border
                                        border.width: ThemeModule.Theme.border.thin
                                        radius: ThemeModule.Theme.radius.sm

                                        Rectangle {
                                            anchors.left: parent.left
                                            anchors.top: parent.top
                                            anchors.bottom: parent.bottom
                                            width: ThemeModule.Theme.border.active
                                            visible: settingsController.currentGroup === modelData
                                            color: ThemeModule.Theme.colors.cyan
                                        }

                                        Text {
                                            anchors.fill: parent
                                            anchors.leftMargin: ThemeModule.Theme.spacing.lg
                                            anchors.rightMargin: ThemeModule.Theme.spacing.sm
                                            text: modelData
                                            color: settingsController.currentGroup === modelData
                                                ? ThemeModule.Theme.colors.cyan
                                                : ThemeModule.Theme.colors.text
                                            font.pixelSize: ThemeModule.Theme.fonts.buttonText
                                            font.bold: true
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                            elide: Text.ElideRight
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            onClicked: settingsController.setGroup(modelData)
                                        }
                                    }
                                }
                            }
                        }

                        Text {
                            text: String(settingsController.sections.length) + " SECTION" + (settingsController.sections.length === 1 ? "" : "S")
                            color: ThemeModule.Theme.colors.dim
                            font.family: ThemeModule.Theme.fonts.mono
                            font.pixelSize: ThemeModule.Theme.fonts.consoleText
                            Layout.fillWidth: true
                        }
                    }
                }

                Rectangle {
                    objectName: "SettingsContentDivider"
                    Layout.preferredWidth: ThemeModule.Theme.spacing.md
                    Layout.fillHeight: true
                    color: "transparent"

                    Rectangle {
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: ThemeModule.Theme.border.active
                        color: ThemeModule.Theme.colors.cyan
                        opacity: 0.45
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

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: ThemeModule.Theme.spacing.md
                            Text {
                                text: settingsController.currentGroup + " SETTINGS"
                                color: ThemeModule.Theme.colors.text
                                font.pixelSize: ThemeModule.Theme.fonts.sectionHeading
                                font.bold: true
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                            Text {
                                text: isConfigGroup() ? "ROUTE DATA" : "LOCAL"
                                color: ThemeModule.Theme.colors.green
                                font.family: ThemeModule.Theme.fonts.mono
                                font.pixelSize: ThemeModule.Theme.fonts.consoleText
                            }
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
                                        onClicked: runGroupAction(modelData, actionInput.text)
                                    }
                                }
                            }
                        }

                        Repeater {
                            model: settingsController.sections
                            delegate: ColumnLayout {
                                id: sectionWrapper
                                property string currentBand: modelData.band || ""
                                property string previousBand: index > 0 ? (settingsController.sections[index - 1].band || "") : ""
                                Layout.fillWidth: true
                                spacing: ThemeModule.Theme.spacing.sm

                                Rectangle {
                                    visible: sectionWrapper.currentBand.length > 0 && sectionWrapper.currentBand !== sectionWrapper.previousBand
                                    Layout.fillWidth: true
                                    implicitHeight: bandText.implicitHeight + ThemeModule.Theme.spacing.sm
                                    color: ThemeModule.Theme.colors.panel
                                    border.color: ThemeModule.Theme.colors.border
                                    border.width: ThemeModule.Theme.border.thin
                                    radius: ThemeModule.Theme.radius.sm
                                    Text {
                                        id: bandText
                                        anchors.fill: parent
                                        anchors.leftMargin: ThemeModule.Theme.spacing.md
                                        anchors.rightMargin: ThemeModule.Theme.spacing.md
                                        text: sectionWrapper.currentBand
                                        color: ThemeModule.Theme.colors.cyan
                                        font.family: ThemeModule.Theme.fonts.mono
                                        font.pixelSize: ThemeModule.Theme.fonts.badge
                                        font.bold: true
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                }

                                Rectangle {
                                    id: sectionCard
                                    objectName: "SettingsSectionCard"
                                    property bool expanded: modelData.expandedDefault === undefined ? true : Boolean(modelData.expandedDefault)
                                    Layout.fillWidth: true
                                    implicitHeight: sectionColumn.implicitHeight + ThemeModule.Theme.spacing.lg * 2
                                    color: ThemeModule.Theme.colors.panelStrong
                                    border.color: expanded ? ThemeModule.Theme.colors.borderActive : ThemeModule.Theme.colors.borderSoft
                                    border.width: ThemeModule.Theme.border.thin
                                    radius: ThemeModule.Theme.radius.panel

                                    ColumnLayout {
                                        id: sectionColumn
                                        anchors.fill: parent
                                        anchors.margins: ThemeModule.Theme.spacing.lg
                                        spacing: ThemeModule.Theme.spacing.md

                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: ThemeModule.Theme.spacing.sm

                                            CyberButton {
                                                objectName: "SettingsSectionToggle"
                                                text: sectionCard.expanded ? "v" : ">"
                                                variant: "secondary"
                                                onClicked: sectionCard.expanded = !sectionCard.expanded
                                            }

                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                spacing: ThemeModule.Theme.spacing.xxs
                                                Text {
                                                    text: modelData.title || ""
                                                    color: ThemeModule.Theme.colors.cyan
                                                    font.pixelSize: ThemeModule.Theme.fonts.panelTitle
                                                    font.bold: true
                                                    Layout.fillWidth: true
                                                    elide: Text.ElideRight
                                                }
                                                Text {
                                                    text: (modelData.subtitle || "") + (modelData.summary ? " | " + modelData.summary : "")
                                                    color: ThemeModule.Theme.colors.muted
                                                    font.family: ThemeModule.Theme.fonts.mono
                                                    font.pixelSize: ThemeModule.Theme.fonts.consoleText
                                                    Layout.fillWidth: true
                                                    elide: Text.ElideRight
                                                }
                                            }

                                            Flow {
                                                visible: Boolean(modelData.actions) && modelData.actions.length > 0
                                                spacing: ThemeModule.Theme.spacing.sm
                                                Layout.maximumWidth: Math.max(260, parent.width * 0.5)
                                                Layout.alignment: Qt.AlignRight

                                                Repeater {
                                                    model: modelData.actions || []
                                                    delegate: CyberButton {
                                                        objectName: "SettingsFieldActionButton"
                                                        text: modelData.label || ""
                                                        variant: modelData.variant || "secondary"
                                                        onClicked: runFieldAction(modelData)
                                                    }
                                                }
                                            }
                                        }

                                        Rectangle {
                                            visible: sectionCard.expanded
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: ThemeModule.Theme.border.thin
                                            color: ThemeModule.Theme.colors.border
                                        }

                                        GridLayout {
                                            id: fieldGrid
                                            visible: sectionCard.expanded
                                            Layout.fillWidth: true
                                            columns: width >= 760 ? 2 : 1
                                            columnSpacing: ThemeModule.Theme.spacing.md
                                            rowSpacing: ThemeModule.Theme.spacing.sm

                                            Repeater {
                                                model: modelData.fields || []
                                                delegate: Rectangle {
                                                    id: fieldCard
                                                    objectName: modelData.type === "options" ? "SettingsOptionRow" : "SettingsFieldRow"
                                                    property var field: modelData
                                                    Layout.fillWidth: true
                                                    Layout.preferredWidth: fieldGrid.columns > 1
                                                        ? Math.max(260, (fieldGrid.width - fieldGrid.columnSpacing) / 2)
                                                        : fieldGrid.width
                                                    implicitHeight: fieldColumn.implicitHeight + ThemeModule.Theme.spacing.md * 2
                                                    color: ThemeModule.Theme.colors.panel
                                                    border.color: ThemeModule.Theme.colors.border
                                                    border.width: ThemeModule.Theme.border.thin
                                                    radius: ThemeModule.Theme.radius.sm

                                                    ColumnLayout {
                                                        id: fieldColumn
                                                        anchors.fill: parent
                                                        anchors.margins: ThemeModule.Theme.spacing.md
                                                        spacing: ThemeModule.Theme.spacing.sm

                                                        RowLayout {
                                                            Layout.fillWidth: true
                                                            spacing: ThemeModule.Theme.spacing.sm

                                                            Text {
                                                                text: fieldCard.field.label
                                                                color: ThemeModule.Theme.colors.muted
                                                                font.pixelSize: ThemeModule.Theme.fonts.formText
                                                                Layout.fillWidth: true
                                                                elide: Text.ElideRight
                                                            }

                                                            Repeater {
                                                                model: fieldCard.field.actions || []
                                                                delegate: CyberButton {
                                                                    objectName: "SettingsFieldActionButton"
                                                                    text: modelData.label || ""
                                                                    variant: modelData.variant || "secondary"
                                                                    onClicked: runFieldAction(modelData)
                                                                }
                                                            }
                                                        }

                                                        Loader {
                                                            Layout.fillWidth: true
                                                            sourceComponent: fieldCard.field.type === "bool" ? boolEditor
                                                                : fieldCard.field.type === "summary" ? summaryEditor
                                                                : fieldCard.field.type === "options" ? optionsEditor
                                                                : textEditor
                                                        }

                                                        Text {
                                                            objectName: "SettingsFieldWarning"
                                                            visible: Boolean(fieldCard.field.warning)
                                                            text: fieldCard.field.warning || ""
                                                            color: ThemeModule.Theme.colors.yellow
                                                            font.family: ThemeModule.Theme.fonts.mono
                                                            font.pixelSize: ThemeModule.Theme.fonts.consoleText
                                                            wrapMode: Text.WordWrap
                                                            Layout.fillWidth: true
                                                        }
                                                    }

                                                    Component {
                                                        id: textEditor
                                                        CyberTextField {
                                                            text: String(fieldCard.field.value)
                                                            onEditingFinished: {
                                                                if (String(fieldCard.field.key).length > 0) {
                                                                    settingsController.setValue(fieldCard.field.key, text);
                                                                }
                                                            }
                                                        }
                                                    }

                                                    Component {
                                                        id: boolEditor
                                                        CyberSwitch {
                                                            checked: Boolean(fieldCard.field.value)
                                                            onToggled: {
                                                                if (String(fieldCard.field.key).length > 0) {
                                                                    settingsController.setValue(fieldCard.field.key, checked);
                                                                }
                                                            }
                                                        }
                                                    }

                                                    Component {
                                                        id: optionsEditor
                                                        CyberComboBox {
                                                            objectName: "SettingsOptionEditor"
                                                            model: fieldCard.field.options || []
                                                            currentIndex: Math.max(0, (fieldCard.field.options || []).indexOf(String(fieldCard.field.value)))
                                                            onActivated: settingsController.setValue(fieldCard.field.key, currentText)
                                                        }
                                                    }

                                                    Component {
                                                        id: summaryEditor
                                                        Text {
                                                            text: String(fieldCard.field.value)
                                                            color: ThemeModule.Theme.colors.text
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
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            CyberButton { text: "REFRESH"; variant: "secondary"; onClicked: settingsController.refresh() }
            CyberButton {
                text: isConfigGroup() ? "RESTORE DEFAULT" : "RESTORE VISIBLE DEFAULTS"
                variant: "danger"
                onClicked: settingsController.resetVisible()
            }
        }
    }
}
