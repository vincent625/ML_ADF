"""Small executor registry. No model-generated commands, builds, SQL, or installation."""
from __future__ import annotations

import dataclasses
import difflib
import json
import re
import shutil
import time
from pathlib import Path, PurePosixPath

from .common import ROOT, digest, file_hash, now, read_json, write_json

EXECUTORS = {"copy_pinned_file", "json_parameter", "dependency_pin", "actor_parameter", "verify_hash"}
ACTION_KEYS = {"id", "type", "target", "variant", "source", "source_sha256", "source_revision",
               "before_sha256", "pointer", "old_value", "value", "key", "checks"}
PLAN_KEYS = {"schema_version", "id", "scope", "release_id", "authority", "prerequisites", "actions", "synthetic"}
JSON_FIELDS = {"/parameters/threshold": "number", "/dependencies/report": "string"}
REAL_TARGET = "SeedData/AssayDev/assay/dna/parameters/TmapExecutionActor.ini"
REAL_COMMIT = "6ada6a4bd50d1acec148596059e6142a7748fc01"
REAL_BLOB = "b77957e398510d07ed6783cd1f1ef7eefff3462d"


@dataclasses.dataclass(frozen=True)
class Action:
    id: str
    type: str
    target: str
    variant: str
    specification: dict


@dataclasses.dataclass(frozen=True)
class Plan:
    id: str
    scope: str
    synthetic: bool
    authority: dict
    prerequisites: tuple
    actions: tuple[Action, ...]


def relative_path(value):
    if not isinstance(value, str) or "\\" in value:
        raise ValueError("Target must be a literal relative POSIX path")
    p = PurePosixPath(value)
    if not value or p.is_absolute() or ".." in p.parts or ":" in value or str(p) != value or value == ".":
        raise ValueError("Unsafe or noncanonical path")
    return p


def contained(root, value):
    p = relative_path(value)
    root = Path(root).resolve()
    target = root.joinpath(*p.parts)
    cursor = root
    for part in p.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("Symbolic links are not accepted as executor inputs or targets")
    if not target.resolve().is_relative_to(root):
        raise ValueError("Path escapes sandbox")
    return target


def validate_plan(raw):
    required = {"schema_version", "id", "scope", "synthetic", "authority", "prerequisites", "actions"}
    if not isinstance(raw, dict) or set(raw) - PLAN_KEYS or required - set(raw) or raw.get("schema_version") != 1:
        raise ValueError("Unknown plan fields or schema version")
    if not isinstance(raw["id"], str) or not raw["id"]:
        raise ValueError("Plan ID is required")
    if type(raw.get("synthetic")) is not bool or raw.get("scope") not in {"synthetic_fixture", "pinned_source_fragment_replay"}:
        raise ValueError("Only explicit synthetic fixtures and pinned source-fragment replays are registered")
    if raw["synthetic"] != (raw["scope"] == "synthetic_fixture"):
        raise ValueError("Synthetic status and scope disagree")
    authority = raw.get("authority", {})
    if not isinstance(authority, dict) or authority.get("kind") != ("synthetic_fixture" if raw["synthetic"] else "historical_implementation") or not isinstance(authority.get("evidence"), list) or not authority["evidence"]:
        raise ValueError("Missing explicit input authority/evidence")
    if not isinstance(raw.get("prerequisites"), list) or any(not isinstance(p, dict) or p.get("satisfied") is not True for p in raw["prerequisites"]):
        raise ValueError("Unsatisfied or missing prerequisites")
    if not isinstance(raw.get("actions"), list) or not raw["actions"]:
        raise ValueError("Plan has no actions")
    actions, targets, ids = [], set(), set()
    for item in raw["actions"]:
        if not isinstance(item, dict) or set(item) - ACTION_KEYS:
            raise ValueError("Unknown action fields; commands are not accepted")
        for field in ["id", "type", "target", "variant", "before_sha256", "checks"]:
            if not item.get(field):
                raise ValueError("Missing required action field: " + field)
        if any(not isinstance(item[field], str) for field in ["id", "type", "target", "variant", "before_sha256"]):
            raise ValueError("Action identity, type, path, variant and hash must be strings")
        if item["id"] in ids:
            raise ValueError("Repeated action ID")
        ids.add(item["id"])
        relative_path(item["target"])
        if item["variant"] not in {"DNA", "DNA+Fusion", "synthetic-DNA", "synthetic-DNA+Fusion"}:
            raise ValueError("Unknown variant")
        prefix = {"DNA": "SeedData/AssayDev/assay/dna/", "DNA+Fusion": "SeedData/AssayDev/assay/dna_fusion/",
                  "synthetic-DNA": "DNA/", "synthetic-DNA+Fusion": "DNA_Fusion/"}[item["variant"]]
        if not item["target"].startswith(prefix) or raw["synthetic"] != item["variant"].startswith("synthetic-"):
            raise ValueError("Target path and declared variant/scope disagree")
        if not re.fullmatch(r"[0-9a-f]{64}", item["before_sha256"]):
            raise ValueError("Missing exact precondition hash")
        if item["type"] not in EXECUTORS:
            raise ValueError("Executor is not registered")
        base_fields = {"id", "type", "target", "variant", "before_sha256", "checks"}
        specific = {"copy_pinned_file": {"source", "source_sha256", "source_revision"},
                    "json_parameter": {"pointer", "old_value", "value"}, "dependency_pin": {"pointer", "old_value", "value"},
                    "actor_parameter": {"key", "old_value", "value"}, "verify_hash": set()}[item["type"]]
        if set(item) - base_fields - specific:
            raise ValueError("Fields are incompatible with this executor")
        if item["target"] in targets and item["type"] != "verify_hash":
            raise ValueError("Multiple mutations of one target must be consolidated into one reviewed operation")
        targets.add(item["target"])
        if item["type"] == "copy_pinned_file":
            relative_path(item.get("source"))
            if not re.fullmatch(r"[0-9a-f]{64}", item.get("source_sha256", "")):
                raise ValueError("Pinned source hash is missing")
            if not raw["synthetic"] and not re.fullmatch(r"[0-9a-f]{40}", item.get("source_revision", "")):
                raise ValueError("Historical source replay requires a pinned commit")
            if not raw["synthetic"] and (item["target"] != REAL_TARGET or item.get("source_revision") != REAL_COMMIT or item["source"] != "data/source_replay/approved/" + REAL_TARGET):
                raise ValueError("Approved source/commit/target tuple is not registered")
        elif item["type"] in {"json_parameter", "dependency_pin"}:
            if not raw["synthetic"] or not item["target"].endswith("/config.json"):
                raise ValueError("No real ADF JSON schema has been registered for this target")
            expected_type = JSON_FIELDS.get(item.get("pointer"))
            if item["type"] == "dependency_pin" and item.get("pointer") != "/dependencies/report":
                raise ValueError("Dependency executor requires the declared dependency field")
            if expected_type is None:
                raise ValueError("JSON field is not registered")
            if expected_type == "number" and (type(item.get("value")) not in {int, float} or not 0 <= item["value"] <= 1):
                raise ValueError("Synthetic threshold schema requires a number in [0,1]")
            if expected_type == "string" and not isinstance(item.get("value"), str):
                raise ValueError("Declared dependency must be a string")
            if "old_value" not in item:
                raise ValueError("Existing JSON value is required")
        elif item["type"] == "actor_parameter":
            if item.get("key") != "tmap.custom.tmap.args" or not item["target"].endswith("/parameters/TmapExecutionActor.ini"):
                raise ValueError("Actor key/target not registered")
            if not isinstance(item.get("value"), str) or not isinstance(item.get("old_value"), str):
                raise ValueError("Actor values must be exact strings")
        if not isinstance(item["checks"], list):
            raise ValueError("Checks must be a list")
        for check in item["checks"]:
            if not isinstance(check, dict) or set(check) - {"kind", "value", "pointer", "key", "target"} or check.get("kind") not in {"sha256", "json_value", "actor_value", "text_absent", "same_as"}:
                raise ValueError("Verification check is not registered")
            needed = {"sha256": {"value"}, "json_value": {"pointer", "value"}, "actor_value": {"key", "value"}, "text_absent": {"value"}, "same_as": {"target"}}[check["kind"]]
            if needed - set(check):
                raise ValueError("Verification check is missing required values")
            if check["kind"] == "json_value" and (not raw["synthetic"] or check["pointer"] not in JSON_FIELDS or not item["target"].endswith("/config.json")):
                raise ValueError("JSON verification target/schema is not registered")
            if check["kind"] == "sha256" and not re.fullmatch(r"[0-9a-f]{64}", check.get("value", "")):
                raise ValueError("Verification requires an exact SHA-256")
            if check["kind"] == "same_as":
                relative_path(check.get("target"))
        actions.append(Action(item["id"], item["type"], item["target"], item["variant"], item))
    return Plan(str(raw.get("id", "")), raw["scope"], raw["synthetic"], authority,
                tuple(raw["prerequisites"]), tuple(actions))


def json_parent(data, pointer):
    parts = [p.replace("~1", "/").replace("~0", "~") for p in pointer.split("/")[1:]]
    for part in parts[:-1]:
        data = data[part]
    return data, parts[-1]


def actor_value(path, key):
    matches = [line.split("=", 1)[1].rstrip("\r\n") for line in Path(path).read_text().splitlines(keepends=True) if line.startswith(key + "=")]
    if len(matches) != 1:
        raise ValueError("Actor key must occur exactly once")
    return matches[0]


def baseline_manifest(directory):
    directory = Path(directory)
    records = {}
    for p in directory.rglob("*"):
        if p.is_symlink():
            raise ValueError("Baseline contains symbolic links")
        if p.is_file():
            records[str(p.relative_to(directory))] = file_hash(p)
    return records


def check_file(candidate, target, check):
    path = contained(candidate, target)
    kind = check["kind"]
    if kind == "sha256":
        observed, expected = file_hash(path), check.get("value")
    elif kind == "json_value":
        parent, key = json_parent(read_json(path), check["pointer"])
        observed, expected = parent[key], check.get("value")
    elif kind == "actor_value":
        observed, expected = actor_value(path, check["key"]), check.get("value")
    elif kind == "text_absent":
        observed, expected = check["value"] not in path.read_text(), True
    else:
        observed, expected = file_hash(path), file_hash(contained(candidate, check["target"]))
    return {"kind": kind, "target": target, "observed": observed, "expected": expected, "passed": observed == expected,
            "scope": "source_or_fixture_content_check_not_scientific_validation"}


def execute(raw, baseline, root=ROOT):
    root, baseline = Path(root).resolve(), Path(baseline).resolve()
    plan = validate_plan(raw)
    if not baseline.is_relative_to(root / "data"):
        raise ValueError("Baseline must be a local data copy inside the project")
    before = baseline_manifest(baseline)
    # All prerequisites are checked before any candidate mutation.
    for action in plan.actions:
        spec = action.specification
        target = contained(baseline, action.target)
        if not target.is_file() or file_hash(target) != spec["before_sha256"]:
            raise ValueError("Existing file hash precondition failed: " + action.target)
        if action.type == "copy_pinned_file":
            source = contained(root, spec["source"])
            if not source.is_relative_to(root / "data") or not source.is_file() or file_hash(source) != spec["source_sha256"]:
                raise ValueError("Pinned approved input is missing or changed")
            if not plan.synthetic:
                import hashlib
                content = source.read_bytes()
                blob = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
                if blob != REAL_BLOB:
                    raise ValueError("Source bytes do not match the registered approved Git blob")
        elif action.type in {"json_parameter", "dependency_pin"}:
            parent, key = json_parent(read_json(target), spec["pointer"])
            if parent[key] != spec["old_value"]:
                raise ValueError("Existing JSON value precondition failed")
        elif action.type == "actor_parameter":
            if actor_value(target, spec["key"]) != spec["old_value"]:
                raise ValueError("Existing actor value precondition failed")
            approved = contained(root, "data/source_replay/approved/" + REAL_TARGET)
            if action.target != REAL_TARGET or not approved.exists() or actor_value(approved, spec["key"]) != spec["value"]:
                raise ValueError("Actor value has no registered approved source")
    run_id = digest({"plan": raw, "baseline": before})[:20]
    run_dir = root / "runs/sandbox" / run_id
    saved = read_json(run_dir / "manifest.json")
    if saved:
        candidate = run_dir / "candidate"
        if baseline_manifest(candidate) != saved["candidate_manifest"]:
            raise ValueError("Previous candidate changed; refusing to reuse stale result")
        return {**saved, "reused": True}
    if run_dir.exists():
        raise ValueError("An incomplete run already occupies this output ID; preserve it for inspection")
    start = time.perf_counter()
    candidate = run_dir / "candidate"
    candidate.parent.mkdir(parents=True, exist_ok=False)
    shutil.copytree(baseline, candidate)
    diff = []
    for action in plan.actions:
        spec = action.specification
        old, target = contained(baseline, action.target), contained(candidate, action.target)
        if action.type == "copy_pinned_file":
            shutil.copyfile(contained(root, spec["source"]), target)
        elif action.type in {"json_parameter", "dependency_pin"}:
            data = read_json(target)
            parent, key = json_parent(data, spec["pointer"])
            parent[key] = spec["value"]
            write_json(target, data)
        elif action.type == "actor_parameter":
            lines = target.read_text().splitlines(keepends=True)
            target.write_text("".join(spec["key"] + "=" + spec["value"] + "\n" if line.startswith(spec["key"] + "=") else line for line in lines))
        if action.type != "verify_hash":
            diff.extend(difflib.unified_diff(old.read_text(errors="replace").splitlines(keepends=True), target.read_text(errors="replace").splitlines(keepends=True), fromfile="baseline/" + action.target, tofile="candidate/" + action.target))
    checks = [check_file(candidate, a.target, c) for a in plan.actions for c in a.specification["checks"]]
    after = baseline_manifest(candidate)
    originals_preserved = baseline_manifest(baseline) == before
    result = {"run_id": run_id, "created_at": now(), "plan_id": plan.id, "plan_sha256": digest(raw),
              "scope": plan.scope, "synthetic": plan.synthetic, "installable_adf": False,
              "status": "passed" if originals_preserved and all(c["passed"] for c in checks) else "failed",
              "originals_preserved": originals_preserved, "baseline_manifest": before, "candidate_manifest": after,
              "changed_files": [p for p in after if before.get(p) != after[p]], "checks": checks,
              "actions_attempted": len(plan.actions), "runtime_seconds": time.perf_counter() - start,
              "candidate_path": str(candidate.relative_to(root)), "authority": plan.authority,
              "build": {"status": "blocked", "reason": "Complete pinned build checkout, documented approved build process, and full required assets are not available to this executor"},
              "scientific_validation": "not_run", "physical_runs": "not_run", "reused": False}
    (run_dir / "changes.diff").write_text("".join(diff))
    write_json(run_dir / "plan.json", raw)
    write_json(run_dir / "manifest.json", result)
    return result


def seed_fixtures(root=ROOT):
    root = Path(root)
    before, approved = root / "data/fixtures/baseline", root / "data/fixtures/approved"
    for variant in ["DNA", "DNA_Fusion"]:
        path = before / variant / "config.json"
        if not path.exists():
            write_json(path, {"SYNTHETIC_NON_INSTALLABLE": True, "parameters": {"threshold": .2}, "dependencies": {"report": "fixture-1"}})
        asset = before / variant / "shared.txt"
        asset.parent.mkdir(parents=True, exist_ok=True)
        if not asset.exists():
            asset.write_text("SYNTHETIC fixture asset version 1\n")
    approved.mkdir(parents=True, exist_ok=True)
    asset = approved / "shared.txt"
    if not asset.exists():
        asset.write_text("SYNTHETIC fixture asset version 2\n")
    actions = []
    for variant, label in [("DNA", "synthetic-DNA"), ("DNA_Fusion", "synthetic-DNA+Fusion")]:
        target = variant + "/config.json"
        actions.append({"id": variant + "-parameter", "type": "json_parameter", "target": target, "variant": label,
                        "before_sha256": file_hash(before / target), "pointer": "/parameters/threshold", "old_value": .2, "value": .4,
                        "checks": [{"kind": "json_value", "pointer": "/parameters/threshold", "value": .4}]})
        target = variant + "/shared.txt"
        actions.append({"id": variant + "-shared", "type": "copy_pinned_file", "target": target, "variant": label,
                        "before_sha256": file_hash(before / target), "source": str(asset.relative_to(root)), "source_sha256": file_hash(asset),
                        "source_revision": "synthetic-fixture-2", "checks": [{"kind": "sha256", "value": file_hash(asset)}, {"kind": "same_as", "target": "DNA/shared.txt"}]})
    plan = {"schema_version": 1, "id": "synthetic-safe-executor-demo", "scope": "synthetic_fixture", "synthetic": True,
            "authority": {"kind": "synthetic_fixture", "evidence": ["Locally authored fixture; no historical or scientific correctness claim"]},
            "prerequisites": [{"name": "Fixture inputs present", "satisfied": True}], "actions": actions}
    write_json(root / "data/plans/synthetic.json", plan)
    return plan


def source_replay_plan(root=ROOT):
    root = Path(root)
    target = "SeedData/AssayDev/assay/dna/parameters/TmapExecutionActor.ini"
    before, approved = root / "data/source_replay/before" / target, root / "data/source_replay/approved" / target
    if not before.exists() or not approved.exists():
        return {"status": "blocked", "reason": "Pinned source files have not been collected"}
    plan = {"schema_version": 1, "id": "IRS-65265-pinned-source-file-replay", "scope": "pinned_source_fragment_replay", "synthetic": False,
            "authority": {"kind": "historical_implementation", "evidence": [
                "https://github.com/thermofisher/csd-adf-gx-manticore-v2-dna-70/pull/3",
                "https://github.com/thermofisher/csd-adf-gx-manticore-v2-dna-70/blob/6ada6a4bd50d1acec148596059e6142a7748fc01/" + target],
                "note": "Replay of merged historical source, not a new human approval or a model-generated plan"},
            "prerequisites": [{"name": "Pinned before and historical implementation file bytes collected", "satisfied": True}],
            "actions": [{"id": "replace-tmap-actor-file", "type": "copy_pinned_file", "target": target, "variant": "DNA",
                         "source": str(approved.relative_to(root)), "source_sha256": file_hash(approved),
                         "source_revision": "6ada6a4bd50d1acec148596059e6142a7748fc01", "before_sha256": file_hash(before),
                         "checks": [{"kind": "sha256", "value": file_hash(approved)}, {"kind": "text_absent", "value": "--repair-min-freq"},
                                    {"kind": "actor_value", "key": "tmap.custom.tmap.args", "value": "--profile-amp --ovr-candeval"}]}]}
    write_json(root / "data/plans/source_replay.json", plan)
    return plan
