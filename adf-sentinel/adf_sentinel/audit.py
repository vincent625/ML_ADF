from __future__ import annotations

import collections
import difflib
import hashlib
import json
import re
import zipfile
from pathlib import Path

from .common import ROOT, SITE, KEY_RE, digest, file_hash, now, payload, plain, read_json, read_jsonl, write_json, write_jsonl


def reconcile(root=ROOT):
    root = Path(root)
    releases = read_jsonl(root / "data/extracted/releases.jsonl")
    issues = {r["issue_key"]: r for r in read_jsonl(root / "data/extracted/issues.jsonl")}
    plus = next((r for r in releases if r["family"] == "OCA Plus" and r["adf_revision"] == "0.0.8" and r["source_page"] == "11568897"), None)
    ticket = issues.get("IRS-29096")
    counts = collections.Counter(KEY_RE.findall(ticket["description"])) if ticket else collections.Counter()
    confluence_support = set(plus["listed_issue_keys"]) - {"IRS-29096"} if plus else set()
    jira_support = set(counts) - {"IRS-29096"}
    ovat = issues.get("IRS-29057", {})
    no_change = [c for c in ovat.get("comments", []) if re.search(r"not (?:a|an) ADF change", c["body"], re.I)]
    removal = [c for c in ovat.get("comments", []) if re.search(r"removed.*OvatRuleSet.*0\.0\.9", c["body"], re.I)]
    result = {"OCA_Plus_Integration_5": {"release_id": plus["id"] if plus else None,
        "confluence_supporting_keys": sorted(confluence_support), "confluence_supporting_count": len(confluence_support),
        "jira_description_unique_keys": sorted(jira_support), "jira_description_unique_count": len(jira_support),
        "IRS_26136_occurrences": counts["IRS-26136"], "keys_only_in_release_table": sorted(confluence_support - jira_support),
        "interpretation": "Reconciliation question; neither list alone proves omitted fixes. Repeated IRS-26136 is one issue episode.",
        "source": plus["source_revisions"] if plus else None},
        "IRS_29057": {"initial_software_only_no_adf_change": no_change, "later_ruleset_removal_in_0_0_9": removal,
                      "interpretation": "Dated actions differ by release: initial verification and later removal must not collapse into one permanent ticket label."},
        "testing_mapping": "An empty/uncovered saved Xray panel and narrative testing elsewhere represent an evidence mapping gap, not proof no tests ran.",
        "GI_scale": "No global GI-scale assertion; targets and expectations require the specific release/variant contract.",
        "hold_decisions": "Historical next-week holds stay dated, with no invented present-day expiry or permanent block."}
    write_json(root / "runs/audit/reconciliation.json", result)
    return result


def normalized_zip(path):
    records = {}
    with zipfile.ZipFile(path) as archive:
        entries = [e for e in archive.infolist() if not e.is_dir()]
        prefixes = {e.filename.split("/", 1)[0] for e in entries if "/" in e.filename}
        strip = len(prefixes) == 1 and all("/" in e.filename for e in entries)
        for entry in entries:
            name = entry.filename.split("/", 1)[1] if strip else entry.filename
            # Streaming hash ignores ZIP headers, file ordering, and archive timestamps.
            h = hashlib.sha256()
            with archive.open(entry) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(chunk)
            records[name] = {"sha256": h.hexdigest(), "bytes": entry.file_size}
    return records


def artifact_checks(root=ROOT):
    root = Path(root)
    originals, source_blobs, comparisons = [], [], []
    for p in sorted((root / "data/raw/attachments").glob("*/*")):
        if p.is_file() and not p.name.endswith(".part"):
            md5 = hashlib.md5(usedforsecurity=False)
            with p.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    md5.update(chunk)
            originals.append({"path": str(p.relative_to(root)), "bytes": p.stat().st_size, "sha256": file_hash(p), "actual_file_md5": md5.hexdigest(), "method": "hashes_computed_from_downloaded_file_bytes"})
    for phase in ["before", "approved"]:
        metadata = root / ("data/raw/connected/github/dna_tmap_" + phase + ".json")
        path = root / ("data/source_replay/" + phase + "/SeedData/AssayDev/assay/dna/parameters/TmapExecutionActor.ini")
        if metadata.exists() and path.exists():
            content = path.read_bytes()
            git_sha = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
            expected = payload(read_json(metadata))["sha"]
            source_blobs.append({"phase": phase, "sha256": digest(content), "actual_git_blob_sha": git_sha, "expected_git_blob_sha": expected, "passed": git_sha == expected})
    files = {p.name: p for p in (root / "data/raw/attachments").glob("*/*.zip")}
    for variant in ["DNA", "DNAandFusions"]:
        prefix = "Genexus-Oncomine-Focus-v2-GX7-w1.0.0-" + variant + "-SW_7.0-v"
        old, new = files.get(prefix + "0.0.2.zip"), files.get(prefix + "0.0.3.zip")
        if old and new:
            before, after = normalized_zip(old), normalized_zip(new)
            changes = [{"path": key, "before": before.get(key), "after": after.get(key),
                        "change": "added" if key not in before else "removed" if key not in after else "changed"}
                       for key in sorted(before.keys() | after.keys()) if before.get(key) != after.get(key)]
            comparisons.append({"variant": variant, "before": str(old.relative_to(root)), "after": str(new.relative_to(root)),
                                "before_files": len(before), "after_files": len(after), "changes": changes,
                                "scope": "Historical archive content comparison; label-only evidence, no reconstructed ADF build claim"})
    result = {"files_hashed": originals, "pinned_source_blob_checks": source_blobs, "historical_comparisons": comparisons,
              "scope": "Archive/source integrity, separate from software execution, scientific QC, and physical runs"}
    observations = []
    if len(source_blobs) == 2 and all(row["passed"] for row in source_blobs):
        from .plans import actor_value, REAL_TARGET, REAL_COMMIT
        before = root / "data/source_replay/before" / REAL_TARGET
        after = root / "data/source_replay/approved" / REAL_TARGET
        diff_path = root / "runs/audit/IRS-65265-tmap-reference.diff"
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        diff_path.write_text("".join(difflib.unified_diff(before.read_text().splitlines(keepends=True), after.read_text().splitlines(keepends=True), fromfile="pinned-base/"+REAL_TARGET, tofile="pinned-head/"+REAL_TARGET)))
        observations.append({"id": "IRS-65265-observed-tmap-source-change", "issue_key": "IRS-65265",
            "actual_implemented_action": {"target": REAL_TARGET, "parameter": "tmap.custom.tmap.args",
                "before": actor_value(before, "tmap.custom.tmap.args"), "after": actor_value(after, "tmap.custom.tmap.args"),
                "before_sha256": file_hash(before), "after_sha256": file_hash(after), "commit": REAL_COMMIT, "variant_scope": ["DNA"]},
            "implementation_diff": str(diff_path.relative_to(root)),
            "approved_decision_evidence": "https://github.com/thermofisher/csd-adf-gx-manticore-v2-dna-70/pull/3",
            "released_artifact_internal_file_evidence": None, "verification_result": "Pinned Git blob and source-content checks only",
            "full_two_locations_and_variants_requirement": "not established by this one-file replay",
            "label_strength": "source_implementation_observed_not_full_bundling_ground_truth", "reviewer_state": "unreviewed",
            "primary_benchmark_eligible": False, "reason": "Decision-time inputs, exact action scope, released serialized-core mapping, and human action review are incomplete"})
    write_jsonl(root / "data/reference/implementation_observations.jsonl", observations)
    write_json(root / "runs/audit/artifact_checks.json", result)
    return result


def preserve_supplied(root=ROOT):
    root = Path(root)
    supplied = root.parent / "irs-65265-review"
    snapshot = [{"path": str(p.relative_to(root.parent)), "sha256": file_hash(p)} for p in sorted(supplied.rglob("*")) if p.is_file()]
    destination = root / "data/supplied_originals_manifest.json"
    old = read_json(destination)
    if old is None:
        write_json(destination, snapshot)
        return {"status": "baseline_recorded", "files": len(snapshot)}
    return {"status": "unchanged" if old == snapshot else "changed", "files": len(snapshot)}


def run_audit(root=ROOT):
    root = Path(root)
    reconciliation = reconcile(root)
    artifact = artifact_checks(root)
    integrity = read_json(root / "data/extracted/integrity.json", {})
    supplied = preserve_supplied(root)
    source_runs = [read_json(p) for p in sorted((root / "runs/sandbox").glob("*/manifest.json"))]
    result = {"run_at": now(), "integrity": integrity, "supplied_files": supplied,
              "source_blob_checks_passed": all(r["passed"] for r in artifact["pinned_source_blob_checks"]) if len(artifact["pinned_source_blob_checks"]) == 2 else None,
              "sandbox_runs": [{"run_id": r["run_id"], "scope": r["scope"], "status": r["status"], "originals_preserved": r["originals_preserved"]} for r in source_runs],
              "OCA_support_counts": {"confluence": reconciliation["OCA_Plus_Integration_5"]["confluence_supporting_count"], "jira_unique": reconciliation["OCA_Plus_Integration_5"]["jira_description_unique_count"]}}
    write_json(root / "runs/audit/summary.json", result)
    return result
