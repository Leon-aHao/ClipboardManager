from PySide6.QtCore import Signal, Qt, QSize, QRectF, QMimeData, QUrl, QPoint
from PySide6.QtGui import (
    QPainter, QColor, QPainterPath, QFontMetrics, QPixmap, QFont, QPen, QBrush,
    QLinearGradient, QDrag, QCursor, QAction,
)
from PySide6.QtWidgets import (
    QListWidget, QListWidgetItem, QStyledItemDelegate, QStyleOptionViewItem,
    QStyle, QApplication, QMenu, QDialog, QVBoxLayout, QLabel, QScrollArea,
)

from ..models.clipboard_item import ClipboardItem, ContentFormat


class _ItemDelegate(QStyledItemDelegate):
    _NORMAL = QColor(255, 255, 255, 120)
    _HOVER = QColor(255, 255, 255, 180)
    _RADIUS = 14.0
    _BTN_SIZE = 22.0
    _BTN_PAD = 4.0

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(option.rect).adjusted(4, 2, -4, -2)
        path = QPainterPath()
        path.addRoundedRect(rect, self._RADIUS, self._RADIUS)

        hovered = option.state & QStyle.StateFlag.State_MouseOver
        painter.setClipPath(path)
        painter.fillRect(rect, self._HOVER if hovered else self._NORMAL)
        painter.setClipping(False)

        border_gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        border_gradient.setColorAt(0.0, QColor(255, 255, 255, 140))
        border_gradient.setColorAt(0.2, QColor(255, 255, 255, 33))
        border_gradient.setColorAt(0.5, QColor(255, 255, 255, 0))
        border_gradient.setColorAt(0.8, QColor(255, 255, 255, 33))
        border_gradient.setColorAt(1.0, QColor(255, 255, 255, 140))
        painter.setPen(QPen(QBrush(border_gradient), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, self._RADIUS, self._RADIUS)

        # Inner dark line — hugs the white border, concentrated at corners
        inner_rect = rect.adjusted(0.8, 0.8, -0.8, -0.8)
        dark_grad = QLinearGradient(inner_rect.topLeft(), inner_rect.bottomRight())
        dark_grad.setColorAt(0.0, QColor(0, 0, 0, 95))
        dark_grad.setColorAt(0.12, QColor(0, 0, 0, 28))
        dark_grad.setColorAt(0.35, QColor(0, 0, 0, 0))
        dark_grad.setColorAt(0.65, QColor(0, 0, 0, 0))
        dark_grad.setColorAt(0.88, QColor(0, 0, 0, 28))
        dark_grad.setColorAt(1.0, QColor(0, 0, 0, 95))
        painter.setPen(QPen(QBrush(dark_grad), 0.8))
        painter.drawRoundedRect(inner_rect, self._RADIUS - 0.8, self._RADIUS - 0.8)

        data = index.data(Qt.ItemDataRole.UserRole)
        if data is None:
            super().paint(painter, option, index)
            return

        fmt_icon = index.data(Qt.ItemDataRole.UserRole + 2) or ""
        pixmap = index.data(Qt.ItemDataRole.UserRole + 3)
        has_icon = bool(pixmap and isinstance(pixmap, QPixmap) and not pixmap.isNull()) or fmt_icon in ("📁",)

        # 仅文本/HTML 类型显示翻译按钮
        show_translate = (fmt_icon == "Aa")
        # 右侧边距：X 按钮占 30px，若有翻译按钮再 + 26px
        right_margin = 60 if show_translate else 34

        if has_icon:
            icon_rect = QRectF(rect).adjusted(8, 8, 0, -8)
            icon_rect.setWidth(32)
            icon_rect.setHeight(32)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 140))
            icon_path = QPainterPath()
            icon_path.addRoundedRect(icon_rect, 8, 8)
            painter.drawPath(icon_path)

            if pixmap and isinstance(pixmap, QPixmap) and not pixmap.isNull():
                scaled = pixmap.scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                x = icon_rect.x() + (icon_rect.width() - scaled.width()) / 2
                y = icon_rect.y() + (icon_rect.height() - scaled.height()) / 2
                painter.drawPixmap(int(x), int(y), scaled)
            else:
                painter.setPen(QColor(100, 140, 220))
                painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, fmt_icon)

            text_rect = QRectF(rect).adjusted(42, 6, -right_margin, -6)
        else:
            text_rect = QRectF(rect).adjusted(12, 6, -right_margin, -6)

        preview = index.data(Qt.ItemDataRole.DisplayRole) or ""
        meta = index.data(Qt.ItemDataRole.UserRole + 1) or ""

        preview_font = QFont(painter.font())
        preview_font.setPixelSize(15)
        painter.setFont(preview_font)
        fm_preview = QFontMetrics(preview_font)
        painter.setPen(QColor(30, 30, 30))
        elided = fm_preview.elidedText(preview, Qt.TextElideMode.ElideRight, int(text_rect.width()))
        preview_rect = text_rect.adjusted(0, 1, 0, -text_rect.height() / 2 + 4)
        painter.drawText(preview_rect, Qt.AlignmentFlag.AlignVCenter, elided)

        meta_font = QFont(painter.font())
        meta_font.setPixelSize(11)
        painter.setFont(meta_font)
        fm_meta = QFontMetrics(meta_font)
        painter.setPen(QColor(80, 80, 80))
        meta_rect = QRectF(text_rect).adjusted(0, text_rect.height() / 2 - 1, 0, 0)
        elided_meta = fm_meta.elidedText(meta, Qt.TextElideMode.ElideRight, int(meta_rect.width()))
        painter.drawText(meta_rect, Qt.AlignmentFlag.AlignVCenter, elided_meta)

        # ---- 操作按钮 ----
        x_hovered = bool(index.data(Qt.ItemDataRole.UserRole + 4))
        tl_hovered = bool(index.data(Qt.ItemDataRole.UserRole + 6)) if show_translate else False

        # X 删除按钮
        x_btn_rect = self._action_btn_rect(rect, offset=0)
        self._draw_action_button(painter, x_btn_rect, "✕", x_hovered)

        # 译 翻译按钮（仅文本类型）
        if show_translate:
            tl_btn_rect = self._action_btn_rect(rect, offset=1)
            self._draw_action_button(painter, tl_btn_rect, "译", tl_hovered)

    def _action_btn_rect(self, card_rect: QRectF, offset: int) -> QRectF:
        """返回操作按钮在 card_rect 中的位置。offset 0=最右侧(X), 1=左一(译)。"""
        x = card_rect.right() - self._BTN_PAD - self._BTN_SIZE \
            - offset * (self._BTN_SIZE + self._BTN_PAD)
        y = card_rect.center().y() - self._BTN_SIZE / 2
        return QRectF(x, y, self._BTN_SIZE, self._BTN_SIZE)

    def _draw_action_button(self, painter: QPainter, btn_rect: QRectF, char: str, hovered: bool):
        """绘制单个毛玻璃风格操作按钮。"""
        radius = btn_rect.width() / 2

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 半透明白色填充
        btn_path = QPainterPath()
        btn_path.addRoundedRect(btn_rect, radius, radius)
        fill_alpha = 140 if hovered else 60
        painter.setClipPath(btn_path)
        painter.fillRect(btn_rect, QColor(255, 255, 255, fill_alpha))
        painter.setClipping(False)

        # 亮白渐变边框（四角亮 → 中间透明）
        border_grad = QLinearGradient(btn_rect.topLeft(), btn_rect.bottomRight())
        border_grad.setColorAt(0.0, QColor(255, 255, 255, 200))
        border_grad.setColorAt(0.2, QColor(255, 255, 255, 45))
        border_grad.setColorAt(0.5, QColor(255, 255, 255, 0))
        border_grad.setColorAt(0.8, QColor(255, 255, 255, 45))
        border_grad.setColorAt(1.0, QColor(255, 255, 255, 200))
        painter.setPen(QPen(QBrush(border_grad), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(btn_rect, radius, radius)

        # 内层暗线（四角浓 → 中间无）
        inner_r = btn_rect.adjusted(0.7, 0.7, -0.7, -0.7)
        inner_radius = radius - 0.7
        dark_grad = QLinearGradient(inner_r.topLeft(), inner_r.bottomRight())
        dark_grad.setColorAt(0.0, QColor(0, 0, 0, 85))
        dark_grad.setColorAt(0.12, QColor(0, 0, 0, 22))
        dark_grad.setColorAt(0.35, QColor(0, 0, 0, 0))
        dark_grad.setColorAt(0.65, QColor(0, 0, 0, 0))
        dark_grad.setColorAt(0.88, QColor(0, 0, 0, 22))
        dark_grad.setColorAt(1.0, QColor(0, 0, 0, 85))
        painter.setPen(QPen(QBrush(dark_grad), 0.7))
        painter.drawRoundedRect(inner_r, inner_radius, inner_radius)

        # 字符
        btn_font = QFont(painter.font())
        btn_font.setPixelSize(14 if char == "译" else 13)
        painter.setFont(btn_font)
        painter.setPen(QColor(60, 60, 60))
        painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, char)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(0, 56)


class _PreviewDialog(QDialog):
    """Frameless popup showing full-size image or text preview."""

    def __init__(self, item: ClipboardItem, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._is_image = (item.format == ContentFormat.IMAGE and item.image_data)
        layout = QVBoxLayout(self)

        if self._is_image:
            layout.setContentsMargins(12, 12, 12, 12)
            self._setup_image(item)
        else:
            layout.setContentsMargins(20, 20, 20, 20)
            self._setup_text(item)

    def _setup_image(self, item: ClipboardItem):
        frame = QLabel(self)
        pixmap = QPixmap()
        pixmap.loadFromData(item.image_data)
        pw, ph = 600, 450
        pixmap = pixmap.scaled(pw, ph,
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        frame.setPixmap(pixmap)
        frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame.setFixedSize(pw, ph)
        self.setFixedSize(pw + 24, ph + 24)
        self.layout().addWidget(frame)

    def _setup_text(self, item: ClipboardItem):
        frame = QLabel(self)
        text = item.plain_text or ""
        frame.setText(text)
        frame.setWordWrap(True)
        frame.setStyleSheet(
            "QLabel { color: #000000; font-size: 14px; padding: 8px; background: transparent; }"
        )
        frame.setMaximumWidth(460)
        frame.setMinimumWidth(200)
        frame.adjustSize()
        self.resize(frame.width() + 40, frame.height() + 40)
        self.layout().addWidget(frame)

    def paintEvent(self, event):
        if not self._is_image:
            self._paint_glass(event)
        super().paintEvent(event)

    def _paint_glass(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        radius = 28.0
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)

        # Semi-transparent white fill (whiter than popup's 100 alpha)
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        p.setClipPath(path)
        p.fillRect(rect, QColor(255, 255, 255, 190))
        p.setClipping(False)

        # Gradient border — bright at corners, transparent in middle
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0.0, QColor(255, 255, 255, 210))
        gradient.setColorAt(0.2, QColor(255, 255, 255, 50))
        gradient.setColorAt(0.5, QColor(255, 255, 255, 0))
        gradient.setColorAt(0.8, QColor(255, 255, 255, 50))
        gradient.setColorAt(1.0, QColor(255, 255, 255, 210))
        p.setPen(QPen(QBrush(gradient), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, radius, radius)

        # Inner dark line — concentrated at corners
        ir = rect.adjusted(1.2, 1.2, -1.2, -1.2)
        dg = QLinearGradient(ir.topLeft(), ir.bottomRight())
        dg.setColorAt(0.0, QColor(0, 0, 0, 95))
        dg.setColorAt(0.12, QColor(0, 0, 0, 28))
        dg.setColorAt(0.35, QColor(0, 0, 0, 0))
        dg.setColorAt(0.65, QColor(0, 0, 0, 0))
        dg.setColorAt(0.88, QColor(0, 0, 0, 28))
        dg.setColorAt(1.0, QColor(0, 0, 0, 95))
        p.setPen(QPen(QBrush(dg), 0.8))
        p.drawRoundedRect(ir, radius - 1.2, radius - 1.2)
        p.end()

    def show_at(self, pos: QPoint):
        """Position dialog so its bottom-right is near the cursor."""
        x = pos.x() - self.width()
        y = pos.y() - self.height()
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            if x < avail.left():
                x = avail.left()
            if y < avail.top():
                y = avail.top()
        self.move(max(0, x), max(0, y))
        self.show()


class _TranslationResultDialog(QDialog):
    """毛玻璃弹窗 — 显示原文和翻译结果。"""

    def __init__(self, original: str, translated: str, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 16, 20, 16)
        self._layout.setSpacing(8)

        # 原文标签
        self._src_label = QLabel(original)
        self._src_label.setWordWrap(True)
        self._src_label.setStyleSheet("color: #444444; font-size: 13px; background: transparent;")
        self._src_label.setMaximumWidth(420)
        self._layout.addWidget(self._src_label)

        # 分隔线
        self._sep = QLabel(self)
        self._sep.setFixedHeight(1)
        self._sep.setStyleSheet("background: rgba(0,0,0,0.08);")
        self._layout.addWidget(self._sep)

        # 译文标签
        self._tgt_label = QLabel(translated)
        self._tgt_label.setWordWrap(True)
        self._tgt_label.setStyleSheet("color: #1a1a1a; font-size: 16px; font-weight: bold; background: transparent;")
        self._tgt_label.setMaximumWidth(420)
        self._layout.addWidget(self._tgt_label)

        self._resize()

    def update_content(self, original: str, translated: str):
        """更新原文和译文内容（翻译完成时调用）。"""
        self._src_label.setText(original)
        self._tgt_label.setText(translated)
        self._tgt_label.setStyleSheet("color: #1a1a1a; font-size: 16px; font-weight: bold; background: transparent;")
        self._resize()

    def _resize(self):
        self.adjustSize()
        w = min(self.width(), 460)
        self.setFixedSize(w + 40, self.height() + 32)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        radius = 28.0
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)

        # 白色填充
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        p.setClipPath(path)
        p.fillRect(rect, QColor(255, 255, 255, 200))
        p.setClipping(False)

        # 渐变边框
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0.0, QColor(255, 255, 255, 210))
        gradient.setColorAt(0.2, QColor(255, 255, 255, 50))
        gradient.setColorAt(0.5, QColor(255, 255, 255, 0))
        gradient.setColorAt(0.8, QColor(255, 255, 255, 50))
        gradient.setColorAt(1.0, QColor(255, 255, 255, 210))
        p.setPen(QPen(QBrush(gradient), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, radius, radius)

        # 内层暗线
        ir = rect.adjusted(1.2, 1.2, -1.2, -1.2)
        dg = QLinearGradient(ir.topLeft(), ir.bottomRight())
        dg.setColorAt(0.0, QColor(0, 0, 0, 85))
        dg.setColorAt(0.12, QColor(0, 0, 0, 22))
        dg.setColorAt(0.35, QColor(0, 0, 0, 0))
        dg.setColorAt(0.65, QColor(0, 0, 0, 0))
        dg.setColorAt(0.88, QColor(0, 0, 0, 22))
        dg.setColorAt(1.0, QColor(0, 0, 0, 85))
        p.setPen(QPen(QBrush(dg), 0.8))
        p.drawRoundedRect(ir, radius - 1.2, radius - 1.2)
        p.end()

    def show_at_cursor(self):
        from PySide6.QtGui import QCursor
        cursor = QCursor.pos()
        x = cursor.x() - self.width() // 2
        y = cursor.y() - self.height() - 20
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            x = max(avail.left() + 4, min(x, avail.right() - self.width() - 4))
            y = max(avail.top() + 4, min(y, avail.bottom() - self.height() - 4))
        self.move(x, y)
        self.show()
        self.raise_()


class HistoryListWidget(QListWidget):
    item_copy_clicked = Signal(int)
    item_delete_requested = Signal(int)
    item_translate_requested = Signal(int)
    drag_started = Signal()

    _DRAG_DEAD_ZONE = 5
    _PREVIEW_SIZE = 80
    _PREVIEW_OPACITY = 0.7
    _BTN_SIZE = 22.0
    _BTN_PAD = 4.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSpacing(4)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.setItemDelegate(_ItemDelegate(self))
        self.itemClicked.connect(self._on_item_clicked)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        self._items_by_id: dict[int, ClipboardItem] = {}
        self._temp_file_manager = None

        # drag tracking
        self._drag_press_pos: QPoint | None = None
        self._drag_press_index = None
        self._drag_in_progress = False

        # right-click preview
        self._preview_dialog: _PreviewDialog | None = None
        self.viewport().installEventFilter(self)

        # action button hover tracking
        self._hovered_delete_item_id: int | None = None
        self._hovered_translate_item_id: int | None = None

    def set_temp_file_manager(self, mgr):
        self._temp_file_manager = mgr

    def get_item_at(self, pos: QPoint) -> ClipboardItem | None:
        """Return the ClipboardItem at local position, or None."""
        idx = self.indexAt(pos)
        if not idx.isValid():
            return None
        item_id = idx.data(Qt.ItemDataRole.UserRole)
        return self._items_by_id.get(item_id)

    # ---- public API ----

    def set_items(self, items: list[ClipboardItem]):
        self.clear()
        self._items_by_id.clear()
        for item in items:
            self._items_by_id[item.id] = item
            list_item = QListWidgetItem()
            list_item.setData(Qt.ItemDataRole.UserRole, item.id)
            list_item.setData(Qt.ItemDataRole.DisplayRole, item.preview_text())
            if item.format == ContentFormat.IMAGE:
                meta_text = self._format_time(item.timestamp)
            else:
                meta_text = f"{item.format_label()} · {self._format_time(item.timestamp)}"
            list_item.setData(Qt.ItemDataRole.UserRole + 1, meta_text)
            list_item.setData(Qt.ItemDataRole.UserRole + 2, self._icon_text(item))

            pixmap = None
            if item.format == ContentFormat.IMAGE and item.image_data:
                pixmap = QPixmap()
                pixmap.loadFromData(item.image_data)
            list_item.setData(Qt.ItemDataRole.UserRole + 3, pixmap)
            list_item.setData(Qt.ItemDataRole.UserRole + 4, False)   # X hover
            list_item.setData(Qt.ItemDataRole.UserRole + 6, False)   # translate hover

            list_item.setSizeHint(QSize(0, 56))
            self.addItem(list_item)

        # Reset hover state when list refreshes
        self._hovered_delete_item_id = None
        self._hovered_translate_item_id = None

    def remove_item_by_id(self, item_id: int):
        self._items_by_id.pop(item_id, None)
        for i in range(self.count()):
            if self.item(i).data(Qt.ItemDataRole.UserRole) == item_id:
                self.takeItem(i)
                break

    # ---- button geometry helpers ----

    def _action_btn_rect(self, list_item: QListWidgetItem, offset: int) -> QRectF | None:
        """返回操作按钮在 viewport 坐标中的矩形。offset 0=X(最右), 1=译(左一)。"""
        idx = self.indexFromItem(list_item)
        if not idx.isValid():
            return None
        rect = self.visualItemRect(list_item)
        card = QRectF(rect).adjusted(4, 2, -4, -2)
        x = card.right() - self._BTN_PAD - self._BTN_SIZE \
            - offset * (self._BTN_SIZE + self._BTN_PAD)
        y = card.center().y() - self._BTN_SIZE / 2
        return QRectF(x, y, self._BTN_SIZE, self._BTN_SIZE)

    def _has_translate_btn(self, list_item: QListWidgetItem) -> bool:
        """检查该条目是否显示翻译按钮（仅文本/HTML）。"""
        icon = list_item.data(Qt.ItemDataRole.UserRole + 2) or ""
        return icon == "Aa"

    def _set_btn_hover(self, item_id, role_index: int, hovered: bool):
        """更新指定 item 的按钮 hover 状态并触发重绘。"""
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == item_id:
                item.setData(Qt.ItemDataRole.UserRole + role_index, hovered)
                self.update(self.indexFromItem(item))
                break

    # ---- mouse events ----

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            idx = self.indexAt(pos)
            if idx.isValid():
                item = self.item(idx.row())
                item_id = idx.data(Qt.ItemDataRole.UserRole)
                # 翻译按钮点击
                if self._has_translate_btn(item):
                    tl_rect = self._action_btn_rect(item, offset=1)
                    if tl_rect is not None and tl_rect.contains(pos) and item_id is not None:
                        self.item_translate_requested.emit(item_id)
                        return
                # X 删除按钮点击
                x_rect = self._action_btn_rect(item, offset=0)
                if x_rect is not None and x_rect.contains(pos) and item_id is not None:
                    self.item_delete_requested.emit(item_id)
                    return
            self._drag_press_pos = pos
            self._drag_press_index = idx if idx.isValid() else None
            self._drag_in_progress = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_press_pos is not None and not self._drag_in_progress:
            delta = (event.position().toPoint() - self._drag_press_pos).manhattanLength()
            if delta >= self._DRAG_DEAD_ZONE and self._drag_press_index is not None:
                self._drag_in_progress = True
                self._start_drag(self._drag_press_index)
                return
        if not self._drag_in_progress:
            pos = event.position().toPoint()
            idx = self.indexAt(pos)
            old_x = self._hovered_delete_item_id
            old_tl = self._hovered_translate_item_id
            new_x = None
            new_tl = None

            if idx.isValid():
                item = self.item(idx.row())
                item_id = idx.data(Qt.ItemDataRole.UserRole)

                # Check translate button hover
                if self._has_translate_btn(item):
                    tl_rect = self._action_btn_rect(item, offset=1)
                    if tl_rect is not None and tl_rect.contains(pos):
                        new_tl = item_id

                # Check X button hover
                x_rect = self._action_btn_rect(item, offset=0)
                if x_rect is not None and x_rect.contains(pos):
                    new_x = item_id

            # Update cursor
            if new_x is not None or new_tl is not None:
                self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.viewport().unsetCursor()

            # Update hover states
            self._hovered_delete_item_id = new_x
            self._hovered_translate_item_id = new_tl

            if old_x != new_x:
                if old_x is not None:
                    self._set_btn_hover(old_x, 4, False)
                if new_x is not None:
                    self._set_btn_hover(new_x, 4, True)

            if old_tl != new_tl:
                if old_tl is not None:
                    self._set_btn_hover(old_tl, 6, False)
                if new_tl is not None:
                    self._set_btn_hover(new_tl, 6, True)

            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_press_pos = None
            self._drag_press_index = None
        elif event.button() == Qt.MouseButton.RightButton:
            self._close_preview()
        super().mouseReleaseEvent(event)

    # ---- right-click preview ----

    def _try_show_preview(self, pos: QPoint):
        index = self.indexAt(pos)
        if not index.isValid():
            return
        item_id = index.data(Qt.ItemDataRole.UserRole)
        item = self._items_by_id.get(item_id)
        if item is None:
            return

        cursor = self.mapToGlobal(pos)
        dialog = _PreviewDialog(item)  # parentless — floats above popup
        dialog.show_at(cursor)
        dialog.raise_()
        self._preview_dialog = dialog
        QApplication.instance().installEventFilter(self)

    def _close_preview(self):
        if self._preview_dialog is not None:
            self._preview_dialog.close()
            self._preview_dialog = None
        QApplication.instance().removeEventFilter(self)

    def eventFilter(self, watched, event):
        from PySide6.QtCore import QEvent
        # Viewport: intercept right-click press to show preview
        if watched is self.viewport():
            if event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.RightButton:
                    self._try_show_preview(event.position().toPoint())
                    return True
        # Application-wide: catch right-button release anywhere → close preview
        elif watched is QApplication.instance():
            if event.type() == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.RightButton:
                    self._close_preview()
                    return True
        return super().eventFilter(watched, event)

    # ---- drag ----

    def _start_drag(self, index):
        item_id = index.data(Qt.ItemDataRole.UserRole)
        item = self._items_by_id.get(item_id)
        if item is None:
            self._drag_in_progress = False
            return

        mime_data = self._build_mime_data(item)
        if mime_data is None:
            self._drag_in_progress = False
            return

        preview_pix = self._render_drag_pixmap(item)
        pix = preview_pix or QPixmap()

        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.setPixmap(pix)
        drag.setHotSpot(QPoint(pix.width() // 2, pix.height() // 2))
        self.drag_started.emit()

        drag.exec(Qt.DropAction.CopyAction)

        self._drag_press_pos = None
        self._drag_press_index = None
        self._drag_in_progress = False

    def _build_mime_data(self, item: ClipboardItem) -> QMimeData | None:
        mime = QMimeData()
        fmt = item.format

        if fmt == ContentFormat.IMAGE:
            if not item.image_data:
                return None
            mime.setData("image/png", item.image_data)
            if self._temp_file_manager:
                path = self._temp_file_manager.create_temp_file(item.image_data)
                url = QUrl.fromLocalFile(path).toString()
                mime.setUrls([QUrl.fromLocalFile(path)])
                mime.setHtml(f'<img src="{url}" />')
            return mime

        elif fmt == ContentFormat.TEXT:
            if not item.plain_text:
                return None
            mime.setText(item.plain_text)
            return mime

        elif fmt == ContentFormat.HTML:
            if not item.plain_text and not item.html_content:
                return None
            if item.html_content:
                mime.setHtml(item.html_content)
            mime.setText(item.plain_text)
            return mime

        elif fmt == ContentFormat.FILES:
            if not item.file_list:
                return None
            urls = [QUrl.fromLocalFile(f) for f in item.file_list]
            mime.setUrls(urls)
            if item.plain_text:
                mime.setText(item.plain_text)
            return mime

        elif fmt == ContentFormat.COLOR:
            if not item.color_value:
                return None
            mime.setText(item.color_value)
            return mime

        else:
            return None

    # ---- preview rendering ----

    def _render_drag_pixmap(self, item: ClipboardItem) -> QPixmap:
        if item.format == ContentFormat.IMAGE and item.image_data:
            return self._render_image_drag(item)
        else:
            return self._render_text_drag(item)

    def _render_image_drag(self, item: ClipboardItem) -> QPixmap:
        size = self._PREVIEW_SIZE
        opacity = self._PREVIEW_OPACITY
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setOpacity(opacity)
            radius = 10.0
            margin = 2.0
            inner = QRectF(0, 0, size, size).adjusted(margin, margin, -margin, -margin)

            img = QPixmap()
            img.loadFromData(item.image_data)
            scaled = img.scaled(int(inner.width()), int(inner.height()),
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation)
            x = (size - scaled.width()) / 2
            y = (size - scaled.height()) / 2
            painter.drawPixmap(int(x), int(y), scaled)
            painter.setOpacity(opacity * 0.5)
            painter.setPen(QPen(QColor(255, 255, 255, 140), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            path = QPainterPath()
            path.addRoundedRect(inner, radius, radius)
            painter.drawPath(path)
        finally:
            painter.end()
        return pixmap

    def _render_text_drag(self, item: ClipboardItem) -> QPixmap:
        text = item.plain_text or ""
        if not text:
            text = item.preview_text()

        # Calculate size from text content
        font = QFont()
        font.setPixelSize(13)
        fm = QFontMetrics(font)
        max_w, max_h = 280, 160
        pad = 14
        line_h = fm.height() + 2
        avail_w = max_w - pad * 2

        # Wrap text
        lines = []
        for paragraph in text.split("\n"):
            if not paragraph:
                lines.append("")
                continue
            current = ""
            for ch in paragraph:
                if fm.horizontalAdvance(current + ch) > avail_w:
                    lines.append(current)
                    current = ch
                else:
                    current += ch
            if current:
                lines.append(current)

        shown = lines[:12]  # max 12 lines
        if len(lines) > 12:
            shown[-1] = shown[-1][:avail_w // fm.averageCharWidth() - 3] + "..."

        content_h = len(shown) * line_h
        w = min(max_w, max(fm.horizontalAdvance(max(shown, key=len)) + pad * 2, 120))
        h = min(max_h, content_h + pad * 2)

        pixmap = QPixmap(w, h)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setOpacity(0.75)

            radius = 12.0
            rect = QRectF(0, 0, w, h)
            inner = rect.adjusted(1.5, 1.5, -1.5, -1.5)

            # Glass fill
            glass_path = QPainterPath()
            glass_path.addRoundedRect(inner, radius, radius)
            painter.setClipPath(glass_path)
            painter.fillRect(inner, QColor(255, 255, 255, 195))
            painter.setClipping(False)

            # White gradient border
            wb = QLinearGradient(inner.topLeft(), inner.bottomRight())
            wb.setColorAt(0.0, QColor(255, 255, 255, 200))
            wb.setColorAt(0.2, QColor(255, 255, 255, 45))
            wb.setColorAt(0.5, QColor(255, 255, 255, 0))
            wb.setColorAt(0.8, QColor(255, 255, 255, 45))
            wb.setColorAt(1.0, QColor(255, 255, 255, 200))
            painter.setPen(QPen(QBrush(wb), 1.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(glass_path)

            # Inner dark line
            ir = inner.adjusted(0.8, 0.8, -0.8, -0.8)
            dg = QLinearGradient(ir.topLeft(), ir.bottomRight())
            dg.setColorAt(0.0, QColor(0, 0, 0, 85))
            dg.setColorAt(0.12, QColor(0, 0, 0, 22))
            dg.setColorAt(0.35, QColor(0, 0, 0, 0))
            dg.setColorAt(0.65, QColor(0, 0, 0, 0))
            dg.setColorAt(0.88, QColor(0, 0, 0, 22))
            dg.setColorAt(1.0, QColor(0, 0, 0, 85))
            dg_rect = ir.adjusted(0.5, 0.5, -0.5, -0.5)
            dg_path = QPainterPath()
            dg_path.addRoundedRect(dg_rect, radius - 0.8, radius - 0.8)
            painter.setPen(QPen(QBrush(dg), 0.7))
            painter.drawPath(dg_path)

            # Draw text
            painter.setPen(QColor(30, 30, 30))
            painter.setFont(font)
            painter.setOpacity(1.0)
            y = pad
            for line in shown:
                painter.drawText(int(pad), int(y + fm.ascent()), line)
                y += line_h
        finally:
            painter.end()
        return pixmap

    # ---- internal ----

    def _on_item_clicked(self, list_item: QListWidgetItem):
        item_id = list_item.data(Qt.ItemDataRole.UserRole)
        if item_id is not None:
            self.item_copy_clicked.emit(item_id)

    @staticmethod
    def _icon_text(item: ClipboardItem) -> str:
        fmt = item.format
        if fmt == ContentFormat.IMAGE:
            return ""
        elif fmt == ContentFormat.FILES:
            return "📁"
        elif fmt == ContentFormat.COLOR:
            return ""
        return "Aa"

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
