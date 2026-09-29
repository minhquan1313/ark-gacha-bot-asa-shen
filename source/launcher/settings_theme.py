"""Scoped presentation tokens for the approved Server and Stations settings."""

from source.launcher.dashboard_theme import PALETTE

CONTROL_HEIGHT = 44
SECTION_HEADER_HEIGHT = 104
BREADCRUMB_HEIGHT = 112
BREADCRUMB_WRAPPED_HEIGHT = 174
SECTION_CARD_RADIUS = 11
BREADCRUMB_RADIUS = 8
BREADCRUMB_LIP_DEPTH = 12
CARD_PADDING = 16
CARD_SPACING = 16
ENTRY_ROW_PADDING_Y = 10
ENTRY_ROW_GAP = 8

# Side-card tint strength (0..1). Restart the app after adjusting these values.
GACHA_TINT_MAX_OPACITY = 0.12
# Logical pixels from the arrow edge toward the tinted edge; negative starts earlier.
GACHA_TINT_START_OFFSET_PX = 0


def settings_style():
    """Style only the new Settings shell and approved content widgets."""
    return f"""
        QWidget#SettingsPage {{ background: {PALETTE["background"]}; }}
        QFrame#SettingsShell {{ background: transparent; border: none; }}
        QFrame#SettingsTabs {{ background: #030F18; border: 1px solid #086582; border-radius: 9px; }}
        QFrame#SettingsBottomBar {{ background: #03111B; border: 1px solid #087C9A; border-radius: 10px; }}
        QLabel#SettingsSaveHint {{ color: {PALETTE["secondary"]}; font-family: 'Segoe UI'; font-size: 12px; }}
        QFrame#SettingsBreadcrumb QLabel {{ background: transparent; border: none; color: {PALETTE["secondary"]}; font-family: 'Segoe UI'; font-size: 14px; }}
        QFrame#SettingsBreadcrumb QLabel#SettingsBreadcrumbTitle {{ color: {PALETTE["cyan"]}; font-size: 23px; font-weight: 700; }}
        QFrame#SettingsBreadcrumb QLabel#SettingsProfileCaption {{ color: {PALETTE["text"]}; font-size: 11px; font-weight: 700; }}
        {dropdown_style("QFrame#SettingsBreadcrumb QComboBox")}
        QComboBox#GachaDestination {{
            background: #051A29; color: {PALETTE["text"]}; border: 1px solid #00A2C6;
            border-radius: 6px; padding: 0 28px 0 12px; font-family: 'Segoe UI'; font-size: 14px; font-weight: 400;
            min-height: {CONTROL_HEIGHT - 2}px; max-height: {CONTROL_HEIGHT - 2}px;
        }}
        QComboBox#GachaDestination:hover, QComboBox#GachaDestination:focus {{ background: #0B3046; border-color: #13E7FF; }}
        QComboBox#GachaDestination:disabled {{ color: #567387; border-color: #184054; background: #05131D; }}
        QComboBox#GachaDestination::down-arrow {{ image: none; width: 0; height: 0; }}
        QComboBox#GachaDestination::drop-down {{ border: none; width: 26px; }}
        QComboBox#GachaDestination QAbstractItemView {{
            background: #061923; color: {PALETTE["text"]}; selection-background-color: #075472;
            border: 1px solid #087C9A; padding: 6px;
            font-family: 'Segoe UI'; font-size: 14px; font-weight: 400;
        }}
        QComboBox#GachaDestination[invalidDestination="true"] {{ border-color: #FF4677; }}
        QFrame#SettingsBreadcrumb QComboBox#MissingTemplateSelector {{ border-color: #FFD166; }}
        QFrame#SettingsBreadcrumb QComboBox#ActiveTemplateSelector {{ border-color: #27F5B0; }}
        QWidget#ApprovedSettingsContent {{ background: transparent; }}
        QWidget#ApprovedSettingsContent QLabel {{ background: transparent; border: none; color: {PALETTE["secondary"]}; font-family: 'Segoe UI'; font-size: 12px; }}
        QWidget#ApprovedSettingsContent QLabel[settingsRole="title"] {{ color: {PALETTE["cyan"]}; font-size: 21px; font-weight: 600; }}
        QWidget#ApprovedSettingsContent QLabel[settingsRole="subtitle"] {{ color: {PALETTE["secondary"]}; font-size: 14px; }}
        QWidget#ApprovedSettingsContent QLabel[settingsRole="label"] {{ color: #C9E7F6; font-size: 15px; font-weight: 600; }}
        QWidget#ApprovedSettingsContent QLineEdit {{
            background: #020E17; border: 1px solid #155875; border-radius: 5px;
            padding: 0 12px; color: {PALETTE["text"]}; font-family: 'Segoe UI'; font-size: 15px;
            min-height: {CONTROL_HEIGHT - 2}px; max-height: {CONTROL_HEIGHT - 2}px;
        }}
        QWidget#ApprovedSettingsContent QLineEdit:focus {{ border-color: #13E7FF; background: #051B29; }}
        QWidget#ApprovedSettingsContent QLineEdit:disabled {{ color: #8EBDCC; border-color: #23566A; }}
        QWidget#ApprovedSettingsContent QCheckBox#AutoKeysSupportedAction {{ color: #00D9FF; font-family: 'Segoe UI'; font-size: 15px; font-weight: 600; }}
        QWidget#ApprovedSettingsContent QFrame#SettingsEntryRow {{ background: #04111A; border: none; border-bottom: 1px solid #14516A; }}
        QWidget#ApprovedSettingsContent QLabel[settingsRole="dediSection"] {{ color: {PALETTE["cyan"]}; font-size: 18px; font-weight: 700; }}
        QWidget#ApprovedSettingsContent QFrame#DediSummaryMetadata {{ background: transparent; border: none; }}
        QWidget#ApprovedSettingsContent QFrame#CraftCrafter {{ background: transparent; border: none; }}
        QWidget#ApprovedSettingsContent QFrame#DediPointRow {{ background: #04111A; border: none; }}
        QWidget#ApprovedSettingsContent QFrame#CraftCrafter QFrame#DediPointRow {{ background: transparent; }}
        QWidget#ApprovedSettingsContent QFrame#DediGrinderCard {{ background: #061923; border: 1px solid #167691; border-left: 3px solid #00D9FF; border-radius: 6px; }}
        QWidget#ApprovedSettingsContent QFrame#DediRouteEditor {{ background: #03111B; border: 1px solid #14516A; border-radius: 6px; }}
        QScrollArea#SettingsEntryScroll {{ background: transparent; border: none; }}
        QScrollArea#SettingsEntryScroll QScrollBar:horizontal {{ background: #03111B; height: 8px; margin: 0; border: none; }}
        QScrollArea#SettingsEntryScroll QScrollBar::handle:horizontal {{ background: #155875; min-width: 24px; border-radius: 4px; }}
        QScrollArea#SettingsEntryScroll QScrollBar::handle:horizontal:hover {{ background: #00D9FF; }}
        QScrollArea#SettingsEntryScroll QScrollBar::add-line:horizontal,
        QScrollArea#SettingsEntryScroll QScrollBar::sub-line:horizontal {{ width: 0; border: none; background: transparent; }}
        QScrollArea#SettingsEntryScroll QScrollBar::add-page:horizontal,
        QScrollArea#SettingsEntryScroll QScrollBar::sub-page:horizontal {{ background: transparent; }}
        QWidget#ApprovedSettingsContent QFrame#SettingsDivider {{ color: #12506A; background: transparent; border: none; }}
        QWidget#ApprovedSettingsContent QFrame#CraftSettingsDivider {{ background: #12506A; border: none; margin-top: 8px; margin-bottom: 8px; }}
        QWidget#ApprovedSettingsContent QLabel#AutoKeysWarning {{ color: #FFD166; }}
        QWidget#ApprovedSettingsContent QFrame#TemplateFieldActive,
        QWidget#ApprovedSettingsContent QFrame#TemplateFieldMissing {{ background: transparent; border: none; padding: 0; }}
        QWidget#ApprovedSettingsContent QLabel#TemplateTick {{ color: #27F5B0; }}
        QWidget#ApprovedSettingsContent QLabel#TemplateWarning {{ color: #FFD166; }}
        QFrame#ServerInformation {{ background: #031722; border: 1px solid #12506A; border-radius: 8px; }}
    """


def dropdown_style(selector: str = "QComboBox"):
    """Share the profile selector surface, native popup, and interaction styling."""
    return f"""
        {selector} {{
            background: #051A29; color: {PALETTE["text"]}; border: 1px solid #00A2C6;
            border-radius: 6px; padding: 0 28px 0 12px; font-family: 'Segoe UI'; font-size: 14px; font-weight: 400;
            min-height: {CONTROL_HEIGHT - 2}px; max-height: {CONTROL_HEIGHT - 2}px;
        }}
        {selector}:hover, {selector}:focus {{ background: #0B3046; border-color: #13E7FF; }}
        {selector}:disabled {{ color: #567387; border-color: #184054; background: #05131D; }}
        {selector}::down-arrow {{ image: none; width: 0; height: 0; }}
        {selector}::drop-down {{ border: none; width: 26px; }}
        {selector} QAbstractItemView {{
            background: #061923; color: {PALETTE["text"]}; selection-background-color: #075472;
            border: 1px solid #087C9A; padding: 6px;
            font-family: 'Segoe UI'; font-size: 14px; font-weight: 400;
        }}
    """
