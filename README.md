# Clipboard Manager

A Windows system-tray clipboard history manager built with PySide6.

## Features

- Monitors system clipboard and records text, HTML, images, files, and color values
- Glass-morphism popup UI with mouse-follow glow animation
- Drag items directly to other applications
- Pinned items protected from auto-cleanup
- Dark / light theme support
- Auto-start with Windows

## Requirements

- Python 3.10+
- PySide6 >= 6.5.0

## Quick Start

```bash
pip install -r requirements.txt
python -m clipboard_manager.main
```

## Build

```bash
pyinstaller clipboard_manager.spec
```

The standalone executable will be in `dist/ClipboardManager.exe`.

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
