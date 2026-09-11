import os
import sys

BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app_desktop import HeatExchangerDesktopApp


def resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def main():
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    ex = HeatExchangerDesktopApp()
    ex.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
