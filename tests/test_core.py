import base64
import io
import json
import tempfile
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageDraw

from screenanswer.core import (
    ChangeGate, Config, UserError, ask, endpoint, fingerprint,
    load_config, make_payload, save_config,
)
from screenanswer.windows import intersects


@contextmanager
def fake_api(status=200, body=None, redirect=None):
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append((self.path, self.headers.get("Authorization"), payload))
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            if redirect:
                self.send_header("Location", redirect)
            self.end_headers()
            data = body if body is not None else {"choices": [{"message": {"content": "【答案】4"}}]}
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", seen
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class CoreTests(unittest.TestCase):
    def test_endpoint_and_security(self):
        self.assertEqual(endpoint("https://example.com/v1/"), "https://example.com/v1/chat/completions")
        self.assertEqual(endpoint("https://example.com/v1/chat/completions/"), "https://example.com/v1/chat/completions")
        for url in ("http://remote.example/v1", "https://user:secret@example.com/v1", "file:///tmp/x",
                    "https://example.com/v1?key=secret", "https://example.com:wrong/v1", "https://example.com/responses"):
            with self.subTest(url=url), self.assertRaises(UserError):
                endpoint(url)

    def test_settings_validation(self):
        for changes in ({"model": ""}, {"api_key": ""}, {"api_key": "a\nb"}, {"interval": 0},
                        {"timeout": float("nan")}, {"mode": "bad"}, {"prompt": ""}):
            config = Config(model="vision-test", api_key="test-only")
            for key, value in changes.items():
                setattr(config, key, value)
            with self.subTest(changes=changes), self.assertRaises(UserError):
                config.validate()

    def test_image_payload(self):
        config = Config(model="vision-test", api_key="test-only")
        payload = make_payload(config, Image.new("RGB", (3000, 100), "white"))
        image_url = payload["messages"][1]["content"][1]["image_url"]["url"]
        image = Image.open(io.BytesIO(base64.b64decode(image_url.split(",")[1])))
        self.assertEqual(image.width, 2560)
        self.assertEqual(payload["model"], "vision-test")
        self.assertNotIn("test-only", json.dumps(payload))

    def test_local_api_vision_and_ocr(self):
        with fake_api() as (url, seen):
            config = Config(base_url=url, model="mock", api_key="test-only")
            self.assertEqual(ask(config, Image.new("RGB", (60, 60))), "【答案】4")
            config.mode = "ocr"
            self.assertEqual(ask(config, text="2+2=?"), "【答案】4")
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0][0], "/v1/chat/completions")
        self.assertEqual(seen[0][1], "Bearer test-only")
        self.assertIn("2+2", seen[1][2]["messages"][1]["content"])
        self.assertNotIn("image_url", json.dumps(seen[1][2]))

    def test_redirection_does_not_forward_credentials(self):
        with fake_api() as (target, target_seen):
            with fake_api(307, redirect=target) as (source, _):
                with self.assertRaisesRegex(UserError, "重定向"):
                    ask(Config(base_url=source, model="mock", api_key="test-only", mode="ocr"), text="test")
        self.assertEqual(target_seen, [])

    def test_api_failures_and_refusal(self):
        for status, body, expected in (
            (401, {"secret": "should-not-appear"}, "Key"),
            (429, {}, "额度"),
            (200, {"choices": []}, "格式"),
            (200, {"choices": [{"message": {"content": None, "refusal": "no"}}]}, "拒绝"),
        ):
            with self.subTest(status=status), fake_api(status, body) as (url, _):
                with self.assertRaisesRegex(UserError, expected) as caught:
                    ask(Config(base_url=url, model="mock", api_key="test-only", mode="ocr"), text="test")
                self.assertNotIn("should-not-appear", str(caught.exception))

    def test_gate_dedup_settling_and_small_option_change(self):
        gate = ChangeGate()
        image = Image.new("RGB", (800, 500), "white")
        a = fingerprint(image)
        self.assertFalse(gate.ready(a))
        self.assertTrue(gate.ready(a))
        gate.mark(a)
        self.assertFalse(gate.ready(a))
        ImageDraw.Draw(image).rectangle((100, 100, 110, 120), fill="black")
        b = fingerprint(image)
        self.assertFalse(gate.ready(b))
        self.assertTrue(gate.ready(b))
        gate.mark(b)
        self.assertFalse(gate.ready(b))

    def test_dpapi_config_no_plaintext_and_forget(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            config = Config(model="mock", api_key="private-test-key")
            save_config(path, config, remember=True)
            self.assertNotIn("private-test-key", path.read_text(encoding="utf-8"))
            loaded, remembered, warning = load_config(path)
            self.assertEqual(loaded.api_key, "private-test-key")
            self.assertTrue(remembered)
            self.assertFalse(warning)
            save_config(path, config, remember=False)
            self.assertEqual(load_config(path)[0].api_key, "")
            self.assertNotIn("private-test-key", path.read_text(encoding="utf-8"))
            path.write_text('{"interval": "bad"}', encoding="utf-8")
            self.assertTrue(load_config(path)[2])

    def test_overlap_negative_coordinates(self):
        self.assertTrue(intersects((-1920, 0, -1000, 600), (-1500, 10, -1200, 50)))
        self.assertFalse(intersects((0, 0, 100, 100), (100, 0, 200, 100)))


if __name__ == "__main__":
    unittest.main()
