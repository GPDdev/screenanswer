"""Launch and close only this project's packaged executable."""
import ctypes
import os
import subprocess
import time
from ctypes import wintypes
from pathlib import Path

from PIL import ImageGrab

from screenanswer.windows import enable_dpi


def main():
    enable_dpi()
    project = Path(__file__).resolve().parents[1]
    artifacts = project / "test-artifacts"
    artifacts.mkdir(exist_ok=True)
    # Test configuration is isolated from the real user's AppData.
    environment = dict(os.environ, APPDATA=str(artifacts / "exe-appdata"))
    process = subprocess.Popen([str(project / "dist/ScreenAnswer.exe")], env=environment)
    user = ctypes.windll.user32
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    found = []

    # Onefile PyInstaller launches a child; query only this exact executable's PIDs.
    def collect(hwnd, _):
        pid = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        title = ctypes.create_unicode_buffer(256)
        user.GetWindowTextW(hwnd, title, 256)
        if title.value.startswith("框答  0.1.0") and user.IsWindowVisible(hwnd):
            handle = kernel.OpenProcess(0x1000, False, pid.value)
            if handle:
                try:
                    size = wintypes.DWORD(32768)
                    path = ctypes.create_unicode_buffer(size.value)
                    if kernel.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
                        if Path(path.value).resolve() == (project / "dist/ScreenAnswer.exe").resolve():
                            found.append(hwnd)
                finally:
                    kernel.CloseHandle(handle)
        return True

    callback = callback_type(collect)
    try:
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline and not found:
            if process.poll() is not None:
                raise AssertionError(f"Packaged app exited early: {process.returncode}")
            user.EnumWindows(callback, 0)
            time.sleep(0.1)
        assert found, "Packaged main window did not appear"
        time.sleep(0.5)
        rect = wintypes.RECT()
        user.GetWindowRect(wintypes.HWND(found[0]), ctypes.byref(rect))
        ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=True).save(artifacts / "exe-preview.png")
        user.PostMessageW(found[0], 0x0010, 0, 0)
        assert process.wait(timeout=10) == 0
        print("PASS packaged EXE opens native window and exits cleanly")
    finally:
        if process.poll() is None:
            for hwnd in found:
                user.PostMessageW(hwnd, 0x0010, 0, 0)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()


if __name__ == "__main__":
    main()
