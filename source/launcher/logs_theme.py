"""Scoped, desktop-first presentation for the Logs reader."""

LEVEL_COLORS = {
    "INFO": "#00d9ff",
    "DEBUG": "#80b5db",
    "WARN": "#ffd166",
    "ERROR": "#ff4d6d",
    "CRITICAL": "#ff5ba7",
    "RUNNING": "#27f5b0",
    "SUCCESS": "#27f5b0",
    "QUEUE": "#9a85ff",
    "TEMPLATE": "#7296aa",
}
LOGS_STYLE = """
QWidget#LogsPage { background:transparent; }
QWidget#LogsPage QLabel {background:transparent; border:none; color:#b7d3e2; font:12px 'Segoe UI';}
QWidget#LogsPage QLabel[role="title"] {color:#00d9ff; font:bold 26px 'Segoe UI';}
QWidget#LogsPage QLabel[role="technical"] {color:#91bcd3; font:11px 'Consolas';}
QWidget#LogsPage QLabel[role="heading"] {color:#00d9ff; font:bold 16px 'Segoe UI';}
QWidget#LogsPage QLabel[role="metric"] {color:#edf8ff; font:bold 23px 'Consolas';}
QWidget#LogsPage QFrame#LogMetricCard, QWidget#LogsPage QFrame#LogConsolePanel {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #041a27,stop:1 #020d15);border:1px solid #12627c;border-radius:6px;}
QWidget#LogsPage QFrame#LogMetricCard:hover {border-color:#2494ae; background:#061f2c;}
QWidget#LogsPage QPushButton {background:#061925; border:1px solid #20566f;border-radius:5px;color:#dceef9;padding:0 10px;font:bold 11px 'Segoe UI';}
QWidget#LogsPage QPushButton:hover, QWidget#LogsPage QPushButton:focus {background:#0a3245;border-color:#32bfd8;}
QWidget#LogsPage QPushButton:checked {background:#06445b;border-color:#00d9ff;color:white;}
QWidget#LogsPage QPushButton[destructive="true"] {background:#230f1c;color:#ff5479;border-color:#97354e;}
QWidget#LogsPage QLineEdit {background:#02131e;border:1px solid #17647d;border-radius:5px;color:#dbeef8;padding:0 8px;font:13px 'Consolas';}
QWidget#LogsPage QLineEdit:focus {border-color:#00d9ff;background:#052335;}
QWidget#LogsPage QTableView {background:#020d15;alternate-background-color:#04131e;color:#bad8e9;border:none;selection-background-color:#123f53;selection-color:#f0faff;outline:none;gridline-color:#0a2735;font:13px 'Consolas';}
QWidget#LogsPage QTableView:focus {border:1px solid #235b72;}
QWidget#LogsPage QHeaderView::section {background:#051b29;color:#99c9e0;border:none;border-bottom:1px solid #185771;padding-left:4px;font:11px 'Consolas';height:30px;}
QWidget#LogsPage QCheckBox {color:#c3dfed;font:11px 'Segoe UI';background:transparent;border:none;}
QWidget#LogsPage QFrame#LogStatusFooter {border:none;border-top:1px solid #174052;background:#04151f;}
QWidget#LogsPage QScrollBar:vertical {background:#02111a;width:8px;margin:0;}
QWidget#LogsPage QScrollBar::handle:vertical {background:#126780;min-height:28px;border-radius:4px;}
QWidget#LogsPage QScrollBar::handle:vertical:hover {background:#179ab8;}
QWidget#LogsPage QScrollBar::add-line:vertical,QWidget#LogsPage QScrollBar::sub-line:vertical {height:0;border:none;}
QWidget#LogsPage QScrollBar::add-page:vertical,QWidget#LogsPage QScrollBar::sub-page:vertical {background:transparent;}
QMenu#LogsFilterMenu {background:#041924;color:#d3e9f5;border:1px solid #16718c;padding:6px;}
QMenu#LogsFilterMenu::item {padding:8px 24px;border-radius:3px;}
QMenu#LogsFilterMenu::item:selected {background:#0a3d52;color:#00d9ff;}
"""
