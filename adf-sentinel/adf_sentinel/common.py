from __future__ import annotations

import hashlib
import html
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://lsg-thermofisher.atlassian.net"
KEY_RE = re.compile(r"\b[A-Z][A-Z0-9_]+-\d+\b")
VERSION_RE = re.compile(r"(?<![\d.])v?(\d+\.\d+\.\d+(?:\.\d+)?)(?![\d.])", re.I)
TAXONOMY = ["approved_file", "parameter_metadata", "dependency_pin", "shared_sync",
            "verification_only", "investigation_code", "defer_inherit_block"]
MODES = ["supported_automatic", "assisted_review", "manual", "blocked"]


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(value).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable(kind, *parts):
    return kind + "_" + digest(parts)[:20]


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path, obj):
    atomic_text(path, json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def atomic_text(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".writing-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(value)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_jsonl(path, rows):
    atomic_text(path, "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows))


def payload(envelope):
    """Accept native exports, MCP text envelopes, and our archived transport wrapper."""
    value = envelope.get("response", envelope)
    original = value
    if "content" in value and isinstance(value["content"], list):
        for block in value["content"]:
            if block.get("type") == "text":
                try:
                    value = json.loads(block["text"])
                    break
                except (ValueError, KeyError):
                    pass
    if value is original and value.get("structuredContent"):
        value = value["structuredContent"]
    return value.get("data", value)


def timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def semver(value):
    return tuple(int(v) for v in re.findall(r"\d+", str(value)))


def clean_url(value):
    """Preserve business destinations without copying URL credentials/capabilities."""
    try:
        parts = urlsplit(value)
        netloc = parts.netloc.rsplit("@", 1)[-1]
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                 if not re.search(r"token|jwt|secret|password|signature|credential|api.?key|authorization|bearer", k, re.I)]
        fragment = "" if re.search(r"(?:token|jwt|secret|password|signature|credential|api.?key)=", parts.fragment, re.I) else parts.fragment
        return urlunsplit((parts.scheme, netloc, parts.path, urlencode(query), fragment))
    except ValueError:
        return re.sub(r"(?i)(token|jwt|signature|credential|password)=[^&\s]+", r"\1=[redacted]", value)


def scrub(text):
    text = html.unescape(str(text))
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email]", text)
    text = re.sub(r"(?i)\b(?:bearer\s+\S+|(?:api[_ -]?token|password|secret)\s*[:=]\s*\S+)", "[redacted]", text)
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[host]", text)
    text = re.sub(r"\b(?:[0-9a-f]{24}|[0-9a-f]{6}:[0-9a-f-]{36})\b", "[account]", text)
    text = re.sub(r"https?://[^\s<>\"']+", lambda m: clean_url(m.group()), text)
    text = re.sub(r"\[~[^\]]+\]", "[person]", text)
    return re.sub(r"[ \t\xa0]+", " ", text).strip()


class Node:
    def __init__(self, tag="root", attrs=None, parent=None, start=0):
        self.tag, self.attrs, self.parent, self.start = tag, dict(attrs or []), parent, start
        self.children = []

    def walk(self, tags=None):
        for child in self.children:
            if isinstance(child, Node):
                if tags is None or child.tag in tags:
                    yield child
                yield from child.walk(tags)

    def ancestor(self, tag):
        node = self.parent
        while node is not None:
            if node.tag == tag:
                return node
            node = node.parent
        return None

    def text(self, private=False):
        if self.tag in {"script", "style", "noscript"}:
            return ""
        if not private and (self.attrs.get("data-type") == "mention" or self.tag == "ri:user"):
            return "[person]"
        result = "".join(c.text(private) if isinstance(c, Node) else c for c in self.children)
        if self.tag == "br":
            return "\n"
        if self.tag in {"p", "li", "tr", "h1", "h2", "h3", "h4", "div"}:
            result += "\n"
        if self.tag in {"td", "th"}:
            result += " | "
        return result


class Document(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.current = self.root
        self.offsets = [0]
        for match in re.finditer("\n", source):
            self.offsets.append(match.end())
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        line, col = self.getpos()
        node = Node(tag, attrs, self.current, self.offsets[line - 1] + col)
        self.current.children.append(node)
        if tag not in self.VOID:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        node = self.current
        while node.parent is not None:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, text):
        self.current.children.append(text)


def plain(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return scrub(Document(value).root.text())
    if isinstance(value, list):
        return "\n".join(plain(v) for v in value)
    if isinstance(value, dict):
        if value.get("type") == "mention":
            return "[person]"
        if value.get("type") in {"inlineCard", "blockCard"}:
            return str(value.get("attrs", {}).get("url", ""))
        return " ".join(str(value.get("text", "")) for _ in [0]) + plain(value.get("content", []))
    return scrub(value)


def source_ref(path, locator, url=None, **extra):
    path = Path(path)
    return {"path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            "sha256": file_hash(path), "locator": locator, "url": url, **extra}
