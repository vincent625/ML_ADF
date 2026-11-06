from __future__ import annotations

import collections
import html
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse, urlunparse

from .common import ROOT, atomic_text, clean_url, digest, file_hash, now, payload, read_json, read_jsonl, write_json, write_jsonl


def sources_and_report(root=ROOT):
    root = Path(root)
    collection = read_json(root / "data/extracted/collection_manifest.json", {})
    issues = read_jsonl(root / "data/extracted/issues.jsonl")
    artifacts = read_jsonl(root / "data/extracted/artifacts.jsonl")
    actions = read_jsonl(root / "data/labels/weak_actions.jsonl")
    external = {}
    for entry in read_jsonl(root / "data/extracted/href_references.jsonl"):
        url = clean_url(entry["url"])
        try:
            host = (urlparse(url).hostname or "").lower()
        except ValueError:
            continue
        if not host or "atlassian" in host or "gravatar" in host or "avatar" in host:
            continue
        kind = "github" if host in {"github.com", "api.github.com", "raw.githubusercontent.com"} else "package_store" if "jfrog" in host or "nexus" in url or "artifactory" in url else "external_result_or_document"
        value = external.setdefault(url, {"id": "external_" + digest(url)[:20], "url": url, "kind": kind,
                     "state": "pending", "references": [], "credential_query_removed": url != entry["url"],
                     "reason": "Needs approved reader/export and relevance review; no Jira credentials forwarded"})
        value["references"].append({"issue_key": entry["owner"], "locator": entry["source"]["locator"], "source": entry["source"]})
    for issue in issues:
        locations = [("description", issue.get("description", ""))] + [("comment:" + str(c["id"]), c["body"]) for c in issue.get("comments", [])]
        for location, text in locations:
            for match in re.finditer(r"https?://[^\s<>\"']+", html.unescape(text)):
                url = match.group().rstrip(".,;)")
                try:
                    parsed = urlparse(url)
                    host = (parsed.hostname or "").lower()
                except ValueError:
                    external.setdefault(url, {"id": "external_" + digest(url)[:20], "url": url,
                        "kind": "unsupported_redacted_url", "state": "unsupported", "references": [],
                        "reason": "URL in sanitized text is malformed/redacted; recover the original through its raw source locator"})["references"].append({"issue_key": issue["issue_key"], "locator": location, "source": issue["source"]})
                    continue
                if "atlassian" in host or "gravatar" in host or "avatar" in host:
                    continue
                # Auth-bearing URL query strings are never included in manifests or model inputs.
                sensitive = any(re.search(r"token|jwt|secret|password|signature|credential", k, re.I) for k in parse_qs(parsed.query))
                if sensitive:
                    url = urlunparse(parsed._replace(query="", fragment=""))
                kind = "github" if host in {"github.com", "api.github.com", "raw.githubusercontent.com"} else "package_store" if "jfrog" in host or "nexus" in url or "artifactory" in url else "external_result_or_document"
                entry = external.setdefault(url, {"id": "external_" + digest(url)[:20], "url": url, "kind": kind,
                                                "state": "pending", "references": [], "credential_query_removed": sensitive,
                                                "reason": "Needs approved reader/export and release relevance review; no Jira credentials forwarded"})
                entry["references"].append({"issue_key": issue["issue_key"], "locator": location, "source": issue["source"]})
    known = {}
    for path in (root / "data/raw/connected/github").glob("*.json"):
        document = payload(read_json(path))
        if not isinstance(document, dict):
            continue
        url = document.get("display_url", document.get("url"))
        if url:
            known[clean_url(url)] = {"path": str(path.relative_to(root)), "sha256": file_hash(path),
                                    "commit": document.get("head_sha"), "blob": document.get("sha")}
    for url, entry in external.items():
        canonical = re.sub(r"(/pull/\d+)/(?:files|commits|checks).*", r"\1", url)
        if canonical in known:
            entry.update(state="collected", collected_evidence=known[canonical], reason="Approved connected reader; immutable source metadata/content retained")
        entry["mutable_ref"] = bool(re.search(r"/(?:blob|tree)/(?:main|master)(?:/|$)", url))
        if entry["mutable_ref"]:
            entry["reason"] = "Mutable branch link needs a pinned commit; not sufficient artifact provenance"
    write_jsonl(root / "data/extracted/external_artifacts.jsonl", list(external.values()))
    pending_artifacts = [{k: a.get(k) for k in ["id", "owner", "filename", "bytes_reported", "access_state", "failure_reason", "source"]} for a in artifacts if a["access_state"] != "collected"]
    partial_issues = [{"issue_key": i["issue_key"], "release_ids": i["release_ids"], "completeness": i["completeness"]} for i in issues if any(i["completeness"][k] != "collected" for k in ["comments", "history", "remote_links"])]
    missing = {"generated_at": now(), "overall_state": "partial", "pending_reader_queue": "data/collection_queue.json",
               "inaccessible_references": read_json(root / "data/collection_failures.json", []),
               "partial_issue_snapshots": partial_issues, "pending_attachment_originals": pending_artifacts,
               "external_artifact_manifest": "data/extracted/external_artifacts.jsonl",
               "cutoff_and_label_work": "data/reference/annotation_queue.jsonl",
               "missing_capabilities": [{"source": "Confirmed original comment revisions", "state": "inaccessible", "reason": "Jira field changelogs do not establish old edited comment bodies"},
                                        {"source": "Approved serialized-core ADF builder", "state": "pending", "reason": "Real .ser archives are collected, but no documented approved core builder is available in the inspected pinned source"},
                                        {"source": "Test management / scientific run exports", "state": "pending", "reason": "Narrative test references need raw execution evidence and mapping; no absence-of-testing inference"},
                                        {"source": "Reviewed action labels and confirmed decision events", "state": "pending", "reason": "All proposed labels require review; first-in-progress cutoffs are proxies"},
                                        {"source": "Manual and assisted touch-time observations", "state": "pending", "reason": "No matched timed replay or shadow pilot has been observed"}],
               "limits": collection.get("operational_limits", {}), "no_silent_truncation": "Every known pending item stays in these manifests; viewing limits in the dashboard do not limit the exported dataset."}
    write_json(root / "data/extracted/missing_sources.json", missing)
    import csv
    from .effort import FIELDS
    template = root / "data/effort/action_measurement_template.csv"
    template.parent.mkdir(parents=True, exist_ok=True)
    with template.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for action in actions:
            writer.writerow({"action_id": action["id"], "release_id": "|".join(action["release_ids"]), "scope": "bundle_only"})
    training = read_json(root / "runs/training/comparison.json", {})
    benchmark = read_json(root / "runs/benchmark/final_results.json", {})
    effort = read_json(root / "runs/effort/report.json", {})
    verification = read_json(root / "runs/verification/results.json", {})
    runs = [read_json(p) for p in (root / "runs/sandbox").glob("*/manifest.json")]
    complete = {field: sum(i["completeness"][field] == "collected" for i in issues) for field in ["comments", "history", "remote_links"]}
    fit = [m for m in training.get("models", []) if m["status"] in {"trained", "trained_exploratory"}]
    body = f"""# ADF Sentinel: execution report

Generated {now()} (UTC). User-facing run date: October 31, 2026, America/Los_Angeles.

The project is implemented and runs locally. Collection is partial. Reviewed labels, a validated unseen benchmark, a genuine rebuilt ADF, and measured engineering savings are not established.

## Actually collected and run

| Evidence / result | Recorded count or state |
|---|---|
| Confluence pages read | {collection.get('pages')} |
| Distinct release identities / families | {collection.get('releases')} / {len(collection.get('families', {}))} |
| Validated Jira issue records | {collection.get('validated_issues')} |
| Issues explicitly associated with release rows | {collection.get('release_associated_issues')} |
| Unique referenced issue candidates | {collection.get('references_discovered')} |
| Recorded source graph edges | {collection.get('edges')} |
| Complete comments / field histories / remote links | {complete.get('comments')} / {complete.get('history')} / {complete.get('remote_links')} |
| Original attachments downloaded / metadata records | {collection.get('attachments_downloaded')} / {collection.get('attachments_metadata')} |
| Historical issue views / unconfirmed cutoff proxies | {collection.get('historical_issue_views')} / {collection.get('cutoff_proxies')} |
| Proposed action labels / reviewed labels | {collection.get('weak_actions')} / {len(read_jsonl(root/'data/labels/reviewed_actions.jsonl'))} |
| Fitted model baselines | {len(fit)} |
| Remaining reader requests | {collection.get('pending_requests')} |
| Frozen strict benchmark | {benchmark.get('status', 'not yet run')} |
| Measured engineer minutes saved | {effort.get('measured_net_minutes') if effort.get('measured_net_minutes') is not None else 'Not measured'} |

The source graph distinguishes release listings, mentions, formal link directions, and parent relationships. Context issues are not silently promoted to implemented changes. Failed validation cannot distinguish a missing issue from inaccessible content. All such candidates are retained.

## Learning and temporal scope

Training scope: `{training.get('scope', 'not yet run')}`. The majority, TF-IDF logistic regression, TF-IDF SVM and structured-tree models use the same training rows; a transparent rules baseline is also implemented. Weak-label fits are exploratory. No agreement with the labeling rules is reported as accuracy. Approved pinned embedding and callable LLM baseline configurations are missing.

Release-index dates define the chronological map. Undated releases are separate. First release-ticket transitions to In Progress are explicitly unconfirmed bundling-start proxies. Edited comments are not back-dated. Recovered description history is kept separate from current retrospective inputs. Strict action inputs require confirmed cutoffs, historical evidence and reviewed truth. Final-test label files are not read by the predictor or training/model selection.

## Executed sandbox scope

"""
    for run in runs:
        body += f"- **{run['scope']}**: {run['actions_attempted']} action(s), {len(run['checks'])} deterministic checks, {run['status']}; originals preserved: {run['originals_preserved']}. Runtime {run['runtime_seconds']:.4f} seconds. Candidate: `{run['candidate_path']}`.\n"
    body += f"""
The real replay uses actual before/after bytes pinned to the merged IRS-65265 implementation. It is one source file, not a rebuilt Genexus ADF. Synthetic fixtures are explicitly labeled and excluded from historical model claims. Real historical ADF archive hashes are computed from downloaded bytes, with ZIP-content comparison independent of archive timestamps. Serialized core payloads are never executed or deserialized.

## Verification

{json.dumps(verification, indent=2)}

Focused tests exercise pagination, resume/cycle/dedup behavior, independent version fields, cutoffs, train-only vocabulary, prediction/reference separation, copied-file execution, exact hashes, preconditions, unsupported operations, expected failures, local HTTP safeguards and effort arithmetic. Browser verification, when present above, checks actual clicks and responsive layout; structural checks do not establish scientific validation.

## Exact remaining work

1. Resume `data/collection_queue.json`; inspect `data/collection_failures.json` and `data/extracted/missing_sources.json`. The attachment-download budget is explicit, and every uncollected original remains listed. Deeper contextual frontiers require release relevance review rather than expansion through unrelated generic containers.
2. Review `data/reference/annotation_queue.jsonl`: establish independent action boundaries, release/variant scope, approved exact values/targets, implementation/released-byte evidence, verification outcomes and disagreements. Supply confirmed release chronology in `data/release_annotations.jsonl` and reviewed action imports through `prepare --annotations`.
3. Supply approved serialized-core build tooling and any remaining required inputs before claiming real candidate assembly. No installation, instrument run or release was authorized or performed.
4. Record matched manual/assisted observations in `data/effort/observations.csv`. The per-action template is editable. Runtime measurements are not engineer time saved; two elapsed weeks are not 80 engineer hours. Calendar dependencies and physical testing remain separate.

The original `irs-65265-review` project is preserved. The local dashboard and evidence export require no external service once results are recorded.
"""
    atomic_text(root / "RUN_REPORT.md", body)
    return {"status": "reported", "report": str(root / "RUN_REPORT.md"), "external_urls": len(external), "missing_attachments": len(pending_artifacts)}
