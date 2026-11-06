"""Prepare explicit review records. This module has no execution capability.

Run from /rhome/yanzhu/ML_ADF:
    python adf-review-workbench/intake.py --record path/to/record.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import PurePosixPath
from urllib.parse import parse_qsl, urlsplit


OPERATIONS = {
    "file_replacement", "parameter_metadata", "dependency_pin",
    "shared_variant_change", "investigation", "verification",
    "retain_defer_block",
}
TOP_FIELDS = {
    "schema_version", "id", "issue_key", "source_links", "evidence", "release",
    "variants", "operation", "target_path", "field", "expected_old_value",
    "new_value", "baseline_sha256", "artifact", "dependency", "variant_targets",
    "question", "decision", "acceptance_checks", "reviewer_decision",
}
CAPABILITY_KEYS = {
    "token", "access_token", "id_token", "jwt", "signature", "sig",
    "authorization", "api_key", "apikey", "x-amz-signature", "x-amz-credential",
    "x-amz-security-token", "x-goog-signature", "x-goog-credential",
}
SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _safe_path(value):
    if not _text(value) or "\\" in value or any(ord(char) < 32 for char in value):
        return False
    parts = value.split("/")
    return not PurePosixPath(value).is_absolute() and all(
        part not in {"", ".", ".."} for part in parts
    ) and not re.match(r"^[A-Za-z]:", value)


def _source_url(value):
    if not _text(value):
        return False
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and not any(char.isspace() or ord(char) < 32 for char in value)
            and parsed.username is None
            and parsed.password is None
            and not any(key.lower() in CAPABILITY_KEYS for key, _ in parse_qsl(parsed.query))
        )
    except ValueError:
        return False


def _finite_json(value):
    if isinstance(value, float):
        return math.isfinite(value)
    if value is None or isinstance(value, (str, int, bool)):
        return True
    if isinstance(value, list):
        return all(_finite_json(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _finite_json(item) for key, item in value.items())
    return False


def validate_record(record: dict) -> dict:
    """Return completeness and recorded decision status, never permission to execute.

    Approval metadata is user-supplied evidence, not an authenticated signature.
    A complete record can be ready for human review while approval remains pending.
    """
    missing = []
    invalid = []

    def bad(field, reason):
        invalid.append({"field": field, "reason": reason})

    def need_text(obj, field, prefix=""):
        value = obj.get(field)
        name = prefix + field
        if value is None or value == "":
            missing.append(name)
        elif not _text(value):
            bad(name, "must be a non-empty string")

    def unknown(obj, allowed, prefix=""):
        for field in sorted(set(obj) - allowed):
            bad(prefix + field, "unknown field; command or execution fields are unsupported")

    def target(obj, field, prefix=""):
        value = obj.get(field)
        if value is None or value == "":
            missing.append(prefix + field)
        elif not _safe_path(value):
            bad(prefix + field, "must be a relative path without traversal, empty segments, or backslashes")

    def value_required(obj, field, prefix=""):
        if field not in obj or obj[field] is None:
            missing.append(prefix + field)
        elif not _finite_json(obj[field]):
            bad(prefix + field, "must contain finite JSON values")

    if not isinstance(record, dict):
        return {
            "record_id": None, "operation": None, "missing_fields": [],
            "invalid_fields": [{"field": "$", "reason": "record must be an object"}],
            "review_ready": False, "approval_status": "invalid",
            "human_approval_present": False, "execution_enabled": False,
            "next_step": "Correct the record format before review.",
        }

    unknown(record, TOP_FIELDS)
    if record.get("schema_version") != 1 or isinstance(record.get("schema_version"), bool):
        bad("schema_version", "must be 1")
    for field in ("id", "issue_key", "release"):
        need_text(record, field)
    if _text(record.get("issue_key")) and not re.fullmatch(r"[A-Z][A-Z0-9_]*-\d+", record["issue_key"]):
        bad("issue_key", "must be a Jira-style issue key")

    links = record.get("source_links")
    if not links:
        missing.append("source_links")
    elif not isinstance(links, list) or any(not _source_url(link) for link in links):
        bad("source_links", "must be a list of HTTP(S) source links without embedded credentials or capability tokens")

    evidence = record.get("evidence")
    if not evidence:
        missing.append("evidence")
    elif not isinstance(evidence, list):
        bad("evidence", "must be a list")
    else:
        for index, item in enumerate(evidence):
            prefix = f"evidence[{index}]."
            if not isinstance(item, dict):
                bad(prefix[:-1], "must be an object")
                continue
            unknown(item, {"kind", "url", "note", "source_sha256"}, prefix)
            if not isinstance(item.get("kind"), str) or item["kind"] not in {"source_requirement", "historical_implementation", "historical_decision", "test_result", "current_decision"}:
                bad(prefix + "kind", "must identify evidence kind; historical evidence is not current approval")
            if not _source_url(item.get("url")):
                bad(prefix + "url", "must be a source link without credentials or capability tokens")
            need_text(item, "note", prefix)
            if item.get("source_sha256") is not None and not SHA256.fullmatch(str(item["source_sha256"])):
                bad(prefix + "source_sha256", "must be a 64-digit SHA-256")

    variants = record.get("variants")
    if not variants:
        missing.append("variants")
    elif not isinstance(variants, list) or any(not _text(v) for v in variants):
        bad("variants", "must be a non-empty list of explicit variant names or an explicit not-applicable scope")
    elif len(set(variants)) != len(variants):
        bad("variants", "variant names must be unique")

    operation = record.get("operation")
    if not isinstance(operation, str) or operation not in OPERATIONS:
        bad("operation", "must be a supported review operation")
        operation = None

    checks = record.get("acceptance_checks")
    if not checks:
        missing.append("acceptance_checks")
    elif not isinstance(checks, list) or any(not _text(check) for check in checks):
        bad("acceptance_checks", "must list non-empty acceptance criteria; these are not executed")

    if operation in {"file_replacement", "parameter_metadata", "dependency_pin", "verification"}:
        target(record, "target_path")
    elif record.get("target_path") is not None and not _safe_path(record["target_path"]):
        bad("target_path", "must be a safe relative path when supplied")

    if operation == "file_replacement":
        baseline = record.get("baseline_sha256")
        if baseline is None:
            missing.append("baseline_sha256")
        elif not isinstance(baseline, str) or not SHA256.fullmatch(baseline):
            bad("baseline_sha256", "must be the expected destination SHA-256 before replacement")
        artifact = record.get("artifact")
        if artifact is None:
            missing.append("artifact")
        elif not isinstance(artifact, dict):
            bad("artifact", "must be an object")
        else:
            unknown(artifact, {"source_url", "revision", "sha256"}, "artifact.")
            if artifact.get("source_url") is None:
                missing.append("artifact.source_url")
            elif not _source_url(artifact["source_url"]):
                bad("artifact.source_url", "must be a source link without credentials or capability tokens")
            need_text(artifact, "revision", "artifact.")
            if _text(artifact.get("revision")) and artifact["revision"].lower() in {"main", "master", "head", "latest"}:
                bad("artifact.revision", "a floating branch or latest alias is not a pinned revision")
            if artifact.get("sha256") is None:
                missing.append("artifact.sha256")
            elif not isinstance(artifact["sha256"], str) or not SHA256.fullmatch(artifact["sha256"]):
                bad("artifact.sha256", "must be a 64-digit SHA-256")

    if operation == "parameter_metadata":
        need_text(record, "field")
        value_required(record, "expected_old_value")
        value_required(record, "new_value")

    if operation == "dependency_pin":
        dependency = record.get("dependency")
        if dependency is None:
            missing.append("dependency")
        elif not isinstance(dependency, dict):
            bad("dependency", "must be an object")
        else:
            unknown(dependency, {"package", "expected_version", "new_version"}, "dependency.")
            for field in ("package", "expected_version", "new_version"):
                need_text(dependency, field, "dependency.")
            if _text(dependency.get("new_version")) and dependency["new_version"].lower() in {"main", "master", "head", "latest", "*"}:
                bad("dependency.new_version", "must be an explicit version rather than a floating alias")

    if operation == "shared_variant_change":
        targets = record.get("variant_targets")
        if not targets:
            missing.append("variant_targets")
        elif not isinstance(targets, list):
            bad("variant_targets", "must be a list of explicit per-variant targets and values")
        else:
            named_variants = []
            for index, item in enumerate(targets):
                prefix = f"variant_targets[{index}]."
                if not isinstance(item, dict):
                    bad(prefix[:-1], "must be an object")
                    continue
                unknown(item, {"variant", "target_path", "field", "expected_old_value", "new_value"}, prefix)
                need_text(item, "variant", prefix)
                target(item, "target_path", prefix)
                need_text(item, "field", prefix)
                value_required(item, "expected_old_value", prefix)
                value_required(item, "new_value", prefix)
                if _text(item.get("variant")):
                    named_variants.append(item["variant"])
            if isinstance(variants, list) and all(_text(v) for v in variants):
                if set(named_variants) != set(variants):
                    bad("variant_targets", "must cover exactly the named variants")
                if len(named_variants) != len(set(named_variants)):
                    bad("variant_targets", "must contain one target record per named variant")

    if operation in {"investigation", "verification"}:
        need_text(record, "question")
    if operation == "retain_defer_block":
        need_text(record, "question")
        if not isinstance(record.get("decision"), str) or record["decision"] not in {"retain", "defer", "block"}:
            bad("decision", "must explicitly identify retain, defer, or block")
        if record.get("decision") == "retain":
            target(record, "target_path")
            need_text(record, "field")
            value_required(record, "expected_old_value")

    # Validate optional operation objects even when they are inapplicable, so a
    # supposedly harmless record cannot carry ignored command payloads.
    applicable = {
        "artifact": operation == "file_replacement",
        "dependency": operation == "dependency_pin",
        "variant_targets": operation == "shared_variant_change",
    }
    for field, applies in applicable.items():
        if record.get(field) is not None and not applies:
            bad(field, "not applicable to this operation; remove unused payloads")

    decision = record.get("reviewer_decision")
    approval_status = "pending"
    decision_valid = True
    if decision is None:
        missing.append("reviewer_decision")
    elif not isinstance(decision, dict):
        bad("reviewer_decision", "must be an object")
        approval_status = "invalid"
        decision_valid = False
    else:
        before = len(invalid)
        unknown(decision, {"status", "reviewer", "decided_at", "evidence_url", "note", "scope"}, "reviewer_decision.")
        status = decision.get("status")
        if not isinstance(status, str) or status not in {"pending", "approved", "rejected", "deferred"}:
            bad("reviewer_decision.status", "must be pending, approved, rejected, or deferred")
            approval_status = "invalid"
            status = None
        else:
            approval_status = status
        if status in {"approved", "rejected", "deferred"}:
            for field in ("reviewer", "decided_at", "evidence_url", "note", "scope"):
                need_text(decision, field, "reviewer_decision.")
            if decision.get("scope") != "current_record":
                bad("reviewer_decision.scope", "a current-record decision is required; historical implementation is not current approval")
            if decision.get("evidence_url") is not None and not _source_url(decision["evidence_url"]):
                bad("reviewer_decision.evidence_url", "must be a source link without credentials or capability tokens")
            if _text(decision.get("decided_at")):
                try:
                    from datetime import datetime
                    parsed = datetime.fromisoformat(decision["decided_at"].replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        raise ValueError("timezone required")
                except ValueError:
                    bad("reviewer_decision.decided_at", "must be an ISO date-time with a timezone")
        elif status == "pending":
            # A source requirement may list an author, but it is not a decision.
            if any(decision.get(field) is not None for field in ("reviewer", "decided_at", "evidence_url")):
                bad("reviewer_decision", "pending decisions must not contain reviewer, decided_at, or decision evidence")
        decision_valid = (
            len(invalid) == before
            and not any(field.startswith("reviewer_decision.") for field in missing)
        )
        if not decision_valid:
            approval_status = "invalid"

    missing = list(dict.fromkeys(missing))
    ready = not missing and not invalid
    approval_present = approval_status == "approved" and decision_valid
    if not ready:
        next_step = "Resolve the listed missing or invalid information before review."
    elif approval_status == "pending":
        next_step = "Review the evidence and record the responsible engineer's decision."
    elif approval_status == "approved":
        next_step = "Recorded approval metadata is complete; an independent executor and scope check are still required."
    elif approval_status == "rejected":
        next_step = "Preserve the rejection and resolve its reasons before proposing a new record."
    else:
        next_step = "Preserve the deferral and revisit when the recorded prerequisite is resolved."
    return {
        "record_id": record.get("id"), "operation": operation,
        "missing_fields": missing, "invalid_fields": invalid,
        "review_ready": ready, "approval_status": approval_status,
        "human_approval_present": approval_present,
        "approval_is_authenticated": False,
        "execution_enabled": False, "next_step": next_step,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", required=True, help="JSON review record; no changes are executed")
    args = parser.parse_args()
    with open(args.record, encoding="utf-8") as handle:
        record = json.load(handle)
    print(json.dumps(validate_record(record), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
