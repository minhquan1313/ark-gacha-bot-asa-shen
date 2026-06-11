import QtQuick
import "../theme" as ThemeModule

BaseHelperWindow {
    width: ThemeModule.Theme.size.transferHelperWidth
    minimumWidth: ThemeModule.Theme.size.transferHelperWidth
    helperTitle: "SERVER TRANSFER HELPER"
    helperBody: "QML helper shell for transfer setup. Existing transfer runtime modules remain available while the detailed form is migrated to models."
}
