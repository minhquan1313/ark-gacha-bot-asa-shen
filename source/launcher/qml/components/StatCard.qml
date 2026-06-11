import QtQuick
import QtQuick.Layouts
import "../theme" as ThemeModule

Panel {
    id: card

    property string label: ""
    property string value: "0"
    property string sublabel: ""

    implicitHeight: ThemeModule.Theme.size.statCardHeight

    Item {
        Layout.fillWidth: true
        Layout.fillHeight: true

        Column {
            anchors.centerIn: parent
            spacing: ThemeModule.Theme.spacing.xs

            Text {
                text: card.label
                color: ThemeModule.Theme.colors.muted
                font.pixelSize: ThemeModule.Theme.fonts.statLabel
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                width: parent.width
            }
            Text {
                text: card.value
                color: ThemeModule.Theme.colors.text
                font.pixelSize: ThemeModule.Theme.fonts.statValue
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                width: parent.width
            }
            Text {
                text: card.sublabel
                color: ThemeModule.Theme.colors.muted
                font.family: ThemeModule.Theme.fonts.mono
                font.pixelSize: ThemeModule.Theme.fonts.footer
                horizontalAlignment: Text.AlignHCenter
                width: parent.width
            }
        }
    }
}
