"""Local HTTP integration tests using only synthetic fixture documents."""
import hashlib
import http.client
import importlib.util
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

WORKBENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKBENCH))
spec = importlib.util.spec_from_file_location("workbench_test_server", WORKBENCH / "serve.py")
serve = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = serve
spec.loader.exec_module(serve)


def snapshot(root):
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file()
    }


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.fixture_base = Path(cls.temp.name)
        cls.root = cls.fixture_base / "workbench"
        (cls.root / "results").mkdir(parents=True)
        (cls.root / "templates").mkdir()
        (cls.root / "workbench.html").write_text("<!doctype html><title>Synthetic test workbench</title>")
        (cls.root / "results/workbench-data.json").write_text(json.dumps({
            "packets": [{"issue_key": "IRS-65265", "summary": "Synthetic packet fixture"}],
            "execution_enabled": False,
        }))
        (cls.root / "templates/time_observations.csv").write_text("pair_id,action_id,mode\n")
        source = cls.fixture_base / "adf-sentinel/data/raw"
        source.mkdir(parents=True)
        (source / "private-source.json").write_text('{"synthetic_private_value":"never served"}')
        cls.root_patch = patch.object(serve, "ROOT", cls.root)
        cls.root_patch.start()
        cls.addClassCleanup(cls.root_patch.stop)
        cls.server = serve.make_server(0)
        cls.addClassCleanup(cls.server.server_close)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.addClassCleanup(cls._stop_server)
        cls.port = cls.server.server_address[1]
        cls.origin = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def _stop_server(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=3)

    def setUp(self):
        self.before = snapshot(self.fixture_base)

    def tearDown(self):
        self.assertEqual(snapshot(self.fixture_base), self.before, "HTTP requests must not mutate workbench or source evidence")

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def post_record(self, record, **headers):
        request_headers = {"Content-Type": "application/json", "Origin": self.origin}
        request_headers.update(headers)
        status, response_headers, body = self.request("POST", "/api/check", json.dumps(record).encode(), request_headers)
        return status, response_headers, json.loads(body)

    @staticmethod
    def complete_fixture_record():
        return {
            "schema_version": 1, "id": "synthetic-test-record", "issue_key": "IRS-65265",
            "source_links": ["https://example.com/synthetic-requirement"],
            "evidence": [{"kind": "source_requirement", "url": "https://example.com/synthetic-requirement", "note": "Synthetic test evidence, not a real approval."}],
            "release": "Synthetic fixture release", "variants": ["DNA"],
            "operation": "investigation", "question": "What evidence is missing?",
            "acceptance_checks": ["Reviewer can trace the source requirement."],
            "reviewer_decision": {"status": "pending", "scope": "current_record"},
        }

    def test_serves_only_prepared_data_and_downloads(self):
        for path, expected_type in (("/", "text/html"), ("/api/data", "application/json"), ("/download/timing-template", "text/csv")):
            with self.subTest(path=path):
                status, headers, body = self.request("GET", path)
                self.assertEqual(status, 200)
                self.assertTrue(headers["Content-Type"].startswith(expected_type))
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
                self.assertTrue(body)
        status, headers, body = self.request("GET", "/download/packet/IRS-65265")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["summary"], "Synthetic packet fixture")
        self.assertIn("attachment", headers["Content-Disposition"])

    def test_incomplete_real_issue_draft_lists_missing_information_without_execution(self):
        status, _, result = self.post_record({"schema_version": 1, "id": "draft-65265", "issue_key": "IRS-65265", "operation": "parameter_metadata"})
        self.assertEqual(status, 200)
        self.assertFalse(result["review_ready"])
        self.assertFalse(result["execution_enabled"])
        self.assertIn("target_path", result["missing_fields"])
        self.assertIn("expected_old_value", result["missing_fields"])
        self.assertIn("new_value", result["missing_fields"])

    def test_unknown_command_rejected_without_execution(self):
        record = self.complete_fixture_record()
        record["command"] = "synthetic command must never execute"
        status, _, result = self.post_record(record)
        self.assertEqual(status, 200)
        self.assertFalse(result["review_ready"])
        self.assertFalse(result["execution_enabled"])
        self.assertTrue(any(item["field"] == "command" for item in result["invalid_fields"]))

    def test_complete_pending_and_recorded_approved_fixtures_still_cannot_execute(self):
        record = self.complete_fixture_record()
        status, _, pending = self.post_record(record)
        self.assertEqual(status, 200)
        self.assertTrue(pending["review_ready"])
        self.assertFalse(pending["human_approval_present"])
        self.assertFalse(pending["execution_enabled"])
        record["reviewer_decision"] = {
            "status": "approved", "reviewer": "Synthetic test reviewer",
            "decided_at": "2026-11-03T10:00:00-08:00", "scope": "current_record",
            "evidence_url": "https://example.com/synthetic-test-decision",
            "note": "Synthetic fixture decision only; never a real approval.",
        }
        status, _, approved = self.post_record(record)
        self.assertEqual(status, 200)
        self.assertTrue(approved["human_approval_present"])
        self.assertFalse(approved["execution_enabled"])

    def test_hostile_host_and_origin_rejected(self):
        status, _, _ = self.request("GET", "/api/data", headers={"Host": "attacker.example"})
        self.assertEqual(status, 403)
        status, _, _ = self.post_record(self.complete_fixture_record(), Origin="https://attacker.example")
        self.assertEqual(status, 403)
        status, _, _ = self.post_record(self.complete_fixture_record(), Host="127.0.0.1:1")
        self.assertEqual(status, 403)

    def test_huge_bad_and_nonobject_json_rejected(self):
        for payload in (b"{broken", b"[]", b"\xff"):
            with self.subTest(payload=payload):
                status, _, _ = self.request("POST", "/api/check", payload, {"Content-Type": "application/json", "Origin": self.origin})
                self.assertEqual(status, 400)
        status, _, _ = self.request("POST", "/api/check", b"x" * (serve.MAX_REQUEST + 1), {"Content-Type": "application/json", "Origin": self.origin})
        self.assertEqual(status, 413)
        status, _, _ = self.request("POST", "/api/check", b"{}", {"Content-Type": "text/plain", "Origin": self.origin})
        self.assertEqual(status, 415)

    def test_traversal_raw_sources_and_unknown_write_routes_inaccessible(self):
        paths = (
            "/../adf-sentinel/data/raw/private-source.json",
            "/%2e%2e/adf-sentinel/data/raw/private-source.json",
            "/data/raw/private-source.json", "/results/../serve.py", "/serve.py",
            "/download/packet/..", "/download/packet/not-a-packet",
        )
        for path in paths:
            with self.subTest(path=path):
                status, _, body = self.request("GET", path)
                self.assertEqual(status, 404)
                self.assertNotIn(b"never served", body)
        status, _, _ = self.request("POST", "/api/execute", b"{}", {"Content-Type": "application/json", "Origin": self.origin})
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
