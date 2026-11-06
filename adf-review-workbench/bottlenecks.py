"""Read-only workload evidence and matched human-time observations.

No evidence in the frozen campaign is changed. Counts are weak-label counts,
not a measure of labor, a corrected label set, or an automation eligibility rate.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from evidence_packets import safe_url as _safe_url, sanitize_text as _safe_text


ACTIVE_PHASES = (
    "search", "clarification", "investigation", "edit", "review",
    "supervision", "rework", "intake",
)
MINUTE_FIELDS = tuple(f"{phase}_minutes" for phase in ACTIVE_PHASES) + (
    "wait_minutes", "setup_minutes",
)
CSV_FIELDS = (
    "pair_id", "action_id", "mode", "scope", "milestone", "observer",
    "observed_at", "completion_state",
) + MINUTE_FIELDS
CATEGORIES = {
    "investigation_code": "Investigation / code",
    "verification_only": "Verification",
    "parameter_metadata": "Parameter / metadata",
    "approved_file": "Add / replace file",
    "defer_inherit_block": "Defer / retain / block",
    "dependency_pin": "Dependency version",
    "shared_sync": "Shared variant change",
}
GENERIC_PHRASES = {
    "do you want to add anything else?",
    "please clarify if the below is correct, or if changes are needed.",
}


def _read_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _number(raw: str | None) -> float:
    if raw is None or not raw.strip():
        raise ValueError("missing duration; unknown must not be recorded as zero")
    try:
        value = float(raw)
    except (TypeError, ValueError) as error:
        raise ValueError("duration must be numeric") from error
    if not math.isfinite(value) or value < 0:
        raise ValueError("duration must be finite and nonnegative")
    return value


def summarize_observations(path: Path) -> dict:
    """Compare only complete, uniquely matched manual/assisted observations.

    All durations are minutes. A zero is an observed zero; an empty cell is
    unknown. Waiting and one-time setup are reported separately from active
    labor. The caller must define equivalent completion milestones in advance.
    Invalid/incomplete/incomparable pairs are excluded, with visible reasons.
    """
    path = Path(path)
    result = {
        "status": "unknown_no_observations", "observed_rows": 0,
        "matched_pairs": 0, "net_active_minutes_saved": None,
        "manual_active_minutes": None, "assisted_active_minutes": None,
        "manual_wait_minutes": None, "assisted_wait_minutes": None,
        "recorded_setup_minutes": None, "pairs": [], "rejected_pairs": [],
        "invalid_rows": [], "active_phases": list(ACTIVE_PHASES),
        "waiting_is_labor": False, "setup_included_in_savings": False,
        "scope_note": "Observed matched tasks only; not a forecast or causal effect estimate.",
    }
    if not path.exists():
        result["missing_file"] = str(path)
        return result
    grouped = defaultdict(list)
    invalid_pair_ids = set()
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            result["status"] = "invalid_header"
            result["invalid_rows"].append({"row": 1, "errors": ["CSV header missing"]})
            return result
        missing_headers = [name for name in CSV_FIELDS if name not in reader.fieldnames]
        if missing_headers:
            result["status"] = "invalid_header"
            result["invalid_rows"].append({"row": 1, "errors": [f"Missing columns: {', '.join(missing_headers)}"]})
            return result
        for row_number, raw in enumerate(reader, start=2):
            if not any((value or "").strip() for key, value in raw.items() if key):
                continue
            result["observed_rows"] += 1
            errors = []
            if None in raw:
                errors.append("Extra CSV cells")
            row = {key: (raw.get(key) or "").strip() for key in CSV_FIELDS}
            for field in CSV_FIELDS[:8]:
                if not row[field]:
                    errors.append(f"{field}: required")
            if row["mode"] not in {"manual", "assisted"}:
                errors.append("mode: must be manual or assisted")
            if row["completion_state"] != "completed":
                errors.append("completion_state: only completed observations are comparable")
            try:
                timestamp = datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    errors.append("observed_at: timezone is required")
            except ValueError:
                errors.append("observed_at: valid ISO timestamp is required")
            for field in MINUTE_FIELDS:
                try:
                    row[field] = _number(row[field])
                except ValueError as error:
                    errors.append(f"{field}: {error}")
            if errors:
                result["invalid_rows"].append({"row": row_number, "pair_id": row["pair_id"], "errors": errors})
                if row["pair_id"]:
                    invalid_pair_ids.add(row["pair_id"])
                continue
            row["row"] = row_number
            grouped[row["pair_id"]].append(row)
    for pair_id in sorted(set(grouped) | invalid_pair_ids):
        rows = grouped[pair_id]
        reasons = []
        modes = Counter(row["mode"] for row in rows)
        if pair_id in invalid_pair_ids:
            reasons.append("Pair includes an invalid or incomplete row")
        if modes != {"manual": 1, "assisted": 1}:
            reasons.append("Pair requires exactly one manual and one assisted observation")
        if len(rows) == 2:
            for field in ("action_id", "scope", "milestone"):
                if len({row[field] for row in rows}) != 1:
                    reasons.append(f"Incomparable {field}")
        if reasons:
            result["rejected_pairs"].append({"pair_id": pair_id, "reasons": reasons})
            continue
        manual = next(row for row in rows if row["mode"] == "manual")
        assisted = next(row for row in rows if row["mode"] == "assisted")
        manual_active = sum(manual[f"{phase}_minutes"] for phase in ACTIVE_PHASES)
        assisted_active = sum(assisted[f"{phase}_minutes"] for phase in ACTIVE_PHASES)
        result["pairs"].append({
            "pair_id": pair_id, "action_id": manual["action_id"],
            "scope": manual["scope"], "milestone": manual["milestone"],
            "manual_active_minutes": manual_active,
            "assisted_active_minutes": assisted_active,
            "net_active_minutes_saved": manual_active - assisted_active,
            "manual_wait_minutes": manual["wait_minutes"],
            "assisted_wait_minutes": assisted["wait_minutes"],
            "recorded_setup_minutes": manual["setup_minutes"] + assisted["setup_minutes"],
            "manual_phase_minutes": {phase: manual[f"{phase}_minutes"] for phase in ACTIVE_PHASES},
            "assisted_phase_minutes": {phase: assisted[f"{phase}_minutes"] for phase in ACTIVE_PHASES},
            "source_rows": [manual["row"], assisted["row"]],
        })
    if result["pairs"]:
        result["matched_pairs"] = len(result["pairs"])
        for field in (
            "net_active_minutes_saved", "manual_active_minutes", "assisted_active_minutes",
            "manual_wait_minutes", "assisted_wait_minutes", "recorded_setup_minutes",
        ):
            result[field] = sum(pair[field] for pair in result["pairs"])
        result["status"] = "partially_measured" if result["invalid_rows"] or result["rejected_pairs"] else "measured_matched_observations"
    elif result["observed_rows"]:
        result["status"] = "unknown_no_comparable_pairs"
    return result


def _review_reasons(action: dict) -> list[str]:
    category, text = action.get("category"), action.get("text", "")
    reasons = []
    if (category == "defer_inherit_block" and re.search("threshold", text, re.I)
            and not re.search(r"\b(hold|defer|retain|block|inherit|postpone|delay)\b", text, re.I)):
        reasons.append("threshold_without_explicit_hold_word")
    if category == "dependency_pin" and re.search(r"fix[ -]?version", text, re.I):
        reasons.append("jira_fix_version_may_be_administrative")
    if category == "investigation_code" and text.strip().lower() in GENERIC_PHRASES:
        reasons.append("generic_clarification_may_not_be_implementation_action")
    return reasons


def build_report(source_root: Path, output_root: Path) -> dict:
    source_root, output_root = Path(source_root).resolve(), Path(output_root).resolve()
    if output_root == source_root or source_root in output_root.parents:
        raise ValueError("Report output must be outside the preserved source directory")
    for name in ("bottlenecks.json", "bottlenecks.md"):
        if (output_root / name).is_symlink():
            raise ValueError("Report output files must not be symbolic links")
    actions_path = source_root / "data/labels/weak_actions.jsonl"
    effort_path = source_root / "runs/effort/report.json"
    counts = Counter()
    reviewed = 0
    flag_counts = Counter()
    examples = defaultdict(list)
    flagged_ids = set()
    for action in _read_jsonl(actions_path):
        counts[action.get("category", "unknown")] += 1
        if action.get("reviewer_state") == "reviewed":
            reviewed += 1
        for reason in _review_reasons(action):
            flag_counts[reason] += 1
            flagged_ids.add(action.get("id"))
            if len(examples[reason]) < 4:
                evidence = action.get("evidence") or []
                example = {
                    "reason": reason, "action_id": action.get("id"),
                    "issue_key": action.get("issue_key"),
                    "proposed_category": action.get("category"),
                    "text": _safe_text(action.get("text", ""))[:600],
                    "text_truncated": len(action.get("text", "")) > 600,
                    "url": _safe_url(evidence[0].get("url", "")) if evidence else "",
                    "source_locator": _safe_text(str(evidence[0].get("locator") or "")) if evidence else None,
                    "state": "candidate_for_human_review_not_corrected_truth",
                }
                examples[reason].append(example)
    effort = json.loads(effort_path.read_text(encoding="utf-8"))
    total = sum(counts.values())
    observation_path = output_root.parent / "templates/time_observations.csv"
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "proposal_count": total, "reviewed_labels": reviewed,
        "category_counts": [
            {"key": key, "name": CATEGORIES.get(key, key), "count": count,
             "percent": 100 * count / total if total else None}
            for key, count in counts.most_common()
        ],
        "bottleneck_hypothesis": {
            "area": "Investigation and clarifying the exact release-specific change",
            "reason": "Largest weak-label category; source reconstruction, unresolved targets and values, and variant applicability require review.",
            "confidence": "hypothesis_not_timed",
            "calendar_delay": "Dependency, approval, resource or scientific-test waits may dominate calendar time; no observations rank these.",
        },
        "quality_review_flags": {
            "flag_count": len(flagged_ids), "counts_by_reason": dict(flag_counts),
            "examples": [example for group in examples.values() for example in group],
            "interpretation": "Narrow text-pattern review candidates, not confirmed errors or a corrected label set. Counts can overlap. Frozen labels unchanged.",
        },
        "interventions": [
            {"priority": 1, "title": "Prepare one evidence packet per change",
             "reduction": "Reduce repeated searching with dated source excerpts, prior implementation links, release associations and explicit unanswered questions.",
             "engineer_decision": "Confirm release applicability and resolve changing or conflicting instructions."},
            {"priority": 2, "title": "Require a complete change record",
             "reduction": "Capture exact target, approved old/new value or pinned artifact, affected variants and acceptance checks before handoff.",
             "engineer_decision": "Approve intended values, scope and acceptance criteria; historical status does not approve a new execution."},
            {"priority": 3, "title": "Run routine checks immediately",
             "reduction": "After approval, use registered operations and check expected values, hashes, paths and affected variants; expose a reviewable diff.",
             "engineer_decision": "Review changes and separate structural checks from scientific/physical validation. Current real executor coverage is narrow."},
            {"priority": 4, "title": "Prepare reproducible debugging evidence",
             "reduction": "Collect last-known-working versus candidate differences and approved regression results so investigation begins with a reproducible case.",
             "engineer_decision": "Determine and validate the fix; source collection alone cannot establish root cause."},
        ],
        "timing": summarize_observations(observation_path),
        "existing_timing_evidence": {
            "status": effort.get("status"), "measured_actions": effort.get("measured_actions"),
            "measured_net_minutes": effort.get("measured_net_minutes"),
        },
        "caveats": [
            "Categories are unreviewed action excerpts, not unique completed engineering tasks.",
            "Category shares are not effort shares, validated automation eligibility or time savings.",
            "Flagged labels require human review; original labels, models and frozen campaign remain unchanged.",
            "No observed human timing means savings are unknown, not zero.",
            "Matched timing is descriptive; order, learning and task selection can bias comparisons.",
        ],
        "sources": [
            {"path": str(path.resolve()), "sha256": _hash(path)}
            for path in (actions_path, effort_path)
        ],
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "bottlenecks.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Bottlenecks and time-reduction pilot", "",
        "**Hypothesis:** investigation and clarifying exact release-specific changes consume the most engineer time. No human-time observations establish this ranking yet.", "",
        f"The source contains **{total:,} unreviewed proposed excerpts** and **{reviewed} reviewed labels**. Counts are not hours or independent completed tasks.", "",
        "| Proposed category | Excerpts | Share of excerpts |", "|---|---:|---:|",
    ]
    for category in report["category_counts"]:
        lines.append(f"| {category['name']} | {category['count']:,} | {category['percent']:.1f}% |")
    lines += ["", "## Recommended work", ""]
    for item in report["interventions"]:
        lines += [f"{item['priority']}. **{item['title']}.** {item['reduction']} Engineer: {item['engineer_decision']}", ""]
    lines += [
        "## Label quality review", "",
        f"**{len(flagged_ids)} excerpts** match narrow patterns worth review. These are candidates, not confirmed errors, relabeled examples, or proof that all remaining labels are correct.", "",
    ]
    for reason, count in flag_counts.items():
        lines += [f"- `{reason}`: {count} candidate excerpts."]
    lines += ["", "Examples (source statements remain historical):", ""]
    for example in report["quality_review_flags"]["examples"]:
        text = example["text"].replace("\n", " ").replace("|", "\\|")
        lines.append(f"- `{example['action_id']}` / [{example['issue_key']}]({example['url']}): {text} — `{example['reason']}`.")
    lines += [
        "", "## Timing result", "",
        f"Status: `{report['timing']['status']}`. Matched pairs: {report['timing']['matched_pairs']}. **Hours saved remain unknown** until complete comparable observations are recorded.", "",
        "Record active effort by phase, waiting separately, and setup separately. Compare the same action, scope and predeclared completion milestone. Missing duration fields remain unknown and invalidate that pair. See `PILOT.md`.", "",
        "## Source integrity", "",
    ]
    for source in report["sources"]:
        lines.append(f"- `{source['path']}` — SHA-256 `{source['sha256']}`.")
    (output_root / "bottlenecks.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parent.parent / "adf-sentinel")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "results")
    args = parser.parse_args()
    report = build_report(args.source, args.output)
    print(json.dumps({"proposal_count": report["proposal_count"], "review_flags": report["quality_review_flags"]["flag_count"], "timing_status": report["timing"]["status"]}))


if __name__ == "__main__":
    main()
