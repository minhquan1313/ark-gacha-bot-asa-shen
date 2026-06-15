import QtQuick
import QtQuick.Controls
import "../theme" as ThemeModule

ComboBox {
    id: control

    implicitHeight: ThemeModule.Theme.size.formFieldHeight
    leftPadding: ThemeModule.Theme.spacing.sm
    rightPadding: ThemeModule.Theme.size.iconButton
    font.pixelSize: ThemeModule.Theme.fonts.formText
    property bool popupOpen: popup.visible
    property bool inputFocused: Boolean(inputField && inputField.activeFocus)

    function openFromField() {
        if (!enabled) {
            return
        }
        if (editable) {
            inputField.forceActiveFocus()
        } else {
            forceActiveFocus()
        }
        popup.open()
    }

    function toggleFromIndicator() {
        if (!enabled) {
            return
        }
        if (popup.visible) {
            popup.close()
            return
        }
        openFromField()
    }

    contentItem: TextInput {
        id: inputField
        objectName: "CyberComboBoxInput"
        text: control.editable ? control.editText : control.displayText
        readOnly: !control.editable
        color: ThemeModule.Theme.colors.text
        selectedTextColor: ThemeModule.Theme.colors.panelStrong
        selectionColor: ThemeModule.Theme.colors.cyan
        verticalAlignment: TextInput.AlignVCenter
        font: control.font
        clip: true
        selectByMouse: true
        onEditingFinished: if (control.editable) control.editText = text

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton
            onPressed: {
                Qt.callLater(control.openFromField)
                mouse.accepted = false
            }
        }
    }

    indicator: Item {
        x: control.width - width
        y: 0
        width: ThemeModule.Theme.size.iconButton
        height: control.height

        Text {
            anchors.centerIn: parent
            text: control.popupOpen ? "^" : "v"
            color: ThemeModule.Theme.colors.cyan
            font.pixelSize: ThemeModule.Theme.fonts.buttonText
            font.bold: true
        }

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton
            onClicked: control.toggleFromIndicator()
        }
    }

    background: Rectangle {
        color: ThemeModule.Theme.colors.panelStrong
        border.color: control.activeFocus || control.popupOpen ? ThemeModule.Theme.colors.cyan : ThemeModule.Theme.colors.border
        border.width: ThemeModule.Theme.border.thin
        radius: ThemeModule.Theme.radius.sm
    }

    popup: Popup {
        y: control.height
        width: control.width
        implicitHeight: contentItem.implicitHeight
        padding: ThemeModule.Theme.spacing.xs
        z: 1000

        contentItem: ListView {
            clip: true
            implicitHeight: Math.min(contentHeight, ThemeModule.Theme.size.comboPopupHeight)
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
        }

        background: Rectangle {
            color: ThemeModule.Theme.colors.panelStrong
            border.color: ThemeModule.Theme.colors.borderActive
            border.width: ThemeModule.Theme.border.thin
            radius: ThemeModule.Theme.radius.sm
        }
    }

    delegate: ItemDelegate {
        width: control.width
        text: control.textRole ? model[control.textRole] : modelData
        highlighted: control.highlightedIndex === index

        contentItem: Text {
            text: parent.text
            color: parent.highlighted ? ThemeModule.Theme.colors.text : ThemeModule.Theme.colors.text
            font: control.font
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
        }

        background: Rectangle {
            color: parent.highlighted ? ThemeModule.Theme.colors.buttonPrimaryFill : "transparent"
            border.color: parent.highlighted ? ThemeModule.Theme.colors.borderActive : "transparent"
            border.width: ThemeModule.Theme.border.thin
            radius: ThemeModule.Theme.radius.sm
        }
    }
}
