"""Capture only this app's client area with simulated data, without API calls."""
import sys
import tkinter as tk
from pathlib import Path

from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from screenanswer.app import Application, readonly
from screenanswer.core import Config
from screenanswer.windows import enable_dpi


def capture(window, path):
    window.update()
    x, y = window.winfo_rootx(), window.winfo_rooty()
    ImageGrab.grab(bbox=(x, y, x + window.winfo_width(), y + window.winfo_height()), all_screens=True).save(path)


def main():
    enable_dpi()
    project = Path(__file__).resolve().parents[1]
    output = project / "docs/images"
    output.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    app = Application(root, project / ".publish/screenshot-config.json", hotkeys=False)
    try:
        app.config = Config(base_url="https://api.example.com/v1", model="YOUR_VISION_MODEL", api_key="")
        app.region_text.set("示例区域  800 × 280 px")
        app.count_text.set("界面演示，未调用 API")
        app.status.set("截图使用示例数据；实际答案由你配置的模型生成。")
        app.shortcut_text.set("Ctrl+Alt+Q 框选    Ctrl+Alt+A 识别")
        readonly(app.output,
                 "【题目】\n12 + 30 = ?\nA. 32    B. 42    C. 52\n\n"
                 "【答案】\nB. 42\n\n【简要解析】\n12 + 30 = 42。\n\n"
                 "此处为界面展示用的示例答案。")
        root.update()
        root.geometry(f"+{max(20, (root.winfo_screenwidth()-root.winfo_width())//2)}+40")
        capture(root, output / "main.png")
        app.settings()
        dialog = app.settings_window
        dialog.update()
        dialog.geometry(f"+{max(20, (dialog.winfo_screenwidth()-dialog.winfo_width())//2)}+40")
        capture(dialog, output / "settings.png")
        dialog.destroy()
    finally:
        app.close()
    print("Saved clean application screenshots with simulated data")


if __name__ == "__main__":
    main()
