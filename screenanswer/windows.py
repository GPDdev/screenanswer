from __future__ import annotations

import base64
import ctypes
import os
import subprocess
import tempfile
from ctypes import wintypes
from pathlib import Path

from .core import UserError


def enable_dpi():
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        ctypes.windll.user32.SetProcessDPIAware()


def desktop_box():
    user = ctypes.windll.user32
    x, y = user.GetSystemMetrics(76), user.GetSystemMetrics(77)
    return x, y, x + user.GetSystemMetrics(78), y + user.GetSystemMetrics(79)


def position_window(window, box):
    window.update_idletasks()
    handle = ctypes.windll.user32.GetParent(window.winfo_id())
    x1, y1, x2, y2 = box
    ctypes.windll.user32.SetWindowPos(wintypes.HWND(handle), wintypes.HWND(-1), x1, y1, x2-x1, y2-y1, 0x0040)


def window_box(window):
    handle = ctypes.windll.user32.GetParent(window.winfo_id())
    rect = wintypes.RECT()
    if not ctypes.windll.user32.GetWindowRect(wintypes.HWND(handle), ctypes.byref(rect)):
        raise UserError("无法读取窗口位置。")
    return rect.left, rect.top, rect.right, rect.bottom


def intersects(a, b):
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


class Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def _crypt(data: bytes, decrypt=False) -> bytes:
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source, target = Blob(len(data), buffer), Blob()
    if decrypt:
        ok = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)
        )
    else:
        ok = ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(source), "ScreenAnswer API key", None, None, None, 1, ctypes.byref(target)
        )
    if not ok:
        raise UserError("Windows 无法加密或解密 API Key。")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.windll.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        ctypes.windll.kernel32.LocalFree(target.data)


def protect(text):
    return base64.b64encode(_crypt(text.encode("utf-8"))).decode("ascii")


def unprotect(text):
    return _crypt(base64.b64decode(text, validate=True), decrypt=True).decode("utf-8")


def recognize(image):
    # OCR runs locally; only the extracted text is sent to the configured API.
    # Windows' file-based OCR bridge needs a short-lived temporary PNG.
    script = Path(__file__).with_name("ocr.ps1")
    with tempfile.TemporaryDirectory(prefix="screenanswer-ocr-") as folder:
        path = Path(folder) / "capture.png"
        image = image.copy()
        image.thumbnail((2500, 2500))
        image.save(path)
        powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        try:
            result = subprocess.run(
                [str(powershell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                 "-File", str(script), "-ImagePath", str(path)],
                capture_output=True, timeout=35, creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except subprocess.TimeoutExpired:
            raise UserError("本地 OCR 超时，请缩小区域或改用视觉模型。") from None
        if result.returncode:
            raise UserError("Windows OCR 不可用。请在 Windows 语言设置中安装所需语言的 OCR 组件，或改用视觉模型。")
        text = result.stdout.decode("utf-8-sig").strip()
        if not text:
            raise UserError("未识别到文字，请框选更清晰的题目或改用视觉模型。")
        return text


class Hotkeys:
    def __init__(self):
        self.registered = []
        for number, key in ((1, "Q"), (2, "A")):
            if ctypes.windll.user32.RegisterHotKey(None, number, 0x4003, ord(key)):
                self.registered.append(number)

    def poll(self):
        msg = wintypes.MSG()
        found = []
        while ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), None, 0x0312, 0x0312, 1):
            found.append(int(msg.wParam))
        return found

    def close(self):
        for number in self.registered:
            ctypes.windll.user32.UnregisterHotKey(None, number)
