"""Approved attachment URLs enter on echo-disabled stdin and are never written to disk."""
import concurrent.futures
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 1024 ** 3

# The caller must wait for this marker before submitting any signed URL.
# Disabling echo inside the ready process avoids a shell-startup timing race.
if sys.stdin.isatty():
    import termios
    attributes = termios.tcgetattr(sys.stdin.fileno())
    attributes[3] &= ~(termios.ECHO | termios.ECHONL)
    termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, attributes)
print("READY_FOR_APPROVED_URLS", flush=True)

class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        dest = urllib.parse.urlparse(newurl)
        if dest.scheme != "https" or not (dest.hostname in {"api.media.atlassian.com", "api.atlassian.com"} or (dest.hostname or "").endswith((".amazonaws.com", ".atlassian.com"))):
            raise ValueError("Attachment redirect outside approved HTTPS storage")
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def download(item):
    owner, filename = item["owner"], item["filename"]
    if not re.fullmatch(r"(?:jira_\d+|confluence_att\d+)", owner) or Path(filename).name != filename or filename in {".", ".."}:
        raise ValueError("Unsafe destination")
    target = ROOT / "data/raw/attachments" / owner / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    parsed = urllib.parse.urlparse(item["url"])
    if parsed.scheme != "https" or parsed.hostname not in {"api.media.atlassian.com", "api.atlassian.com"}:
        raise ValueError("Unapproved download host")
    temporary = target.with_name(target.name + ".part")
    row = {"owner": owner, "filename": filename, "path": str(target.relative_to(ROOT)), "collected_at": datetime.now(timezone.utc).isoformat()}
    if target.exists():
        row.update(state="collected", bytes=target.stat().st_size, sha256=hashlib.sha256(target.read_bytes()).hexdigest(), cached=True)
        return row
    try:
        size, h, md5 = 0, hashlib.sha256(), hashlib.md5(usedforsecurity=False)
        with urllib.request.build_opener(Redirects()).open(item["url"], timeout=45) as response, temporary.open("wb") as stream:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > 256 * 1024 ** 2:
                    raise ValueError("Per-file download byte limit")
                stream.write(chunk)
                h.update(chunk)
                md5.update(chunk)
        os.replace(temporary, target)
        row.update(state="collected", bytes=size, sha256=h.hexdigest(), md5=md5.hexdigest(), cached=False)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        row.update(state="inaccessible", reason="HTTP " + str(exc.code) if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__)
    return row

items = []
for line in sys.stdin:
    if line.strip() == "END":
        break
    items.append(json.loads(line))
existing_bytes = sum(p.stat().st_size for p in (ROOT / "data/raw/attachments").glob("*/*") if p.is_file())
declared_new = sum(int(i.get("bytes_reported", 0)) for i in items if not (ROOT / "data/raw/attachments" / i["owner"] / i["filename"]).exists())
if existing_bytes + declared_new > LIMIT:
    raise SystemExit("Explicit 1 GiB download budget exceeded; retain remaining artifacts as pending")
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(download, items))
path = ROOT / "data/download_log.json"
previous = json.loads(path.read_text()) if path.exists() else []
path.write_text(json.dumps(previous + results, indent=2))
for result in results:
    print(json.dumps(result), flush=True)
