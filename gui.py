import os
import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.theme import apply_theme


def main():
    app = QApplication(sys.argv)
    apply_theme(app)

    safe_start = os.environ.get("CHERRYQ_LEGACY_SAFE_START") == "1"
    window = MainWindow(safe_start=safe_start)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
