import sys
import os

# Allow running both as `python main.py` and `python -m clipboard_manager.main`
if __name__ == "__main__":
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

from PySide6.QtWidgets import QApplication

try:
    from .controllers.app_controller import AppController
    from .utils import win32_api
except ImportError:
    from clipboard_manager.controllers.app_controller import AppController
    from clipboard_manager.utils import win32_api


def main():
    # Single instance check
    mutex = win32_api.create_app_mutex()
    if mutex is None:
        print("ClipboardManager is already running.")
        return 1

    app = QApplication(sys.argv)
    app.setApplicationName("ClipboardManager")
    app.setQuitOnLastWindowClosed(False)

    controller = AppController()
    controller.initialize()

    code = app.exec()
    return code


if __name__ == "__main__":
    sys.exit(main())
