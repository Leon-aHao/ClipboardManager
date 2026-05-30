from PySide6.QtCore import Qt, Signal, QPoint, QPointF, QEvent, QRectF, QTimer
from PySide6.QtWidgets import (
    QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QApplication, QDialog,
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QCursor, QPainterPath, QRegion,
    QLinearGradient, QRadialGradient, QFont, QEnterEvent,
)

from .history_list_widget import HistoryListWidget, _PreviewDialog
from ..models.clipboard_item import ClipboardItem
from ..utils import win32_api


class _GlassButton(QPushButton):
    """iOS 26 liquid glass button with gradient hairline border."""

    def __init__(self, text: str, parent=None, bg_opacity: int = 90):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hovered = False
        self._bg_opacity = bg_opacity

    def enterEvent(self, event: QEnterEvent):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        radius = 12.0

        # fill
        path = QPainterPath()
        path.addRoundedRect(r, radius, radius)
        p.setClipPath(path)
        bg_alpha = 160 if self._hovered else self._bg_opacity
        p.fillRect(r, QColor(255, 255, 255, bg_alpha))
        p.setClipping(False)

        # gradient border
        border_gradient = QLinearGradient(r.topLeft(), r.bottomRight())
        border_gradient.setColorAt(0.0, QColor(255, 255, 255, 210))
        border_gradient.setColorAt(0.2, QColor(255, 255, 255, 50))
        border_gradient.setColorAt(0.5, QColor(255, 255, 255, 0))
        border_gradient.setColorAt(0.8, QColor(255, 255, 255, 50))
        border_gradient.setColorAt(1.0, QColor(255, 255, 255, 210))
        p.setPen(QPen(QBrush(border_gradient), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, radius, radius)

        # Inner dark line — hugs the white border, concentrated at corners
        ir = r.adjusted(0.8, 0.8, -0.8, -0.8)
        dark_grad = QLinearGradient(ir.topLeft(), ir.bottomRight())
        dark_grad.setColorAt(0.0, QColor(0, 0, 0, 95))
        dark_grad.setColorAt(0.12, QColor(0, 0, 0, 28))
        dark_grad.setColorAt(0.35, QColor(0, 0, 0, 0))
        dark_grad.setColorAt(0.65, QColor(0, 0, 0, 0))
        dark_grad.setColorAt(0.88, QColor(0, 0, 0, 28))
        dark_grad.setColorAt(1.0, QColor(0, 0, 0, 95))
        p.setPen(QPen(QBrush(dark_grad), 0.8))
        p.drawRoundedRect(ir, radius - 0.8, radius - 0.8)

        # text
        p.setPen(QColor(30, 30, 30))
        font = QFont(p.font())
        font.setPixelSize(13)
        p.setFont(font)
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.text())
        p.end()


class PopupWindow(QDialog):
    item_clicked = Signal(int)
    clear_all_requested = Signal()
    max_records_changed = Signal(int)

    def __init__(self, width: int = 320, height: int = 400, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(width, height)

        self._panel_width = width
        self._panel_height = height
        self._filter_installed = False

        # glow tracking
        self._glow_pos = None
        self._target_pos = None
        self._glow_alpha = 0.0
        self._target_alpha = 0.0
        self._fade_duration_ms = 200
        self._glow_timer = QTimer(self)
        self._glow_timer.timeout.connect(self._animate_glow)
        self.setMouseTracking(True)

        # drag state
        self._drag_pressed = False
        self._drag_active = False
        self._drag_origin = QPoint()
        self._window_origin = QPoint()

        # right-click preview
        self._preview_dialog = None

        # limit popup
        self._limit_popup = None
        self._max_records = 0

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.addStretch()
        clear_btn = _GlassButton("清空")
        clear_btn.setFixedSize(64, 32)
        clear_btn.clicked.connect(self.clear_all_requested.emit)
        header.addWidget(clear_btn)
        close_btn = _GlassButton("✕")
        close_btn.setFixedSize(64, 32)
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)
        layout.addLayout(header)

        self._list = HistoryListWidget()
        self._list.item_copy_clicked.connect(self.item_clicked.emit)
        self._list.setStyleSheet(
            "QListWidget { background: transparent; border: none; }"
            "QListWidget::item { background: transparent; }"
            "QListWidget::item:selected { background: transparent; }"
        )
        layout.addWidget(self._list, 1)

        # 让列表区域的鼠标事件也能触发光晕
        self._viewport = self._list.viewport()
        self._viewport.installEventFilter(self)
        self._viewport.setMouseTracking(True)

        # Bottom row: count label + limit selector
        bottom = QHBoxLayout()
        self._count_label = QLabel("0 条记录")
        self._count_label.setStyleSheet("color: #555555; font-size: 11px;")
        bottom.addWidget(self._count_label)
        bottom.addStretch()

        self._limit_btn = _GlassButton("保留")
        self._limit_btn.setFixedSize(52, 28)
        self._limit_btn.setToolTip("自动保存条数上限")
        self._limit_btn.clicked.connect(self._show_limit_menu)
        bottom.addWidget(self._limit_btn)
        layout.addLayout(bottom)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        radius = 28
        rect = self.rect().adjusted(1, 1, -1, -1)

        # 鼠标跟随浅蓝光晕（底层）
        if self._glow_pos is not None and self._glow_alpha > 0.001:
            glow_radius = 180
            glow = QRadialGradient(self._glow_pos, glow_radius)
            glow.setColorAt(0.0, QColor(140, 180, 255, int(110 * self._glow_alpha)))
            glow.setColorAt(0.11, QColor(140, 180, 255, int(96 * self._glow_alpha)))
            glow.setColorAt(0.22, QColor(140, 180, 255, int(80 * self._glow_alpha)))
            glow.setColorAt(0.33, QColor(140, 180, 255, int(62 * self._glow_alpha)))
            glow.setColorAt(0.44, QColor(140, 180, 255, int(44 * self._glow_alpha)))
            glow.setColorAt(0.55, QColor(140, 180, 255, int(28 * self._glow_alpha)))
            glow.setColorAt(0.66, QColor(140, 180, 255, int(16 * self._glow_alpha)))
            glow.setColorAt(0.77, QColor(140, 180, 255, int(7 * self._glow_alpha)))
            glow.setColorAt(0.88, QColor(140, 180, 255, int(2 * self._glow_alpha)))
            glow.setColorAt(1.0, QColor(140, 180, 255, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawRoundedRect(rect, radius, radius)

        # 外边框：亮白渐变（左上/右下亮 → 中间透明）
        gradient_outer = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient_outer.setColorAt(0.0, QColor(255, 255, 255, 210))
        gradient_outer.setColorAt(0.2, QColor(255, 255, 255, 50))
        gradient_outer.setColorAt(0.5, QColor(255, 255, 255, 0))
        gradient_outer.setColorAt(0.8, QColor(255, 255, 255, 50))
        gradient_outer.setColorAt(1.0, QColor(255, 255, 255, 210))
        p.setPen(QPen(QBrush(gradient_outer), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, radius, radius)

        # 内边框：黑灰径向渐变（四角浓 → 四边中点透明，与亮白反对称）
        inner_rect = rect.adjusted(1.5, 1.5, -1.5, -1.5)
        center = inner_rect.center()
        r = max(inner_rect.width(), inner_rect.height()) / 2.0
        gradient_inner = QRadialGradient(center, r)
        gradient_inner.setColorAt(0.0, QColor(0, 0, 0, 0))
        gradient_inner.setColorAt(0.55, QColor(0, 0, 0, 0))
        gradient_inner.setColorAt(0.8, QColor(0, 0, 0, 25))
        gradient_inner.setColorAt(1.0, QColor(0, 0, 0, 90))
        p.setPen(QPen(QBrush(gradient_inner), 1.0))
        p.drawRoundedRect(inner_rect, radius - 1.5, radius - 1.5)

        # 半透明白色背景
        path = QPainterPath()
        path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), radius, radius)
        p.setClipPath(path)
        p.fillRect(rect, QColor(255, 255, 255, 100))
        p.end()

    def set_history(self, items: list[ClipboardItem]):
        self._list.set_items(items)
        label = f"{len(items)}/{self._max_records}条记录" if self._max_records else f"{len(items)}条记录"
        self._count_label.setText(label)

    def set_max_records(self, limit: int):
        self._max_records = limit

    def set_temp_file_manager(self, mgr):
        self._list.set_temp_file_manager(mgr)

    def show_at_cursor(self):
        cursor = QCursor.pos()
        work = win32_api.get_work_area()
        x = cursor.x() - self._panel_width // 2
        y = cursor.y() - self._panel_height - 30
        if work:
            if y < work.top:
                y = cursor.y() + 30  # flip below if not enough room above
            x = max(work.left + 4, min(x, work.right - self._panel_width - 4))
            y = max(work.top + 4, min(y, work.bottom - self._panel_height - 4))
        self.move(QPoint(x, y))
        self.show()
        self.raise_()

    def hide(self):
        self._target_alpha = 0.0
        self._glow_alpha = 0.0
        self._glow_pos = None
        self._target_pos = None
        if self._limit_popup:
            self._limit_popup.close()
            self._limit_popup = None
        if self._preview_dialog:
            self._preview_dialog.close()
            self._preview_dialog = None
        super().hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pressed = True
            self._drag_active = False
            self._drag_origin = event.globalPosition().toPoint()
            self._window_origin = self.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pressed:
            delta = (event.globalPosition().toPoint() - self._drag_origin).manhattanLength()
            if delta > 5 and not self._drag_active:
                self._drag_active = True
            if self._drag_active:
                offset = event.globalPosition().toPoint() - self._drag_origin
                self.move(self._window_origin + offset)
                return
        # glow
        self._target_pos = QPointF(event.pos())
        self._target_alpha = 1.0
        if not self._glow_timer.isActive():
            self._glow_timer.start(16)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pressed = False
            self._drag_active = False
        super().mouseReleaseEvent(event)

    def eventFilter(self, watched, event):
        # Close preview on right-release anywhere (when preview is showing)
        if self._preview_dialog is not None:
            if event.type() == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.RightButton:
                    self._close_item_preview()
                    return True

        # Limit popup: forward mouse moves to main glow
        if self._limit_popup is not None and watched is self._limit_popup:
            if event.type() == QEvent.Type.MouseMove:
                gp = watched.mapToGlobal(event.position().toPoint())
                lp = self.mapFromGlobal(gp)
                self._target_pos = QPointF(lp)
                self._target_alpha = 1.0
                if not self._glow_timer.isActive():
                    self._glow_timer.start(16)
            return False

        # Viewport-level: glow tracking + right-click press to show preview
        if watched is self._viewport:
            if event.type() == QEvent.Type.MouseMove:
                gp = watched.mapToGlobal(event.position().toPoint())
                lp = self.mapFromGlobal(gp)
                self._target_pos = QPointF(lp)
                self._target_alpha = 1.0
                if not self._glow_timer.isActive():
                    self._glow_timer.start(16)
            elif event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.RightButton:
                    self._show_item_preview(event.position().toPoint())
                    return True

        return super().eventFilter(watched, event)

    def _install_preview_close_filter(self):
        """Install app-level filter to close preview on next right-release."""
        if self._preview_dialog is not None:
            QApplication.instance().installEventFilter(self)

    def _show_item_preview(self, pos):
        item = self._list.get_item_at(pos)
        if item is None:
            return
        cursor = self._viewport.mapToGlobal(pos)
        dialog = _PreviewDialog(item)
        dialog.show_at(cursor)
        dialog.raise_()
        self._preview_dialog = dialog
        QTimer.singleShot(300, self._install_preview_close_filter)

    def _show_limit_menu(self):
        """Toggle a small glass popup above the button with 20/50 options."""
        if self._limit_popup is not None:
            self._limit_popup.close()
            self._limit_popup = None
            return

        popup = QDialog(self)
        popup.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        popup.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        popup_layout = QVBoxLayout(popup)
        popup_layout.setContentsMargins(8, 8, 8, 8)
        popup_layout.setSpacing(4)

        for n in (20, 50):
            btn = _GlassButton(f"{n} 条", bg_opacity=15)
            btn.setFixedSize(64, 32)
            btn.clicked.connect(lambda checked, v=n: [self.max_records_changed.emit(v), popup.close()])
            popup_layout.addWidget(btn)

        popup.adjustSize()
        popup.setFixedSize(popup.width(), popup.height())

        # Custom paint for glass background
        def paint_popup(event):
            p = QPainter(popup)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            radius = 16.0
            r = QRectF(popup.rect()).adjusted(1, 1, -1, -1)
            # Fill
            path = QPainterPath()
            path.addRoundedRect(r, radius, radius)
            p.setClipPath(path)
            p.fillRect(r, QColor(255, 255, 255, 150))
            p.setClipping(False)
            # Gradient border
            grad = QLinearGradient(r.topLeft(), r.bottomRight())
            grad.setColorAt(0.0, QColor(255, 255, 255, 210))
            grad.setColorAt(0.2, QColor(255, 255, 255, 50))
            grad.setColorAt(0.5, QColor(255, 255, 255, 0))
            grad.setColorAt(0.8, QColor(255, 255, 255, 50))
            grad.setColorAt(1.0, QColor(255, 255, 255, 210))
            p.setPen(QPen(QBrush(grad), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r, radius, radius)

            # Inner dark line — concentrated at corners
            ir2 = r.adjusted(0.8, 0.8, -0.8, -0.8)
            dg = QLinearGradient(ir2.topLeft(), ir2.bottomRight())
            dg.setColorAt(0.0, QColor(0, 0, 0, 95))
            dg.setColorAt(0.12, QColor(0, 0, 0, 28))
            dg.setColorAt(0.35, QColor(0, 0, 0, 0))
            dg.setColorAt(0.65, QColor(0, 0, 0, 0))
            dg.setColorAt(0.88, QColor(0, 0, 0, 28))
            dg.setColorAt(1.0, QColor(0, 0, 0, 95))
            p.setPen(QPen(QBrush(dg), 0.8))
            p.drawRoundedRect(ir2, radius - 0.8, radius - 0.8)
            p.end()
        popup.paintEvent = paint_popup

        # Position above the limit button
        btn_pos = self._limit_btn.mapToGlobal(QPoint(0, 0))
        popup.move(btn_pos.x() - popup.width() + self._limit_btn.width(),
                   btn_pos.y() - popup.height() - 4)
        popup.installEventFilter(self)
        popup.setMouseTracking(True)

        popup.finished.connect(lambda: setattr(self, '_limit_popup', None))
        popup.show()
        self._limit_popup = popup

    def _close_item_preview(self):
        if self._preview_dialog is not None:
            self._preview_dialog.close()
            self._preview_dialog = None
        QApplication.instance().removeEventFilter(self)

    def enterEvent(self, event):
        self._target_pos = QPointF(event.pos())
        self._target_alpha = 1.0
        self._fade_duration_ms = 200
        self._glow_timer.start(16)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._limit_popup is None and self._preview_dialog is None:
            self._target_alpha = 0.0
            self._fade_duration_ms = 500
        super().leaveEvent(event)

    def _animate_glow(self):
        need_update = False

        # position lerp (fast)
        if self._target_pos is not None:
            if self._glow_pos is None:
                self._glow_pos = QPointF(self._target_pos)
                need_update = True
            else:
                dx = self._target_pos.x() - self._glow_pos.x()
                dy = self._target_pos.y() - self._glow_pos.y()
                if abs(dx) > 0.3 or abs(dy) > 0.3:
                    self._glow_pos = QPointF(
                        self._glow_pos.x() + dx * 0.55,
                        self._glow_pos.y() + dy * 0.55,
                    )
                    need_update = True

        # opacity animation
        step = 16.0 / max(self._fade_duration_ms, 1)
        if abs(self._target_alpha - self._glow_alpha) > 0.001:
            if self._target_alpha > self._glow_alpha:
                self._glow_alpha = min(self._target_alpha, self._glow_alpha + step)
            else:
                self._glow_alpha = max(self._target_alpha, self._glow_alpha - step)
            need_update = True

        if self._glow_alpha <= 0.0 and self._target_alpha <= 0.0:
            self._glow_timer.stop()

        if need_update:
            self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        elif event.key() == Qt.Key.Key_Down:
            row = self._list.currentRow()
            if row < self._list.count() - 1:
                self._list.setCurrentRow(row + 1)
        elif event.key() == Qt.Key.Key_Up:
            row = self._list.currentRow()
            if row > 0:
                self._list.setCurrentRow(row - 1)
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            selected = self._list.currentItem()
            if selected:
                item_id = selected.data(Qt.ItemDataRole.UserRole)
                if item_id is not None:
                    self.item_clicked.emit(item_id)
        super().keyPressEvent(event)

    def update_size(self, width: int, height: int):
        self._panel_width = width
        self._panel_height = height
        self.setFixedSize(width, height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_list_mask()

    def _update_list_mask(self):
        radius = 28
        rect = self._list.rect()
        path = QPainterPath()
        path.addRoundedRect(float(rect.x()), float(rect.y()), float(rect.width()), float(rect.height()), radius, radius)
        region = QRegion(path.toFillPolygon().toPolygon())
        self._list.setMask(region)
