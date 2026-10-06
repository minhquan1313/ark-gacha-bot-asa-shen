"""Dashboard and shell tokens, deliberately separate from the other pages."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PALETTE = {
    "background": "#02080E",
    "panel": "#06131C",
    "panel_alt": "#071923",
    "cyan": "#00D9FF",
    "bright": "#13E7FF",
    "muted": "#4A8EAF",
    "text": "#F4F7FA",
    "secondary": "#9ABBD0",
    "border": "#135773",
    "success": "#27F5B0",
    "danger": "#FF4D6D",
}


def asset_path(relative: str):
    """Resolve bundled artwork independently of the working directory."""
    return str(ROOT / relative)


def dashboard_style(scale: float):
    """Return styles inherited only by the dashboard content."""

    def px(size: float):
        """Keep small labels readable at the baseline window size."""
        return max(10, round(size * scale))

    return f"""
        QWidget#DashboardPage {{ background: {PALETTE["background"]}; }}
        QWidget#DashboardPage QLabel {{
            background: transparent; border: none; color: {PALETTE["text"]};
            font-family: 'Segoe UI'; font-size: {px(14)}px;
        }}
        QWidget#DashboardPage QLabel[role="muted"] {{ color: {PALETTE["secondary"]}; }}
        QWidget#DashboardPage QLabel[role="eyebrow"] {{
            color: {PALETTE["cyan"]}; font-size: {px(27)}px; font-weight: 800;
        }}
        QWidget#DashboardPage QLabel[role="heroTitle"] {{
            font-size: {px(53)}px; font-weight: 900;
        }}
        QWidget#DashboardPage QLabel[role="subtitle"] {{
            color: {PALETTE["secondary"]}; font-size: {px(12)}px; letter-spacing: 2px;
        }}
        QWidget#DashboardPage QLabel[role="section"] {{ font-size: {px(18)}px; font-weight: 700; }}
        QWidget#DashboardPage QLabel[role="statLabel"] {{
            color: {PALETTE["secondary"]}; font-size: {px(14)}px; letter-spacing: 0.5px;
        }}
        QWidget#DashboardPage QLabel[role="statValue"] {{ font-size: {px(38)}px; font-weight: 800; }}
        QWidget#DashboardPage QLabel[role="timeValue"] {{ font-size: {px(32)}px; font-weight: 800; }}
        QWidget#DashboardPage QLabel[role="metricValue"] {{ font-size: {px(16)}px; font-weight: 700; }}
        QWidget#DashboardPage QLabel[role="percent"] {{ color: {PALETTE["cyan"]}; font-weight: 700; }}
        QWidget#DashboardPage QLabel[role="footer"] {{
            color: {PALETTE["muted"]}; font-size: {px(11)}px; letter-spacing: 1px;
        }}
        QWidget#DashboardPage QCheckBox {{ color: {PALETTE["text"]}; font-size: {px(16)}px; }}
        QWidget#DashboardPage QTextEdit#Console {{
            background: #010A11; border: none; border-radius: 4px;
            color: {PALETTE["text"]}; font-family: Consolas;
            font-size: {px(14)}px; padding: 7px; selection-background-color: #145775;
        }}
        QWidget#DashboardPage QFrame#InlineSwitchBox {{
            background: #071522; border: 1px solid {PALETTE["border"]}; border-radius: 8px;
        }}
        QWidget#DashboardPage QFrame#ConsoleDivider {{ background: {PALETTE["border"]}; border: none; }}
    """


def shell_style(scale: float):
    """Style only the launcher shell, leaving page content selectors untouched."""
    return f"""
        QWidget#AppRoot {{ background: {PALETTE["background"]}; }}
        QFrame#TitleBar {{ background: #020D16; border-bottom: 1px solid #057291; }}
        QFrame#Sidebar {{ background: #030E17; border-right: 1px solid #10435A; }}
        QLabel#ChromeTitle {{ font-size: {round(24 * scale)}px; color: {PALETTE["cyan"]}; }}
        QLabel#ChromeVersion, QLabel#ChromeStatus {{ font-size: {round(14 * scale)}px; }}
        QLabel#SidebarBrand {{ font-size: {round(26 * scale)}px; }}
        QLabel#SidebarTagline {{ color: {PALETTE["secondary"]}; font-size: {max(9, round(11 * scale))}px; letter-spacing: 1px; }}
        QLabel#SidebarMeta, QLabel#SidebarReady {{ font-size: {max(10, round(12 * scale))}px; }}
        QLabel#SidebarCopyright {{ color: {PALETTE["muted"]}; font-size: {max(9, round(12 * scale))}px; letter-spacing: 1px; }}
    """


def button_style(variant: str, scale: float, compact: bool = False):
    """Provide all dashboard button states from a single style definition."""
    primary = variant == "primary"
    nav = variant == "nav"
    danger = variant == "danger"
    fg = "#00121E" if primary else PALETTE["danger"] if danger else PALETTE["secondary"]
    border = PALETTE["cyan"] if primary else PALETTE["danger"] if danger else PALETTE["border"]
    bg = "qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #11EDFF,stop:0.55 #00C8F4,stop:1 #0097DA)" if primary else "qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #092334,stop:1 #06111D)"
    size = round((16 if nav else 12 if compact else 21 if primary else 14) * scale)
    return f"""
        QPushButton {{ background: {"transparent" if nav else bg}; color: {fg};
            border: 1px solid {"transparent" if nav else border}; border-radius: {round(9 * scale)}px;
            padding: {round(6 * scale)}px {round(12 * scale)}px; font-family: 'Segoe UI';
            font-size: {max(10, size)}px; font-weight: {600 if nav else 700};
            text-align: {"left" if nav else "center"}; }}
        QPushButton:hover, QPushButton:focus {{ border-color: #13E7FF;
            background: {"#27E7FF" if primary else "#0B3046"}; color: {"#00121E" if primary else "#F4F7FA"}; }}
        QPushButton:checked {{ border-color: #00D9FF; background:
            qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #006A95,stop:0.35 #074568,stop:1 #052235);
            color: #F4F7FA; }}
        QPushButton:pressed {{ background: #087B9E; color: #FFFFFF; border-color: #9BF5FF; }}
        QPushButton:disabled {{ background: #0B1821; color: #537080; border-color: #183747; }}
    """
