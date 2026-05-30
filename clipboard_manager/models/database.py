import json
import os
import sqlite3
import time
from typing import Optional

from .clipboard_item import ClipboardItem, ContentFormat

DEFAULT_SETTINGS = {
    "max_records": "500",
    "panel_width": "320",
    "panel_height": "400",
    "theme": "dark",
    "animation_enabled": "1",
    "merge_consecutive": "0",
    "locale": "zh",
}


def _get_db_path() -> str:
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    db_dir = os.path.join(appdata, "ClipboardManager")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "clipboard.db")


class ClipboardDatabase:
    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path or _get_db_path()
        self._conn: Optional[sqlite3.Connection] = None

    def initialize(self):
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS clipboard_history (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                content_hash TEXT UNIQUE NOT NULL,
                format       TEXT NOT NULL,
                plain_text   TEXT,
                html_content TEXT,
                image_blob   BLOB,
                file_list    TEXT,
                color_value  TEXT,
                timestamp    REAL NOT NULL,
                pinned       INTEGER DEFAULT 0,
                source_app   TEXT
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON clipboard_history(timestamp DESC)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_history_hash ON clipboard_history(content_hash)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_history_pinned ON clipboard_history(pinned)")
        self._conn.commit()
        self._init_default_settings()

    def _init_default_settings(self):
        for key, value in DEFAULT_SETTINGS.items():
            self._conn.execute(
                "INSERT OR IGNORE INTO app_settings(key, value) VALUES (?, ?)",
                (key, value),
            )
        self._conn.commit()

    def load_all(self) -> list[ClipboardItem]:
        rows = self._conn.execute(
            "SELECT id, content_hash, format, plain_text, html_content, image_blob, "
            "file_list, color_value, timestamp, pinned, source_app "
            "FROM clipboard_history ORDER BY pinned DESC, timestamp DESC"
        ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def insert_item(self, item: ClipboardItem) -> int:
        cursor = self._conn.execute(
            "INSERT OR REPLACE INTO clipboard_history "
            "(content_hash, format, plain_text, html_content, image_blob, file_list, "
            "color_value, timestamp, pinned, source_app) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                item.content_hash,
                item.format.name,
                item.plain_text,
                item.html_content,
                item.image_data,
                json.dumps(item.file_list) if item.file_list else None,
                item.color_value,
                item.timestamp,
                int(item.pinned),
                item.source_app,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid

    def delete_item(self, item_id: int):
        self._conn.execute("DELETE FROM clipboard_history WHERE id = ?", (item_id,))
        self._conn.commit()

    def clear_all(self):
        self._conn.execute("DELETE FROM clipboard_history")
        self._conn.commit()

    def update_pin(self, item_id: int, pinned: bool):
        self._conn.execute(
            "UPDATE clipboard_history SET pinned = ? WHERE id = ?",
            (int(pinned), item_id),
        )
        self._conn.commit()

    def get_setting(self, key: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else None

    def set_setting(self, key: str, value: str):
        self._conn.execute(
            "INSERT OR REPLACE INTO app_settings(key, value) VALUES (?, ?)",
            (key, value),
        )
        self._conn.commit()

    def get_all_settings(self) -> dict:
        rows = self._conn.execute("SELECT key, value FROM app_settings").fetchall()
        return {row[0]: row[1] for row in rows}

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    @staticmethod
    def _row_to_item(row: tuple) -> ClipboardItem:
        fmt_str = row[2]
        try:
            fmt = ContentFormat[fmt_str]
        except KeyError:
            fmt = ContentFormat.UNKNOWN

        return ClipboardItem(
            id=row[0],
            content_hash=row[1],
            format=fmt,
            plain_text=row[3] or "",
            html_content=row[4],
            image_data=row[5],
            file_list=json.loads(row[6]) if row[6] else None,
            color_value=row[7],
            timestamp=row[8],
            pinned=bool(row[9]),
            source_app=row[10],
        )
