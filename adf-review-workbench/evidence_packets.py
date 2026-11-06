"""Read-only, bounded review packets from an existing ADF evidence snapshot.

This module does not infer approvals, execute changes, or alter source evidence.
Only Python's standard library is required.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DEFAULT_ISSUES = ["IRS-65265", "IRS-29057", "IRS-57322", "IRS-66772"]
INPUTS = {
    "issues": "data/extracted/issues.jsonl",
    "actions": "data/labels/weak_actions.jsonl",
    "releases": "data/extracted/releases.jsonl",
    "history": "data/extracted/historical_issue_views.jsonl",
    "artifacts": "data/extracted/external_artifacts.jsonl",
}
LIMITS = {"description_chars": 10000, "comment_chars": 6000,
          "comments": 40, "actions": 42, "actions_per_category": 6,
          "action_chars": 1400, "releases": 12, "history": 6,
          "history_chars": 2500, "artifacts": 16}
_URL = re.compile(r"https?://[^\s<>\[\]{}|\"']+")
_CREDENTIAL_PAIR = re.compile(r"\([A-Za-z][\w.-]{1,40}/[^()\s/]{5,}\)")
_ASSIGNMENT = re.compile(
    r'''(?i)["']?\b(password|passwd|api[_-]?key|access[_-]?token|refresh[_-]?token|'''
    r'''authorization|client[_-]?secret)\b["']?\s*[:=]\s*(?:Bearer\s+)?'''
    r'''(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;]+)''')


def safe_url(value: str) -> str:
    """Remove embedded authentication and every nonessential query parameter."""
    try:
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            return ""
        host = parts.hostname
        if ":" in host:
            host = f"[{host}]"
        if parts.port:
            host += f":{parts.port}"
        # Jira comment IDs are the only query values needed by review packets.
        query = urlencode([(key, val) for key, val in parse_qsl(parts.query)
                           if key == "focusedCommentId" and val.isdigit()])
        return urlunsplit((parts.scheme, host, parts.path, query, ""))
    except (ValueError, TypeError):
        return ""


def sanitize_text(value: str) -> str:
    value = _URL.sub(lambda match: safe_url(match.group()), value)
    value = _CREDENTIAL_PAIR.sub("([credential redacted])", value)
    value = _ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[redacted]", value)
    value = re.sub(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{12,}",
                   r"\1 [redacted]", value)
    return value


def sanitize(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize(item) for key, item in value.items()}
    return value


def read_jsonl(path: Path):
    if path.exists():
        # splitlines() would incorrectly split U+2028 inside JSON strings.
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bounded(value: Any, limit: int) -> tuple[str, bool]:
    text = sanitize_text(str(value or ""))
    return text[:limit], len(text) > limit


def chronological_key(item: dict) -> tuple:
    value = item.get("created") or item.get("updated") or ""
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return (0, stamp.timestamp(), str(item.get("id", "")))
    except (TypeError, ValueError):
        return (1, value, str(item.get("id", "")))


def diverse_actions(actions: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for action in actions:
        groups[action.get("category", "unknown")].append(action)
    result = []
    for index in range(LIMITS["actions_per_category"]):
        for category in sorted(groups):
            if index < len(groups[category]):
                result.append(groups[category][index])
    return result[:LIMITS["actions"]]


def _source_manifest(source_root: Path) -> list[dict]:
    result = []
    for relative in INPUTS.values():
        path = source_root / relative
        result.append({"path": str(path), "relative_path": relative,
                       "available": path.is_file(),
                       "sha256": sha256(path) if path.is_file() else None,
                       "bytes": path.stat().st_size if path.is_file() else None})
    return result


def _provenance(source: Any, root: Path, cache: dict) -> dict:
    if not isinstance(source, dict):
        return {"state": "missing_source_reference"}
    result = {key: source.get(key) for key in
              ("path", "sha256", "url", "locator", "collected_at", "available_at")
              if source.get(key) is not None}
    relative = source.get("path")
    if relative:
        path = (root / relative).resolve()
        if root in path.parents and path.is_file():
            actual = cache.setdefault(str(path), None)
            if actual is None:
                actual = cache[str(path)] = sha256(path)
            result["local_source_sha256"] = actual
            result["source_hash_matches"] = actual == source.get("sha256")
        else:
            result["source_hash_matches"] = None
            result["source_state"] = "local_source_missing_or_outside_root"
    return sanitize(result)


def _questions() -> list[dict]:
    return [
        {"key": "release_scope", "question": "Which release and variants does each action apply to?",
         "reason": "Issue listings and related links do not establish action-level scope."},
        {"key": "exact_change", "question": "What exact target and old/new value or immutable file should be used?",
         "reason": "Descriptions and proposed labels are not executable instructions."},
        {"key": "approval", "question": "Who approves this specific new change and where is that approval recorded?",
         "reason": "Historical statements and merged changes are reference evidence, not new approval."},
        {"key": "acceptance", "question": "What checks and expected outcomes establish completion?",
         "reason": "Structural file checks do not establish scientific or physical validation."},
        {"key": "chronology", "question": "Which decision date and original instructions should govern this review?",
         "reason": "Current text, edited comments and later instructions must be distinguished."},
    ]


def _write_output(path: Path, text: str) -> None:
    if path.is_symlink():
        raise ValueError("Refusing to follow an output-file symbolic link")
    path.write_text(text, encoding="utf-8")


def packet_markdown(packet: dict) -> str:
    lines = [f"# {packet['issue_key']}: {packet['title']}", "",
             f"[Open source issue]({packet['source_url']})", "",
             "Retrospective review aid. Proposed labels are unreviewed. No new approval or execution is inferred.", "",
             "## Current snapshot", "",
             f"Created: {packet['current_snapshot'].get('created')}; updated: {packet['current_snapshot'].get('updated')}", "",
             packet['current_snapshot']['description'], ""]
    if packet['current_snapshot']['description_truncated']:
        lines.append("[Description truncated; inspect the source for the complete text.]\n")
    lines += ["## Dated comment timeline", ""]
    for item in packet['timeline']:
        lines += [f"### {item.get('created')} — comment {item['id']}", "",
                  f"Updated: {item.get('updated')}. [Source]({item['source'].get('url', packet['source_url'])})", "",
                  item['text'], ""]
        if item['truncated']:
            lines.append("[Comment excerpt truncated.]\n")
    lines += ["## Proposed actions — unreviewed", ""]
    for action in packet['proposed_actions']:
        lines += [f"- **{action['category']}** ({action['id']}): {action['text']}"]
    lines += ["", "## Release associations — require action-level review", ""]
    for release in packet['release_associations']:
        lines += [f"- {release['id']}: {release['release_name']}; software {release.get('software_version')}; "
                  f"ADF {release.get('adf_revision')}; decision cutoff {release.get('decision_cutoff')} "
                  f"({release.get('cutoff_state')})."]
    lines += ["", "## Artifact references", ""]
    for item in packet['artifact_references']:
        lines += [f"- [{item['kind']}]({item['url']}): {item['state']}; "
                  f"mutable reference: {item.get('mutable_ref')}. {item.get('reason') or ''}"]
    lines += ["", "## Questions requiring confirmation", ""]
    for item in packet['missing_inputs']:
        lines += [f"- {item['question']} {item['reason']}"]
    lines += ["", "## Coverage and limits", "", "```json",
              json.dumps(packet['counts'], indent=2), "```", "",
              "Source retrieval status (distinct from the number displayed above):", "",
              "```json", json.dumps(packet['current_snapshot'].get('completeness'), indent=2),
              "```", ""]
    lines += [f"- {caveat}" for caveat in packet['caveats']]
    lines += ["", "## Input file provenance", ""]
    for source in packet['source_manifest']:
        lines.append(f"- `{source['relative_path']}`: SHA-256 `{source['sha256']}`; {source['bytes']} bytes.")
    return "\n".join(lines) + "\n"


def build_packets(source_root: Path, output_root: Path, issue_keys: list[str]) -> list[dict]:
    source_root, output_root = Path(source_root).resolve(), Path(output_root).resolve()
    if output_root == source_root or source_root in output_root.parents:
        raise ValueError("Output must be outside the preserved source project")
    if not issue_keys or any(not re.fullmatch(r"[A-Z][A-Z0-9]*-[1-9][0-9]*", key)
                             for key in issue_keys):
        raise ValueError("Supply valid Jira issue keys")
    issue_keys = list(dict.fromkeys(issue_keys))
    wanted = set(issue_keys)
    issues = {item['issue_key']: item for item in read_jsonl(source_root / INPUTS['issues'])
              if item.get('issue_key') in wanted}
    actions = defaultdict(list)
    for item in read_jsonl(source_root / INPUTS['actions']):
        if item.get('issue_key') in wanted:
            actions[item['issue_key']].append(item)
    releases = list(read_jsonl(source_root / INPUTS['releases']))
    histories = defaultdict(list)
    for item in read_jsonl(source_root / INPUTS['history']):
        if item.get('issue_key') in wanted:
            histories[item['issue_key']].append(item)
    artifacts = defaultdict(list)
    for item in read_jsonl(source_root / INPUTS['artifacts']):
        for key in {ref.get('issue_key') for ref in item.get('references', [])} & wanted:
            artifacts[key].append(item)
    manifest = _source_manifest(source_root)
    source_cache = {}
    output_root.mkdir(parents=True, exist_ok=True)
    packets = []
    for key in issue_keys:
        issue = issues.get(key, {})
        description, description_truncated = bounded(issue.get('description'), LIMITS['description_chars'])
        comments = sorted(issue.get('comments', []), key=chronological_key)
        timeline = []
        for comment in comments[:LIMITS['comments']]:
            text, truncated = bounded(comment.get('body'), LIMITS['comment_chars'])
            timeline.append({"id": comment.get('id'), "created": comment.get('created'),
                             "updated": comment.get('updated'), "text": text,
                             "truncated": truncated,
                             "source": _provenance(comment.get('source'), source_root, source_cache)})
        proposed = []
        for action in diverse_actions(actions[key]):
            text, truncated = bounded(action.get('text'), LIMITS['action_chars'])
            proposed.append({"id": action['id'], "category": action.get('category'),
                             "text": text, "truncated": truncated,
                             "release_ids": action.get('release_ids', []),
                             "variant_scope": action.get('variant_scope', []),
                             "reviewer_state": action.get('reviewer_state', 'unreviewed'),
                             "label_strength": action.get('label_strength'),
                             "source": [_provenance(item, source_root, source_cache)
                                        for item in action.get('evidence', [])[:3]]})
        release_ids = set(issue.get('release_ids', []))
        linked = [item for item in releases if item.get('id') in release_ids
                  or key in item.get('listed_issue_keys', [])]
        associations = []
        for release in linked[:LIMITS['releases']]:
            entry = {name: release.get(name) for name in
                     ('id', 'release_name', 'family', 'adf_revision', 'software_version',
                      'workflow_version', 'release_date', 'decision_cutoff', 'cutoff_state',
                      'variant_scope', 'chronology_state')}
            entry['association_state'] = 'listed_or_linked_issue_requires_action_scope_review'
            revisions = release.get('source_revisions', [])
            entry['source_url'] = revisions[0].get('url') if revisions else None
            entry['sources'] = [_provenance(item, source_root, source_cache) for item in revisions[:3]]
            associations.append(entry)
        history = []
        for view in histories[key][:LIMITS['history']]:
            text, truncated = bounded(view.get('text'), LIMITS['history_chars'])
            history.append({name: view.get(name) for name in
                            ('release_id', 'cutoff', 'cutoff_state', 'state', 'excluded')})
            history[-1].update(text=text, truncated=truncated,
                               source=_provenance(view.get('source'), source_root, source_cache))
        references = []
        ordered_artifacts = sorted(artifacts[key], key=lambda item: (bool(item.get('mutable_ref')), item.get('url', '')))
        for artifact in ordered_artifacts[:LIMITS['artifacts']]:
            entry = {name: artifact.get(name) for name in
                     ('id', 'kind', 'url', 'state', 'reason', 'mutable_ref')}
            refs = [ref for ref in artifact.get('references', []) if ref.get('issue_key') == key]
            entry['sources'] = [_provenance(ref.get('source'), source_root, source_cache) for ref in refs[:3]]
            references.append(entry)
        counts = {"comments_available": len(comments), "comments_shown": len(timeline),
                  "actions_available": len(actions[key]), "actions_shown": len(proposed),
                  "action_category_counts": dict(Counter(item.get('category') for item in actions[key])),
                  "releases_available": len(linked), "releases_shown": len(associations),
                  "historical_views_available": len(histories[key]), "historical_views_shown": len(history),
                  "artifacts_available": len(artifacts[key]), "artifacts_shown": len(references),
                  "truncated_comments_shown": sum(item['truncated'] for item in timeline),
                  "truncated_actions_shown": sum(item['truncated'] for item in proposed)}
        packet = {"schema_version": "1.0", "issue_key": key,
                  "title": issue.get('summary', 'Issue absent from cached snapshot'),
                  "source_url": f"https://lsg-thermofisher.atlassian.net/browse/{key}",
                  "generated_at": datetime.now(timezone.utc).isoformat(),
                  "source_issue_available": bool(issue),
                  "evidence_state": "retrospective_unreviewed_no_new_approval",
                  "current_snapshot": {"description": description, "created": issue.get('created'),
                      "updated": issue.get('updated'), "current_status": issue.get('current_status'),
                      "source": _provenance(issue.get('source'), source_root, source_cache),
                      "completeness": issue.get('completeness'),
                      "description_truncated": description_truncated},
                  "timeline": timeline, "proposed_actions": proposed,
                  "release_associations": associations, "historical_views": history,
                  "artifact_references": references, "missing_inputs": _questions(),
                  "caveats": [
                      "Source collection is partial; zero displayed records does not prove none exist.",
                      "Current descriptions are retrospective and may have been edited after a release decision.",
                      "Comments are ordered by creation; updated dates are retained and original edited text may be unknown.",
                      "Different dated instructions may apply to different releases; do not collapse them into one instruction.",
                      "Action selection samples up to six per proposed category; all counts describe the cached snapshot.",
                      "Artifact links and issue closure do not establish approval, downloaded bytes or successful validation.",
                      "Sensitive query strings and credential-like text are redacted in this generated review aid.",
                      "No saved source, model, benchmark, plan or evidence export was modified."],
                  "counts": counts, "source_manifest": manifest, "limits": LIMITS,
                  "output_files": {"json": str(output_root / f"{key}.json"),
                                   "markdown": str(output_root / f"{key}.md")}}
        packet = sanitize(packet)
        _write_output(output_root / f"{key}.json", json.dumps(packet, ensure_ascii=False, indent=2) + "\n")
        _write_output(output_root / f"{key}.md", packet_markdown(packet))
        packets.append(packet)
    index = {"schema_version": "1.0", "packet_count": len(packets),
             "issues": [{"issue_key": packet['issue_key'], "title": packet['title'],
                         "counts": packet['counts'], "output_files": packet['output_files']}
                        for packet in packets],
             "source_manifest": manifest, "new_approvals": 0, "executed_changes": 0}
    _write_output(output_root / "index.json", json.dumps(index, indent=2) + "\n")
    return packets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--issues', nargs='+', default=DEFAULT_ISSUES)
    args = parser.parse_args()
    packets = build_packets(args.source, args.output, args.issues)
    print(json.dumps({"packets": len(packets), "issues": [item['issue_key'] for item in packets],
                      "comments_shown": sum(item['counts']['comments_shown'] for item in packets),
                      "actions_shown": sum(item['counts']['actions_shown'] for item in packets),
                      "output": str(args.output.resolve())}))


if __name__ == '__main__':
    main()
