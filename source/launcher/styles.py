from source.launcher.constants import COLORS, FONT_SIZES


def launcher_style_sheet():
    return f"""
        QWidget#AppRoot, QWidget#PageStack {{
            background: {COLORS["bg"]};
            color: {COLORS["text"]};
            font-family: Segoe UI;
        }}
        QFrame#TitleBar {{
            background: #03070C;
            border-bottom: 1px solid {COLORS["border"]};
        }}
        QLabel#ChromeTitle {{
            color: {COLORS["cyan"]};
            font-size: {FONT_SIZES["chrome_title"]}px;
            font-weight: 900;
            letter-spacing: 1px;
        }}
        QLabel#ChromeVersion, QLabel#SidebarMeta, QLabel#FooterLabel, QLabel#StatSubLabel {{
            color: {COLORS["muted"]};
            font-family: Consolas;
        }}
        QLabel#ChromeStatus, QLabel#SidebarReady {{
            color: {COLORS["green"]};
            font-family: Consolas;
            font-weight: 700;
        }}
        QPushButton#ChromeButton, QPushButton#ChromeCloseButton {{
            background: transparent;
            color: {COLORS["cyan"]};
            border: none;
            font-weight: 800;
        }}
        QPushButton#ChromeButton:hover {{
            background: rgba(0, 216, 255, 41);
        }}
        QPushButton#ChromeCloseButton:hover {{
            background: {COLORS["red"]};
            color: white;
        }}
        QFrame#Sidebar {{
            background: #050A10;
            border: none;
        }}
        QLabel#SidebarBrand {{
            color: {COLORS["text"]};
            font-size: {FONT_SIZES["sidebar_brand"]}px;
            font-weight: 900;
        }}
        QPushButton#NavButton {{
            min-height: 40px;
            text-align: left;
            padding-left: 18px;
            background: transparent;
            color: {COLORS["text"]};
            border: none;
            font-size: {FONT_SIZES["nav"]}px;
            font-weight: 800;
        }}
        QPushButton#NavButton:hover {{
            background: rgba(0, 216, 255, 20);
            border: none;
        }}
        QPushButton#NavButton:checked {{
            background: rgba(0, 216, 255, 41);
            color: {COLORS["cyan"]};
            border: none;
        }}
        QPushButton#MusicButton {{
            background: transparent;
            color: {COLORS["cyan"]};
            border: 1px solid rgba(0, 216, 255, 36);
            min-height: 32px;
        }}
        QFrame#Panel, QFrame#HeroBanner, QFrame#StepItem {{
            background: rgba(10, 16, 25, 235);
            border: 1px solid {COLORS["border"]};
        }}
        QLabel#PanelTitle, QLabel#PageTitle {{
            color: {COLORS["muted"]};
            font-size: {FONT_SIZES["panel_title"]}px;
            font-weight: 900;
        }}
        QLabel#PageTitle {{
            color: {COLORS["cyan"]};
            font-size: {FONT_SIZES["page_title"]}px;
        }}
        QLabel#WelcomeTitle {{
            color: {COLORS["cyan"]};
            font-size: {FONT_SIZES["welcome_title"]}px;
            font-weight: 900;
        }}
        QLabel#SectionHeading {{
            color: {COLORS["text"]};
            font-size: {FONT_SIZES["section_heading"]}px;
            font-weight: 900;
        }}
        QLabel#MutedCopy, QLabel#FormLabel {{
            color: {COLORS["muted"]};
        }}
        QLabel#StatLabel {{
            color: {COLORS["muted"]};
            font-size: {FONT_SIZES["stat_label"]}px;
            font-weight: 800;
        }}
        QLabel#StatValue {{
            color: {COLORS["text"]};
            font-size: {FONT_SIZES["stat_value"]}px;
            font-weight: 900;
        }}
        QLabel#FooterValue {{
            color: {COLORS["text"]};
            font-family: Consolas;
            font-size: {FONT_SIZES["footer"]}px;
            font-weight: 800;
        }}
        QTextEdit#Console {{
            background: #02060A;
            color: {COLORS["text"]};
            border: 1px solid rgba(0, 216, 255, 36);
            font-family: Consolas;
            font-size: {FONT_SIZES["console"]}px;
        }}
        QPushButton#PrimaryButton, QPushButton#SecondaryButton, QPushButton#DangerButton, QPushButton#GhostButton {{
            min-height: 34px;
            padding: 5px 16px;
            font-weight: 900;
        }}
        QPushButton#PrimaryButton {{
            background: rgba(0, 216, 255, 41);
            color: {COLORS["cyan"]};
            border: 1px solid rgba(0, 216, 255, 168);
        }}
        QPushButton#PrimaryButton:hover {{
            background: rgba(0, 216, 255, 66);
        }}
        QPushButton#SecondaryButton, QPushButton#GhostButton {{
            background: rgba(18, 28, 42, 140);
            color: {COLORS["text"]};
            border: 1px solid {COLORS["border"]};
        }}
        QPushButton#SecondaryButton:hover, QPushButton#GhostButton:hover {{
            color: {COLORS["cyan"]};
            border: 1px solid rgba(0, 216, 255, 128);
        }}
        QPushButton#DangerButton {{
            background: rgba(255, 77, 109, 31);
            color: {COLORS["red"]};
            border: 1px solid rgba(255, 77, 109, 148);
        }}
        QFrame#SettingsTabs {{
            background: #050A10;
            border-right: 1px solid {COLORS["border"]};
        }}
        QPushButton#SettingsTab {{
            min-height: 34px;
            text-align: left;
            padding-left: 10px;
            background: rgba(18, 28, 42, 89);
            color: {COLORS["text"]};
            border: 1px solid {COLORS["border"]};
        }}
        QPushButton#SettingsTab:checked {{
            background: rgba(0, 216, 255, 46);
            color: {COLORS["cyan"]};
        }}
        QLineEdit#SettingField {{
            min-height: 26px;
            background: #050A10;
            color: {COLORS["text"]};
            border: 1px solid {COLORS["border"]};
            padding: 2px 8px;
            font-family: Consolas;
        }}
        QFrame#InlineSwitchBox {{
            background: rgba(18, 28, 42, 90);
            border: 1px solid {COLORS["border"]};
        }}
        QCheckBox {{
            color: {COLORS["text"]};
        }}
        QLabel#StepNumber {{
            color: {COLORS["cyan"]};
            font-size: {FONT_SIZES["step_number"]}px;
            font-family: Consolas;
        }}
        QLabel#BadgeDone, QLabel#BadgeWarn, QLabel#BadgePending {{
            padding: 4px 9px;
            font-size: {FONT_SIZES["badge"]}px;
            font-weight: 900;
        }}
        QLabel#BadgeDone {{
            color: {COLORS["green"]};
            border: 1px solid rgba(107, 255, 158, 102);
        }}
        QLabel#BadgeWarn {{
            color: {COLORS["yellow"]};
            border: 1px solid rgba(255, 209, 102, 102);
        }}
        QLabel#BadgePending {{
            color: {COLORS["muted"]};
            border: 1px solid {COLORS["border"]};
        }}
        QLabel#UpdateIcon {{
            color: {COLORS["cyan"]};
            font-size: {FONT_SIZES["update_icon"]}px;
        }}
        QLabel#UpdateLatest {{
            color: {COLORS["green"]};
            font-size: {FONT_SIZES["section_heading"]}px;
            font-weight: 800;
        }}
        QLabel#AboutTitle {{
            color: {COLORS["text"]};
            font-size: {FONT_SIZES["about_title"]}px;
            font-weight: 900;
        }}
        QScrollArea#SettingsScroll {{
            background: transparent;
            border: none;
        }}
        QScrollBar:vertical {{
            background: #050A10;
            width: 10px;
        }}
        QScrollBar::handle:vertical {{
            background: {COLORS["border"]};
            min-height: 24px;
        }}
        """
