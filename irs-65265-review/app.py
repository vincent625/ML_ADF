"""Loopback-only, dependency-free ADF Sentinel web application."""
import argparse
import json
import logging
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from sentinel import BASE, DEFAULT_DATA, Sentinel, evidence, generate

LOG = logging.getLogger("sentinel")
LOCK = threading.RLock()


def handler_for(engine):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, value, status=200, mime="application/json", filename=None):
            body = json.dumps(value).encode() if mime == "application/json" else value
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; script-src 'self'; style-src 'self'; "
                             "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            route = urlsplit(self.path)
            scenario = parse_qs(route.query).get("scenario", ["wrong-primer"])[0]
            try:
                with LOCK:
                    if route.path == "/api/state":
                        self.reply(engine.view(scenario))
                    elif route.path == "/api/evidence":
                        self.reply(evidence())
                    elif route.path == "/api/export":
                        self.reply(engine.export(scenario), filename=f"{scenario}-evidence.json")
                    elif route.path == "/api/bundle":
                        path = engine.bundle(scenario)
                        self.reply(path.read_bytes(), mime="application/zip", filename=path.name)
                    elif route.path == "/api/parameter-preview":
                        self.reply(engine.parameter_preview(scenario))
                    elif route.path == "/favicon.ico":
                        self.reply(b"", status=204, mime="image/x-icon")
                    elif route.path in ("/", "/style.css", "/app.js"):
                        name = "index.html" if route.path == "/" else route.path[1:]
                        mime = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                                ".js": "text/javascript; charset=utf-8"}[Path(name).suffix]
                        self.reply((BASE / "static" / name).read_bytes(), mime=mime)
                    else:
                        self.reply({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            except ValueError as error:
                LOG.warning("Invalid GET request: %s", error)
                self.reply({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            except (OSError, KeyError) as error:
                LOG.exception("Evidence read failed")
                self.reply({"error": f"Evidence read failed: {error}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

        def do_POST(self):
            origin = self.headers.get("Origin")
            if origin and origin != f"http://{self.headers.get('Host')}":
                self.reply({"error": "Cross-origin mutation rejected"}, HTTPStatus.FORBIDDEN)
                return
            if self.headers.get("Content-Type") != "application/json":
                self.reply({"error": "Content-Type must be application/json"}, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16384:
                    raise ValueError("Request body must be 1-16384 bytes")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("Request body must be a JSON object")
                scenario = data.get("scenario", "wrong-primer")
                with LOCK:
                    if self.path == "/api/run":
                        value = engine.run(scenario)
                    elif self.path == "/api/preview":
                        value = engine.preview(scenario, data["test_id"])
                    elif self.path == "/api/apply":
                        value = engine.apply(data["proposal_id"], data.get("reviewer", ""))
                    elif self.path == "/api/parameter":
                        value = engine.parameter_change(scenario, data.get("reviewer", ""))
                    elif self.path == "/api/reset":
                        value = generate(engine.root)
                    else:
                        self.reply({"error": "Not found"}, HTTPStatus.NOT_FOUND)
                        return
                self.reply(value)
            except (ValueError, KeyError, TypeError) as error:
                LOG.warning("Rejected mutation: %s", error)
                self.reply({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            except (OSError, RuntimeError) as error:
                LOG.exception("Sandbox operation failed")
                self.reply({"error": f"Sandbox operation failed: {error}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    return Handler


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--reset", action="store_true", help="Regenerate known sandbox fixtures and audit state")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.reset:
        print("Reset:", generate(args.data), flush=True)
    engine = Sentinel(args.data)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(engine))
    print(f"ADF Sentinel: http://127.0.0.1:{args.port} (synthetic sandbox, loopback only)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Sentinel.", flush=True)
    finally:
        server.server_close()
