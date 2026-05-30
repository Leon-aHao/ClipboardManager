from PySide6.QtCore import QObject
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from ..core.clipboard_monitor import ClipboardMonitor
from ..models.database import ClipboardDatabase
from ..models.clipboard_store import ClipboardStore
from ..models.clipboard_item import ContentFormat
from ..views.tray_icon import TrayIcon
from ..views.popup_window import PopupWindow
from ..utils.temp_file_manager import TempFileManager
from ..utils.win32_api import is_autostart_enabled, set_autostart


class AppController(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._db = ClipboardDatabase()
        self._db.initialize()
        self._store = ClipboardStore()
        self._monitor = ClipboardMonitor()
        self._tray = TrayIcon()
        self._popup = PopupWindow()
        self._temp_files = TempFileManager()
        self._temp_files.cleanup()

    def initialize(self):
        settings = self._db.get_all_settings()
        max_records = int(settings.get("max_records", "500"))
        theme = settings.get("theme", "dark")
        panel_w = int(settings.get("panel_width", "320"))
        panel_h = int(settings.get("panel_height", "400"))

        self._store.max_records = max_records
        self._popup.update_size(panel_w, panel_h)
        self._popup.set_temp_file_manager(self._temp_files)
        self._popup.set_max_records(max_records)

        items = self._db.load_all()
        self._store.load_from_db(items)
        self._store.trim_excess()

        self._tray.setup_icons()
        self._tray.set_autostart_state(is_autostart_enabled())
        self._tray.rebuild_menu()  # Must be before show() on Windows
        self._tray.show()
        self._tray.showMessage(
            "ClipboardManager", "剪贴板管理器已启动",
            QSystemTrayIcon.MessageIcon.Information, 1500,
        )

        self._store.item_evicted.connect(self._db.delete_item)
        self._monitor.content_captured.connect(self._on_content_captured)
        self._tray.toggle_popup.connect(self._toggle_popup)
        self._tray.close_popup_requested.connect(self._close_popup)
        self._tray.close_tray_popup.connect(self._tray.close_tray_popup_window)
        self._tray.pause_requested.connect(self._monitor.pause)
        self._tray.resume_requested.connect(self._monitor.resume)
        self._tray.clear_requested.connect(self._clear_all)
        self._tray.exit_requested.connect(self._save_and_exit)
        self._tray.autostart_toggled.connect(set_autostart)
        self._popup.item_clicked.connect(self._copy_to_clipboard)
        self._popup.clear_all_requested.connect(self._clear_all)
        self._popup.max_records_changed.connect(self._on_max_records_changed)

        self._monitor.start()

        from ..utils.theme_manager import ThemeManager
        ThemeManager.apply(QApplication.instance(), theme)

    def _on_content_captured(self, item):
        self._store.insert_or_move(item)
        db_id = self._db.insert_item(item)
        stored = self._store._hash_index.get(item.content_hash)
        if stored:
            stored.id = db_id
        self._tray.flash_capture()
        if self._popup.isVisible():
            self._popup.set_history(self._store.get_all())

    def _toggle_popup(self):
        if self._popup.isVisible():
            self._popup.hide()
        else:
            self._popup.set_history(self._store.get_all())
            self._popup.show_at_cursor()

    def _close_popup(self):
        if self._popup.isVisible():
            self._popup.hide()

    def _copy_to_clipboard(self, item_id: int):
        item = self._store.get_by_id(item_id)
        if item is None:
            return
        clipboard = QApplication.clipboard()
        if item.format == ContentFormat.IMAGE and item.image_data:
            pixmap = QPixmap()
            pixmap.loadFromData(item.image_data)
            clipboard.setPixmap(pixmap)
        elif item.format == ContentFormat.FILES and item.file_list:
            from PySide6.QtCore import QMimeData, QUrl
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(f) for f in item.file_list])
            mime.setText("\n".join(item.file_list))
            clipboard.setMimeData(mime)
        elif item.format == ContentFormat.HTML and item.html_content:
            from PySide6.QtCore import QMimeData
            mime = QMimeData()
            mime.setHtml(item.html_content)
            mime.setText(item.plain_text)
            clipboard.setMimeData(mime)
        else:
            clipboard.setText(item.plain_text)

    def _on_max_records_changed(self, limit: int):
        self._store.max_records = limit
        self._store.trim_excess()
        self._db.set_setting("max_records", str(limit))
        self._popup.set_max_records(limit)
        if self._popup.isVisible():
            self._popup.set_history(self._store.get_all())

    def _clear_all(self):
        self._store.clear()
        self._db.clear_all()
        if self._popup.isVisible():
            self._popup.set_history([])

    def _save_and_exit(self):
        self._temp_files.cleanup(max_age_seconds=0)  # clean all temp files
        self._db.close()
        QApplication.quit()
