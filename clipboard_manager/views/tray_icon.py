from PySide6.QtCore import Qt, QTimer, Signal, QPoint, QPointF, QRectF, QEvent
from PySide6.QtGui import QCursor
from PySide6.QtGui import (
    QAction, QIcon, QPixmap, QPainter, QColor, QPen, QBrush,
    QLinearGradient, QRadialGradient, QPainterPath,
)
from PySide6.QtWidgets import (
    QSystemTrayIcon, QMenu, QDialog, QVBoxLayout, QPushButton,
)


def _create_icon(color=0x89b4fa):
    px = QPixmap(32, 32)
    px.fill(QColor(0, 0, 0, 0))
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(QColor(color)))
    painter.setPen(QPen(QColor(color).darker(120), 1.5))
    painter.drawRoundedRect(7, 5, 18, 22, 3, 3)
    painter.setBrush(QBrush(QColor(0xcdd6f4)))
    painter.drawRoundedRect(11, 3, 10, 5, 2, 2)
    painter.setPen(QPen(QColor(0x1e1e2e), 1.5))
    painter.drawLine(10, 16, 22, 16)
    painter.drawLine(10, 20, 22, 20)
    painter.drawLine(10, 24, 17, 24)
    painter.end()
    return QIcon(px)


class TrayIcon(QSystemTrayIcon):
    toggle_popup = Signal()
    close_popup_requested = Signal()
    close_tray_popup = Signal()
    pause_requested = Signal()
    resume_requested = Signal()
    clear_requested = Signal()
    settings_requested = Signal()
    exit_requested = Signal()
    autostart_toggled = Signal(bool)
    translation_config_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._idle_icon = _create_icon(0x89b4fa)
        self._capture_icon = _create_icon(0xa6e3a1)
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._restore_icon)
        self._pause_action = QAction("暂停监听")  # For state tracking only
        self._tray_popup = None
        self._autostart_enabled = False
        self._init_connections()

    def set_autostart_state(self, enabled: bool):
        self._autostart_enabled = enabled

    def setup_icons(self, idle_pixmap=None, capture_pixmap=None):
        if idle_pixmap is not None:
            self._idle_icon = QIcon(idle_pixmap)
        if capture_pixmap is not None:
            self._capture_icon = QIcon(capture_pixmap)
        self.setIcon(self._idle_icon)

    def rebuild_menu(self):
        pass  # Custom popup replaces native context menu

    def close_tray_popup_window(self):
        if self._tray_popup is not None:
            self._tray_popup.close()
            self._tray_popup = None

    def _init_connections(self):
        try:
            self.activated.disconnect(self._on_activated)
        except Exception:
            pass
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Context:
            self._show_tray_popup()
        elif reason in (QSystemTrayIcon.ActivationReason.Trigger,
                        QSystemTrayIcon.ActivationReason.DoubleClick):
            self.close_tray_popup.emit()
            self.toggle_popup.emit()

    def _show_tray_popup(self):
        if self._tray_popup is not None:
            self._tray_popup.close()
            self._tray_popup = None
            return

        self.close_popup_requested.emit()

        popup = QDialog()
        popup.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        popup.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        layout = QVBoxLayout(popup)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        exit_btn = self._make_popup_btn("退出")
        exit_btn.clicked.connect(self.exit_requested.emit)
        exit_btn.clicked.connect(popup.close)
        layout.addWidget(exit_btn)

        pause_btn = self._make_popup_btn(
            "恢复监听" if self._pause_action.text() == "恢复监听" else "暂停监听"
        )
        pause_btn.clicked.connect(self._on_pause_toggle)
        pause_btn.clicked.connect(popup.close)
        layout.addWidget(pause_btn)

        translate_cfg_btn = self._make_popup_btn("翻译配置")
        translate_cfg_btn.clicked.connect(self.translation_config_requested.emit)
        translate_cfg_btn.clicked.connect(popup.close)
        layout.addWidget(translate_cfg_btn)

        autostart_text = "✓ 开机自启" if self._autostart_enabled else "开机自启"
        autostart_btn = self._make_popup_btn(autostart_text)
        autostart_btn.clicked.connect(lambda: self._on_autostart_toggle(autostart_btn))
        autostart_btn.clicked.connect(popup.close)
        layout.addWidget(autostart_btn)

        popup.adjustSize()
        popup.setFixedSize(popup.width(), popup.height())

        # Glow animation state
        popup._glow_pos = None       # Current rendered glow position
        popup._target_pos = None     # Target position (mouse)
        popup._glow_alpha = 0.0      # Current rendered alpha
        popup._target_alpha = 0.0    # Target alpha (1.0 in, 0.0 out)
        popup._fade_ms = 300

        glow_timer = QTimer(popup)
        glow_timer.setInterval(16)  # ~60fps

        def animate_glow():
            try:
                if popup.isHidden():
                    glow_timer.stop()
                    return
                need = False
                # Position lerp (fast follow)
                if popup._target_pos is not None:
                    if popup._glow_pos is None:
                        popup._glow_pos = popup._target_pos
                        need = True
                    else:
                        dx = popup._target_pos.x() - popup._glow_pos.x()
                        dy = popup._target_pos.y() - popup._glow_pos.y()
                        if abs(dx) > 0.1 or abs(dy) > 0.1:
                            popup._glow_pos = QPointF(
                                popup._glow_pos.x() + dx * 0.5,
                                popup._glow_pos.y() + dy * 0.5,
                            )
                            need = True
                # Alpha lerp
                step = 16.0 / max(popup._fade_ms, 1)
                if abs(popup._target_alpha - popup._glow_alpha) > 0.001:
                    if popup._target_alpha > popup._glow_alpha:
                        popup._glow_alpha = min(popup._target_alpha, popup._glow_alpha + step)
                    else:
                        popup._glow_alpha = max(popup._target_alpha, popup._glow_alpha - step)
                    need = True
                if popup._glow_alpha <= 0.0 and popup._target_alpha <= 0.0:
                    glow_timer.stop()
                if need:
                    popup.update()
            except Exception:
                glow_timer.stop()
        glow_timer.timeout.connect(animate_glow)

        # Install event filter to catch mouse on popup AND its children (buttons)
        popup.installEventFilter(popup)
        popup.setMouseTracking(True)

        def popup_event_filter(watched, event):
            t = event.type()
            if t == QEvent.Type.Enter:
                popup._target_alpha = 1.0
                popup._target_pos = popup.mapFromGlobal(QCursor.pos())
                glow_timer.start()
            elif t == QEvent.Type.Leave:
                popup._target_alpha = 0.0
            elif t == QEvent.Type.MouseMove:
                popup._target_pos = event.position()
                popup._target_alpha = 1.0
                if not glow_timer.isActive():
                    glow_timer.start()
            return False
        popup.eventFilter = popup_event_filter

        def paint_popup(event):
            p = QPainter(popup)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            radius = 20.0
            r = QRectF(popup.rect()).adjusted(1, 1, -1, -1)

            # Red glow following mouse
            if popup._glow_pos is not None and popup._glow_alpha > 0.001:
                glow = QRadialGradient(popup._glow_pos, 100)
                glow.setColorAt(0.0, QColor(255, 20, 20, int(255 * popup._glow_alpha)))
                glow.setColorAt(0.15, QColor(255, 25, 25, int(220 * popup._glow_alpha)))
                glow.setColorAt(0.35, QColor(255, 15, 15, int(100 * popup._glow_alpha)))
                glow.setColorAt(0.55, QColor(255, 10, 10, int(30 * popup._glow_alpha)))
                glow.setColorAt(1.0, QColor(255, 0, 0, 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(glow)
                p.drawRoundedRect(r, radius, radius)

            path = QPainterPath()
            path.addRoundedRect(r, radius, radius)
            p.setClipPath(path)
            p.fillRect(r, QColor(255, 255, 255, 140))
            p.setClipping(False)
            grad = QLinearGradient(r.topLeft(), r.bottomRight())
            grad.setColorAt(0.0, QColor(255, 255, 255, 200))
            grad.setColorAt(0.2, QColor(255, 255, 255, 45))
            grad.setColorAt(0.5, QColor(255, 255, 255, 0))
            grad.setColorAt(0.8, QColor(255, 255, 255, 45))
            grad.setColorAt(1.0, QColor(255, 255, 255, 200))
            p.setPen(QPen(QBrush(grad), 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r, radius, radius)
            ir = r.adjusted(0.8, 0.8, -0.8, -0.8)
            dg = QLinearGradient(ir.topLeft(), ir.bottomRight())
            dg.setColorAt(0.0, QColor(0, 0, 0, 80))
            dg.setColorAt(0.12, QColor(0, 0, 0, 18))
            dg.setColorAt(0.35, QColor(0, 0, 0, 0))
            dg.setColorAt(0.65, QColor(0, 0, 0, 0))
            dg.setColorAt(0.88, QColor(0, 0, 0, 18))
            dg.setColorAt(1.0, QColor(0, 0, 0, 80))
            p.setPen(QPen(QBrush(dg), 0.8))
            p.drawRoundedRect(ir, radius - 0.8, radius - 0.8)
            p.end()
        popup.paintEvent = paint_popup

        # Position above the cursor
        cursor = QCursor.pos()
        popup.move(cursor.x() - popup.width() // 2,
                   cursor.y() - popup.height() - 10)
        popup.finished.connect(lambda: setattr(self, '_tray_popup', None))
        popup.show()
        self._tray_popup = popup

    @staticmethod
    def _make_popup_btn(text: str):
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(120, 32)
        btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(255, 255, 255, 40);"
            "  border: 1px solid rgba(255, 255, 255, 200);"
            "  border-radius: 10px;"
            "  color: #1a1a1a;"
            "  font-size: 13px;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(255, 255, 255, 100);"
            "}"
        )
        return btn

    def _on_pause_toggle(self):
        if self._pause_action.text() == "暂停监听":
            self.pause_requested.emit()
            self._pause_action.setText("恢复监听")
        else:
            self.resume_requested.emit()
            self._pause_action.setText("暂停监听")

    def _on_autostart_toggle(self, btn):
        self._autostart_enabled = not self._autostart_enabled
        btn.setText("✓ 开机自启" if self._autostart_enabled else "开机自启")
        self.autostart_toggled.emit(self._autostart_enabled)

    def flash_capture(self):
        self.setIcon(self._capture_icon)
        self._flash_timer.start(300)

    def _restore_icon(self):
        self.setIcon(self._idle_icon)
