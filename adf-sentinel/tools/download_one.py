"""Consume an approved short-lived attachment URL on stdin; never persist the URL."""
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("owner")
parser.add_argument("filename")
parser.add_argument("--max-bytes", type=int, default=256 * 1024 * 1024)
args = parser.parse_args()
if not re.fullmatch(r"(?:jira_\d+|confluence_att\d+)", args.owner) or Path(args.filename).name != args.filename or args.filename in {".", ".."}:
    raise SystemExit("Unsafe download destination")
root = Path(__file__).resolve().parents[1]
target = root / "data/raw/attachments" / args.owner / args.filename
target.parent.mkdir(parents=True, exist_ok=True)
if sys.stdin.isatty():
    import termios
    attributes = termios.tcgetattr(sys.stdin.fileno())
    attributes[3] &= ~(termios.ECHO | termios.ECHONL)
    termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, attributes)
print("READY_FOR_APPROVED_URL", flush=True)
url = sys.stdin.readline().strip()
parsed = urllib.parse.urlparse(url)
if parsed.scheme != "https" or parsed.hostname not in {"api.media.atlassian.com", "api.atlassian.com"}:
    raise SystemExit("Not an approved attachment download host")

class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        dest = urllib.parse.urlparse(newurl)
        allowed = dest.hostname in {"api.media.atlassian.com", "api.atlassian.com"} or (dest.hostname or "").endswith((".amazonaws.com", ".atlassian.com"))
        if dest.scheme != "https" or not allowed:
            raise ValueError("Attachment redirected outside approved HTTPS storage")
        return super().redirect_request(req, fp, code, msg, headers, newurl)

total, h = 0, hashlib.sha256()
tmp = target.with_name(target.name + ".part")
try:
    with urllib.request.build_opener(Redirects()).open(url, timeout=45) as response, tmp.open("wb") as stream:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > args.max_bytes:
                raise ValueError("Explicit per-file download limit exceeded")
            stream.write(chunk)
            h.update(chunk)
    os.replace(tmp, target)
    print(json.dumps({"state": "collected", "path": str(target.relative_to(root)), "bytes": total, "sha256": h.hexdigest()}))
except Exception as exc:
    tmp.unlink(missing_ok=True)
    # URLs in urllib exceptions can contain bearer capabilities. Report only safe details.
    print(json.dumps({"state": "inaccessible", "reason": "HTTP " + str(exc.code) if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__, "path": str(target.relative_to(root))}))
    sys.exit(1)
