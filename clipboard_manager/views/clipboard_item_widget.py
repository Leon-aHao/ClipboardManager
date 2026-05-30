from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QFontMetrics
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QVBoxLayout, QSizePolicy, QFrame,
)

from ..models.clipboard_item import ClipboardItem, ContentFormat


class ClipboardItemWidget(QWidget):
    def __init__(self, item: ClipboardItem, parent=None):
        super().__init__(parent)
        self.item = item

        # Outer transparent container - no background
        self.setStyleSheet("background: transparent;")

        # Inner card with rounded corners
        self._card = QFrame()
        self._card.setObjectName("itemCard")
        self._card.setStyleSheet(
            "#itemCard { background: rgba(49, 50, 68, 200); border-radius: 14px; }"
        )

        card_layout = QHBoxLayout(self._card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(8)

        # Thumbnail
        self._thumb = QLabel()
        self._thumb.setFixedSize(32, 32)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setStyleSheet(
            "QLabel { background: rgba(69, 71, 90, 180); border-radius: 8px; color: #89b4fa; font-size: 11px; }"
        )
        card_layout.addWidget(self._thumb)

        # Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        self._preview = QLabel()
        self._preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._preview.setMinimumHeight(18)
        self._preview.setStyleSheet("font-size: 13px; color: #cdd6f4; background: transparent;")
        self._preview.setWordWrap(False)
        self._full_text = item.preview_text()
        self._update_preview_text()
        text_layout.addWidget(self._preview)

        self._meta = QLabel(f"{item.format_label()} · {self._format_time(item.timestamp)}")
        self._meta.setMinimumHeight(12)
        self._meta.setStyleSheet("color: #585b70; font-size: 10px; background: transparent;")
        text_layout.addWidget(self._meta)
        card_layout.addLayout(text_layout, 1)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 2, 14, 2)
        outer.addWidget(self._card)

        self._set_thumbnail()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_preview_text()

    def _set_thumbnail(self):
        fmt = self.item.format
        if fmt == ContentFormat.IMAGE and self.item.image_data:
            pixmap = QPixmap()
            pixmap.loadFromData(self.item.image_data)
            self._thumb.setPixmap(pixmap.scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio))
            self._thumb.setText("")
        elif fmt == ContentFormat.FILES:
            self._thumb.setText("📁")
        elif fmt == ContentFormat.HTML:
            self._thumb.setText("🌐")
        elif fmt == ContentFormat.COLOR:
            hex_val = self.item.color_value or "#000"
            self._thumb.setText("")
            self._thumb.setStyleSheet(
                f"QLabel {{ background: {hex_val}; border-radius: 4px; }}"
            )
        else:
            self._thumb.setText("Aa")

    def _update_preview_text(self):
        fm = QFontMetrics(self._preview.font())
        elided = fm.elidedText(self._full_text, Qt.TextElideMode.ElideRight, self._preview.width())
        self._preview.setText(elided)

    @staticmethod
    def _format_time(ts: float) -> str:
        from datetime import datetime
        dt = datetime.fromtimestamp(ts)
        now = datetime.now()
        diff = now - dt
        if diff.days > 0:
            return dt.strftime("%m-%d %H:%M")
        if diff.seconds < 60:
            return "刚刚"
        if diff.seconds < 3600:
            return f"{diff.seconds // 60} 分钟前"
        return f"{diff.seconds // 3600} 小时前"
