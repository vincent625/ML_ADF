import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from app import handler_for
from sentinel import Sentinel, generate


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="sentinel-http-")
        cls.root = Path(cls.directory.name) / "data"
        cls.engine = Sentinel(cls.root)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(cls.engine))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.directory.cleanup()

    def request(self, route, payload=None, headers=None):
        options = {}
        if payload is not None:
            options["data"] = json.dumps(payload).encode()
            options["headers"] = {"Content-Type": "application/json", **(headers or {})}
        with urllib.request.urlopen(urllib.request.Request(self.base + route, **options)) as response:
            return response.status, response.headers, response.read()

    def test_static_app_and_record_driven_counters(self):
        _, headers, body = self.request("/")
        self.assertIn(b"ADF Sentinel", body)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        _, _, body = self.request("/api/state?scenario=wrong-primer")
        data = json.loads(body)
        self.assertEqual(data["summary"], {"pass": 83, "fail": 1})
        self.assertEqual(data["test_count"], 84)

    def test_http_review_retest_export_identity(self):
        _, _, body = self.request("/api/preview", {"scenario": "wrong-kit", "test_id": "dna:panel_kit"})
        proposal = json.loads(body)
        self.request("/api/apply", {"proposal_id": proposal["id"], "reviewer": "HTTP test"})
        _, _, body = self.request("/api/run", {"scenario": "wrong-kit"})
        run = json.loads(body)
        self.assertTrue(all(r["status"] == "pass" for r in run["results"]))
        _, headers, body = self.request("/api/export?scenario=wrong-kit")
        report = json.loads(body)
        self.assertEqual(report["sandbox"]["latest"]["id"], run["id"])
        self.assertIn("attachment", headers["Content-Disposition"])

    def test_cross_origin_mutations_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as captured:
            self.request("/api/run", {"scenario": "control"}, {"Origin": "https://untrusted.invalid"})
        self.assertEqual(captured.exception.code, 403)
        captured.exception.close()

    def test_invalid_input_explicit_error(self):
        with self.assertRaises(urllib.error.HTTPError) as captured:
            self.request("/api/run", {"scenario": "../not-a-sandbox"})
        self.assertEqual(captured.exception.code, 400)
        self.assertIn("Unknown sandbox", captured.exception.read().decode())
        captured.exception.close()

    def test_missing_route_is_not_success(self):
        with self.assertRaises(urllib.error.HTTPError) as captured:
            self.request("/missing")
        self.assertEqual(captured.exception.code, 404)
        captured.exception.close()


if __name__ == "__main__":
    unittest.main()
