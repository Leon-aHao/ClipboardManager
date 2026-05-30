from collections import deque

from PySide6.QtCore import QObject, Signal

from .clipboard_item import ClipboardItem


class ClipboardStore(QObject):
    store_changed = Signal()
    item_inserted = Signal(int)
    item_evicted = Signal(int)  # item_id of permanently removed item

    def __init__(self, max_records: int = 500, parent=None):
        super().__init__(parent)
        self._items: deque[ClipboardItem] = deque()
        self._hash_index: dict[str, ClipboardItem] = {}
        self.max_records = max_records

    def insert_or_move(self, item: ClipboardItem) -> int:
        existing = self._hash_index.get(item.content_hash)
        if existing is not None:
            self._items.remove(existing)
            existing.timestamp = item.timestamp
            existing.source_app = item.source_app or existing.source_app
            self._items.appendleft(existing)
            self.item_inserted.emit(0)
            self.store_changed.emit()
            return 0

        self._hash_index[item.content_hash] = item
        self._items.appendleft(item)

        while len(self._items) > self.max_records:
            oldest = None
            for it in reversed(self._items):
                if not it.pinned:
                    oldest = it
                    break
            if oldest is None:
                break
            self._items.remove(oldest)
            del self._hash_index[oldest.content_hash]
            self.item_evicted.emit(oldest.id)

        self.item_inserted.emit(0)
        self.store_changed.emit()
        return 0

    def remove(self, item_id: int):
        for it in self._items:
            if it.id == item_id:
                self._items.remove(it)
                self._hash_index.pop(it.content_hash, None)
                self.store_changed.emit()
                return

    def trim_excess(self):
        while len(self._items) > self.max_records:
            oldest = None
            for it in reversed(self._items):
                if not it.pinned:
                    oldest = it
                    break
            if oldest is None:
                break
            self._items.remove(oldest)
            del self._hash_index[oldest.content_hash]
            self.item_evicted.emit(oldest.id)
        self.store_changed.emit()

    def clear(self):
        self._items.clear()
        self._hash_index.clear()
        self.store_changed.emit()

    def toggle_pin(self, item_id: int):
        for it in self._items:
            if it.id == item_id:
                it.pinned = not it.pinned
                store_changed = False
                if it.pinned:
                    self._items.remove(it)
                    self._items.appendleft(it)
                    store_changed = True
                if store_changed:
                    self.store_changed.emit()
                return

    def get_all(self) -> list[ClipboardItem]:
        pinned = [it for it in self._items if it.pinned]
        unpinned = [it for it in self._items if not it.pinned]
        return pinned + unpinned

    def filter(self, query: str) -> list[ClipboardItem]:
        if not query:
            return self.get_all()
        q = query.lower()
        return [
            it for it in self.get_all()
            if q in it.plain_text.lower()
        ]

    def get_by_id(self, item_id: int) -> ClipboardItem | None:
        for it in self._items:
            if it.id == item_id:
                return it
        return None

    def load_from_db(self, items: list[ClipboardItem]):
        self._items.clear()
        self._hash_index.clear()
        for item in items:
            self._items.append(item)
            self._hash_index[item.content_hash] = item
        self.store_changed.emit()

    def __len__(self):
        return len(self._items)
