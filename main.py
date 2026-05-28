import sys

from PySide6.QtWidgets import QApplication

from source.launcher.gui import SettingsGUI


def main():
    app = QApplication(sys.argv)
    window = SettingsGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
