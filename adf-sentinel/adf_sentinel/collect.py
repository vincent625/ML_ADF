"""Read-only resumable collection. Connected readers use the same durable work queue."""
from __future__ import annotations

import concurrent.futures
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .common import ROOT, SITE, digest, now, payload, read_json, write_json

READ_OPERATIONS = {
    "getConfluenceContent", "getConfluenceContentDescendants", "listConfluenceContentVersions",
    "getConfluenceContentVersion", "listConfluenceAttachments", "listConfluenceComments",
    "resolveConfluenceContentMacros", "getJiraIssue", "listJiraIssueComments",
    "listJiraIssueChangelogs", "listJiraIssueRemoteIssueLinks", "searchJiraIssuesUsingJql",
}


def job(operation, resource, inputs, reason, source=None, priority=20):
    if operation not in READ_OPERATIONS:
        raise ValueError("Unsupported read operation")
    return {"id": digest([operation, inputs])[:24], "operation": operation, "resource": resource,
            "inputs": inputs, "reason": reason, "source": source, "priority": priority,
            "state": "pending"}


def next_page(data, kind, inputs):
    """No fixed page-count cap. Detect inconsistent totals and stalled cursors."""
    if kind in {"listJiraIssueComments", "listJiraIssueChangelogs"}:
        rows = data.get("comments", data.get("values", data.get("histories", [])))
        start = data.get("startAt", inputs.get("startAt", 0))
        end = start + len(rows)
        total = data.get("total")
        if data.get("isLast") is False or (total is not None and end < total):
            if not rows:
                raise ValueError("Pagination stalled before reported total")
            return {**inputs, "startAt": end}
        return None
    if kind == "searchJiraIssuesUsingJql":
        token = data.get("nextPageToken")
        if token:
            if token == inputs.get("nextPageToken"):
                raise ValueError("Repeated Jira pagination token")
            return {**inputs, "nextPageToken": token}
        if data.get("isLast") is False:
            raise ValueError("Jira search is incomplete without a continuation token")
        return None
    token = data.get("nextCursor") or data.get("meta", {}).get("cursor")
    link = data.get("_links", {}).get("next") or data.get("next")
    if link and not token:
        token = urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("cursor", [None])[0]
    if token:
        if token == inputs.get("cursor"):
            raise ValueError("Repeated Confluence pagination cursor")
        return {**inputs, "cursor": token}
    if link:
        raise ValueError("Unrecognized pagination link: manual inspection required")
    return None


class RestReader:
    """Optional direct adapter, only for credentials explicitly supplied for this site.

    URLs are constrained to this site and GET routes; credentials never follow a redirect.
    See docs/API_ACCESS.md for the official API references used for these mappings.
    """
    def __init__(self, site=SITE):
        if site != SITE:
            raise ValueError("Configure a separate explicit allowlist before changing sites")
        self.site = site
        bearer = os.environ.get("ATLASSIAN_BEARER_TOKEN")
        email, token = os.environ.get("ATLASSIAN_EMAIL"), os.environ.get("ATLASSIAN_API_TOKEN")
        if bearer:
            self.authorization = "Bearer " + bearer
        elif email and token:
            import base64
            self.authorization = "Basic " + base64.b64encode((email + ":" + token).encode()).decode()
        else:
            raise RuntimeError("No approved environment credentials; use the connected reader or authorized exports")
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                raise RuntimeError("Cross-request redirects require a separate credential-free artifact downloader")
        self.opener = urllib.request.build_opener(NoRedirect())

    def call(self, operation, inputs):
        p = dict(inputs)
        key = urllib.parse.quote(str(p.pop("issueIdOrKey", "")), safe="")
        cid = urllib.parse.quote(str(p.pop("content_id", p.pop("contentId", p.pop("content-id", "")))), safe="")
        routes = {
            "getJiraIssue": f"/rest/api/3/issue/{key}",
            "listJiraIssueComments": f"/rest/api/3/issue/{key}/comment",
            "listJiraIssueChangelogs": f"/rest/api/3/issue/{key}/changelog",
            "listJiraIssueRemoteIssueLinks": f"/rest/api/3/issue/{key}/remotelink",
            "searchJiraIssuesUsingJql": "/rest/api/3/search/jql",
            "getConfluenceContent": f"/wiki/api/v2/pages/{cid}",
            "getConfluenceContentDescendants": f"/wiki/api/v2/pages/{cid}/descendants",
            "listConfluenceContentVersions": f"/wiki/api/v2/pages/{cid}/versions",
            "listConfluenceAttachments": f"/wiki/api/v2/pages/{cid}/attachments",
            "getConfluenceContentVersion": f"/wiki/rest/api/content/{cid}",
        }
        if operation not in routes:
            raise NotImplementedError("This operation needs the connected reader; retained in pending frontier")
        for ignored in ["view", "responseContentFormat", "content_format", "detail"]:
            p.pop(ignored, None)
        if operation == "getConfluenceContent":
            p["body-format"] = "storage"
        if operation == "getConfluenceContentVersion":
            p = {"status": "historical", "version": p["versionNumber"], "expand": "body.storage,version"}
        query = urllib.parse.urlencode(p, doseq=True)
        url = self.site + routes[operation] + ("?" + query if query else "")
        request = urllib.request.Request(url, headers={"Authorization": self.authorization, "Accept": "application/json"})
        for attempt in range(5):
            try:
                with self.opener.open(request, timeout=45) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504} or attempt == 4:
                    raise RuntimeError(f"Read failed with HTTP {exc.code}; credential details suppressed") from None
                delay = min(30, max(1, int(exc.headers.get("Retry-After", 2 ** attempt))))
                time.sleep(delay)
        raise RuntimeError("Retry budget exhausted")


def collect(root=ROOT, transport="connected", retry=False, max_jobs=None):
    root = Path(root)
    queue = read_json(root / "data/collection_queue.json", [])
    if transport != "rest":
        return {"status": "ready", "transport": transport, "pending": len(queue),
                "queue": "data/collection_queue.json", "runner": "tools/connected_collector.js",
                "note": "Recorded ingestion is local; live connected calls run in an approved Codex tool session."}
    reader = RestReader()
    checkpoint_path = root / "data/rest_checkpoint.json"
    checkpoint = read_json(checkpoint_path, {})
    pending = [j for j in queue if retry or checkpoint.get(j["id"], {}).get("state") != "collected"]
    selected = pending if max_jobs is None else pending[:max_jobs]
    def fetch(j):
        try:
            data = reader.call(j["operation"], j["inputs"])
            target = root / "data/raw/rest" / (j["id"] + ".json")
            write_json(target, {"tool": j["operation"], "request": j["inputs"], "resource": j["resource"],
                                "collected_at": now(), "response": data})
            return j, {"state": "collected", "path": str(target.relative_to(root))}, data
        except Exception as exc:
            return j, {"state": "inaccessible", "reason": str(exc)}, None
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        for j, result, data in executor.map(fetch, selected):
            checkpoint[j["id"]] = result
            write_json(checkpoint_path, checkpoint)
            if data is not None:
                nxt = next_page(payload(data), j["operation"], j["inputs"])
                if nxt:
                    follow = job(j["operation"], j["resource"], nxt, "pagination", j["source"])
                    if follow["id"] not in {x["id"] for x in queue}:
                        queue.append(follow)
    write_json(root / "data/collection_queue.json", queue)
    return {"status": "partial" if any(v["state"] != "collected" for v in checkpoint.values()) else "collected_batch",
            "attempted": len(selected), "checkpoint": "data/rest_checkpoint.json",
            "remaining": sum(j["id"] not in checkpoint for j in queue),
            "limit": max_jobs, "note": "Resume until remaining is zero; failures stay in the manifest."}
