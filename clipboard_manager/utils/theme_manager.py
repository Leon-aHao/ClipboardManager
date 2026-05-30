from PySide6.QtWidgets import QApplication

DARK_QSS = """
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
}
QLineEdit {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 10px;
    color: #cdd6f4;
}
QLineEdit:focus {
    border-color: #89b4fa;
}
QListWidget {
    background-color: transparent;
    border: none;
    outline: none;
}
QListWidget::item {
    padding: 0px;
    margin: 0px;
    background: transparent;
}
QListWidget::item:selected {
    background: transparent;
}
QLabel {
    background: transparent;
}
QPushButton {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 12px;
    color: #cdd6f4;
}
QPushButton:hover {
    background-color: #45475a;
}
QPushButton:pressed {
    background-color: #585b70;
}
QMenu {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px;
    border-radius: 3px;
}
QMenu::item:selected {
    background-color: #45475a;
}
QMenu::separator {
    height: 1px;
    background: #45475a;
    margin: 4px 8px;
}
QScrollBar:vertical {
    background-color: #1e1e2e;
    width: 8px;
    border: none;
}
QScrollBar::handle:vertical {
    background-color: #45475a;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background-color: #585b70;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

LIGHT_QSS = """
QWidget {
    background-color: #ffffff;
    color: #1e1e2e;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
}
QLineEdit {
    background-color: #f5f5f5;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    padding: 6px 10px;
    color: #1e1e2e;
}
QLineEdit:focus {
    border-color: #0078d4;
}
QListWidget {
    background-color: transparent;
    border: none;
    outline: none;
}
QListWidget::item {
    padding: 0px;
    margin: 0px;
    background: transparent;
}
QListWidget::item:selected {
    background: transparent;
}
QLabel {
    background: transparent;
}
QPushButton {
    background-color: #f5f5f5;
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    padding: 4px 12px;
    color: #1e1e2e;
}
QPushButton:hover {
    background-color: #e0e0e0;
}
QPushButton:pressed {
    background-color: #c0c0c0;
}
QMenu {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px;
    border-radius: 3px;
}
QMenu::item:selected {
    background-color: #e0e0e0;
}
QMenu::separator {
    height: 1px;
    background: #d0d0d0;
    margin: 4px 8px;
}
QScrollBar:vertical {
    background-color: #ffffff;
    width: 8px;
    border: none;
}
QScrollBar::handle:vertical {
    background-color: #c0c0c0;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background-color: #a0a0a0;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


class ThemeManager:
    @classmethod
    def apply(cls, app: QApplication, theme: str):
        if theme == "dark":
            app.setStyleSheet(DARK_QSS)
        else:
            app.setStyleSheet(LIGHT_QSS)
