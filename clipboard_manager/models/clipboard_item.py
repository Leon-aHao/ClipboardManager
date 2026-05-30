from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class ContentFormat(Enum):
    TEXT = auto()
    HTML = auto()
    IMAGE = auto()
    FILES = auto()
    COLOR = auto()
    UNKNOWN = auto()


@dataclass
class ClipboardItem:
    id: int = -1
    content_hash: str = ""
    format: ContentFormat = ContentFormat.TEXT
    plain_text: str = ""
    html_content: Optional[str] = None
    image_data: Optional[bytes] = None
    file_list: Optional[list] = None
    color_value: Optional[str] = None
    timestamp: float = 0.0
    pinned: bool = False
    source_app: Optional[str] = None

    def preview_text(self, max_len: int = 80) -> str:
        if self.format == ContentFormat.TEXT or self.format == ContentFormat.HTML:
            text = self.plain_text.replace("\n", " ").replace("\r", "")
            return text[:max_len] + ("..." if len(text) > max_len else "")
        elif self.format == ContentFormat.IMAGE:
            return "图片"
        elif self.format == ContentFormat.FILES:
            if self.file_list:
                names = [f.split("\\")[-1] for f in self.file_list]
                return f"[文件] {', '.join(names[:3])}"
            return "[文件]"
        elif self.format == ContentFormat.COLOR:
            return f"[颜色] {self.color_value or ''}"
        return "[未知格式]"

    def format_label(self) -> str:
        labels = {
            ContentFormat.TEXT: "文本",
            ContentFormat.HTML: "文本",
            ContentFormat.IMAGE: "图片",
            ContentFormat.FILES: "FILE",
            ContentFormat.COLOR: "COLOR",
            ContentFormat.UNKNOWN: "?",
        }
        return labels.get(self.format, "?")
