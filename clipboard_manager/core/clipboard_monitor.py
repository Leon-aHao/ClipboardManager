import time

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import QApplication

from .content_hasher import ContentHasher
from .format_detector import FormatDetector
from ..models.clipboard_item import ClipboardItem, ContentFormat


class ClipboardMonitor(QObject):
    content_captured = Signal(ClipboardItem)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._clipboard = QApplication.clipboard()
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._process_clipboard)
        self._paused = False
        self._last_hash: str | None = None

    def start(self):
        self._clipboard.dataChanged.connect(self._on_data_changed)

    def _on_data_changed(self):
        if self._paused:
            return
        self._debounce_timer.start(200)

    def _process_clipboard(self):
        mime = self._clipboard.mimeData()
        if mime is None:
            return

        content_hash = ContentHasher.hash_mime_data(mime)
        if content_hash == self._last_hash:
            return
        self._last_hash = content_hash

        fmt = FormatDetector.detect(mime)
        plain_text = FormatDetector.extract_text(mime)
        html_content = FormatDetector.extract_html(mime)
        image_data = FormatDetector.extract_image(mime)
        file_list = FormatDetector.extract_file_list(mime)

        if fmt == ContentFormat.UNKNOWN:
            return
        if not plain_text.strip() and not html_content and not image_data and not file_list:
            return

        item = ClipboardItem(
            content_hash=content_hash,
            format=fmt,
            plain_text=plain_text,
            html_content=html_content,
            image_data=image_data,
            file_list=file_list,
            color_value=FormatDetector.detect_color_from_text(plain_text),
            timestamp=time.time(),
        )
        self.content_captured.emit(item)

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def is_paused(self) -> bool:
        return self._paused
