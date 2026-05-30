import ctypes
from ctypes import wintypes
from typing import Optional

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


def get_tray_rect() -> Optional[RECT]:
    hwnd = user32.FindWindowW("Shell_TrayWnd", None)
    if not hwnd:
        return None
    tray = user32.FindWindowExW(hwnd, None, "TrayNotifyWnd", None)
    if tray:
        rect = RECT()
        if user32.GetWindowRect(tray, ctypes.byref(rect)):
            return rect
    rect = RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return rect
    return None


def get_work_area() -> Optional[RECT]:
    rect = RECT()
    if user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
        return rect
    return None


def create_app_mutex(name: str = "ClipboardManager_SingleInstance") -> Optional[int]:
    mutex = kernel32.CreateMutexW(None, True, name)
    if not mutex:
        return None
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(mutex)
        return None
    return mutex


def get_exe_path() -> str:
    """Return the full path to the running executable (works in both dev and PyInstaller)."""
    import sys
    if getattr(sys, 'frozen', False):
        return sys.executable
    return sys.argv[0]


_AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_AUTOSTART_NAME = "ClipboardManager"


def is_autostart_enabled() -> bool:
    """Check if auto-start registry entry exists."""
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTOSTART_KEY, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, _AUTOSTART_NAME)
        winreg.CloseKey(key)
        return bool(value)
    except FileNotFoundError:
        return False


def set_autostart(enabled: bool):
    """Enable or disable auto-start via registry Run key."""
    import winreg
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTOSTART_KEY, 0, winreg.KEY_SET_VALUE)
    if enabled:
        exe_path = get_exe_path()
        # Wrap path in quotes for registry safety
        quoted = f'"{exe_path}"'
        winreg.SetValueEx(key, _AUTOSTART_NAME, 0, winreg.REG_SZ, quoted)
    else:
        try:
            winreg.DeleteValue(key, _AUTOSTART_NAME)
        except FileNotFoundError:
            pass
    winreg.CloseKey(key)
