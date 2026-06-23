from PySide6.QtCore import QObject, QTimer, Signal
import threading
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from ..core.clipboard_monitor import ClipboardMonitor
from ..core.translator import Translator
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
        self._tray.translation_config_requested.connect(self._on_translation_config_requested)
        self._popup.item_clicked.connect(self._copy_to_clipboard)
        self._popup.item_delete_requested.connect(self._on_item_delete_requested)
        self._popup.item_translate_requested.connect(self._on_item_translate_requested)
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
            self._close_translate_dialog()
            self._popup.hide()
        else:
            self._popup.set_history(self._store.get_all())
            self._popup.show_at_cursor()

    def _on_translation_config_requested(self):
        import os, subprocess
        from ..core.translator import Translator
        path = Translator.get_config_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            Translator()
        subprocess.Popen(['notepad.exe', path])

    def _close_popup(self):
        self._close_translate_dialog()
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

    def _on_item_delete_requested(self, item_id: int):
        # 删除前获取 content_hash 以清理翻译缓存
        item = self._store.get_by_id(item_id)
        content_hash = item.content_hash if item else None
        self._store.remove(item_id)
        self._db.delete_item(item_id)
        if content_hash and hasattr(self, '_translation_cache'):
            self._translation_cache.pop(content_hash, None)
        if self._popup.isVisible():
            self._popup.set_history(self._store.get_all())

    def _on_item_translate_requested(self, item_id: int):
        # 如果已有弹窗且是同一 item → 关闭弹窗（toggle）
        if hasattr(self, '_translate_dialog') and self._translate_dialog is not None:
            if getattr(self, '_translate_dialog_item_id', None) == item_id:
                self._close_translate_dialog()
                return
            else:
                self._close_translate_dialog()

        item = self._store.get_by_id(item_id)
        if item is None:
            return
        text = item.plain_text or ""
        if not text.strip():
            self._show_translate_error("无可翻译内容")
            return

        # 缓存命中（按 content_hash 匹配，词条移动后仍有效）
        if not hasattr(self, '_translation_cache'):
            self._translation_cache = {}
        if item.content_hash in self._translation_cache:
            original, translated = self._translation_cache[item.content_hash]
            self._show_translation_result(original, translated, item_id)
            return

        # 防连点
        if getattr(self, '_translating', False):
            return

        # 先启动翻译，再弹窗
        self._translating = True
        self._start_translate_worker(text, item.content_hash, item_id)
        self._show_translation_result(text, "翻译中...", item_id)

    def _start_translate_worker(self, text: str, content_hash: str, item_id: int):
        """Python 原生线程执行翻译，主线程 QTimer 轮询结果。"""
        result_holder = [None]

        def _run():
            try:
                translator = Translator()
                result = translator.translate(text)
                if result:
                    result_holder[0] = ('ok', text, result, content_hash, item_id)
                else:
                    result_holder[0] = ('err', "翻译失败，请检查网络或翻译接口配置")
            except Exception as e:
                result_holder[0] = ('err', f"翻译异常: {e}")

        threading.Thread(target=_run, daemon=True).start()

        def _poll():
            r = result_holder[0]
            if r is not None:
                self._poll_timer.stop()
                self._translating = False
                if r[0] == 'ok':
                    self._on_translation_result(r[1], r[2], r[3], r[4])
                else:
                    self._show_translate_error(r[1])

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(_poll)
        self._poll_timer.start(100)

    def _on_translation_result(self, original: str, translated: str, content_hash: str, item_id: int):
        if not hasattr(self, '_translation_cache'):
            self._translation_cache = {}
        self._translation_cache[content_hash] = (original, translated)
        # 更新已有的加载中弹窗，而非新建
        if hasattr(self, '_translate_dialog') and self._translate_dialog is not None:
            try:
                self._translate_dialog.update_content(original, translated)
            except Exception:
                self._show_translation_result(original, translated, item_id)

    def _show_translation_result(self, original: str, translated: str, item_id: int):
        from ..views.history_list_widget import _TranslationResultDialog
        self._translate_dialog = _TranslationResultDialog(original, translated)
        self._translate_dialog_item_id = item_id
        self._translate_dialog.finished.connect(self._on_translate_dialog_closed)
        self._translate_dialog.show_at_cursor()
        self._install_translate_dialog_filter()

    def _on_translate_dialog_closed(self):
        """弹窗被关闭时清理引用。"""
        self._translate_dialog = None
        self._translate_dialog_item_id = None

    def _show_translate_error(self, message: str):
        """在光标附近显示翻译错误提示。"""
        from ..views.history_list_widget import _TranslationResultDialog
        self._translate_dialog = _TranslationResultDialog("翻译", message)
        self._translate_dialog_item_id = None
        self._translate_dialog.finished.connect(self._on_translate_dialog_closed)
        self._translate_dialog.show_at_cursor()
        self._install_translate_dialog_filter()

    def _install_translate_dialog_filter(self):
        """安装全局事件过滤器：点击翻译弹窗外任意位置自动关闭。"""
        dlg = self._translate_dialog
        if dlg is None:
            return

        popup = self._popup
        app = QApplication.instance()
        if app is None:
            return

        class _Filter(QObject):
            def eventFilter(this, watched, event):
                from PySide6.QtCore import QEvent
                if dlg is None or not dlg.isVisible():
                    app.removeEventFilter(this)
                    this.deleteLater()
                    return False
                if event.type() == QEvent.Type.MouseButtonPress:
                    pt = event.globalPosition().toPoint()
                    clicked_widget = app.widgetAt(pt)
                    if clicked_widget is not None:
                        w = clicked_widget
                        while w is not None:
                            # 点击在翻译弹窗内 → 不拦截
                            if w is dlg:
                                return False
                            # 点击在剪切板弹窗内 → 不拦截（toggle 逻辑会处理）
                            if w is popup:
                                return False
                            w = w.parentWidget()
                    self._close_translate_dialog()
                    app.removeEventFilter(this)
                    this.deleteLater()
                    return False
                return False

        QTimer.singleShot(0, lambda: app.installEventFilter(_Filter(app)) if dlg.isVisible() else None)

    def _close_translate_dialog(self):
        """关闭翻译弹窗并清理引用。"""
        if hasattr(self, '_translate_dialog') and self._translate_dialog is not None:
            try:
                self._translate_dialog.close()
            except Exception:
                pass
            self._translate_dialog = None
        self._translate_dialog_item_id = None

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
