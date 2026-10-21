from __future__ import annotations

import os
import queue
import sys
import threading
import time
import tkinter as tk
from dataclasses import replace
from pathlib import Path
from tkinter import ttk

from PIL import ImageGrab, ImageTk

from . import __version__
from .core import ChangeGate, Config, UserError, ask, fingerprint, load_config, save_config
from .windows import Hotkeys, desktop_box, enable_dpi, intersects, position_window, recognize, window_box


BG = "#15191f"
PANEL = "#20262e"
TEXT = "#edf1f5"
MUTED = "#a5b0bf"
ACCENT = "#8de3c1"


def readonly(widget, text):
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", text)
    widget.configure(state="disabled")


def text_area(parent, **kwargs):
    frame = ttk.Frame(parent)
    text = tk.Text(
        frame, wrap="word", bg=PANEL, fg=TEXT, insertbackground=TEXT,
        selectbackground="#375f56", relief="flat", padx=14, pady=12,
        font=("Microsoft YaHei UI", 11), undo=False, **kwargs,
    )
    scroll = ttk.Scrollbar(frame, command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    text.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return frame, text


class RegionSelector(tk.Toplevel):
    def __init__(self, parent, screenshot, bounds, done):
        super().__init__(parent)
        self.done, self.screenshot, self.bounds = done, screenshot, bounds
        self.start = None
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="black", cursor="crosshair")
        self.canvas = tk.Canvas(self, highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.photo = ImageTk.PhotoImage(screenshot)
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.rect = self.canvas.create_rectangle(0, 0, 0, 0, outline=ACCENT, width=3)
        self.canvas.create_rectangle(20, 20, 610, 65, fill=BG, outline=BG)
        self.canvas.create_text(
            36, 42, text="拖动框选题目区域    松开确认    Esc / 右键取消",
            anchor="w", fill=TEXT, font=("Microsoft YaHei UI", 12),
        )
        self.canvas.bind("<ButtonPress-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        self.bind("<Escape>", lambda _: self.finish(None))
        self.bind("<Button-3>", lambda _: self.finish(None))
        self.protocol("WM_DELETE_WINDOW", lambda: self.finish(None))
        position_window(self, bounds)
        self.focus_force()
        self.grab_set()

    def point(self, event):
        x = max(0, min(self.screenshot.width, event.x_root - self.bounds[0]))
        y = max(0, min(self.screenshot.height, event.y_root - self.bounds[1]))
        return x, y

    def press(self, event):
        self.start = self.point(event)

    def drag(self, event):
        if self.start:
            self.canvas.coords(self.rect, *self.start, *self.point(event))

    def release(self, event):
        if self.start is None:
            return
        x, y = self.point(event)
        left, right = sorted((self.start[0], x))
        top, bottom = sorted((self.start[1], y))
        if right - left < 20 or bottom - top < 20:
            return
        crop = self.screenshot.crop((left, top, right, bottom))
        region = (left + self.bounds[0], top + self.bounds[1], right + self.bounds[0], bottom + self.bounds[1])
        self.finish((region, crop))

    def finish(self, result):
        self.grab_release()
        self.destroy()
        self.done(result)


class Settings(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("API 设置 | 框答")
        self.configure(bg=BG)
        self.resizable(True, True)
        scale = app.scale
        width = min(int(640 * scale), self.winfo_screenwidth() - 80)
        height = min(int(700 * scale), self.winfo_screenheight() - 100)
        self.geometry(f"{width}x{height}")
        self.minsize(min(int(560 * scale), width), min(int(620 * scale), height))
        self.transient(app.root)
        self.attributes("-topmost", app.pinned.get())
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        scroll_area = ttk.Frame(outer)
        scroll_area.pack(fill="both", expand=True)
        canvas = tk.Canvas(scroll_area, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll_area, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = ttk.Frame(canvas, padding=8)
        body_id = canvas.create_window(0, 0, window=body, anchor="nw")
        body.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(body_id, width=event.width))
        body.columnconfigure(0, weight=1)
        ttk.Label(body, text="连接你的模型", style="Heading.TLabel").grid(row=0, sticky="w")
        ttk.Label(body, text="支持 OpenAI 兼容的 Chat Completions 接口", style="Muted.TLabel").grid(row=1, sticky="w", pady=(4, 18))
        self.variables = {}
        row = 2
        for name, label in (("base_url", "API Base URL（可包含 /v1，或填完整接口）"),
                            ("api_key", "API Key"), ("model", "模型名称（按服务商文档填写）")):
            ttk.Label(body, text=label).grid(row=row, sticky="w", pady=(7, 4))
            var = tk.StringVar(value=getattr(app.config, name))
            self.variables[name] = var
            entry = ttk.Entry(body, textvariable=var, show="●" if name == "api_key" else "")
            entry.grid(row=row+1, sticky="ew", ipady=4)
            row += 2
        self.remember = tk.BooleanVar(value=app.remember)
        ttk.Checkbutton(body, text="记住 Key（使用当前 Windows 账户加密）", variable=self.remember).grid(row=row, sticky="w", pady=(10, 6))
        row += 1
        ttk.Label(body, text="识别方式").grid(row=row, sticky="w", pady=(8, 4))
        self.mode = tk.StringVar(value="视觉模型直接读图" if app.config.mode == "vision" else "本地 OCR + 文本模型")
        ttk.Combobox(body, state="readonly", textvariable=self.mode,
                     values=("视觉模型直接读图", "本地 OCR + 文本模型")).grid(row=row+1, sticky="ew", ipady=3)
        row += 2
        ttk.Label(body, text="读图模式发送区域截图；OCR 模式只发送识别出的文字。", style="Muted.TLabel", wraplength=int(560*scale)).grid(row=row, sticky="w", pady=(6, 10))
        row += 1
        timing = ttk.Frame(body)
        timing.grid(row=row, sticky="ew")
        ttk.Label(timing, text="扫描间隔（秒）").pack(side="left")
        self.interval = tk.StringVar(value=str(app.config.interval))
        ttk.Spinbox(timing, from_=1, to=60, increment=1, textvariable=self.interval, width=6).pack(side="left", padx=(8, 24))
        ttk.Label(timing, text="超时（秒）").pack(side="left")
        self.timeout = tk.StringVar(value=str(app.config.timeout))
        ttk.Spinbox(timing, from_=10, to=300, increment=10, textvariable=self.timeout, width=6).pack(side="left", padx=8)
        row += 1
        ttk.Label(body, text="答题要求（可自行修改）").grid(row=row, sticky="w", pady=(16, 6))
        row += 1
        self.prompt = tk.Text(body, height=5, wrap="word", bg=PANEL, fg=TEXT, insertbackground=TEXT,
                              relief="flat", font=("Microsoft YaHei UI", 10), padx=10, pady=8)
        self.prompt.insert("1.0", app.config.prompt)
        self.prompt.grid(row=row, sticky="nsew")
        row += 1
        self.status = tk.StringVar()
        ttk.Label(outer, textvariable=self.status, style="Muted.TLabel", wraplength=int(560*scale)).pack(anchor="w", pady=(8, 4))
        row += 1
        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(8, 0))
        self.test_button = ttk.Button(actions, text="测试连接（会调用 API）", command=self.test)
        self.test_button.pack(side="left")
        ttk.Button(actions, text="保存", style="Accent.TButton", command=self.save).pack(side="right")
        ttk.Button(actions, text="取消", command=self.destroy).pack(side="right", padx=8)
        self.bind("<Escape>", lambda _: self.destroy())

    def values(self):
        try:
            config = Config(
                **{k: v.get().strip() for k, v in self.variables.items()},
                mode="vision" if self.mode.get() == "视觉模型直接读图" else "ocr",
                interval=float(self.interval.get()), timeout=float(self.timeout.get()),
                prompt=self.prompt.get("1.0", "end").strip(),
            )
            config.validate()
            return config
        except ValueError:
            raise UserError("扫描间隔和超时必须填写数字。") from None

    def save(self):
        try:
            config = self.values()
            save_config(self.app.config_path, config, self.remember.get())
        except (UserError, OSError) as exc:
            self.status.set(str(exc) if isinstance(exc, UserError) else "无法保存设置，请检查配置目录权限。")
            return
        self.app.config, self.app.remember = config, self.remember.get()
        self.app.generation += 1
        self.app.gate = ChangeGate()
        self.app.status.set("设置已保存，可以框选题目。")
        self.destroy()

    def test(self):
        if self.app.busy:
            self.status.set("请等待当前请求结束后再测试。")
            return
        try:
            config = replace(self.values(), mode="ocr")
        except UserError as exc:
            self.status.set(str(exc))
            return
        self.app.busy = True
        self.app.requests += 1
        self.app.count_text.set(f"本次 API 请求 {self.app.requests}")
        self.test_button.configure(state="disabled")
        self.status.set("正在测试文本请求，产生少量 API 用量…")

        def worker():
            try:
                ask(config, text="这是一条连接测试消息，请回复：连接成功。")
                result = "连接成功。读图能力需用真实题目截图验证。"
            except UserError as exc:
                result = str(exc)
            except Exception:
                result = "连接测试失败，请检查接口设置。"
            self.app.events.put(("test", self, result))

        threading.Thread(target=worker, daemon=True).start()


class Application:
    def __init__(self, root, config_path=None, hotkeys=True):
        self.root = root
        root.title(f"框答  {__version__}")
        self.scale = root.winfo_fpixels("1i") / 96
        root.geometry(f"{int(460*self.scale)}x{int(660*self.scale)}")
        root.minsize(int(400*self.scale), int(480*self.scale))
        root.configure(bg=BG)
        self.config_path = config_path or Path(os.environ.get("APPDATA", str(Path.home()))) / "ScreenAnswer/config.json"
        self.config, self.remember, warning = load_config(self.config_path)
        self.events = queue.Queue()
        self.region = None
        self.selector = None
        self.settings_window = None
        self.busy = False
        self.cancel_pending = threading.Event()
        self.closed = False
        self.generation = 0
        self.gate = ChangeGate()
        self.next_scan = 0
        self.last_sent = 0
        self.requests = 0
        self.answer = ""
        self.pinned = tk.BooleanVar(value=True)
        self.automatic = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value=warning or "先配置 API，再框选屏幕上的题目。")
        self.region_text = tk.StringVar(value="尚未框选区域")
        self.count_text = tk.StringVar(value="本次 API 请求 0")
        self._style()
        self._build()
        root.attributes("-topmost", True)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.hotkeys = Hotkeys() if hotkeys else None
        registered = self.hotkeys.registered if self.hotkeys else []
        self.shortcut_text.set("Ctrl+Alt+Q 框选    Ctrl+Alt+A 识别" if len(registered) == 2 else "快捷键未全部注册，可使用窗口按钮")
        root.after(80, self.tick)

    def _style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", font=("Microsoft YaHei UI", 10), background=BG, foreground=TEXT)
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Heading.TLabel", font=("Microsoft YaHei UI", 20, "bold"))
        style.configure("Muted.TLabel", foreground=MUTED, font=("Microsoft YaHei UI", 9))
        style.configure("TButton", background=PANEL, foreground=TEXT, borderwidth=0, padding=(12, 9))
        style.map("TButton", background=[("active", "#35404e"), ("disabled", PANEL)], foreground=[("disabled", "#6d7783")])
        style.configure("Accent.TButton", background=ACCENT, foreground="#122920", font=("Microsoft YaHei UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#b0f0d8"), ("disabled", "#506f63")], foreground=[("disabled", "#b3c7bd")])
        style.configure("TCheckbutton", background=BG, foreground=TEXT)
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("TEntry", fieldbackground=PANEL, foreground=TEXT, insertcolor=TEXT, bordercolor=PANEL)
        style.configure("TSpinbox", fieldbackground=PANEL, foreground=TEXT, arrowcolor=TEXT)
        style.configure("TCombobox", fieldbackground=PANEL, foreground=TEXT, arrowcolor=TEXT)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", TEXT)])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, padding=(14, 8))
        style.map("TNotebook.Tab", background=[("selected", "#34443f")])

    def _build(self):
        body = ttk.Frame(self.root, padding=20)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(5, weight=1)
        header = ttk.Frame(body)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="框答", style="Heading.TLabel").pack(side="left")
        ttk.Button(header, text="API 设置", command=self.settings).pack(side="right")
        ttk.Label(body, text="框选一道题，让答案留在手边。", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 18))
        actions = ttk.Frame(body)
        actions.grid(row=2, column=0, sticky="ew")
        self.select_button = ttk.Button(actions, text="框选区域", style="Accent.TButton", command=self.select)
        self.select_button.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.scan_button = ttk.Button(actions, text="识别一次", command=self.scan)
        self.scan_button.pack(side="left", fill="x", expand=True)
        ttk.Label(body, textvariable=self.region_text, style="Muted.TLabel").grid(row=3, column=0, sticky="w", pady=(10, 6))
        options = ttk.Frame(body)
        options.grid(row=4, column=0, sticky="ew", pady=(0, 14))
        ttk.Checkbutton(options, text="自动扫描变化", variable=self.automatic, command=self.toggle_auto).pack(side="left")
        ttk.Checkbutton(options, text="窗口置顶", variable=self.pinned,
                        command=lambda: self.root.attributes("-topmost", self.pinned.get())).pack(side="right")
        notebook = ttk.Notebook(body)
        notebook.grid(row=5, column=0, sticky="nsew")
        answer_frame, self.output = text_area(notebook, height=10)
        notebook.add(answer_frame, text="答案")
        source = ttk.Frame(notebook, padding=8)
        notebook.add(source, text="题目预览")
        self.preview = ttk.Label(source, text="框选后在这里查看实际发送的区域。", anchor="center")
        self.preview.pack(fill="x", pady=(8, 12))
        source_frame, self.source_text = text_area(source, height=4)
        source_frame.pack(fill="both", expand=True)
        readonly(self.source_text, "视觉模式由模型识别题目；OCR 模式会显示本地提取的文字。")
        readonly(self.output, "准备好了\n\n1  打开 API 设置，填写地址、Key 和模型。\n\n2  框选屏幕中的题目。\n\n3  点击「识别一次」，或打开自动扫描。\n\n把小窗放在题目区域外，方便连续查看答案。")
        footer = ttk.Frame(body)
        footer.grid(row=6, column=0, sticky="ew", pady=(12, 8))
        ttk.Button(footer, text="复制答案", command=self.copy).pack(side="left")
        ttk.Label(footer, textvariable=self.count_text, style="Muted.TLabel").pack(side="right")
        ttk.Label(body, textvariable=self.status, wraplength=int(400*self.scale), style="Muted.TLabel").grid(row=7, column=0, sticky="ew")
        self.shortcut_text = tk.StringVar()
        ttk.Label(body, textvariable=self.shortcut_text, style="Muted.TLabel").grid(row=8, column=0, sticky="w", pady=(8, 0))

    def settings(self):
        if self.selector is not None:
            return
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        self.stop_auto()
        self.settings_window = Settings(self)

    def stop_auto(self):
        self.automatic.set(False)
        self.generation += 1
        self.cancel_pending.set()

    def toggle_auto(self):
        if self.automatic.get():
            if self.selector is not None or (self.settings_window is not None and self.settings_window.winfo_exists()):
                self.automatic.set(False)
                return
            if self.region is None or not self.valid_config():
                self.automatic.set(False)
                if self.region is None:
                    self.status.set("先框选一个题目区域。")
                return
            if not self.answer:
                self.gate = ChangeGate()
            self.next_scan = 0
            self.status.set("自动扫描已开启：画面稳定且有变化时请求答案。")
        else:
            self.stop_auto()
            self.status.set("自动扫描已暂停；已发出的请求可能仍产生 API 用量。")

    def valid_config(self):
        try:
            self.config.validate()
            return True
        except UserError as exc:
            self.status.set(str(exc))
            return False

    def select(self):
        if self.selector is not None:
            return
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.status.set("请先关闭 API 设置窗口。")
            return
        self.stop_auto()
        self.select_button.configure(state="disabled")
        self.root.withdraw()
        self.root.after(250, self._open_selector)

    def _open_selector(self):
        try:
            bounds = desktop_box()
            screenshot = ImageGrab.grab(all_screens=True).convert("RGB")
            if screenshot.size != (bounds[2]-bounds[0], bounds[3]-bounds[1]):
                raise UserError("屏幕缩放或布局已变化，请重启程序后重新框选。")
            self.selector = RegionSelector(self.root, screenshot, bounds, self.selected)
        except Exception:
            self.selected(None)
            self.status.set("无法截图。请确认当前是可交互的 Windows 桌面。")

    def selected(self, result):
        self.selector = None
        self.root.deiconify()
        self.root.lift()
        self.select_button.configure(state="normal")
        if result is None:
            self.status.set("已取消框选。")
            return
        self.region, image = result
        self.gate = ChangeGate()
        x1, y1, x2, y2 = self.region
        self.region_text.set(f"区域  {x2-x1} × {y2-y1} px    位置  {x1}, {y1}")
        self.show_preview(image)
        self.answer = ""
        readonly(self.output, "区域已就绪。点击「识别一次」或开启自动扫描。")
        self.status.set("已框选。请把小窗移到题目区域外，再开始识别。")

    def show_preview(self, image):
        thumb = image.copy()
        thumb.thumbnail((360, 180))
        self.preview_photo = ImageTk.PhotoImage(thumb)
        self.preview.configure(image=self.preview_photo, text="")

    def capture(self):
        if self.region is None:
            raise UserError("请先框选题目区域。")
        bounds = desktop_box()
        if (self.region[0] < bounds[0] or self.region[1] < bounds[1]
                or self.region[2] > bounds[2] or self.region[3] > bounds[3]):
            raise UserError("原区域已不在屏幕内，请重新框选。")
        if intersects(window_box(self.root), self.region):
            raise UserError("小窗遮住了题目。请将小窗移到框选区域之外。")
        return ImageGrab.grab(bbox=self.region, all_screens=True).convert("RGB")

    def scan(self, automatic=False):
        if self.selector is not None or self.busy:
            if not automatic:
                self.status.set("当前请求尚未结束，请稍候。")
            return
        if self.settings_window is not None and self.settings_window.winfo_exists():
            return
        if not self.valid_config():
            self.stop_auto()
            return
        try:
            image = self.capture()
        except UserError as exc:
            self.status.set(str(exc))
            if not automatic:
                self.stop_auto()
            return
        except OSError:
            self.stop_auto()
            self.status.set("截图失败，请重新框选区域。")
            return
        frame = fingerprint(image)
        if automatic and not self.gate.ready(frame):
            return
        # A single in-flight job and a cooldown prevent duplicate billing.
        if automatic and time.monotonic() - self.last_sent < max(3, self.config.interval):
            return
        self.gate.mark(frame)
        self.show_preview(image)
        self.busy = True
        self.cancel_pending = threading.Event()
        canceled = self.cancel_pending
        self.last_sent = time.monotonic()
        generation, config = self.generation, replace(self.config)
        self.answer = ""
        readonly(self.output, "正在读取题目并生成答案…")
        readonly(self.source_text, "正在使用 Windows 本地 OCR…" if config.mode == "ocr" else "此区域截图将发送到你配置的视觉 API。")
        self.status.set("本地识别中…" if config.mode == "ocr" else "正在请求模型…")

        def worker():
            try:
                text = recognize(image) if config.mode == "ocr" else ""
                if canceled.is_set():
                    self.events.put(("canceled", generation, ""))
                    return
                self.events.put(("request", generation, text))
                answer = ask(config, image=image, text=text)
                self.events.put(("answer", generation, answer))
            except UserError as exc:
                self.events.put(("error", generation, str(exc)))
            except Exception:
                self.events.put(("error", generation, "处理失败。请检查截图、OCR 组件和 API 设置后重试。"))

        threading.Thread(target=worker, daemon=True).start()

    def process_event(self, event):
        kind, generation, text = event
        if kind == "test":
            self.busy = False
            if generation.winfo_exists():
                generation.test_button.configure(state="normal")
                generation.status.set(text)
            return
        if kind == "request":
            self.requests += 1
            self.count_text.set(f"本次 API 请求 {self.requests}")
        if kind in ("answer", "error", "canceled"):
            self.busy = False
        if generation != self.generation:
            if kind in ("answer", "error", "canceled") and not self.answer:
                readonly(self.output, "上一次请求已结束，其结果已取消。可再次识别。")
            return
        if kind == "request":
            self.status.set("正在请求模型…")
            if text:
                readonly(self.source_text, text)
        elif kind == "answer":
            self.answer = text
            readonly(self.output, text)
            self.status.set("答案已更新，正在等待区域变化。" if self.automatic.get() else "答案已更新。")
        elif kind == "error":
            self.stop_auto()
            readonly(self.output, "暂时没有获得答案\n\n" + text)
            self.status.set("自动扫描已暂停，可调整后手动重试。")

    def tick(self):
        if self.closed:
            return
        try:
            while True:
                self.process_event(self.events.get_nowait())
        except queue.Empty:
            pass
        if self.hotkeys:
            for key in self.hotkeys.poll():
                if key == 1:
                    self.select()
                elif key == 2:
                    self.scan()
        now = time.monotonic()
        if self.automatic.get() and not self.busy and self.selector is None and now >= self.next_scan:
            self.next_scan = now + self.config.interval
            self.scan(automatic=True)
        self.root.after(80, self.tick)

    def copy(self):
        if self.answer:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.answer)
            self.status.set("答案已复制。")
        else:
            self.status.set("还没有可复制的答案。")

    def close(self):
        self.closed = True
        self.stop_auto()
        if self.hotkeys:
            self.hotkeys.close()
        self.root.destroy()


def main():
    if sys.platform != "win32":
        raise SystemExit("框答目前支持 Windows 10 / 11。")
    enable_dpi()
    root = tk.Tk()
    app = Application(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.close()


if __name__ == "__main__":
    main()
