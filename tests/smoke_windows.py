"""Exercise our own windows against local fake APIs; never uses a real key."""
import json
import time
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont, ImageGrab

from screenanswer.app import Application, readonly
from screenanswer.core import Config
from screenanswer.windows import enable_dpi, position_window, recognize, window_box
from tests.test_core import fake_api


ARTIFACTS = Path(__file__).resolve().parents[1] / "test-artifacts"


def pump(root, predicate=lambda: False, timeout=1):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        root.update()
        if predicate():
            return
        time.sleep(0.02)
    if not predicate():
        raise AssertionError("UI timed out waiting for expected state")


def main():
    enable_dpi()
    ARTIFACTS.mkdir(exist_ok=True)
    root = tk.Tk()
    app = Application(root, ARTIFACTS / "smoke-config.json", hotkeys=False)
    fixture = None
    try:
        # Test the real native OCR engine with a generated fixture image.
        image = Image.new("RGB", (900, 260), "white")
        draw = ImageDraw.Draw(image)
        draw.text((28, 30), "Question: What is 12 + 30?", fill="black",
                  font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 36))
        draw.text((28, 100), "A. 32     B. 42     C. 52", fill="black",
                  font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 36))
        extracted = recognize(image)
        assert "30" in extracted and "42" in extracted, extracted
        print("PASS native Windows OCR, temp image cleanup")

        fixture = tk.Toplevel(root)
        fixture.title("ScreenAnswer test question")
        fixture.configure(bg="white")
        tk.Label(fixture, text="Question: What is 12 + 30?\n\nA. 32     B. 42     C. 52",
                 font=("Arial", 24), bg="white", fg="black", justify="left").pack(padx=30, pady=30)
        root.update()
        position_window(fixture, (80, 120, 930, 470))
        position_window(root, (1100, 120, 1100+int(460*app.scale), 120+int(660*app.scale)))
        root.update()

        answer = "【题目】\n12 + 30 = ?\nA. 32    B. 42    C. 52\n\n【答案】\nB. 42\n\n【简要解析】\n12 + 30 = 42。\n\n（本机模拟 API 测试结果）"
        response = {"choices": [{"message": {"content": answer}}]}
        with fake_api(body=response) as (url, seen):
            app.config = Config(base_url=url, model="local-test", api_key="test-only")
            app.select()
            pump(root, lambda: app.selector is not None, timeout=3)
            selector = app.selector
            # Select only the generated test question from the frozen desktop.
            selector.press(SimpleNamespace(x_root=100, y_root=160))
            selector.drag(SimpleNamespace(x_root=900, y_root=440))
            selector.release(SimpleNamespace(x_root=900, y_root=440))
            assert app.region == (100, 160, 900, 440), app.region
            assert app.selector is None
            app.scan()
            pump(root, lambda: not app.busy, timeout=5)
            assert app.answer == answer
            assert len(seen) == 1
            app.copy()
            assert root.clipboard_get() == answer
            root.clipboard_clear()
            print("PASS real region overlay, physical capture, fake vision API, answer, clipboard")

            app.config.mode = "ocr"
            app.scan()
            pump(root, lambda: not app.busy, timeout=35)
            assert app.answer == answer, app.output.get("1.0", "end")
            text_payload = seen[-1][2]["messages"][1]["content"]
            assert isinstance(text_payload, str) and "42" in text_payload
            assert len(seen) == 2
            print("PASS captured question -> real OCR -> fake text API -> answer window")

            # Unchanged auto scans must not call the server again.
            app.config.mode = "vision"
            app.automatic.set(True)
            app.next_scan = time.monotonic() + 100
            for _ in range(3):
                app.scan(automatic=True)
                root.update()
            assert len(seen) == 2, "duplicate API call on unchanged frame"

            # Settled question change must create exactly one new request.
            fixture.winfo_children()[0].configure(text="Question: What is 20 + 22?\n\nA. 32     B. 42     C. 52")
            root.update()
            app.last_sent = 0
            app.scan(automatic=True)
            assert not app.busy
            app.scan(automatic=True)
            pump(root, lambda: not app.busy, timeout=5)
            assert len(seen) == 3
            print("PASS auto dedup, question change settling, one request")
            app.stop_auto()

            app.scan()
            assert app.busy
            app.stop_auto()
            pump(root, lambda: not app.busy, timeout=5)
            assert not app.answer
            print("PASS cancellation drops stale answer")

            app.automatic.set(True)
            app.toggle_auto()
            app.next_scan = time.monotonic() + 100
            app.last_sent = 0
            before_resume = len(seen)
            app.scan(automatic=True)
            app.scan(automatic=True)
            pump(root, lambda: not app.busy, timeout=5)
            assert len(seen) == before_resume + 1
            app.stop_auto()
            print("PASS resume retries canceled frame")

            # Settings are our own UI; verify save and key persistence behavior.
            app.settings()
            dialog = app.settings_window
            dialog.test()
            pump(root, lambda: not app.busy, timeout=5)
            assert dialog.status.get().startswith("连接成功")
            dialog.remember.set(True)
            dialog.save()
            assert not dialog.winfo_exists()
            persisted = app.config_path.read_text(encoding="utf-8")
            assert "test-only" not in persisted
            assert json.loads(persisted)["protected_key"]
            print("PASS settings connection test and save with encrypted API key")

            # A canceled OCR job must not send a request after recognition ends.
            app.config.mode = "ocr"
            before = len(seen)
            with patch("screenanswer.app.recognize", side_effect=lambda _: (time.sleep(0.15) or "2+2=?")):
                app.scan()
                app.stop_auto()
                pump(root, lambda: not app.busy, timeout=3)
            assert len(seen) == before
            print("PASS cancel-before-send prevents network call")

            # Save a screenshot of only our own app, with an explicit test label.
            root.geometry(f"{int(400*app.scale)}x{int(480*app.scale)}")
            root.update()
            last_label = root.winfo_children()[0].winfo_children()[-1]
            assert last_label.winfo_rooty() + last_label.winfo_height() <= root.winfo_rooty() + root.winfo_height()
            root.geometry(f"{int(460*app.scale)}x{int(660*app.scale)}")
            readonly(app.output, answer)
            app.status.set("本机模拟接口测试已通过。等待配置真实 API。")
            app.answer = answer
            root.update()
            ImageGrab.grab(bbox=window_box(root), all_screens=True).save(ARTIFACTS / "app-preview.png")
            app.settings()
            root.update()
            ImageGrab.grab(bbox=window_box(app.settings_window), all_screens=True).save(ARTIFACTS / "settings-preview.png")
            app.settings_window.destroy()

        with fake_api(status=429, body={}) as (url, seen):
            app.config = Config(base_url=url, model="mock", api_key="test-only")
            app.automatic.set(True)
            app.next_scan = time.monotonic() + 100
            app.scan()
            pump(root, lambda: not app.busy, timeout=5)
            assert not app.automatic.get()
            assert "429" in app.output.get("1.0", "end")
            assert len(seen) == 1
            print("PASS rate limit pauses automatic mode")

        # Frozen overlay also needs to cancel cleanly.
        app.select()
        pump(root, lambda: app.selector is not None, timeout=3)
        old_region = app.region
        app.selector.finish(None)
        assert app.region == old_region
        assert root.state() == "normal"
        print("PASS selector cancel restores window and region")
    finally:
        if app.selector is not None:
            app.selector.destroy()
        if fixture is not None and fixture.winfo_exists():
            fixture.destroy()
        app.close()
        if app.config_path.exists():
            app.config_path.unlink()


if __name__ == "__main__":
    main()
