"""Normalize evidence without treating a mention, closed ticket, or weak label as truth."""
from __future__ import annotations

import collections
import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .collect import job, next_page
from .common import (ROOT, SITE, KEY_RE, VERSION_RE, TAXONOMY, MODES, Document, Node, digest,
                     file_hash, now, payload, plain, read_json, read_jsonl, scrub, semver,
                     stable, timestamp, write_json, write_jsonl, clean_url)


def confluence_page_id(value):
    """Resolve current and legacy page links only on the approved source site."""
    try:
        parsed = urlparse(value)
        if parsed.netloc and parsed.hostname != urlparse(SITE).hostname:
            return None
        if parsed.scheme and parsed.scheme not in {"http", "https"}:
            return None
        if not parsed.path.startswith("/wiki/"):
            return None
        modern = re.search(r"/pages/(\d+)(?:/|$)", parsed.path)
        legacy = parse_qs(parsed.query).get("pageId", [None])[0]
        return modern.group(1) if modern else legacy if legacy and legacy.isdigit() else None
    except (TypeError, ValueError):
        return None


def family_name(title):
    patterns = [(r"Manticore|OFAv2", "Manticore OFAv2"), (r"OCA\s*Plus|OCAPlus", "OCA Plus"),
                (r"OCAv3", "OCAv3"), (r"Myeloid v3", "Myeloid v3"), (r"Myeloid", "Myeloid"),
                (r"Ronin|Valhalla|ODxET|Dx Express", "Ronin / Valhalla / ODxET"),
                (r"Grand\s*Prix|Grad\s*Prix|OCAv5", "GrandPrix"), (r"BRCA", "BRCA"), (r"Microbiome", "Microbiome"),
                (r"TCR", "TCR Beta"), (r"SARS", "SARS CoV2"), (r"Osprey", "Osprey"),
                (r"\bOPA\b", "OPA"), (r"IUO PQ", "IUO PQ"), (r"IVD PQ", "IVD PQ"),
                (r"RUO PQ", "RUO PQ"), (r"RUO IQ", "RUO IQ"), (r"Liverpool", "Liverpool Lymphoid")]
    for pattern, name in patterns:
        if re.search(pattern, title, re.I):
            return name
    return re.sub(r"\s+(?:ADF|change tracking).*", "", title, flags=re.I).strip()


def parse_date(text):
    text = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", text.strip(), flags=re.I)
    value = timestamp(text)
    if value:
        return value.date().isoformat()
    for fmt in ["%d %b %Y", "%d-%b-%Y", "%b %d, %Y", "%B %d, %Y", "%d %B %Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%b-%y"]:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def grid_rows(table):
    """Expand row/column spans; retain original cells for provenance."""
    spans = {}
    for row in table.walk({"tr"}):
        if row.ancestor("table") is not table:
            continue
        cells = [c for c in row.children if isinstance(c, Node) and c.tag in {"td", "th"}]
        if not cells:
            continue
        expanded, col = [], 0
        for cell in cells:
            while col in spans:
                remaining, saved = spans[col]
                expanded.append(saved)
                if remaining <= 1:
                    del spans[col]
                else:
                    spans[col] = (remaining - 1, saved)
                col += 1
            for _ in range(min(100, max(1, int(cell.attrs.get("colspan", 1))))):
                expanded.append(cell)
                rowspan = min(10000, max(1, int(cell.attrs.get("rowspan", 1))))
                if rowspan > 1:
                    spans[col] = (rowspan - 1, cell)
                col += 1
        while col in spans:
            remaining, saved = spans[col]
            expanded.append(saved)
            if remaining <= 1:
                del spans[col]
            else:
                spans[col] = (remaining - 1, saved)
            col += 1
        yield row, expanded


def release_tables(page, ref):
    body = page.get("body", {})
    html_body = body.get("value") or body.get("storage", {}).get("value", "")
    doc = Document(html_body).root
    title, pid = page.get("title", ""), str(page.get("id"))
    revision = page.get("metadata", {}).get("version", {}).get("number", page.get("version", {}).get("number"))
    releases, audit = [], []
    for ti, table in enumerate(doc.walk({"table"})):
        rows = list(grid_rows(table))
        if not rows:
            continue
        headers = [scrub(c.text()).strip(" |\n").lower() for c in rows[0][1]]
        indices = [i for i, h in enumerate(headers) if "adf" in h and any(w in h for w in ["version", "name", "full"])]
        if not indices and "adf" in headers and any("ticket" in h or "zip" in h for h in headers):
            indices = [headers.index("adf")]
        is_release = indices and any(any(w in h for w in ["change", "ticket", "jira", "zip", "download"]) for h in headers)
        if not is_release:
            audit.append({"page_id": pid, "table": ti, "headers": headers, "state": "context_table", "reason": "No identifiable release-index column combination"})
            continue
        vi = indices[0]
        previous = []
        for node in doc.walk():
            if node is table:
                break
            if node.tag in {"p", "h1", "h2", "h3", "h4"} and not node.ancestor("table"):
                t = scrub(node.text())
                if t:
                    previous.append(t)
        heading = " ".join(previous[-2:])[-250:]
        table_id = table.attrs.get("data-local-id", "table-" + str(ti))
        for ri, (row, cells) in enumerate(rows[1:], 1):
            if vi >= len(cells):
                audit.append({"page_id": pid, "table": ti, "row": ri, "state": "partial", "reason": "Missing version cell"})
                continue
            name = scrub(cells[vi].text()).strip(" |\n")
            versions = VERSION_RE.findall(name)
            if not versions:
                audit.append({"page_id": pid, "table": ti, "row": ri, "text": name, "state": "review_required", "reason": "Release-like row has no unambiguous semantic version"})
                continue
            explicit = re.findall(r"(?:^|[-_\s])v(\d+\.\d+\.\d+(?:\.\d+)?)", name, re.I)
            # A workflow w6.0.0 alone does not establish ADF revision 6.0.0.
            without_other_versions = re.sub(r"(?:^|[-_\s])(?:w|SW[_\s-]*)(\d+\.\d+(?:\.\d+)*)", " ", name, flags=re.I)
            candidates = sorted(set(explicit or VERSION_RE.findall(without_other_versions)), key=semver)
            adf = candidates[0] if len(candidates) == 1 else None
            ambiguity = len(candidates) != 1
            text = scrub(row.text())
            variant_text = name + " " + heading
            scope = []
            for pattern, label in [(r"cfTNA|plasma", "cfTNA"), (r"FFPE", "FFPE"), (r"DNA", "DNA"),
                                   (r"Fusion|DNAFus|RNA", "Fusion/RNA"), (r"germline", "germline"),
                                   (r"somatic", "somatic"), (r"dummy", "dummy")]:
                if re.search(pattern, variant_text, re.I):
                    scope.append(label)
            workflow = re.search(r"(?:^|[-_\s])w(\d+\.\d+\.\d+)", name, re.I)
            software = re.search(r"(?:SW|GX)[_\s-]*(\d+\.\d+(?:\.\d+)*)", name, re.I)
            sw_source = "release_name" if software else None
            if not software:
                for i, h in enumerate(headers):
                    if ("software" in h or "sw ver" in h) and i < len(cells):
                        software = re.search(r"\d+\.\d+(?:\.\d+)*", cells[i].text())
                        sw_source = "software_column"
                        break
            if not software:
                software = re.search(r"\b[67]\.\d+(?:\.\d+)*", title)
                sw_source = "page_title_inference" if software else None
            sw = software.group(1) if software and software.lastindex else software.group(0) if software else None
            released_on, date_evidence = None, None
            for i, h in enumerate(headers):
                if h in {"date", "release date", "released on"} and i < len(cells):
                    dates = list(cells[i].walk({"time", "span"}))
                    for d in dates:
                        raw = d.attrs.get("datetime") or d.attrs.get("data-timestamp")
                        if raw:
                            try:
                                released_on = datetime.fromtimestamp(int(raw) / 1000, timezone.utc).date().isoformat() if raw.isdigit() else parse_date(raw)
                            except (ValueError, OverflowError):
                                pass
                    released_on = released_on or parse_date(scrub(cells[i].text()).strip(" |\n"))
                    if released_on:
                        date_evidence = {"kind": "release_index_date_column", "header": h, "text": scrub(cells[i].text()), "certainty": "reported_date"}
            row_id = row.attrs.get("data-local-id", "row-" + str(ri))
            rref = {**ref, "locator": f"page:{pid}@v{revision}/table:{table_id}/row:{row_id}", "html_offset": row.start}
            urls = sorted({a.attrs["href"] for a in row.walk({"a"}) if a.attrs.get("href")})
            media = sorted({a.attrs["data-media-id"] for a in row.walk() if a.attrs.get("data-media-id")})
            rid = stable("release", pid, table_id, name, scope)
            releases.append({"id": rid, "family": family_name(title), "page_title": title,
                "software_version": sw, "software_version_source": sw_source,
                "workflow_version": workflow.group(1) if workflow else None, "adf_revision": adf,
                "revision_candidates": candidates, "revision_ambiguous": ambiguity, "release_name": name, "variant_scope": scope,
                "package_references": [u for u in urls if re.search(r"\.(zip|adf|deb)(?:\?|$)|artifactory|jfrog", u, re.I)],
                "unresolved_media_cards": media, "source_revisions": [rref], "source_page": pid,
                "release_date": released_on, "release_date_evidence": date_evidence,
                "decision_cutoff": None, "cutoff_evidence": None, "cutoff_state": "missing",
                "listed_issue_keys": sorted(set(KEY_RE.findall(text)) | set(KEY_RE.findall(" ".join(urls)))), "release_ticket": None,
                "chronology_state": "reported_date" if released_on else "missing_actual_release_date",
                "notes": text, "row_state": "ambiguous_revision" if ambiguity else "listed_release",
                "historical_snapshot_recovered": False})
    return releases, audit


def walk_fields(value, path="fields"):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from walk_fields(child, f"{path}[{i}]")
    elif isinstance(value, dict):
        for key, child in value.items():
            if key in {"author", "reporter", "creator", "assignee", "updateAuthor", "avatarUrls", "emailAddress", "accountId", "votes", "watches"}:
                continue
            yield from walk_fields(child, f"{path}.{key}")


def prediction_snapshot(fields, comments, histories, cutoff):
    """Only use text proven to precede cutoff. Edited comments cannot be back-dated."""
    cut = timestamp(cutoff)
    if cut is None:
        return {"text": "", "state": "missing_cutoff", "excluded": ["All current text: no decision cutoff"]}
    excluded, texts = [], []
    updated = timestamp(fields.get("updated"))
    created = timestamp(fields.get("created"))
    for field in ["summary", "description", "environment"]:
        value = fields.get(field)
        if not value:
            continue
        if created is None or created > cut:
            excluded.append(field + ": created after cutoff or unknown")
            continue
        if updated and updated <= cut:
            texts.append(plain(value))
            continue
        edits = [(timestamp(h.get("created")), item) for h in histories for item in h.get("items", [])
                 if item.get("field", "").lower() == field and timestamp(h.get("created"))]
        later = sorted((t, i) for t, i in edits if t > cut)
        if later and "fromString" in later[0][1]:
            texts.append(plain(later[0][1]["fromString"]))
        else:
            # Absence of an edit in a possibly incomplete history is not proof of immutability.
            excluded.append(field + ": historical text not proven")
    for comment in comments:
        created_at, updated_at = timestamp(comment.get("created")), timestamp(comment.get("updated"))
        if created_at and updated_at and created_at <= cut and updated_at <= cut:
            texts.append(plain(comment.get("body", "")))
        else:
            excluded.append("comment:" + str(comment.get("id")) + ": post-cutoff/edited/unknown")
    return {"text": "\n".join(texts), "state": "point_in_time_partial" if excluded else "point_in_time",
            "excluded": excluded}


def propose_category(text):
    s = text.lower()
    if re.search(r"no (?:adf )?(?:change|modification)|not (?:a|an) adf change|software.only|verify.*(?:adf|server)", s):
        return "verification_only"
    if re.search(r"cancel|defer|inherit|\bretain\b|hold|next week|not required|unnecessary|already bundled|pending|blocked", s):
        return "defer_inherit_block"
    if re.search(r"both.*(?:dna|fusion)|shared|synchron|across.*variant", s):
        return "shared_sync"
    if re.search(r"(?:version|dependency|package|ruleset|wrapper|deb|pipeline).*(?:update|pin|upgrade)|(?:update|upgrade).*(?:version|package|ruleset|wrapper)", s):
        return "dependency_pin"
    if re.search(r"param|threshold|metadata|primer|kit\b|mapping|rename|setting|flag|argument|analysisargs", s):
        return "parameter_metadata"
    if re.search(r"(?:add|replace|bundle|include|copy|remove|use|update).*(?:file|script|baseline|\.bed|\.ini|\.json|\.h5|\.vcf|asset|reference|ruleset)", s):
        return "approved_file"
    if re.search(r"verify|test|validation|check", s):
        return "verification_only"
    return "investigation_code"


def clause_candidates(text):
    # Keep version decimals intact. Separate independent bullet/paragraph and action clauses.
    return [s.strip(" |\t-") for s in re.split(r"\n+|;\s*|(?<=[.!?])\s+(?=[A-Z])|\s+and\s+(?=(?:update|replace|remove|verify|add|change|synchroni[sz]e)\b)", text)
            if len(s.strip()) >= 18]


def action_proposals(issue, associations, refs):
    result, seen = [], {}
    fields = issue["fields"]
    sources = [("description", fields.get("description", ""), fields.get("updated"), refs["description"])]
    for c in issue["comments"]:
        sources.append(("comment:" + str(c.get("id")), c.get("body", ""), c.get("updated"), c["source"]))
    for name, entry in fields.get("customFields", {}).items():
        if re.search(r"acceptance|requirement|decision", name, re.I):
            value = entry.get("value") if isinstance(entry, dict) else entry
            if isinstance(value, (str, list, dict)) and value:
                sources.append(("custom:" + name, value, fields.get("updated"), {**refs["description"], "locator": "fields.customFields." + name}))
    for location, body, available, source in sources:
        text = plain(body)
        struck = [scrub(n.text()) for n in Document(body).root.walk({"s", "del", "strike"})] if isinstance(body, str) else []
        for clause in clause_candidates(text):
            if not re.search(r"\b(add|replace|update|change|remove|bundle|include|use|verify|test|fix|investigat\w*|cancel\w*|defer\w*|inherit\w*|hold|retain|parameter|threshold|pin|upgrade|need\w*)\b", clause, re.I):
                continue
            category = propose_category(clause)
            target_candidates = sorted(set(re.findall(r"(?<![\w])(?:[\w.+-]+/)*[\w.+-]+\.(?:ini|json|bed|vcf|h5|deb|py|sh|txt|xml|properties|zip)\b", clause, re.I)))
            mode = "manual" if category == "investigation_code" else "assisted_review"
            if category == "defer_inherit_block" and re.search(r"\b(?:pending|blocked|missing|awaiting)\b", clause, re.I):
                mode = "blocked"
            crossed_out = any(clause in t or (len(t) > 18 and t in clause) for t in struck)
            if crossed_out:
                mode = "blocked"
            key = digest([issue["key"], re.sub(r"\s+", " ", clause).lower()])
            if key in seen:
                seen[key]["evidence"].append({**source, "excerpt": clause, "available_at": available})
                continue
            aid = stable("action", issue["key"], location, key)
            row = {"id": aid, "issue_key": issue["key"], "release_ids": sorted(associations),
                   "release_association_state": "candidate_from_issue_listing_requires_action_scope_review",
                   "category": category, "execution_mode": mode, "text": clause,
                   "target": None, "value": None, "version": None, "variant_scope": [],
                   "target_candidates": target_candidates, "version_candidates": VERSION_RE.findall(clause),
                   "prerequisites": ["Review exact action and release applicability", "Supply approved target/value/input evidence"],
                   "verification_requirements": [], "label_strength": "weak", "reviewer_state": "unreviewed",
                   "implemented_action": None, "implementation_diff": None, "released_artifact_evidence": None,
                   "verification_result": None, "disagreement": None,
                   "episode_group": stable("episode", issue["key"]),
                   "historical_state": "struck_through_history_requires_release_scope_review" if crossed_out else "dated_hold_not_current_permanent_block" if re.search(r"hold|next week", clause, re.I) else "dated_proposal_requires_scope_review",
                   "evidence": [{**source, "excerpt": clause, "available_at": available}],
                   "needed_annotations": ["Confirm action boundaries, category and release/variant scope",
                      "Recover decision cutoff and original text", "Link approved exact target and value",
                      "Link implementing diff, released bytes and verification outcome", "Record reviewer and disagreements"],
                   "synthetic": False}
            seen[key] = row
            result.append(row)
    return result


def ingest(root=ROOT):
    root = Path(root)
    issues, pages, versions, histories, comments, remotes, attachments = {}, {}, {}, collections.defaultdict(list), collections.defaultdict(dict), {}, []
    page_comments, raw_manifest, pagination, errors, field_names, seen_jobs = [], [], [], [], {}, set()
    tree_inventory, macro_records = [], []
    references_by_path, raw_issues = {}, {}
    history_totals, version_inventories = {}, collections.defaultdict(list)
    for path in sorted((root / "data/raw").rglob("*.json")):
        if "attachments" in path.parts or path.name in {"issue_keys.json", "linked_page_ids.json", "jira_issue_inventory.json", "collection_wave1.json"}:
            continue
        try:
            envelope = read_json(path)
            if not isinstance(envelope, dict):
                continue
            data = payload(envelope)
            if not isinstance(data, (dict, list)):
                continue
            rpath = str(path.relative_to(root))
            ref = {"path": rpath, "sha256": file_hash(path), "locator": "", "url": None, "collected_at": envelope.get("collected_at")}
            references_by_path[rpath] = ref
            raw_manifest.append({**ref, "collected_at": envelope.get("collected_at"), "bytes": path.stat().st_size,
                                 "state": "inaccessible" if (isinstance(data, dict) and data.get("error")) or envelope.get("error") else "collected"})
            request = envelope.get("request", envelope.get("job", {}).get("inputs", {}))
            request = request if isinstance(request, dict) else {}
            tool = envelope.get("tool", envelope.get("operation", envelope.get("job", {}).get("operation", "")))
            if envelope.get("job", {}).get("id"):
                seen_jobs.add(envelope["job"]["id"])
            if envelope.get("error") or (isinstance(data, dict) and data.get("error")):
                errors.append({"path": rpath, "reason": data.get("message", envelope.get("error")), "state": "inaccessible", "request": request})
                continue
            if "descendants_" in path.name or tool == "getConfluenceContentDescendants":
                tree_inventory.extend({**v, "source": ref} for v in data.get("results", []) if isinstance(v, dict))
            if tool == "resolveConfluenceContentMacros":
                macro_records.append({"page_id": str(data.get("contentId", request.get("contentId"))), "data": data, "source": ref})
            if tool == "getConfluenceContentVersion" and data.get("body"):
                pid = str(request.get("contentId"))
                version = request.get("versionNumber", data.get("version", {}).get("number"))
                versions[(pid, str(version))] = ({**data, "id": pid, "type": data.get("contentType", "page")}, ref)
            if isinstance(data, list):
                if "remote" in path.name.lower() or tool == "listJiraIssueRemoteIssueLinks":
                    resource = envelope.get("resource") or request.get("issueIdOrKey") or re.search(r"([A-Z][A-Z0-9_]+-\d+)", path.name).group(1)
                    remotes[resource] = (data, ref)
                continue
            if data.get("type") in {"page", "blogpost"} and data.get("body"):
                pid = str(data["id"])
                if "historical" in path.name or "version_body" in path.name or tool == "getConfluenceContentVersion":
                    ver = request.get("versionNumber", data.get("version", {}).get("number", data.get("number")))
                    versions[(pid, str(ver))] = (data, ref)
                else:
                    old_page = pages.get(pid)
                    revision = int(data.get("metadata", {}).get("version", {}).get("number", data.get("version", {}).get("number", 0)) or 0)
                    previous_revision = int(old_page[0].get("metadata", {}).get("version", {}).get("number", old_page[0].get("version", {}).get("number", 0)) or 0) if old_page else -1
                    if not old_page or (revision, ref.get("collected_at") or "") >= (previous_revision, old_page[1].get("collected_at") or ""):
                        pages[pid] = (data, ref)
            values = data.get("issues", [data] if data.get("key") and data.get("fields") else [])
            if not isinstance(values, list):
                values = []
            for issue in values:
                if not isinstance(issue, dict) or not isinstance(issue.get("fields"), dict):
                    continue
                key, fields = issue.get("key"), issue.get("fields", {})
                if not key:
                    continue
                old = issues.get(key)
                updated = timestamp(fields.get("updated"))
                old_updated = timestamp(old[0]["fields"].get("updated")) if old else None
                rank = (updated.timestamp() if updated else float("-inf"), len(fields), envelope.get("collected_at") or "", len(json.dumps(issue)))
                old_rank = (old_updated.timestamp() if old_updated else float("-inf"), len(old[0]["fields"]), old[1].get("collected_at") or "", len(json.dumps(old[0]))) if old else None
                if old is None or rank > old_rank:
                    issues[key] = (issue, ref)
                for c in fields.get("comment", {}).get("comments", []):
                    comments[key][str(c["id"])] = {**c, "source": {**ref, "locator": f"issue:{key}/comment:{c['id']}", "url": SITE + "/browse/" + key + "?focusedCommentId=" + str(c["id"])}}
                for name, field in fields.get("customFields", {}).items():
                    if isinstance(field, dict) and field.get("id"):
                        field_names[field["id"]] = {"name": name, "source": {**ref, "locator": "fields.customFields." + name}}
            match = re.search(r"([A-Z][A-Z0-9_]+-\d+)", path.name)
            resource = envelope.get("resource") or request.get("issueIdOrKey") or (match.group(1) if match else None)
            if tool == "listJiraIssueRemoteIssueLinks" and resource:
                remotes[resource] = (data.get("links", data.get("remoteIssueLinks", data.get("results", []))), ref)
            if resource and "comments" in data and not values:
                for c in data["comments"]:
                    comments[resource][str(c["id"])] = {**c, "source": {**ref, "locator": f"issue:{resource}/comment:{c['id']}", "url": SITE + "/browse/" + resource + "?focusedCommentId=" + str(c["id"])}}
            if resource and ("values" in data or "histories" in data) and ("changelog" in path.name.lower() or tool == "listJiraIssueChangelogs"):
                if data.get("total") is not None:
                    history_totals[resource] = max(data["total"], history_totals.get(resource, 0))
                for h in data.get("values", data.get("histories", [])):
                    histories[resource].append({**h, "source": {**ref, "locator": "history:" + str(h.get("id"))}})
            if tool == "listConfluenceContentVersions" or "versions_" in path.name:
                pid = request.get("contentId") or path.stem.split("_")[1]
                version_inventories[str(pid)].extend(data.get("results", []))
            if ("attachments_" in path.name and "confluence" in path.parts) or tool == "listConfluenceAttachments":
                pid = request.get("contentId") or request.get("id") or path.stem.split("_")[1]
                for a in data.get("results", []):
                    attachments.append({**a, "owner": "page:" + str(pid), "system": "confluence", "source": ref})
            if ("comments_" in path.name and "confluence" in path.parts) or tool == "listConfluenceComments":
                page_comments.extend({**c, "source": ref} for c in data.get("results", data.get("comments", [])))
            known_op = tool if tool in {"listJiraIssueComments", "listJiraIssueChangelogs", "getConfluenceContentDescendants", "listConfluenceAttachments", "listConfluenceContentVersions", "listConfluenceComments", "searchJiraIssuesUsingJql"} else None
            if not known_op:
                for token, op in [("versions_", "listConfluenceContentVersions"), ("attachments_", "listConfluenceAttachments"), ("descendants_", "getConfluenceContentDescendants")]:
                    if token in path.name:
                        known_op = op
            if known_op:
                try:
                    nxt = next_page(data, known_op, request)
                    if nxt:
                        pagination.append(job(known_op, str(resource or request.get("contentId", request.get("id", "unknown"))), nxt, "pagination", ref, priority=1))
                except ValueError as exc:
                    errors.append({"path": rpath, "state": "partial", "reason": str(exc)})
        except (ValueError, OSError, TypeError, KeyError) as exc:
            errors.append({"path": str(path), "state": "partial", "reason": str(exc)})
    releases, table_audit, edges, nodes, queue = [], [], [], [], list(pagination)
    discovered_keys, linked_pages = set(), set()
    first_seen = min((r["collected_at"] for r in raw_manifest if r["collected_at"]), default=now())
    for pid, (page, ref) in pages.items():
        url = SITE + "/wiki/spaces/IRS/pages/" + pid
        ref.update(url=url)
        parsed, audit = release_tables(page, ref)
        releases.extend(parsed)
        table_audit.extend(audit)
        nodes.append({"id": "page:" + pid, "type": "page", "title": page.get("title"), "source": ref})
        body = page.get("body", {}).get("value", page.get("body", {}).get("storage", {}).get("value", ""))
        document = Document(body).root
        text = document.text()
        discovered_keys.update(KEY_RE.findall(text))
        for occurrence, m in enumerate(KEY_RE.finditer(text)):
            edges.append({"id": stable("edge", pid, m.group(), occurrence), "source": "page:" + pid, "target": m.group(),
                          "type": "page_reference", "direction": "outward", "depth": 0,
                          "first_seen": first_seen, "source_location": {**ref, "locator": "rendered_text", "start": m.start(), "end": m.end()},
                          "membership_status": "contextual", "membership_rationale": "Mention alone is not release membership"})
        for anchor in document.walk({"a"}):
            href = anchor.attrs.get("href", "")
            linked_pid = confluence_page_id(href)
            if linked_pid:
                linked_pages.add(linked_pid)
                edges.append({"id": stable("edge", pid, linked_pid, "page_link", href), "source": "page:" + pid,
                    "target": "page:" + linked_pid, "type": "page_link", "direction": "outward", "depth": 0,
                    "first_seen": ref.get("collected_at") or first_seen, "source_location": {**ref, "locator": "anchor.href", "destination": clean_url(href)},
                    "membership_status": "contextual", "membership_rationale": "Linked page requires relevance review"})
        # Every wrapper is recorded, including unsupported ones; explicit IDs avoid the 10-macro all-mode cap.
        macros = []
        for node in document.walk():
            if node.attrs.get("data-type") == "extension":
                try:
                    params = json.loads(node.attrs.get("data-parameters", "{}"))
                    mid = params.get("macroMetadata", {}).get("macroId", {}).get("value")
                    if mid:
                        macros.append(mid)
                except ValueError:
                    pass
        if macros and not any((root / "data/raw/connected/confluence").glob("macros_" + pid + "*")):
            for i in range(0, len(macros), 10):
                queue.append(job("resolveConfluenceContentMacros", "page:" + pid,
                                 {"contentId": pid, "macroIds": macros[i:i + 10]}, "resolve_macro_wrappers", ref, 5))
    # Repeated rows/name cells are occurrences of one release identity, not independent releases.
    deduplicated = {}
    for release in releases:
        if release["id"] not in deduplicated:
            deduplicated[release["id"]] = release
            release["source_occurrences"] = [release["source_revisions"][0]["locator"]]
        else:
            existing = deduplicated[release["id"]]
            existing["source_revisions"].extend(release["source_revisions"])
            existing["source_occurrences"].append(release["source_revisions"][0]["locator"])
            existing["listed_issue_keys"] = sorted(set(existing["listed_issue_keys"]) | set(release["listed_issue_keys"]))
            existing["package_references"] = sorted(set(existing["package_references"]) | set(release["package_references"]))
            if existing.get("release_date") != release.get("release_date"):
                existing.update(chronology_state="conflicting_row_dates_requires_review", release_date=None)
    releases = list(deduplicated.values())
    # Optional engineer-supplied chronology annotations. No approval is inferred here.
    for annotation in read_jsonl(root / "data/release_annotations.jsonl"):
        if annotation.get("id") in deduplicated and annotation.get("reviewer") and annotation.get("evidence"):
            release = deduplicated[annotation["id"]]
            for field in ["release_date", "decision_cutoff", "cutoff_evidence", "cutoff_state"]:
                if annotation.get(field) is not None:
                    release[field] = annotation[field]
    associations = collections.defaultdict(set)
    release_map = {r["id"]: r for r in releases}
    historical_rows = []
    for (pid, revision), (historical_page, historical_source) in versions.items():
        current = pages.get(pid, ({}, {}))[0]
        historical_page = {**historical_page, "title": historical_page.get("title", current.get("title", "Unknown historical page")),
                           "metadata": {"version": {"number": revision}}}
        prior_rows, _ = release_tables(historical_page, historical_source)
        for prior in prior_rows:
            discovered_keys.update(prior["listed_issue_keys"])
            for key in prior["listed_issue_keys"]:
                edges.append({"id": stable("edge", pid, revision, prior["id"], key), "source": "page:" + pid, "target": key,
                    "type": "historical_release_reference", "direction": "outward", "depth": 0,
                    "first_seen": historical_source.get("collected_at") or first_seen, "source_location": prior["source_revisions"][0],
                    "membership_status": "historical_listed_support_requires_reconciliation",
                    "membership_rationale": "Historical row listing; later removal is not assumed implemented or omitted"})
            matches = [r["id"] for r in releases if r["source_page"] == pid and r["family"] == prior["family"]
                       and r["software_version"] == prior["software_version"] and r["workflow_version"] == prior["workflow_version"]
                       and r["adf_revision"] is not None and r["adf_revision"] == prior["adf_revision"] and r["variant_scope"] == prior["variant_scope"]]
            historical_rows.append({**prior, "historical_version": revision, "current_release_matches": matches,
                                    "state": "historical_reference_not_an_independent_case", "identity_review_required": len(matches) != 1})
            if len(matches) == 1:
                release_map[matches[0]]["source_revisions"].extend(prior["source_revisions"])
    for entry in tree_inventory:
        parent, child = str(entry.get("parentId", "11568923")), str(entry.get("id"))
        edges.append({"id": stable("edge", parent, child, "page_child"), "source": "page:" + parent,
                      "target": "page:" + child, "type": "page_child", "direction": "outward", "depth": entry.get("depth"),
                      "first_seen": entry["source"].get("collected_at") or first_seen, "source_location": entry["source"],
                      "membership_status": "page_hierarchy", "membership_rationale": "Native Confluence descendant relationship"})
        if child not in pages:
            queue.append(job("getConfluenceContent", "page:" + child, {"content_id": child, "content_format": "html", "detail": "full"}, "discovered_descendant", entry["source"], 4))
    for macro in macro_records:
        for location, text in walk_fields(macro["data"], "macro"):
            for index, match in enumerate(KEY_RE.finditer(plain(text))):
                discovered_keys.add(match.group())
                edges.append({"id": stable("edge", macro["page_id"], location, index, match.group()), "source": "page:" + macro["page_id"],
                              "target": match.group(), "type": "macro_reference", "direction": "outward", "depth": 0,
                              "first_seen": macro["source"].get("collected_at") or first_seen, "source_location": {**macro["source"], "locator": location},
                              "membership_status": "contextual", "membership_rationale": "Resolved macro reference; row membership requires review"})
    for release in releases:
        edges.append({"id": stable("edge", release["source_page"], release["id"]), "source": "page:" + release["source_page"], "target": release["id"],
                      "type": "release_source_page", "direction": "outward", "depth": 0, "first_seen": release["source_revisions"][0].get("collected_at") or first_seen,
                      "source_location": release["source_revisions"][0], "membership_status": "release_evidence", "membership_rationale": "Release identity extracted from this specific row"})
        for key in release["listed_issue_keys"]:
            associations[key].add(release["id"])
            discovered_keys.add(key)
            edges.append({"id": stable("edge", release["id"], key), "source": release["id"], "target": key,
                          "type": "release_table_listing", "direction": "outward", "first_seen": first_seen, "depth": 0,
                          "source_location": release["source_revisions"][0], "membership_status": "listed_support_requires_reconciliation",
                          "membership_rationale": "Explicit release row listing; implementation membership not yet verified"})
        candidates = [k for k in release["listed_issue_keys"] if k in issues and re.search(r"\bADF\b.*(?:v?\d|integrat|bundl)|integrat.*\bADF\b|bundl.*\bADF\b", plain(issues[k][0]["fields"].get("summary", "")), re.I)]
        release["release_ticket_candidates"] = candidates
        if len(candidates) == 1:
            release["release_ticket"] = candidates[0]
            ticket = issues[candidates[0]][0]
            progress = [(timestamp(h.get("created")), h) for h in histories[candidates[0]]
                        if any(it.get("field") == "status" and re.search(r"in progress", it.get("toString", ""), re.I) for it in h.get("items", []))]
            valid_progress = [(t, h) for t, h in progress if t is not None]
            if valid_progress and release["cutoff_state"] != "confirmed":
                event_time, event = min(valid_progress, key=lambda item: item[0])
                release.update(decision_cutoff=event_time.isoformat(), cutoff_evidence={"event": "first_release_ticket_in_progress", "source": event["source"], "interpretation": "Proxy for start of bundling; requires release-owner confirmation"}, cutoff_state="proxy_requires_confirmation")
    normalized_issues, weak_actions, contextual_keys, historical_views, href_references = [], [], set(), [], []
    for key, (raw, ref) in sorted(issues.items()):
        fields = raw["fields"]
        cref = {**ref, "url": SITE + "/browse/" + key, "locator": "fields.description"}
        cs = sorted(comments[key].values(), key=lambda c: (c.get("created", ""), str(c.get("id"))))
        hs = list({str(h.get("id")): h for h in histories[key]}.values())
        current = {"key": key, "fields": fields, "comments": cs, "histories": hs}
        for rid in associations[key]:
            release = release_map[rid]
            if release.get("decision_cutoff"):
                view = prediction_snapshot(fields, cs, hs, release["decision_cutoff"])
                historical_views.append({"issue_key": key, "release_id": rid, "cutoff": release["decision_cutoff"],
                                         "cutoff_state": release["cutoff_state"], "source": cref, **view})
        related_paths = list(walk_fields(fields))
        for comment in cs:
            body = comment.get("body", "")
            if isinstance(body, str):
                related_paths.append(("comment:" + str(comment.get("id")), body))
            else:
                related_paths.extend(walk_fields(body, "comment:" + str(comment.get("id"))))
        related_paths.extend(walk_fields(hs, "history"))
        if key in remotes:
            related_paths.extend(walk_fields(remotes[key][0], "remote_links"))
        for location, value in related_paths:
            text = plain(value)
            page_urls = set(re.findall(r"https?://[^\s<>\"']+|/wiki/[^\s<>\"']+", value))
            for page_url in page_urls:
                linked_pid = confluence_page_id(page_url)
                if linked_pid:
                    linked_pages.add(linked_pid)
                    edges.append({"id": stable("edge", key, location, linked_pid, "confluence_link"), "source": key,
                        "target": "page:" + linked_pid, "type": "confluence_remote_link" if location.startswith("remote_links") else "confluence_page_reference",
                        "direction": "outward", "depth": 1, "first_seen": cref.get("collected_at") or first_seen,
                        "source_location": {**cref, "locator": location, "destination": clean_url(page_url)},
                        "membership_status": "contextual", "membership_rationale": "Linked document is context, not confirmed release membership"})
            # Links labeled "see issue" still carry references in their href, not visible text.
            for link in re.finditer(r"(?:href|data-url)=[\"']([^\"']+)[\"']", value if isinstance(value, str) else "", re.I):
                href = link.group(1)
                if href.startswith(("https://", "http://")):
                    href_references.append({"owner": key, "url": clean_url(href), "source": {**cref, "locator": location + ".href", "start": link.start(1), "end": link.end(1)}})
                for index, match in enumerate(KEY_RE.finditer(href)):
                    target = match.group()
                    if target == key or target in KEY_RE.findall(text):
                        continue
                    contextual_keys.add(target)
                    edges.append({"id": stable("edge", key, location, "href", index, target), "source": key, "target": target,
                        "type": "historical_reference" if location.startswith("history") else "smart_link_reference", "direction": "outward", "depth": 1,
                        "first_seen": cref.get("collected_at") or first_seen, "source_location": {**cref, "locator": location + ".href", "start": link.start(1), "end": link.end(1), "representation": "html_attribute"},
                        "membership_status": "contextual", "membership_rationale": "Link destination; not confirmed release implementation"})
            for index, m in enumerate(KEY_RE.finditer(text)):
                target = m.group()
                if target == key:
                    continue
                contextual_keys.add(target)
                edges.append({"id": stable("edge", key, location, target, index), "source": key, "target": target,
                              "type": "historical_reference" if location.startswith("history") else "mentions", "direction": "outward", "depth": 1 if key in discovered_keys else 2,
                              "first_seen": first_seen, "source_location": {**cref, "locator": location, "start": m.start(), "end": m.end(), "excerpt": text[max(0, m.start()-100):m.end()+100]},
                              "membership_status": "contextual", "membership_rationale": "Text reference; no automatic release membership"})
        for link in fields.get("issuelinks", []):
            for direction in ["inward", "outward"]:
                target = link.get(direction + "Issue", {}).get("key")
                if target:
                    contextual_keys.add(target)
                    edges.append({"id": stable("edge", key, link.get("id"), direction), "source": key, "target": target,
                                  "type": link.get("type", {}).get("name", "formal_link"), "direction": direction, "depth": 1,
                                  "first_seen": first_seen, "source_location": {**cref, "locator": "fields.issuelinks." + str(link.get("id"))},
                                  "membership_status": "contextual", "membership_rationale": "Formal link type does not prove implemented release change"})
        parent = fields.get("parent", {}).get("key")
        if parent:
            contextual_keys.add(parent)
            edges.append({"id": stable("edge", key, parent, "parent"), "source": key, "target": parent, "type": "parent", "direction": "outward", "depth": 1,
                          "first_seen": first_seen, "source_location": {**cref, "locator": "fields.parent"}, "membership_status": "contextual_container", "membership_rationale": "Fetch parent context without expanding unrelated siblings"})
        for child in fields.get("subtasks", []):
            target = child.get("key")
            if target:
                contextual_keys.add(target)
                edges.append({"id": stable("edge", key, target, "subtask"), "source": key, "target": target, "type": "subtask", "direction": "outward", "depth": 1,
                              "first_seen": first_seen, "source_location": {**cref, "locator": "fields.subtasks"}, "membership_status": "contextual", "membership_rationale": "Subtask relationship requires scope verification"})
        expected = fields.get("comment", {}).get("total")
        comments_complete = expected is not None and len(cs) >= expected
        history_complete, history_total = False, history_totals.get(key)
        if history_total is not None:
            history_complete = len(hs) >= history_total
        normalized_issues.append({"id": stable("snapshot", key, ref["sha256"]), "issue_key": key,
            "summary": plain(fields.get("summary")), "description": plain(fields.get("description")),
            "relevant_custom_fields": {name: plain(v.get("value") if isinstance(v, dict) else v) for name, v in fields.get("customFields", {}).items() if re.search(r"acceptance|requirement|decision|build version", name, re.I)},
            "created": fields.get("created"), "updated": fields.get("updated"), "snapshot_cutoff": cref.get("collected_at"), "snapshot_kind": "current_at_collection",
            "source": cref, "release_ids": sorted(associations[key]), "comments": [{"id": c.get("id"), "body": plain(c.get("body")), "created": c.get("created"), "updated": c.get("updated"), "source": c["source"]} for c in cs],
            "completeness": {"fields": "collected_all_available", "field_mapping": "observed_custom_fields", "comments_retrieved": len(cs), "comments_reported": expected,
                             "comments": "collected" if comments_complete else "partial", "history_retrieved": len(hs), "history_reported": history_total,
                             "history": "collected" if history_complete else "pending", "remote_links": "collected" if key in remotes else "pending"},
            "issue_type": fields.get("issuetype", {}).get("name"), "current_status": fields.get("status", {}).get("name"),
            "point_in_time_state": "not_reconstructed", "test_mapping_state": "unresolved_custom_fields_and_remote_links"})
        if not comments_complete:
            queue.append(job("listJiraIssueComments", key, {"issueIdOrKey": key, "startAt": 0, "maxResults": 100, "view": "evidence", "responseContentFormat": "html"}, "complete_comments", cref, 2))
        if not history_complete:
            queue.append(job("listJiraIssueChangelogs", key, {"issueIdOrKey": key, "startAt": 0, "maxResults": 50}, "historical_field_reconstruction", cref, 10))
        if key not in remotes:
            queue.append(job("listJiraIssueRemoteIssueLinks", key, {"issueIdOrKey": key}, "external_and_test_reference_discovery", cref, 11))
        for attachment in fields.get("attachment", []):
            attachments.append({**attachment, "owner": key, "system": "jira", "source": {**ref, "locator": "fields.attachment." + str(attachment["id"])}})
        # Only release-associated issues produce action proposals, not generic epic siblings.
        if associations[key]:
            weak_actions.extend(action_proposals(current, associations[key], {"description": cref}))
        nodes.append({"id": key, "type": "issue", "title": plain(fields.get("summary")), "state": "collected", "release_ids": sorted(associations[key])})
        raw_issues[key] = current
    # Context nodes and all failed candidates remain reviewable. No project-name filter.
    existing_errors = {e.get("resource") for e in read_json(root / "data/collection_failures.json", [])}
    incoming_index = collections.defaultdict(list)
    for edge in edges:
        incoming_index[edge["target"]].append(edge)
    for key in sorted((discovered_keys | contextual_keys) - issues.keys()):
        is_seed = key in discovered_keys
        incoming = incoming_index[key]
        # References from generic containers are recorded, but do not fan out through unrelated siblings.
        relevant = is_seed or any(e["source"] in discovered_keys for e in incoming)
        reason = "release_source_reference" if is_seed else "direct_context_of_release_issue" if relevant else "requires_relevance_review_before_deeper_expansion"
        nodes.append({"id": key, "type": "issue", "state": "inaccessible" if key in existing_errors else "pending", "reason": reason})
        if key not in existing_errors and relevant:
            queue.append(job("getJiraIssue", key, {"issueIdOrKey": key, "view": "full", "fields": ["*all"], "expand": "names", "responseContentFormat": "html"}, reason, incoming[0]["source_location"] if incoming else None, 3 if is_seed else 12))
    for pid in sorted(linked_pages - pages.keys()):
        nodes.append({"id": "page:" + pid, "type": "page", "state": "pending", "reason": "linked_page_outside_descendant_tree"})
        queue.append(job("getConfluenceContent", "page:" + pid, {"content_id": pid, "content_format": "html", "detail": "full"}, "linked_page_outside_descendant_tree", priority=4))
    for pid, (page, ref) in pages.items():
        for prefix, operation, inputs in [
            ("versions", "listConfluenceContentVersions", {"contentId": pid, "limit": 250}),
            ("attachments", "listConfluenceAttachments", {"contentId": pid, "limit": 250}),
            ("comments", "listConfluenceComments", {"content-id": pid, "limit": 250, "body-format": "html", "include-replies": True})]:
            if not any((root / "data/raw/connected/confluence").glob(prefix + "_" + pid + "*")):
                queue.append(job(operation, "page:" + pid, inputs, "linked_page_" + prefix, ref, 9))
    historical_requests = {}
    for release in releases:
        cutoff = timestamp(release.get("decision_cutoff"))
        if cutoff is None:
            continue
        pid = release["source_page"]
        listed = version_inventories[pid]
        eligible = [v for v in listed if timestamp(v.get("createdAt")) and timestamp(v["createdAt"]) <= cutoff]
        if eligible:
            version = max(eligible, key=lambda v: v["number"])
            identity = (pid, str(version["number"]))
            if identity not in versions:
                historical_requests[identity] = job("getConfluenceContentVersion", "page:" + pid,
                    {"contentId": pid, "versionNumber": version["number"], "content_format": "html"},
                    "nearest_historical_page_body_before_bundling_proxy_cutoff", release["source_revisions"][0], 15)
            else:
                release["historical_snapshot_recovered"] = True
                release["historical_page_source"] = versions[identity][1]
    queue.extend(historical_requests.values())
    artifacts = []
    seen_artifacts = set()
    for a in attachments:
        aid = str(a.get("id"))
        identity = (a["system"], aid)
        if identity in seen_artifacts:
            continue
        seen_artifacts.add(identity)
        original_dir = root / "data/raw/attachments" / (a["system"] + "_" + aid)
        files = [p for p in original_dir.glob("*") if p.is_file() and not p.name.endswith(".part")]
        filename = a.get("filename", a.get("title", ""))
        artifacts.append({"id": a["system"] + ":" + aid, "owner": a["owner"], "filename": filename,
            "artifact_type": "archive_reference" if filename.lower().endswith(".zip") else "attachment",
            "bytes_reported": a.get("size", a.get("fileSize")), "mime_type": a.get("mimeType", a.get("mediaType")),
            "source_url": clean_url(a.get("content", a.get("downloadLink")) or ""), "source": a["source"],
            "version": a.get("version"), "media_id": a.get("fileId"), "timestamp": a.get("created", a.get("version", {}).get("createdAt") if isinstance(a.get("version"), dict) else None),
            "path": str(files[0].relative_to(root)) if files else None, "sha256": file_hash(files[0]) if files else None,
            "access_state": "collected" if files else "pending", "failure_reason": None if files else "Original bytes not yet downloaded; metadata/card is not binary evidence"})
    outputs = root / "data/extracted"
    write_jsonl(outputs / "releases.jsonl", sorted(releases, key=lambda r: (r["family"], semver(r["adf_revision"]), r["id"])))
    write_jsonl(outputs / "issues.jsonl", normalized_issues)
    write_jsonl(outputs / "artifacts.jsonl", artifacts)
    previous_edges = {e["id"]: e for e in read_jsonl(outputs / "reference_edges.jsonl")}
    adjacency = collections.defaultdict(set)
    for edge in edges:
        if KEY_RE.fullmatch(edge["source"]) and KEY_RE.fullmatch(edge["target"]):
            adjacency[edge["source"]].add(edge["target"])
    distances = {key: 0 for key in discovered_keys}
    frontier = collections.deque(discovered_keys)
    while frontier:
        source = frontier.popleft()
        for target in adjacency[source]:
            if target not in distances:
                distances[target] = distances[source] + 1
                frontier.append(target)
    for edge in edges:
        observed = edge["source_location"].get("collected_at") or edge["first_seen"]
        old = previous_edges.get(edge["id"], {})
        previous = old.get("first_seen") if old.get("first_seen_basis") == "archived_collection_observation_not_release_date" else None
        edge["first_seen"] = min(observed, previous) if previous else observed
        edge["first_seen_basis"] = "archived_collection_observation_not_release_date"
        if KEY_RE.fullmatch(edge["source"]):
            edge["depth"] = distances[edge["source"]] + 1 if edge["source"] in distances else None
    write_jsonl(outputs / "reference_edges.jsonl", list({e["id"]: e for e in edges}.values()))
    write_jsonl(outputs / "source_nodes.jsonl", nodes + [{"id": r["id"], "type": "release", "title": r["release_name"], "family": r["family"]} for r in releases])
    write_jsonl(outputs / "table_review.jsonl", table_audit)
    write_jsonl(outputs / "raw_manifest.jsonl", raw_manifest)
    write_jsonl(outputs / "historical_issue_views.jsonl", historical_views)
    write_jsonl(outputs / "historical_release_rows.jsonl", historical_rows)
    write_jsonl(outputs / "macro_records.jsonl", macro_records)
    # These destination references stay outside the model corpus and retain raw-source spans.
    write_jsonl(outputs / "href_references.jsonl", href_references)
    write_json(outputs / "field_names.json", {"completeness": "observed_nonempty_fields_from_all_fields_reads", "fields": field_names})
    write_jsonl(root / "data/labels/weak_actions.jsonl", weak_actions)
    write_jsonl(root / "data/reference/annotation_queue.jsonl", weak_actions)
    # The exact requested work is durable and can be resumed without refetching collected resources.
    unique_queue = {q["id"]: q for q in queue if q["id"] not in seen_jobs}
    write_json(root / "data/collection_queue.json", sorted(unique_queue.values(), key=lambda q: (q["priority"], q["resource"])))
    manifest = {"generated_at": now(), "source": SITE, "seed_page": "11568923", "pages": len(pages),
                "releases": len(releases), "families": dict(collections.Counter(r["family"] for r in releases)),
                "validated_issues": len(issues), "release_associated_issues": sum(bool(v) for v in associations.values()),
                "references_discovered": len(discovered_keys | contextual_keys), "edges": len({e["id"] for e in edges}),
                "attachments_metadata": len(artifacts), "attachments_downloaded": sum(a["access_state"] == "collected" for a in artifacts),
                "attachment_bytes_reported": sum(a["bytes_reported"] or 0 for a in artifacts),
                "weak_actions": len(weak_actions), "reviewed_actions": 0, "raw_records": len(raw_manifest),
                "historical_issue_views": len(historical_views), "cutoff_proxies": sum(bool(r.get("decision_cutoff")) for r in releases),
                "pending_requests": len(unique_queue), "collection_errors": errors,
                "unexpanded_frontier": [n for n in nodes if n.get("state") in {"pending", "inaccessible"}],
                "operational_limits": {"main_connected_workers": 8, "linked_page_workers": 4, "combined_read_workers_upper_bound": 12,
                                       "rest_workers": 4, "archive_expansion": "see artifacts.LIMITS", "download_budget_bytes": 1024 ** 3},
                "completeness": "partial" if unique_queue or any(a["access_state"] != "collected" for a in artifacts) else "collected"}
    write_json(outputs / "collection_manifest.json", manifest)
    return manifest


def prepare(root=ROOT, annotations=None):
    root = Path(root)
    releases = read_jsonl(root / "data/extracted/releases.jsonl")
    weak = read_jsonl(root / "data/labels/weak_actions.jsonl")
    issues = {r["issue_key"]: r for r in read_jsonl(root / "data/extracted/issues.jsonl")}
    by_id = {a["id"]: a for a in weak}
    reviewed, rejected = [], []
    supplied = read_jsonl(annotations or root / "data/annotations.jsonl")
    for label in supplied:
        missing = [key for key in ["id", "reviewer", "reviewed_at", "evidence", "category", "execution_mode", "release_ids", "label_strength"] if not label.get(key)]
        if missing or label.get("id") not in by_id or label.get("label_strength") not in {"strong", "reviewed"} or label.get("category") not in TAXONOMY or label.get("execution_mode") not in MODES or label.get("synthetic"):
            rejected.append({"id": label.get("id"), "reason": "Missing/invalid reviewed-label fields", "missing": missing})
            continue
        merged = {**by_id[label["id"]], **label, "reviewer_state": "reviewed"}
        # Strong action truth needs implementation/outcome evidence, not merely a closed status.
        if not label.get("implementation_diff") and not label.get("approved_decision"):
            rejected.append({"id": label["id"], "reason": "No implementation diff or approved decision"})
            continue
        reviewed.append(merged)
    write_jsonl(root / "data/labels/reviewed_actions.jsonl", reviewed)
    write_json(root / "data/extracted/annotation_import.json", {"accepted": len(reviewed), "rejected": rejected})
    # Choose release boundaries from evidence dates before any model fit. All equal dates stay together.
    dates = sorted({r["release_date"] for r in releases if r.get("release_date") and r.get("row_state") != "ambiguous_revision"})
    train_end = dates[max(0, int(len(dates) * .6) - 1)] if len(dates) >= 3 else None
    validation_end = dates[max(1, int(len(dates) * .8) - 1)] if len(dates) >= 3 else None
    assignment = {}
    for r in releases:
        date = r.get("release_date") if not r.get("revision_ambiguous") else None
        assignment[r["id"]] = "undated" if not date or not train_end else "train" if date <= train_end else "validation" if date <= validation_end else "test"
    # Group repeated tickets/change episodes: retain carry-over separately; never pretend they are unseen.
    split_order = {"train": 0, "validation": 1, "test": 2, "undated": 3}
    earliest = {}
    for a in weak:
        partitions = [assignment[rid] for rid in a["release_ids"] if rid in assignment]
        earliest[a["issue_key"]] = min(partitions, key=lambda p: split_order[p]) if partitions else "undated"
    inputs, strict, carry = [], [], []
    release_map = {r["id"]: r for r in releases}
    for a in weak:
        rid_candidates = [rid for rid in a["release_ids"] if rid in assignment]
        if not rid_candidates:
            continue
        chosen = min(rid_candidates, key=lambda rid: (split_order[assignment[rid]], release_map[rid].get("release_date") or "9999"))
        release = release_map[chosen]
        # Explicitly retrospective exploratory projection. Answer fields never enter feature files.
        inputs.append({"id": a["id"], "issue_key": a["issue_key"], "release_id": chosen,
                       "family": release["family"], "release_date": release.get("release_date"),
                       "partition": assignment[chosen], "episode_group": a["episode_group"],
                       "text": a["text"], "input_state": "retrospective_current_text",
                       "cutoff": release.get("decision_cutoff"), "source": a["evidence"][0], "synthetic": False})
        if release.get("cutoff_state") == "confirmed" and a["id"] in {l["id"] for l in reviewed}:
            # A future reviewed import must provide separately attested historical text and hashes.
            label = next(l for l in reviewed if l["id"] == a["id"])
            historical = label.get("prediction_input", {})
            source = historical.get("source", {})
            if historical.get("state") == "point_in_time" and historical.get("cutoff") == release.get("decision_cutoff") and source.get("sha256") and timestamp(historical.get("available_at")) and timestamp(historical["available_at"]) <= timestamp(historical["cutoff"]):
                strict.append({**inputs[-1], "text": historical["text"], "input_state": "point_in_time", "source": source})
        for rid in rid_candidates:
            if split_order[assignment[rid]] > split_order[earliest[a["issue_key"]]] and assignment[rid] in {"validation", "test"}:
                carry.append({"action_id": a["id"], "issue_key": a["issue_key"], "release_id": rid, "partition": assignment[rid], "reason": "Ticket occurred in an earlier partition"})
    # Duplicate excerpts across different tickets are conservatively kept in their earliest partition only.
    seen_text = {}
    retained, duplicate_rows = [], []
    for r in sorted(inputs, key=lambda r: (split_order[r["partition"]], r.get("release_date") or "9999", r["id"])):
        normalized = re.sub(r"\b[A-Z][A-Z0-9_]+-\d+\b|\d+(?:\.\d+)+", "<value>", r["text"], flags=re.I).lower()
        fp = digest(re.sub(r"[^a-z0-9<>]+", " ", normalized).strip())
        if fp in seen_text and seen_text[fp]["partition"] != r["partition"]:
            duplicate_rows.append({"id": r["id"], "duplicate_of": seen_text[fp]["id"], "reason": "Copied/near-identical excerpt crosses chronological partition"})
            continue
        seen_text.setdefault(fp, r)
        retained.append(r)
    retained_ids = {r["id"] for r in retained}
    strict = [r for r in strict if r["id"] in retained_ids]
    split_manifest = {"created_at": now(), "frozen_before_model_selection": True,
        "boundary_method": "Release-index dates; 60% / 20% / 20% unique dates; no Jira closure substitutions",
        "train_through": train_end, "validation_through": validation_end, "release_assignment": assignment,
        "release_counts": dict(collections.Counter(assignment.values())), "retrospective_input_counts": dict(collections.Counter(r["partition"] for r in retained)),
        "strict_input_counts": dict(collections.Counter(r["partition"] for r in strict)),
        "reviewed_labels": len(reviewed), "weak_labels": len(weak), "carry_over_occurrences": len(carry),
        "exclusions": {"undated": sum(r["partition"] == "undated" for r in retained), "cross_partition_duplicate_excerpts": len(duplicate_rows)},
        "selection_rule": "Prefer zero erroneous automatic exact plans with at least five validation cases per enabled class, then correct automatic plan count, macro-F1, then lower runtime. With insufficient evidence, freeze advisory-only status and disable all automatic thresholds.",
        "benchmark_status": "blocked" if not strict else "pending_integrity_audit",
        "blocking_reasons": ["No confirmed release decision cutoffs" if not any(r["cutoff_state"] == "confirmed" for r in releases) else None,
                             "No defensible reviewed action labels" if not reviewed else None,
                             "No complete point-in-time prediction views" if not strict else None]}
    split_manifest["blocking_reasons"] = [r for r in split_manifest["blocking_reasons"] if r]
    split_manifest["data_hash"] = digest({"inputs": retained, "strict": strict, "labels": reviewed, "assignments": assignment})
    prior_split = read_json(root / "data/split_manifest.json")
    if prior_split and prior_split.get("data_hash") == split_manifest["data_hash"]:
        split_manifest["created_at"] = prior_split["created_at"]
    existing = read_json(root / "runs/frozen/manifest.json")
    if existing and existing.get("data_hash") != split_manifest["data_hash"] and (root / "runs/benchmark/final_results.json").exists():
        raise ValueError("Prepared data changed after final benchmark was recorded; preserve the campaign and use a new output root")
    write_json(root / "data/split_manifest.json", split_manifest)
    write_jsonl(root / "data/model_inputs/retrospective.jsonl", retained)
    for partition in ["train", "validation", "test"]:
        cases = [r for r in strict if r["partition"] == partition]
        write_jsonl(root / f"data/model_inputs/strict_{partition}.jsonl", cases)
        case_ids = {r["id"] for r in cases}
        destination = root / ("data/reference/test_labels.jsonl" if partition == "test" else f"data/labels/reviewed_{partition}.jsonl")
        write_jsonl(destination, [r for r in reviewed if r["id"] in case_ids])
    write_jsonl(root / "data/reference/carry_over.jsonl", carry)
    write_jsonl(root / "data/reference/duplicate_groups.jsonl", duplicate_rows)
    integrity = {"action_ids_unique": len({r["id"] for r in weak}) == len(weak),
                 "release_ids_unique": len(release_map) == len(releases),
                 "all_action_releases_exist": all(rid in release_map for a in weak for rid in a["release_ids"]),
                 "no_labels_in_feature_files": all(not ({"category", "execution_mode", "label_strength", "implemented_action"} & r.keys()) for r in retained + strict),
                 "reviewed_labels": len(reviewed), "strict_cases": len(strict), "rejected_annotations": len(rejected),
                 "primary_performance_claim_permitted": bool(strict and reviewed and not rejected)}
    write_json(root / "data/extracted/integrity.json", integrity)
    return {"status": "prepared", "split": split_manifest, "integrity": integrity}
