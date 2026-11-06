from __future__ import annotations

import collections
import hashlib
import json
import mimetypes
import threading
import zipfile
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .common import ROOT, digest, file_hash, now, read_json, read_jsonl, write_json


@lru_cache(maxsize=1)
def graph_context(path, modified):
    result = {}
    for edge in read_jsonl(path):
        if edge.get("membership_status") == "contextual" and not edge["source"].startswith("page:"):
            result.setdefault(edge["source"], edge["target"])
    return result


def snapshot(root=ROOT, compact=False):
    root = Path(root)
    collection = read_json(root / "data/extracted/collection_manifest.json", {})
    split = read_json(root / "data/split_manifest.json", {})
    training = read_json(root / "runs/training/comparison.json", {})
    frozen = read_json(root / "runs/frozen/manifest.json", {})
    benchmark = read_json(root / "runs/benchmark/final_results.json", {})
    effort = read_json(root / "runs/effort/report.json", {})
    receipt = read_json(root / "runs/advisory/predictions.receipt.json", {})
    sandbox = [read_json(p) for p in sorted((root / "runs/sandbox").glob("*/manifest.json"))]
    result = {"collection": {k: v for k, v in collection.items() if k not in {"unexpanded_frontier", "collection_errors"}},
              "source_errors": collection.get("collection_errors", []), "frontier_count": len(collection.get("unexpanded_frontier", [])),
              "split": {k: v for k, v in split.items() if k != "release_assignment"},
              "training": {k: v for k, v in training.items() if k not in {"train_ids", "train_release_ids"}},
              "frozen": frozen, "benchmark": benchmark, "effort": effort, "prediction_receipt": receipt,
              "sandbox": sandbox, "audit": read_json(root / "runs/audit/summary.json", {}),
              "reconciliation": read_json(root / "runs/audit/reconciliation.json", {})}
    if not compact:
        releases = read_jsonl(root / "data/extracted/releases.jsonl")
        result["releases"] = [{**r, "partition": split.get("release_assignment", {}).get(r["id"], "undated")} for r in releases]
        result["issues"] = [{k: i.get(k) for k in ["issue_key", "summary", "release_ids", "completeness", "source", "point_in_time_state"]} for i in read_jsonl(root / "data/extracted/issues.jsonl")]
        result["predictions"] = read_jsonl(root / "runs/advisory/predictions.jsonl")
        result["artifacts"] = read_jsonl(root / "data/extracted/artifacts.jsonl")
        graph_path = root / "data/extracted/reference_edges.jsonl"
        result["graph_context"] = graph_context(str(graph_path), graph_path.stat().st_mtime_ns) if graph_path.exists() else {}
        result["runtime_stages"] = read_jsonl(root / "runs/stages.jsonl")
        result["label_examples"] = [a for a in read_jsonl(root / "data/labels/weak_actions.jsonl") if a["issue_key"] in {"IRS-29057", "IRS-29096", "IRS-26136"}]
    return result


def export_evidence(root=ROOT):
    root = Path(root)
    target = root / "exports/adf-sentinel-evidence.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    included = []
    candidates = [root / name for name in ["README.md", "DEMO_10_MIN.md", "RUN_REPORT.md", "requirements.txt", "requirements.lock.txt"]]
    for folder in ["adf_sentinel", "static", "docs", "schemas", "tests", "tools", "data/extracted", "data/model_inputs", "data/plans", "data/effort", "data/source_replay", "data/fixtures", "runs/audit", "runs/benchmark", "runs/advisory", "runs/effort", "runs/training", "runs/frozen", "runs/sandbox", "runs/verification"]:
        candidates.extend(p for p in (root / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts and not p.is_symlink())
    receipt = read_json(root / "runs/advisory/predictions.receipt.json")
    prediction_file = root / "runs/advisory/predictions.jsonl"
    if receipt and prediction_file.exists() and receipt.get("prediction_sha256") == file_hash(prediction_file):
        candidates.extend([root / "data/reference/annotation_queue.jsonl", root / "data/reference/implementation_observations.jsonl", root / "data/labels/weak_actions.jsonl"])
    candidates.extend([root / "data/split_manifest.json", root / "data/collection_queue.json", root / "data/collection_failures.json", root / "data/download_log.json"])
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(candidates)):
            if path.exists():
                name = str(path.relative_to(root))
                archive.write(path, name)
                included.append({"path": name, "sha256": file_hash(path)})
        archive.writestr("EXPORT_SCOPE.txt", "Local evidence, manifests, trained exploratory artifacts, and results. Raw source responses and release binaries remain in the original local evidence store; their hashes and paths are in raw/artifact manifests. No instrument installation or release is included.\n")
        archive.writestr("VIEW_RECORDED_RESULTS.txt", "From this extracted folder, run: python -m adf_sentinel serve --port 8876\nThen open http://127.0.0.1:8876 . Python 3.11+ views the recorded results without external services. Install requirements.lock.txt in an isolated environment to rerun classifier inference. Source-fragment and synthetic candidates are non-installable. Original source-system responses and historical ADF binaries are referenced by hash and remain in the original evidence store.\n")
        archive.writestr("EXPORT_MANIFEST.json", json.dumps(included, indent=2))
    return {"status": "exported", "path": str(target), "sha256": file_hash(target), "files": len(included)}


def make_handler(root=ROOT):
    root = Path(root)
    lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def send(self, value, status=200):
            data = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            url = urlparse(self.path)
            path = url.path
            if path == "/api/data":
                return self.send(snapshot(root))
            if path == "/api/graph":
                return self.send({"nodes": read_jsonl(root / "data/extracted/source_nodes.jsonl"), "edges": read_jsonl(root / "data/extracted/reference_edges.jsonl")})
            if path == "/api/frontier":
                return self.send({"requests": read_json(root / "data/collection_queue.json", []), "failures": read_json(root / "data/collection_failures.json", [])})
            if path == "/api/input":
                from .predictor import input_rows
                key = parse_qs(url.query).get("id", [""])[0]
                rows = input_rows(root / "data/model_inputs/retrospective.jsonl", root / "data/model_inputs")
                matches = [r for r in rows if r["id"] == key]
                if matches:
                    row = matches[0]
                    historical = next((v for v in read_jsonl(root / "data/extracted/historical_issue_views.jsonl") if v["issue_key"] == row["issue_key"] and v["release_id"] == row["release_id"]), None)
                    return self.send({**row, "historical_view": historical})
                return self.send({"error": "Input not found"}, 404)
            if path == "/api/diff":
                key = parse_qs(url.query).get("run", [""])[0]
                if not key or not all(c in "0123456789abcdef" for c in key) or len(key) != 20:
                    return self.send({"error": "Unknown run"}, 404)
                diff = root / "runs/sandbox" / key / "changes.diff"
                return self.send({"diff": diff.read_text() if diff.exists() else ""})
            if path == "/export":
                result = export_evidence(root)
                file = Path(result["path"])
                data = file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", 'attachment; filename="adf-sentinel-evidence.zip"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            allowed = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}
            if path not in allowed:
                return self.send({"error": "Not found"}, 404)
            file = root / "static" / allowed[path]
            data = file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(str(file))[0] + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            origin = self.headers.get("Origin")
            if origin and origin not in {"http://127.0.0.1:" + str(self.server.server_port), "http://localhost:" + str(self.server.server_port)}:
                return self.send({"error": "Local origin required"}, 403)
            if self.headers.get_content_type() != "application/json":
                return self.send({"error": "JSON required"}, 415)
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1024 * 1024:
                return self.send({"error": "Request too large"}, 413)
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
                with lock:
                    if self.path == "/api/predict":
                        from .learning import predict
                        return self.send(predict(root, strict=False))
                    if self.path == "/api/execute":
                        from .plans import execute, seed_fixtures, source_replay_plan
                        fixture = data.get("kind") == "fixture"
                        plan = seed_fixtures(root) if fixture else source_replay_plan(root)
                        return self.send(execute(plan, root / ("data/fixtures/baseline" if fixture else "data/source_replay/before"), root))
                    if self.path == "/api/expected-failure":
                        from .plans import execute, seed_fixtures
                        plan = seed_fixtures(root)
                        plan["actions"][0]["before_sha256"] = "0" * 64
                        try:
                            execute(plan, root / "data/fixtures/baseline", root)
                        except ValueError as exc:
                            return self.send({"status": "blocked_expected", "reason": "Expected rejection before mutation: " + str(exc)})
                        raise ValueError("Expected precondition rejection did not occur")
                    if self.path == "/api/reveal":
                        receipt = read_json(root / "runs/advisory/predictions.receipt.json")
                        predictions_path = root / "runs/advisory/predictions.jsonl"
                        if not receipt or not predictions_path.exists() or file_hash(predictions_path) != receipt["prediction_sha256"]:
                            return self.send({"error": "Persist predictions before revealing reference evidence"}, 409)
                        key = data.get("id")
                        predictions = {p["id"] for p in read_jsonl(predictions_path)}
                        if key not in predictions:
                            return self.send({"error": "This action has no persisted prediction"}, 409)
                        reference = next((a for a in read_jsonl(root / "data/reference/annotation_queue.jsonl") if a["id"] == key), None)
                        return self.send({"reference": reference, "reviewer_state": "unreviewed", "correctness": None,
                                          "note": "Source-based proposal/reference excerpt. Reviewed ground truth is unavailable; no accuracy score is computed."})
                    return self.send({"error": "Unknown local operation"}, 404)
            except (ValueError, KeyError, OSError) as exc:
                return self.send({"error": str(exc)}, 400)
    return Handler


def serve(root=ROOT, port=8876):
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(root))
    print(f"ADF Sentinel: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
