# ClipboardManager

Windows 系统托盘剪贴板历史管理工具，基于 PySide6 + SQLite 开发。

## 功能特性

- **自动监控剪贴板** — 支持文本、HTML、图片、文件列表、颜色值等格式
- **毛玻璃弹窗 UI** — 鼠标跟随光晕动画，无边框玻璃拟态设计
- **右键预览** — 按住右键放大查看图片细节或长文本全文
- **拖拽导出** — 直接拖到桌面保存、拖到微信/QQ/Word 发送
- **英译中翻译** — 点击"译"按钮一键翻译英文内容，支持百度翻译 API
- **单条删除** — 每条记录右侧 X 按钮直接删除
- **开机自启** — 可配置的自动启动
- **暂停监听** — 防止敏感信息被记录
- **可配置记录数** — 20/50 条，超出自动淘汰

![ClipboardManager 主界面](docs/images/clipboard01.png)

![右键放大预览](docs/images/clipboard02.png)

## 快速开始

```bash
pip install -r requirements.txt
python -m clipboard_manager.main
```

## 下载

从 [Releases](https://github.com/Leon-aHao/ClipboardManager/releases) 页面下载 `ClipboardManager.exe`，双击运行，无需安装 Python。

## 自行构建

```bash
pyinstaller clipboard_manager.spec
```

## 翻译配置

默认使用百度翻译 API（需自行申请 appid/key）。配置文件位于 `%APPDATA%/ClipboardManager/translation_config.json`，也可在托盘右键菜单 → 翻译配置中打开。

## 项目结构

```
clipboard_manager/
├── main.py                 # 入口
├── controllers/            # AppController 中央调度器
├── core/                   # 剪贴板监控、格式检测、哈希去重、翻译服务
├── models/                 # 数据模型 + SQLite 数据库
├── views/                  # PySide6 UI（弹窗、托盘、历史列表）
└── utils/                  # Win32 API、主题管理、临时文件
```
## Requirements

- Windows 10+
- Python 3.10+
- PySide6 >= 6.5.0

## Quick Start

```bash
pip install -r requirements.txt
python -m clipboard_manager.main
```

## Download

从 [Releases](https://github.com/Leon-aHao/clipboard-manager-demo/releases) 页面下载 `ClipboardManager.exe`，双击运行，无需安装 Python。

## Build

```bash
pyinstaller clipboard_manager.spec
```

## Project Structure

```
clipboard_manager/
├── main.py                 # Entry point
├── controllers/            # App controller (wires signals/slots)
├── core/                   # Clipboard monitor, format detection, hashing
├── models/                 # Data models + SQLite database
├── views/                  # PySide6 UI (popup, tray, history list)
└── utils/                  # Win32 API, themes, temp files
```
