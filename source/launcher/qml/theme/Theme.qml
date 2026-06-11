pragma Singleton

import QtQuick

QtObject {
    readonly property QtObject colors: QtObject {
        readonly property color bg: "#070A0F"
        readonly property color panel: "#0A1019"
        readonly property color panelStrong: "#03070C"
        readonly property color panelSoft: "#101C2B"
        readonly property color glass: "#8C121C2A"
        readonly property color cyan: "#00D8FF"
        readonly property color blue: "#2F80FF"
        readonly property color green: "#6BFF9E"
        readonly property color yellow: "#FFD166"
        readonly property color red: "#FF4D6D"
        readonly property color text: "#F4F8FF"
        readonly property color muted: "#8EA3B8"
        readonly property color dim: "#5F7285"
        readonly property color border: "#16465A"
        readonly property color borderSoft: "#2E78DCFF"
        readonly property color borderActive: "#8C00D8FF"
    }

    readonly property QtObject spacing: QtObject {
        readonly property int xxs: 2
        readonly property int xs: 4
        readonly property int sm: 8
        readonly property int md: 12
        readonly property int lg: 16
        readonly property int xl: 22
        readonly property int xxl: 28
    }

    readonly property QtObject radius: QtObject {
        readonly property int sm: 4
        readonly property int md: 8
        readonly property int lg: 12
        readonly property int panel: 6
    }

    readonly property QtObject border: QtObject {
        readonly property int thin: 1
        readonly property int active: 2
    }

    readonly property QtObject size: QtObject {
        readonly property int minimumWidth: 420
        readonly property int minimumHeight: 640
        readonly property int defaultWidth: 1200
        readonly property int defaultHeight: 800
        readonly property int titleBarHeight: 42
        readonly property int sidebarWidth: 190
        readonly property int sidebarNarrowWidth: 96
        readonly property int breakpointNarrow: 720
        readonly property int buttonHeight: 34
        readonly property int iconButton: 36
        readonly property int heroHeight: 180
        readonly property int helperWidth: 280
        readonly property int helperHeight: 180
        readonly property int overlayWidth: 240
        readonly property int statCardHeight: 96
        readonly property int quickActionsWidth: 260
        readonly property int settingsTabsWidth: 240
        readonly property int settingsLabelWidth: 190
        readonly property int toolCardHeight: 160
        readonly property int contentCardWidth: 460
        readonly property int logoLarge: 110
        readonly property int transferHelperWidth: 520
        readonly property int dialogWidth: 430
        readonly property int switchKnob: 14
    }

    readonly property QtObject fonts: QtObject {
        readonly property string display: "Segoe UI"
        readonly property string body: "Segoe UI"
        readonly property string mono: "Consolas"
        readonly property int chromeTitle: 21
        readonly property int nav: 12
        readonly property int panelTitle: 12
        readonly property int pageTitle: 14
        readonly property int welcomeTitle: 30
        readonly property int sectionHeading: 16
        readonly property int statLabel: 11
        readonly property int statValue: 24
        readonly property int footer: 12
        readonly property int consoleText: 11
        readonly property int formText: 11
        readonly property int buttonText: 11
    }

    readonly property QtObject motion: QtObject {
        readonly property int fast: 120
        readonly property int normal: 220
        readonly property int slow: 600
    }
}
