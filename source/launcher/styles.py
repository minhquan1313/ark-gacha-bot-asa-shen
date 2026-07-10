from source.launcher.config.constants import (
    COLORS,
    FONT_SIZES,
    UI_COLORS,
    UI_FONTS,
    UI_METRICS,
)


def launcher_style_sheet():
    return f"""
        QWidget#AppRoot, QWidget#PageStack {{
            background: {COLORS["bg"]};
            color: {COLORS["text"]};
            font-family: {UI_FONTS["body"]};
        }}
        QWidget#AppRoot {{
            border-radius: {UI_METRICS["window_radius"]}px;
        }}
        QFrame#TitleBar {{
            background: #03070C;
            border-bottom: 1px solid {UI_COLORS["border_soft"]};
            border-top-left-radius: {UI_METRICS["window_radius"]}px;
            border-top-right-radius: {UI_METRICS["window_radius"]}px;
        }}
        QLabel#ChromeTitle {{
            color: {COLORS["cyan"]};
            font-family: {UI_FONTS["display"]};
            font-size: {FONT_SIZES["chrome_title"]}px;
            font-weight: 900;
            letter-spacing: 1px;
        }}
        QLabel#ChromeVersion, QLabel#SidebarMeta, QLabel#FooterLabel, QLabel#StatSubLabel {{
            color: {COLORS["muted"]};
            font-family: {UI_FONTS["mono"]};
        }}
        QLabel#ChromeStatus, QLabel#SidebarReady {{
            color: {COLORS["green"]};
            font-family: {UI_FONTS["mono"]};
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
            font-family: {UI_FONTS["display"]};
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
        QFrame#Panel, QFrame#HeroBanner, QFrame#StepItem {{
            background: {UI_COLORS["panel_bg"]};
            border: 1px solid {UI_COLORS["border_soft"]};
            border-radius: {UI_METRICS["radius_lg"]}px;
        }}
        QLabel#PanelTitle, QLabel#PageTitle {{
            color: {COLORS["muted"]};
            font-family: {UI_FONTS["display"]};
            font-size: {FONT_SIZES["panel_title"]}px;
            font-weight: 900;
        }}
        QLabel#PageTitle {{
            color: {COLORS["cyan"]};
            font-size: {FONT_SIZES["page_title"]}px;
        }}
        QLabel#WelcomeTitle {{
            color: {COLORS["cyan"]};
            font-family: {UI_FONTS["display"]};
            font-size: {FONT_SIZES["welcome_title"]}px;
            font-weight: 900;
        }}
        QLabel#SectionHeading {{
            color: {COLORS["text"]};
            font-family: {UI_FONTS["display"]};
            font-size: {FONT_SIZES["section_heading"]}px;
            font-weight: 900;
        }}
        QLabel#MutedCopy, QLabel#FormLabel {{
            color: {COLORS["muted"]};
        }}
        QLabel#SettingsDividerLabel {{
            color: {COLORS["cyan"]};
            font-family: {UI_FONTS["display"]};
            font-size: {FONT_SIZES["stat_label"]}px;
            font-weight: 900;
        }}
        QFrame#SettingsDividerLine {{
            background: {COLORS["border"]};
            border: none;
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
            font-family: {UI_FONTS["mono"]};
            font-size: {FONT_SIZES["footer"]}px;
            font-weight: 800;
        }}
        QTextEdit#Console {{
            background: #02060A;
            color: {COLORS["text"]};
            border: none;
            border-radius: {UI_METRICS["radius_md"]}px;
            font-family: {UI_FONTS["mono"]};
            font-size: {FONT_SIZES["console"]}px;
        }}
        QFrame#ConsolePanel {{
            background: #02060A;
            border: none;
            border-radius: {UI_METRICS["radius_lg"]}px;
        }}
        QFrame#ConsoleOverlay {{
            background: #02060A;
            border: none;
        }}
        QPushButton#PrimaryButton, QPushButton#SecondaryButton, QPushButton#DangerButton, QPushButton#GhostButton {{
            min-height: {UI_METRICS["control_height"]}px;
            padding: 5px 16px;
            font-weight: 900;
        }}
        QPushButton#PrimaryButton {{
            background: rgba(0, 216, 255, 41);
            color: {COLORS["cyan"]};
            border: 1px solid rgba(0, 216, 255, 168);
            border-radius: {UI_METRICS["radius_sm"]}px;
        }}
        QPushButton#PrimaryButton:hover {{
            background: rgba(0, 216, 255, 66);
        }}
        QPushButton#SecondaryButton, QPushButton#GhostButton {{
            background: rgba(18, 28, 42, 140);
            color: {COLORS["text"]};
            border: 1px solid {UI_COLORS["border_soft"]};
            border-radius: {UI_METRICS["radius_sm"]}px;
        }}
        QPushButton#SecondaryButton:hover, QPushButton#GhostButton:hover {{
            color: {COLORS["cyan"]};
            border: 1px solid rgba(0, 216, 255, 128);
        }}
        QPushButton#DangerButton {{
            background: rgba(255, 77, 109, 31);
            color: {COLORS["red"]};
            border: 1px solid rgba(255, 77, 109, 148);
            border-radius: {UI_METRICS["radius_sm"]}px;
        }}
        QFrame#SettingsShell {{
            background: {UI_COLORS["panel_bg"]};
            border: 1px solid {UI_COLORS["border_soft"]};
            border-radius: {UI_METRICS["radius_lg"]}px;
        }}
        QFrame#SettingsTabs {{
            background: #050A10;
            border-right: 1px solid {UI_COLORS["border_soft"]};
            border-top-left-radius: {UI_METRICS["radius_lg"]}px;
        }}
        QScrollArea#SettingsScroll {{
            background: transparent;
            border: none;
            border-top-right-radius: {UI_METRICS["radius_lg"]}px;
        }}
        QScrollArea#SettingsScroll > QWidget,
        QScrollArea#SettingsScroll QWidget#HelperScrollContent {{
            background: transparent;
            border: none;
        }}
        QWidget#SettingsForm {{
            background: transparent;
            border-top-right-radius: {UI_METRICS["radius_lg"]}px;
        }}
        QPushButton#SettingsTab {{
            min-height: 36px;
            text-align: left;
            padding-left: 12px;
            background: rgba(18, 28, 42, 70);
            color: {COLORS["text"]};
            border: 1px solid {UI_COLORS["border_soft"]};
            border-radius: {UI_METRICS["radius_sm"]}px;
        }}
        QPushButton#SettingsTab:hover {{
            background: rgba(0, 216, 255, 25);
            border: 1px solid rgba(0, 216, 255, 90);
        }}
        QPushButton#SettingsTab:checked {{
            background: rgba(0, 216, 255, 54);
            color: {COLORS["cyan"]};
            border: 1px solid rgba(0, 216, 255, 125);
        }}
        QFrame#SettingsFooter {{
            background: rgba(3, 7, 12, 225);
            border-top: 1px solid {UI_COLORS["border_soft"]};
            border-bottom-left-radius: {UI_METRICS["radius_lg"]}px;
            border-bottom-right-radius: {UI_METRICS["radius_lg"]}px;
        }}
        QLabel#SettingsFooterHint {{
            color: {COLORS["muted"]};
            font-family: {UI_FONTS["mono"]};
            font-size: {FONT_SIZES["footer"]}px;
        }}
        QToolButton#TemplateActionSplitButton {{
            min-height: {UI_METRICS["control_height"]}px;
            max-height: {UI_METRICS["control_height"]}px;
            min-width: 112px;
            padding: {UI_METRICS["split_button_padding"]};
            background: rgba(10, 36, 49, 190);
            color: {COLORS["text"]};
            border: 1px solid rgba(0, 216, 255, 150);
            border-radius: {UI_METRICS["radius_sm"]}px;
            font-weight: 900;
        }}
        QToolButton#TemplateActionSplitButton:hover {{
            color: {COLORS["cyan"]};
            border: 1px solid {COLORS["cyan"]};
            background: rgba(14, 58, 77, 210);
        }}
        QToolButton#TemplateActionSplitButton::menu-button {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 28px;
            border-left: 1px solid rgba(0, 216, 255, 120);
            border-top-right-radius: {UI_METRICS["radius_sm"]}px;
            border-bottom-right-radius: {UI_METRICS["radius_sm"]}px;
        }}
        QToolButton#TemplateActionSplitButton::menu-arrow {{
            width: 8px;
            height: 8px;
        }}
        QMenu#TemplateActionMenu {{
            background: #050B12;
            color: {COLORS["text"]};
            border: 1px solid rgba(0, 216, 255, 150);
            padding: {UI_METRICS["menu_padding"]};
        }}
        QMenu#TemplateActionMenu::item {{
            min-width: 190px;
            padding: {UI_METRICS["menu_item_padding"]};
            font-weight: 800;
        }}
        QMenu#TemplateActionMenu::item:selected {{
            background: rgba(0, 216, 255, 45);
            color: {COLORS["cyan"]};
        }}
        QComboBox#TemplateSelector, QComboBox#ActiveTemplateSelector, QComboBox#MissingTemplateSelector {{
            min-height: {UI_METRICS["control_height"]}px;
            background: {UI_COLORS["field_bg"]};
            color: {COLORS["text"]};
            border: 1px solid {UI_COLORS["border_soft"]};
            border-radius: {UI_METRICS["radius_sm"]}px;
            padding: {UI_METRICS["combo_padding"]};
            font-family: {UI_FONTS["mono"]};
        }}
        QComboBox#TemplateSelector::drop-down,
        QComboBox#ActiveTemplateSelector::drop-down,
        QComboBox#MissingTemplateSelector::drop-down,
        QComboBox#HelperCombo::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 28px;
            border-left: 1px solid {UI_COLORS["border_soft"]};
            border-top-right-radius: {UI_METRICS["radius_sm"]}px;
            border-bottom-right-radius: {UI_METRICS["radius_sm"]}px;
        }}
        QComboBox#TemplateSelector:hover {{
            border: 1px solid {COLORS["cyan"]};
        }}
        QComboBox#ActiveTemplateSelector {{
            color: {COLORS["green"]};
            border: 1px solid {COLORS["green"]};
        }}
        QComboBox#MissingTemplateSelector {{
            color: {COLORS["red"]};
            border: 1px solid {COLORS["red"]};
        }}
        QFrame#TemplateFieldActive {{
            background: rgba(107, 255, 158, 12);
            border: 1px solid {COLORS["green"]};
        }}
        QFrame#TemplateFieldMissing {{
            background: rgba(255, 77, 109, 12);
            border: 1px solid {COLORS["red"]};
        }}
        QFrame#TemplateFieldActive QLineEdit#SettingField {{
            border: 1px solid {COLORS["green"]};
        }}
        QFrame#TemplateFieldMissing QLineEdit#SettingField {{
            border: 1px solid {COLORS["red"]};
        }}
        QLabel#TemplateTick {{
            color: {COLORS["green"]};
            font-weight: 900;
        }}
        QLabel#TemplateWarning {{
            color: {COLORS["red"]};
            font-weight: 900;
        }}
        QWidget#TemplateGroupActive {{
            border: 1px solid {COLORS["green"]};
        }}
        QWidget#TemplateGroupMissing {{
            border: 1px solid {COLORS["red"]};
        }}
        QLineEdit#SettingField {{
            min-height: {UI_METRICS["control_height"]}px;
            background: {UI_COLORS["field_bg"]};
            color: {COLORS["text"]};
            border: 1px solid {UI_COLORS["border_soft"]};
            border-radius: {UI_METRICS["radius_sm"]}px;
            padding: {UI_METRICS["control_padding"]};
            font-family: {UI_FONTS["mono"]};
        }}
        QFrame#InlineSwitchBox {{
            background: {UI_COLORS["panel_bg_soft"]};
            border: 1px solid {UI_COLORS["border_soft"]};
            border-radius: {UI_METRICS["radius_md"]}px;
        }}
        QFrame#DepositRouteCard {{
            background: rgba(18, 28, 42, 90);
            border: 1px solid {UI_COLORS["border_soft"]};
            border-radius: {UI_METRICS["radius_lg"]}px;
        }}
        QFrame#HelperPanel {{
            background: {UI_COLORS["panel_bg_soft"]};
            border: none;
            border-radius: {UI_METRICS["radius_lg"]}px;
        }}
        QFrame#StationConfigWarningCard {{
            background: rgba(18, 28, 42, 90);
            border: 1px solid rgba(255, 209, 102, 190);
            border-radius: {UI_METRICS["radius_lg"]}px;
        }}
        QWidget#DepositHelperWindow, QDialog#DepositHelperGuide {{
            background: transparent;
            color: {COLORS["text"]};
            border: none;
            border-radius: {UI_METRICS["radius_lg"]}px;
        }}
        QFrame#DepositHelperWindow {{
            background: transparent;
            border: none;
            border-radius: {UI_METRICS["radius_lg"]}px;
        }}
        QWidget#HelperBody {{
            background: transparent;
            border: none;
        }}
        QFrame#HelperHeader {{
            min-height: 40px;
            background: #03070C;
            border-bottom: 1px solid {UI_COLORS["border_soft"]};
            border-top-left-radius: {UI_METRICS["radius_lg"]}px;
            border-top-right-radius: {UI_METRICS["radius_lg"]}px;
        }}
        QLabel#HelperTitle {{
            color: {COLORS["text"]};
            font-family: {UI_FONTS["display"]};
            font-size: {FONT_SIZES["section_heading"]}px;
            font-weight: 900;
            padding-left: 0;
        }}
        QLabel#HelperHint, QLabel#HelperStatus {{
            color: {COLORS["muted"]};
            font-family: {UI_FONTS["mono"]};
        }}
        QLabel#HelperSectionLabel {{
            color: {COLORS["muted"]};
            font-weight: 900;
            font-size: {FONT_SIZES["form"]}px;
            padding: 6px 0 0 0;
        }}
        QWidget#HelperGuidePage {{
            background: transparent;
        }}
        QLabel#HelperGuideImage {{
            background: rgba(18, 28, 42, 120);
            border: 1px solid {UI_COLORS["border_soft"]};
            border-radius: {UI_METRICS["radius_md"]}px;
        }}
        QLabel#HelperGuideStepTitle {{
            color: {COLORS["cyan"]};
            font-weight: 900;
            font-size: {FONT_SIZES["panel_title"]}px;
        }}
        QScrollArea#HelperScroll {{
            background: transparent;
            border: none;
        }}
        QWidget#HelperScrollContent {{
            background: transparent;
        }}
        QFrame#HelperRow {{
            background: {UI_COLORS["helper_row_bg"]};
            border: 1px solid {UI_COLORS["border_soft"]};
            border-radius: {UI_METRICS["radius_md"]}px;
        }}
        QFrame#HelperAddCaptureRow {{
            background: {UI_COLORS["helper_details_bg"]};
            border: 1px dashed {UI_COLORS["border_active"]};
            border-radius: {UI_METRICS["radius_md"]}px;
        }}
        QWidget#HelperRowDetails {{
            background: {UI_COLORS["helper_details_bg"]};
            border: 1px solid {UI_COLORS["border_soft"]};
            border-radius: {UI_METRICS["radius_sm"]}px;
        }}
        QLabel#HelperRowSummary {{
            color: {COLORS["text"]};
            font-family: {UI_FONTS["mono"]};
            font-weight: 700;
        }}
        QPushButton#HelperIconButton {{
            min-height: {UI_METRICS["control_height"]}px;
            min-width: {UI_METRICS["icon_button_width"]}px;
            padding: {UI_METRICS["icon_padding"]};
            font-family: {UI_FONTS["body"]};
            font-weight: 900;
            border-radius: {UI_METRICS["radius_sm"]}px;
        }}
        QPushButton#HelperExpandButton {{
            min-height: {UI_METRICS["helper_expand_height"]}px;
            max-height: {UI_METRICS["helper_expand_height"] + 2}px;
            min-width: {UI_METRICS["helper_expand_width"]}px;
            max-width: {UI_METRICS["helper_expand_width"] + 2}px;
            padding: 0px;
            font-family: {UI_FONTS["mono"]};
            font-weight: 900;
            border-radius: {UI_METRICS["radius_sm"]}px;
        }}
        QComboBox#HelperCombo {{
            min-height: {UI_METRICS["control_height"]}px;
            background: {UI_COLORS["field_bg"]};
            color: {COLORS["text"]};
            border: 1px solid {UI_COLORS["border_soft"]};
            border-radius: {UI_METRICS["radius_sm"]}px;
            padding: {UI_METRICS["combo_padding"]};
            font-family: {UI_FONTS["mono"]};
        }}
        QComboBox#HelperCombo QAbstractItemView {{
            background: #050A10;
            color: {COLORS["text"]};
            selection-background-color: rgba(0, 216, 255, 46);
            border: 1px solid {UI_COLORS["border_soft"]};
        }}
        QComboBox#HelperCombo QAbstractItemView::item {{
            min-height: {UI_METRICS["control_height"]}px;
            padding: {UI_METRICS["control_padding"]};
        }}
        QLabel#ToolCoverCopy {{
            color: {COLORS["text"]};
            font-family: {UI_FONTS["display"]};
            font-size: {FONT_SIZES["panel_title"]}px;
            font-weight: 900;
            background: transparent;
        }}
        QCheckBox {{
            color: {COLORS["text"]};
        }}
        QLabel#StepNumber {{
            color: {COLORS["cyan"]};
            font-size: {FONT_SIZES["step_number"]}px;
            font-family: {UI_FONTS["mono"]};
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
            font-family: {UI_FONTS["display"]};
            font-size: {FONT_SIZES["about_title"]}px;
            font-weight: 900;
        }}
        QScrollArea#SettingsScroll {{
            background: rgba(5, 10, 16, 110);
            border: none;
        }}
        QWidget#SettingsForm {{
            background: rgba(5, 10, 16, 110);
        }}
        QScrollBar:vertical {{
            background: #050A10;
            width: 10px;
        }}
        QScrollBar::handle:vertical {{
            background: {COLORS["border"]};
            min-height: 24px;
            border-radius: 5px;
        }}
        """
