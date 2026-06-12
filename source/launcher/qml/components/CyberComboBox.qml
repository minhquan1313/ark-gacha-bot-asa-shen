import QtQuick
import QtQuick.Controls
import "../theme" as ThemeModule

ComboBox {
    id: control

    implicitHeight: ThemeModule.Theme.size.formFieldHeight
    leftPadding: ThemeModule.Theme.spacing.sm
    rightPadding: ThemeModule.Theme.size.iconButton
    font.pixelSize: ThemeModule.Theme.fonts.formText

    contentItem: TextInput {
        text: control.editable ? control.editText : control.displayText
        readOnly: !control.editable
        color: ThemeModule.Theme.colors.text
        selectedTextColor: ThemeModule.Theme.colors.panelStrong
        selectionColor: ThemeModule.Theme.colors.cyan
        verticalAlignment: TextInput.AlignVCenter
        font: control.font
        clip: true
        onEditingFinished: if (control.editable) control.editText = text
    }

    indicator: Text {
        x: control.width - width - ThemeModule.Theme.spacing.sm
        y: (control.height - height) / 2
        text: "v"
        color: ThemeModule.Theme.colors.cyan
        font.pixelSize: ThemeModule.Theme.fonts.buttonText
        font.bold: true
    }

    background: Rectangle {
        color: ThemeModule.Theme.colors.panelStrong
        border.color: control.activeFocus ? ThemeModule.Theme.colors.cyan : ThemeModule.Theme.colors.border
        border.width: ThemeModule.Theme.border.thin
        radius: ThemeModule.Theme.radius.sm
    }

    popup: Popup {
        y: control.height
        width: control.width
        implicitHeight: contentItem.implicitHeight
        padding: ThemeModule.Theme.spacing.xs

        contentItem: ListView {
            clip: true
            implicitHeight: Math.min(contentHeight, ThemeModule.Theme.size.comboPopupHeight)
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
        }

        background: Rectangle {
            color: ThemeModule.Theme.colors.panelStrong
            border.color: ThemeModule.Theme.colors.border
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
            color: parent.highlighted ? ThemeModule.Theme.colors.cyan : ThemeModule.Theme.colors.text
            font: control.font
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
        }

        background: Rectangle {
            color: parent.highlighted ? ThemeModule.Theme.colors.glass : "transparent"
            radius: ThemeModule.Theme.radius.sm
        }
    }
}
