import re
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QMimeData, QBuffer, QByteArray

from ..models.clipboard_item import ContentFormat

URL_PATTERN = re.compile(
    r"^(https?://|ftp://|www\.)[^\s]+$",
    re.IGNORECASE,
)

COLOR_HEX_PATTERN = re.compile(r"^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")

COLOR_RGB_PATTERN = re.compile(
    r"^rgb\s*\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$"
)


class FormatDetector:
    @staticmethod
    def detect(mime: QMimeData) -> ContentFormat:
        if mime.hasImage():
            return ContentFormat.IMAGE

        if mime.hasFormat("application/x-color"):
            return ContentFormat.COLOR

        if mime.hasUrls():
            local_files = [u for u in mime.urls() if u.isLocalFile()]
            if local_files:
                return ContentFormat.FILES
            return ContentFormat.TEXT

        if mime.hasHtml():
            return ContentFormat.HTML

        if mime.hasText():
            text = mime.text().strip()
            if COLOR_HEX_PATTERN.match(text) or COLOR_RGB_PATTERN.match(text):
                return ContentFormat.COLOR
            return ContentFormat.TEXT

        return ContentFormat.UNKNOWN

    @staticmethod
    def extract_text(mime: QMimeData) -> str:
        if mime.hasText():
            return mime.text()
        return ""

    @staticmethod
    def extract_html(mime: QMimeData) -> Optional[str]:
        if mime.hasHtml():
            return mime.html()
        return None

    @staticmethod
    def extract_image(mime: QMimeData) -> Optional[bytes]:
        if mime.hasImage():
            image = mime.imageData()
            if image is not None and not image.isNull():
                ba = QByteArray()
                buf = QBuffer(ba)
                buf.open(QBuffer.OpenModeFlag.WriteOnly)
                image.save(buf, "PNG")
                buf.close()
                return bytes(ba)
        return None

    @staticmethod
    def extract_file_list(mime: QMimeData) -> Optional[list[str]]:
        if mime.hasUrls():
            return [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
        return None

    @staticmethod
    def detect_color_from_text(text: str) -> Optional[str]:
        text = text.strip()
        if COLOR_HEX_PATTERN.match(text):
            return text.upper()
        m = COLOR_RGB_PATTERN.match(text)
        if m:
            r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if r <= 255 and g <= 255 and b <= 255:
                return f"#{r:02X}{g:02X}{b:02X}"
        return None

    @staticmethod
    def is_url(text: str) -> bool:
        return bool(URL_PATTERN.match(text.strip()))
