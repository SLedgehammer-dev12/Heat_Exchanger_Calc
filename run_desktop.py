import os
import sys


def resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def main():
    from PyQt5.QtWidgets import QApplication

    from app_desktop import HeatExchangerDesktopApp

    app = QApplication(sys.argv)
    ex = HeatExchangerDesktopApp()
    ex.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
