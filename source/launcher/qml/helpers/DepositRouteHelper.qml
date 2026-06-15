import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme" as ThemeModule

BaseHelperWindow {
    id: helper

    property string routeKindFilter: controller ? controller.routeKind : "crystal"
    property int guideIndex: 0
    readonly property var guidePages: [
        {
            "title": "STEP 1 / RENDER BED",
            "body": "Lay in the Gacha render bed first. This keeps route setup aligned with the bot's starting flow.",
            "asset": "welcome"
        },
        {
            "title": "STEP 2 / TELEPORT",
            "body": "Teleport to the route you are editing, then aim at the dedi, vault, or grinder target.",
            "asset": "dashboard"
        },
        {
            "title": "STEP 3 / CAPTURE",
            "body": "Use capture on the route row. The helper focuses Ark, runs ccc, then saves yaw and pitch.",
            "asset": "logo"
        },
        {
            "title": "STEP 4 / CAPTURE",
            "body": "Press ALT + N to return to this helper after capture or view actions.",
            "asset": "logo_text"
        }
    ]
    readonly property var visibleRoutes: routeKindFilter === "grindable"
        ? (controller ? controller.grindableRoutes : [])
        : (controller ? controller.crystalRoutes : [])

    stopControllerOnClose: false
    width: ThemeModule.Theme.size.depositHelperWidth
    height: ThemeModule.Theme.size.depositHelperHeight
    minimumWidth: ThemeModule.Theme.size.depositHelperWidth
    minimumHeight: ThemeModule.Theme.size.helperHeight
    helperTitle: routeKindFilter === "grindable" ? "GRINDABLE ROUTE HELPER" : "CRYSTAL ROUTE HELPER"
    helperBody: ""
    contentFill: true
    statusText: controller ? controller.status : "Ready."

    Component.onCompleted: Qt.callLater(guideDialog.showNearOwner)
    onClosing: guideDialog.close()

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
        commitEditableFields(routeCards);
    }

    RowLayout {
        Layout.fillWidth: true
        Text {
            text: routeKindFilter === "grindable" ? "GRINDABLE ROUTES" : "CRYSTAL ROUTES"
            color: ThemeModule.Theme.colors.cyan
            font.family: ThemeModule.Theme.fonts.mono
            font.pixelSize: ThemeModule.Theme.fonts.badge
            font.bold: true
            Layout.fillWidth: true
        }
        CyberButton {
            objectName: "DepositGuideButton"
            text: "GUIDE"
            variant: "secondary"
            onClicked: guideDialog.showNearOwner()
        }
    }

    Flickable {
        objectName: "DepositRouteScroll"
        clip: true
        contentHeight: routeCards.implicitHeight
        Layout.fillWidth: true
        Layout.fillHeight: true

        ColumnLayout {
            id: routeCards
            width: parent.width
            spacing: ThemeModule.Theme.spacing.sm

            Repeater {
                model: helper.visibleRoutes
                delegate: CollapsiblePanel {
                    id: routeCard
                    objectName: "DepositRouteCard"
                    property string routeKind: modelData.kind
                    property int routeIndex: modelData.index
                    title: modelData.title + " | " + (modelData.teleport || "NO TELEPORT")
                        + " | Dedi " + modelData.dediCount
                        + (modelData.kind === "crystal" ? " | Vault " + modelData.vaultCount : "")
                    requestedExpanded: index === 0
                    Layout.fillWidth: true

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "TELEPORT"
                            color: ThemeModule.Theme.colors.muted
                            Layout.preferredWidth: ThemeModule.Theme.size.helperLabelWidth
                        }
                        CyberTextField {
                            objectName: "DepositTeleportField"
                            text: modelData.teleport || ""
                            Layout.fillWidth: true
                            function commitField() {
                                helper.controller.setRouteTeleport(routeCard.routeKind, routeCard.routeIndex, text);
                            }
                            onEditingFinished: commitField()
                        }
                        CyberButton {
                            text: "REMOVE ROUTE"
                            variant: "danger"
                            enabled: modelData.canRemove
                            onClicked: {
                                helper.commitFormEdits();
                                helper.controller.removeRoute(routeCard.routeKind, routeCard.routeIndex);
                            }
                        }
                    }

                    Repeater {
                        model: modelData.rows || []
                        delegate: ColumnLayout {
                            id: rowBlock
                            property string rowKind: modelData.kind
                            property int rowIndex: modelData.index
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
                                        property string rowKind: rowBlock.rowKind
                                        property int rowIndex: rowBlock.rowIndex
                                        property string rowKey: "yaw"
                                        text: modelData.yaw
                                        Layout.fillWidth: true
                                        function commitField() {
                                            helper.controller.updateRouteRow(routeCard.routeKind, routeCard.routeIndex, rowKind, rowIndex, rowKey, text);
                                        }
                                        onEditingFinished: commitField()
                                    }
                                    Text { text: "Pitch"; color: ThemeModule.Theme.colors.muted }
                                    CyberTextField {
                                        objectName: "DepositRouteValueField"
                                        property string rowKind: rowBlock.rowKind
                                        property int rowIndex: rowBlock.rowIndex
                                        property string rowKey: "pitch"
                                        text: modelData.pitch
                                        Layout.fillWidth: true
                                        function commitField() {
                                            helper.controller.updateRouteRow(routeCard.routeKind, routeCard.routeIndex, rowKind, rowIndex, rowKey, text);
                                        }
                                        onEditingFinished: commitField()
                                    }
                                }

                                CyberSwitch {
                                    text: rowBlock.rowKind === "grinder" ? "ACTIVE" : "CROUCHED"
                                    checked: rowBlock.rowKind === "grinder" ? modelData.active : modelData.crouched
                                    onToggled: helper.controller.updateRouteRow(
                                        routeCard.routeKind,
                                        routeCard.routeIndex,
                                        rowBlock.rowKind,
                                        rowBlock.rowIndex,
                                        rowBlock.rowKind === "grinder" ? "active" : "crouched",
                                        checked
                                    )
                                }

                                CyberTextField {
                                    objectName: "DepositVaultItemsField"
                                    visible: rowBlock.rowKind === "vault"
                                    text: modelData.items || ""
                                    placeholderText: "Vault items, comma separated"
                                    Layout.fillWidth: true
                                    function commitField() {
                                        helper.controller.updateRouteRow(routeCard.routeKind, routeCard.routeIndex, rowBlock.rowKind, rowBlock.rowIndex, "items", text);
                                    }
                                    onEditingFinished: commitField()
                                }

                                RowLayout {
                                    visible: rowBlock.rowKind === "vault"
                                    Layout.fillWidth: true
                                    CyberComboBox {
                                        id: vaultItemCombo
                                        objectName: rowBlock.rowKind === "vault" ? "VaultItemCombo" : ""
                                        editable: true
                                        model: controller ? controller.vaultItems : []
                                        Layout.fillWidth: true
                                    }
                                    CyberButton {
                                        text: "ADD ITEM"
                                        variant: "secondary"
                                        onClicked: {
                                            helper.commitFormEdits();
                                            helper.controller.addVaultItemToRoute(routeCard.routeKind, routeCard.routeIndex, rowBlock.rowIndex, vaultItemCombo.editText || vaultItemCombo.currentText);
                                        }
                                    }
                                }

                                Repeater {
                                    model: modelData.itemValues || []
                                    delegate: RowLayout {
                                        visible: rowBlock.rowKind === "vault"
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
                                            onClicked: helper.controller.removeVaultItemFromRoute(routeCard.routeKind, routeCard.routeIndex, rowBlock.rowIndex, index)
                                        }
                                    }
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                CyberButton {
                                    property string rowKind: rowBlock.rowKind
                                    property int rowIndex: rowBlock.rowIndex
                                    text: "CAPTURE"
                                    enabled: helper.controller && !helper.controller.busy
                                    onClicked: {
                                        helper.commitFormEdits();
                                        helper.controller.captureRouteRow(routeCard.routeKind, routeCard.routeIndex, rowKind, rowIndex);
                                    }
                                }
                                CyberButton {
                                    objectName: "DepositRouteViewButton"
                                    property string rowKind: rowBlock.rowKind
                                    property int rowIndex: rowBlock.rowIndex
                                    text: "VIEW"
                                    enabled: helper.controller && !helper.controller.busy
                                    onClicked: {
                                        helper.commitFormEdits();
                                        helper.controller.viewRouteRow(routeCard.routeKind, routeCard.routeIndex, rowKind, rowIndex);
                                    }
                                }
                                Item { Layout.fillWidth: true }
                                CyberButton {
                                    visible: rowBlock.rowKind !== "grinder"
                                    property string rowKind: rowBlock.rowKind
                                    property int rowIndex: rowBlock.rowIndex
                                    text: "REMOVE"
                                    variant: "danger"
                                    onClicked: {
                                        helper.commitFormEdits();
                                        helper.controller.removeRouteRow(routeCard.routeKind, routeCard.routeIndex, rowKind, rowIndex);
                                    }
                                }
                            }
                        }
                    }

                    GridLayout {
                        columns: 2
                        Layout.fillWidth: true
                        rowSpacing: ThemeModule.Theme.spacing.sm
                        columnSpacing: ThemeModule.Theme.spacing.sm

                        CyberButton {
                            objectName: "DepositAddDediInlineButton"
                            text: "ADD DEDI"
                            variant: "secondary"
                            Layout.fillWidth: true
                            onClicked: {
                                helper.commitFormEdits();
                                helper.controller.addRowToRoute(routeCard.routeKind, routeCard.routeIndex, "dedi");
                            }
                        }
                        CyberButton {
                            text: "CAPTURE DEDI"
                            variant: "primary"
                            Layout.fillWidth: true
                            enabled: helper.controller && !helper.controller.busy
                            onClicked: {
                                helper.commitFormEdits();
                                helper.controller.captureNewRowForRoute(routeCard.routeKind, routeCard.routeIndex, "dedi");
                            }
                        }
                        CyberButton {
                            text: "ADD VAULT"
                            visible: routeCard.routeKind === "crystal"
                            variant: "secondary"
                            Layout.fillWidth: true
                            onClicked: {
                                helper.commitFormEdits();
                                helper.controller.addRowToRoute(routeCard.routeKind, routeCard.routeIndex, "vault");
                            }
                        }
                        CyberButton {
                            text: "CAPTURE VAULT"
                            visible: routeCard.routeKind === "crystal"
                            variant: "primary"
                            Layout.fillWidth: true
                            enabled: helper.controller && !helper.controller.busy
                            onClicked: {
                                helper.commitFormEdits();
                                helper.controller.captureNewRowForRoute(routeCard.routeKind, routeCard.routeIndex, "vault");
                            }
                        }
                    }
                }
            }

            CyberButton {
                objectName: routeKindFilter === "grindable" ? "DepositAddGrindableRouteButton" : "DepositAddCrystalRouteButton"
                text: routeKindFilter === "grindable" ? "ADD GRINDABLE ROUTE" : "ADD CRYSTAL ROUTE"
                variant: "primary"
                Layout.fillWidth: true
                onClicked: {
                    helper.commitFormEdits();
                    helper.controller.addRoute(routeKindFilter);
                }
            }
        }
    }

    HelperGuideWindow {
        id: guideDialog
        objectName: "DepositGuideDialog"
        ownerWindow: helper
        guideTitle: "HELPER GUIDE"

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
