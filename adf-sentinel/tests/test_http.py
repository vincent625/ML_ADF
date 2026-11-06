import hashlib
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from adf_sentinel.common import file_hash, write_json, write_jsonl
from adf_sentinel.server import make_handler


@pytest.fixture
def server(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(tmp_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:" + str(server.server_port), tmp_path
    server.shutdown()
    server.server_close()
    thread.join()


def post(url, data, origin=None):
    headers = {"Content-Type": "application/json"}
    if origin:
        headers["Origin"] = origin
    return urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers))


def test_reference_reveal_requires_persisted_predictions_and_valid_hash(server):
    base, root = server
    with pytest.raises(urllib.error.HTTPError) as exc:
        post(base + "/api/reveal", {"id": "SYNTHETIC"})
    assert exc.value.code == 409
    path = root / "runs/advisory/predictions.jsonl"
    write_jsonl(path, [{"id": "SYNTHETIC"}])
    write_json(path.with_suffix(".receipt.json"), {"prediction_sha256": file_hash(path)})
    write_jsonl(root / "data/reference/annotation_queue.jsonl", [{"id": "SYNTHETIC", "text": "SYNTHETIC reference", "reviewer_state": "unreviewed"}])
    with post(base + "/api/reveal", {"id": "SYNTHETIC"}) as response:
        data = json.load(response)
    assert data["correctness"] is None and data["reviewer_state"] == "unreviewed"
    path.write_text('{"id":"SYNTHETIC","tampered":true}\n')
    with pytest.raises(urllib.error.HTTPError) as exc:
        post(base + "/api/reveal", {"id": "SYNTHETIC"})
    assert exc.value.code == 409


def test_remote_origins_and_arbitrary_paths_are_rejected(server):
    base, _ = server
    with pytest.raises(urllib.error.HTTPError) as exc:
        post(base + "/api/execute", {}, "https://untrusted.invalid")
    assert exc.value.code == 403
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(base + "/../../etc/passwd")
    assert exc.value.code == 404


def test_expected_failure_rejects_before_mutation(server):
    base, root = server
    with post(base + "/api/expected-failure", {}) as response:
        data = json.load(response)
    assert data["status"] == "blocked_expected"
    assert not (root / "runs/sandbox").exists()
