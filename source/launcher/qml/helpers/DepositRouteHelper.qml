import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme" as ThemeModule

BaseHelperWindow {
    id: helper

    stopControllerOnClose: false
    property int guideIndex: 0
    readonly property var guidePages: [
        {
            "title": "STEP 1 / RENDER BED",
            "body": "Lay in the Gacha render bed first. This keeps the route setup aligned with the same starting flow the bot uses.",
            "asset": "welcome"
        },
        {
            "title": "STEP 2 / TELEPORT",
            "body": "Get out of bed and teleport to the route teleporter you are editing in the helper.",
            "asset": "dashboard"
        },
        {
            "title": "STEP 3 / AIM AT TARGET",
            "body": "Aim at the dedi, vault, or grinder until the in-game deposit/access prompt is visible.",
            "asset": "logo"
        },
        {
            "title": "STEP 4 / CAPTURE",
            "body": "Press capture on a row. The helper focuses Ark, runs ccc through the existing console flow, then saves yaw and pitch. Press Alt + N to return to this helper.",
            "asset": "logo_text"
        }
    ]

    width: ThemeModule.Theme.size.depositHelperWidth
    height: ThemeModule.Theme.size.depositHelperHeight
    minimumWidth: ThemeModule.Theme.size.depositHelperWidth
    minimumHeight: ThemeModule.Theme.size.helperHeight
    helperTitle: controller ? controller.title : "DEPOSIT ROUTE HELPER"
    helperBody: ""
    contentFill: true
    statusText: controller ? controller.status : "Ready."

    Component.onCompleted: guideDialog.open()

    function commitEditableFields(item) {
        if (!item || item.visible === false) {
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
        commitEditableFields(teleportField);
        commitEditableFields(routeRows);
    }

    RowLayout {
        Layout.fillWidth: true
        Item { Layout.fillWidth: true }
        CyberButton {
            objectName: "DepositGuideButton"
            text: "GUIDE"
            variant: "secondary"
            onClicked: guideDialog.open()
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Text {
            text: "ROUTE"
            color: ThemeModule.Theme.colors.muted
            Layout.preferredWidth: ThemeModule.Theme.size.settingsLabelWidth
        }
        CyberComboBox {
            id: routeSelector
            textRole: "label"
            valueRole: "index"
            model: controller ? controller.routes : []
            enabled: controller && controller.routes.length > 0
            Layout.fillWidth: true
            onActivated: {
                helper.commitFormEdits()
                var row = model[index]
                controller.selectRoute(row.kind, row.index)
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Text {
            text: "TELEPORT"
            color: ThemeModule.Theme.colors.muted
            Layout.preferredWidth: ThemeModule.Theme.size.settingsLabelWidth
        }
        CyberTextField {
            id: teleportField
            objectName: "DepositTeleportField"
            text: controller ? controller.teleport : ""
            enabled: controller && controller.hasRoute
            Layout.fillWidth: true
            function commitField() {
                controller.setTeleport(text);
            }
            onEditingFinished: commitField()
        }
    }

    RowLayout {
        Layout.fillWidth: true
        CyberButton {
            objectName: "DepositAddCrystalRouteButton"
            text: "ADD CRYSTAL ROUTE"
            variant: "secondary"
            Layout.fillWidth: true
            onClicked: {
                helper.commitFormEdits()
                controller.addRoute("crystal")
            }
        }
        CyberButton {
            objectName: "DepositAddGrindableRouteButton"
            text: "ADD GRINDABLE ROUTE"
            variant: "secondary"
            Layout.fillWidth: true
            onClicked: {
                helper.commitFormEdits()
                controller.addRoute("grindable")
            }
        }
        CyberButton {
            text: "REMOVE ROUTE"
            variant: "danger"
            visible: controller && controller.hasRoute
            enabled: controller && controller.canRemoveRoute
            onClicked: controller.removeCurrentRoute()
        }
    }

    Text {
        visible: controller && !controller.hasRoute
        text: "No deposit route is configured. Add a crystal or grindable route to begin."
        color: ThemeModule.Theme.colors.muted
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }

    Flickable {
        objectName: "DepositRouteScroll"
        visible: controller && controller.hasRoute
        clip: true
        contentHeight: routeRows.implicitHeight
        Layout.fillWidth: true
        Layout.fillHeight: true

        ColumnLayout {
            id: routeRows
            width: parent.width
            spacing: ThemeModule.Theme.spacing.sm

            Repeater {
                model: controller ? controller.rows : []
                delegate: ColumnLayout {
                    Layout.fillWidth: true
                    spacing: ThemeModule.Theme.spacing.xs

                    CollapsiblePanel {
                        objectName: "DepositRouteRow"
                        title: modelData.title + " | Yaw " + modelData.yaw + " | Pitch " + modelData.pitch + (modelData.crouched ? " | Crouched" : "")
                        requestedExpanded: false
                        Layout.fillWidth: true

                        GridLayout {
                            objectName: "DepositRouteRowDetails"
                            columns: 2
                            Layout.fillWidth: true
                            Text { text: "Yaw"; color: ThemeModule.Theme.colors.muted }
                            CyberTextField {
                                objectName: "DepositRouteValueField"
                                property string rowKind: modelData.kind
                                property int rowIndex: modelData.index
                                property string rowKey: "yaw"
                                text: modelData.yaw
                                Layout.fillWidth: true
                                function commitField() {
                                    controller.updateRow(rowKind, rowIndex, rowKey, text);
                                }
                                onEditingFinished: commitField()
                            }
                            Text { text: "Pitch"; color: ThemeModule.Theme.colors.muted }
                            CyberTextField {
                                objectName: "DepositRouteValueField"
                                property string rowKind: modelData.kind
                                property int rowIndex: modelData.index
                                property string rowKey: "pitch"
                                text: modelData.pitch
                                Layout.fillWidth: true
                                function commitField() {
                                    controller.updateRow(rowKind, rowIndex, rowKey, text);
                                }
                                onEditingFinished: commitField()
                            }
                        }

                        CyberSwitch {
                            text: "CROUCHED"
                            checked: modelData.crouched
                            onToggled: controller.updateRow(modelData.kind, modelData.index, "crouched", checked)
                        }

                        CyberTextField {
                            objectName: "DepositVaultItemsField"
                            property string rowKind: modelData.kind
                            property int rowIndex: modelData.index
                            visible: modelData.kind === "vault"
                            text: modelData.items || ""
                            placeholderText: "Vault items, comma separated"
                            Layout.fillWidth: true
                            function commitField() {
                                controller.updateRow(rowKind, rowIndex, "items", text);
                            }
                            onEditingFinished: commitField()
                        }
                        RowLayout {
                            visible: modelData.kind === "vault"
                            Layout.fillWidth: true
                            CyberComboBox {
                                id: vaultItemCombo
                                objectName: modelData.kind === "vault" ? "VaultItemCombo" : ""
                                editable: true
                                model: controller ? controller.vaultItems : []
                                Layout.fillWidth: true
                            }
                            CyberButton {
                                property int vaultIndex: modelData.index
                                text: "ADD ITEM"
                                variant: "secondary"
                                onClicked: {
                                    helper.commitFormEdits();
                                    controller.addVaultItem(vaultIndex, vaultItemCombo.editText || vaultItemCombo.currentText);
                                }
                            }
                        }
                        ColumnLayout {
                            id: vaultItemsColumn
                            property int vaultIndex: modelData.index
                            visible: modelData.kind === "vault" && Boolean(modelData.itemValues) && modelData.itemValues.length > 0
                            Layout.fillWidth: true
                            spacing: ThemeModule.Theme.spacing.xs

                            Repeater {
                                model: modelData.itemValues || []
                                delegate: RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        objectName: "VaultItemValue"
                                        text: modelData
                                        color: ThemeModule.Theme.colors.text
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                    }
                                    CyberButton {
                                        text: "REMOVE ITEM"
                                        variant: "danger"
                                        onClicked: controller.removeVaultItem(vaultItemsColumn.vaultIndex, index)
                                    }
                                }
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        CyberButton {
                            property string rowKind: modelData.kind
                            property int rowIndex: modelData.index
                            text: "CAPTURE"
                            enabled: controller && !controller.busy
                            onClicked: {
                                helper.commitFormEdits();
                                controller.captureRow(rowKind, rowIndex);
                            }
                        }
                        CyberButton {
                            objectName: "DepositRouteViewButton"
                            property string rowKind: modelData.kind
                            property int rowIndex: modelData.index
                            text: "VIEW"
                            enabled: controller && !controller.busy
                            onClicked: {
                                helper.commitFormEdits();
                                controller.viewRow(rowKind, rowIndex);
                            }
                        }
                        Item { Layout.fillWidth: true }
                        CyberButton {
                            property string rowKind: modelData.kind
                            property int rowIndex: modelData.index
                            text: "REMOVE"
                            variant: "danger"
                            onClicked: {
                                helper.commitFormEdits();
                                controller.removeRow(rowKind, rowIndex);
                            }
                        }
                    }
                }
            }
        }
    }

    GridLayout {
        visible: controller && controller.hasRoute
        columns: 2
        Layout.fillWidth: true
        rowSpacing: ThemeModule.Theme.spacing.sm
        columnSpacing: ThemeModule.Theme.spacing.sm
        CyberButton {
            objectName: "DepositAddDediButton"
            text: "ADD DEDI"
            variant: "secondary"
            Layout.fillWidth: true
            onClicked: {
                helper.commitFormEdits()
                controller.addRow("dedi")
            }
        }
        CyberButton {
            objectName: "DepositCaptureDediButton"
            text: "CAPTURE DEDI"
            variant: "primary"
            Layout.fillWidth: true
            enabled: controller && !controller.busy
            onClicked: {
                helper.commitFormEdits()
                controller.captureNewRow("dedi")
            }
        }
        CyberButton {
            objectName: "DepositAddVaultButton"
            text: "ADD VAULT"
            visible: controller && controller.routeKind === "crystal"
            variant: "secondary"
            Layout.fillWidth: true
            onClicked: {
                helper.commitFormEdits()
                controller.addRow("vault")
            }
        }
        CyberButton {
            objectName: "DepositCaptureVaultButton"
            text: "CAPTURE VAULT"
            visible: controller && controller.routeKind === "crystal"
            variant: "primary"
            Layout.fillWidth: true
            enabled: controller && !controller.busy
            onClicked: {
                helper.commitFormEdits()
                controller.captureNewRow("vault")
            }
        }
    }

    Popup {
        id: guideDialog
        objectName: "DepositGuideDialog"
        modal: false
        focus: true
        width: helper.width - ThemeModule.Theme.spacing.xxl
        height: guideContent.implicitHeight + ThemeModule.Theme.spacing.xl * 2
        x: (helper.width - width) / 2
        y: (helper.height - height) / 2
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle {
            color: ThemeModule.Theme.colors.panelStrong
            border.color: ThemeModule.Theme.colors.cyan
            border.width: ThemeModule.Theme.border.thin
            radius: ThemeModule.Theme.radius.md
        }

        ColumnLayout {
            id: guideContent
            anchors.fill: parent
            anchors.margins: ThemeModule.Theme.spacing.xl
            spacing: ThemeModule.Theme.spacing.md

            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: "HELPER GUIDE"
                    color: ThemeModule.Theme.colors.cyan
                    font.pixelSize: ThemeModule.Theme.fonts.sectionHeading
                    font.bold: true
                    Layout.fillWidth: true
                }
                IconButton {
                    text: "X"
                    variant: "danger"
                    onClicked: guideDialog.close()
                }
            }

            Image {
                source: assetPaths[helper.guidePages[helper.guideIndex].asset] || assetPaths.logo
                fillMode: Image.PreserveAspectFit
                Layout.fillWidth: true
                Layout.preferredHeight: ThemeModule.Theme.size.heroHeight
            }

            Text {
                objectName: "DepositGuideTitle"
                text: helper.guidePages[helper.guideIndex].title
                color: ThemeModule.Theme.colors.text
                font.bold: true
                Layout.fillWidth: true
            }

            Text {
                text: helper.guidePages[helper.guideIndex].body
                color: ThemeModule.Theme.colors.muted
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            RowLayout {
                Layout.fillWidth: true
                CyberButton {
                    text: "PREV"
                    variant: "secondary"
                    enabled: helper.guideIndex > 0
                    onClicked: helper.guideIndex = Math.max(0, helper.guideIndex - 1)
                }
                Item { Layout.fillWidth: true }
                Text {
                    objectName: "DepositGuidePage"
                    text: String(helper.guideIndex + 1) + " / " + String(helper.guidePages.length)
                    color: ThemeModule.Theme.colors.muted
                    font.family: ThemeModule.Theme.fonts.mono
                }
                Item { Layout.fillWidth: true }
                CyberButton {
                    text: "NEXT"
                    variant: "primary"
                    enabled: helper.guideIndex < helper.guidePages.length - 1
                    onClicked: helper.guideIndex = Math.min(helper.guidePages.length - 1, helper.guideIndex + 1)
                }
            }
        }
    }
}
