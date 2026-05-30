import hashlib
import os

from PySide6.QtCore import QMimeData, QBuffer, QByteArray


class ContentHasher:
    @staticmethod
    def hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()

    @staticmethod
    def hash_image(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def hash_file_list(paths: list[str]) -> str:
        combined = ""
        for p in sorted(paths):
            try:
                size = os.path.getsize(p)
            except OSError:
                size = 0
            combined += f"{p}|{size};"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    @classmethod
    def hash_mime_data(cls, mime: QMimeData) -> str:
        if mime.hasImage():
            image = mime.imageData()
            if image is not None and not image.isNull():
                ba = QByteArray()
                buf = QBuffer(ba)
                buf.open(QBuffer.OpenModeFlag.WriteOnly)
                image.save(buf, "PNG")
                buf.close()
                return cls.hash_image(bytes(ba))
            return cls.hash_text("__empty_image__")

        if mime.hasUrls():
            paths = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
            if paths:
                return cls.hash_file_list(paths)
            return cls.hash_text("\n".join([u.toString() for u in mime.urls()]))

        if mime.hasHtml():
            html = mime.html()
            return cls.hash_text(html)

        if mime.hasText():
            return cls.hash_text(mime.text())

        return cls.hash_text("__unknown__")
