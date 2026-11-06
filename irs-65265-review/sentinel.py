"""Evidence-grounded sandbox. No instrument, scientific inference, or ADF installer."""
from __future__ import annotations

import copy
import csv
import difflib
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
DEFAULT_DATA = BASE / "demo_data"
VARIANTS = ("dna", "fusion")
SCENARIOS = [
    ("control", "Passing controls", "Unmodified synthetic reference; not an installed ADF."),
    ("wrong-kit", "Wrong DNA kit", "Counterfactual DNA kit mismatch in DNA."),
    ("wrong-primer", "Wrong primer in one variant", "Counterfactual pool 2 mismatch in DNA+Fusion."),
    ("baseline-revision", "Wrong baseline revision", "Counterfactual referenced CNV baseline revision."),
    ("repair-flag", "Repair flag in one argument source", "Counterfactual AnalysisArgs-only repair flag."),
    ("stale-script", "One shared script stale", "Counterfactual Fusion CNV plot script drift."),
    ("report-version", "Wrong report dependency", "Counterfactual DNA report package version."),
    ("missing-plot", "Unexpected missing plot", "Counterfactual missing plot with passing CNV QC."),
    ("stale-pass", "Prior pass after a parameter change", "Run, approve a sandbox R18 revision, then inspect stale evidence."),
]
ENVIRONMENT = {"runner": "sentinel-local-v1", "python": platform.python_version(),
               "pipeline": "NOT_EXECUTED", "instrument": "NOT_CONNECTED"}


def load(path: Path):
    return json.loads(path.read_text())


def save(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def source_checks() -> dict:
    """Execute the supplied validator without rewriting the original evidence."""
    with tempfile.TemporaryDirectory(prefix="sentinel-source-") as directory:
        root = Path(directory)
        for name in ("check_source_evidence.py", "github-review-data.json"):
            shutil.copy2(BASE / name, root / name)
        result = subprocess.run([sys.executable, str(root / "check_source_evidence.py")],
                                capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError(f"Source validator failed: {result.stdout}\n{result.stderr}")
        return load(root / "source-check-results.json")


def evidence() -> dict:
    github = load(BASE / "github-review-data.json")
    coverage = load(BASE / "source-coverage.json")
    with (BASE / "linked-sources.csv").open(newline="") as handle:
        links = list(csv.DictReader(handle))
    requirements = load(BASE / "requirements-candidates.json")
    comments = load(BASE / "comments.json")
    examples = [json.loads(line) for line in (BASE / "training-examples.jsonl").read_text().splitlines()]
    prs = []
    for key in ("dna", "fusion", "templates"):
        prs.append({"scope": key, **github["provenance"][key],
                    "inventory_count": len(github[key]["files"]),
                    "selected_patch_count": len(github[key]["selected_patch_evidence"])})
    shared = []
    for item in github["shared_component_comparison"]:
        row = dict(item)
        row["inventory_status"] = next((f["status"] for f in github["dna"]["files"]
                                        if f["path"] == item["path"]), "unknown")
        row["changes"] = {v: next((f["changes"] for f in github[v]["files"]
                                  if f["path"] == item["path"]), 0) for v in VARIANTS}
        shared.append(row)
    # These are exact captured lines, not model-generated quotations.
    excerpts = {r["id"]: {"source": r["source"], "text": json.dumps(r["expected"], indent=2),
                          "kind": "candidate_contract_not_original_quote"} for r in requirements}
    description = (BASE / "description.txt").read_text()
    sections = {
        "R01": ("Part Number for DNA panel kit", "Part Number for\nRNA"),
        "R05": ("3.1 ", "3.2 "),
        "R06": ("3.2 ", "4.1 "),
        "R08": ("4.2 ", "5 hotspot"),
        "R09": ("Question: This hotspot", "6\nOVAT"),
        "R11": ("ruleset: confirmed with Fernando", "7 new"),
        "R12": ("7 new\nCNV", "8 new CNV"),
        "R14": ("9 Ying already", "9 instrument workflow"),
        "R17": ("11 Sameh", "UI bugs and improvement:"),
    }
    for identifier, (start, end) in sections.items():
        excerpt = description.split(start, 1)[1].split(end, 1)[0]
        excerpts[identifier] = {"source": "description.txt (plain-text capture)",
                              "text": start + excerpt, "kind": "exact_captured_excerpt"}
    for identifier, comment_id in (("R18", "2914455"), ("R19", "2914560")):
        comment = next(c for c in comments if c["id"] == comment_id)
        excerpts[identifier] = {"source": comment["source_url"], "text": comment["text"],
                               "kind": "exact_captured_excerpt", "available_at": comment["updated"]}
    history = []
    for link in links:
        if link["type"] == "Genexus run":
            ids = re.findall(r"\d{7}", link["sources"])
            history.append({**link, "run_id": link["url"].split("/sample/")[1].split("/")[0],
                            "evidence_status": "reported_only_not_current_test_pass",
                            "execution_mode": "archived_replay",
                            "dates": [{k: c[k] for k in ("id", "created", "updated")}
                                      for c in comments if c["id"] in ids]})
    return {"coverage": coverage, "links": links, "url_counts": dict(Counter(x["type"] for x in links)),
            "requirements": requirements, "prs": prs, "shared": shared, "excerpts": excerpts,
            "comments": comments, "history": history, "ai_replay": examples,
            "input_hashes": {name: digest((BASE / name).read_bytes()) for name in (
                "REVIEW.md", "source-coverage.json", "requirements-candidates.json",
                "training-examples.jsonl", "github-review-data.json", "source-check-results.json",
                "linked-sources.csv", "description.txt", "comments.json")},
            "live_source_verification": load(BASE / "live-source-verification.json"),
            "ai_mode": "Stored interpretation replay; no live model configured; no model trained",
            "original_uploads": "Not present in this supplied review package",
            "real_assembly": "BLOCKED: released ADF ZIPs and binary baselines missing",
            "xray": "Saved panel: UNCOVERED / no associated tests. Mapping gap, not proof of no testing.",
            "schedule": [{"phase": "Bundle", "start": "2026-09-16", "end": "2026-09-29", "label": "2w"},
                         {"phase": "Sanity testing", "start": "2026-09-30", "end": "2026-10-06", "label": "1w"},
                         {"phase": "Mol Bio runs / data analysis", "label": "Separate subsequent phases"}],
            "limitations": ["5 of 11 comments loaded; edited text is only available as of update time.",
                            "Attachment badge 67 vs cached count 65; only 10 metadata records captured.",
                            "Resource ZIP reviewed previously contained web assets, not released ADFs.",
                            "PR inventories are not full-content reviews. Central config returned 404.",
                            "Ticket MD5 declarations are not actual released-byte hash validation.",
                            "MAPD = 0.5 behavior is unspecified; use explicit QC outcomes, not an invented cutoff.",
                            "Production labor savings are unmeasured; require a real pilot."]}


def make_contract() -> dict:
    req = {r["id"]: r for r in load(BASE / "requirements-candidates.json")}
    github = load(BASE / "github-review-data.json")
    shared = {x["path"]: x for x in github["shared_component_comparison"]}
    assets = {}
    for identifier, directory in (("R03", "TVC_Mask_Bed"), ("R07", "Bed"), ("R09", "Hotspot"),
                                  ("R12", "CNV"), ("R13", "CNV")):
        expected = req[identifier]["expected"]
        path = f"{directory}/{expected['file']}"
        assets[identifier] = {"file": path, "declared_md5": expected["ticket_md5"],
                              "revision": shared[path]["dnaSha"]}
    for key, field, directory in (("R17-binary", "binary", "Pipeline/bin"),
                                  ("R17-baseline", "baseline", "TVC_Mask_Bed")):
        expected = req["R17"]["expected"]
        path = f"{directory}/{expected[field]}"
        assets[key] = {"file": path, "declared_md5": expected[f"{field}_ticket_md5"],
                       "revision": shared[path]["dnaSha"]}
    return {"release": "IRS-65265", "status": "sandbox_contract_only_not_engineer_approved_release",
            "dna": req["R01"]["expected"], "rna": req["R02"]["expected"], "assets": assets,
            "annotator": "false", "fusion_threshold": "0.001", "report_version": "0.0.3",
            "revisions": {r: 1 for r in req},
            "scripts": {"Pipeline/bin/copynumber_exon_finalize.py": "synthetic CNV finalize revision 3\n",
                        "Pipeline/bin/copynumber_exon_plots.py": "synthetic CNV plots revision 3\n"},
            "source_revisions": {v: github["provenance"][v]["head_sha"] for v in VARIANTS}}


def specifications(contract: dict) -> list[dict]:
    tests = []

    def add(variant, requirement, key, kind, component, expected, **extra):
        tests.append({"id": f"{variant}:{key}", "variant": variant, "requirement": requirement,
                      "kind": kind, "component": component, "expected": expected,
                      "execution_mode": ("simulated_pipeline_behavior" if kind == "qc" else "actual_local_validator"),
                      **extra})

    for variant in VARIANTS:
        for key, value in contract["dna"].items():
            add(variant, "R01", key, "manifest", "kit", value, field=key)
        if variant == "fusion":
            for key, value in contract["rna"].items():
                add(variant, "R02", "rna-" + key, "manifest", "kit", value, field="rna_" + key)
        for key, asset in contract["assets"].items():
            requirement = key.split("-")[0]
            for field in ("file", "declared_md5", "revision"):
                add(variant, requirement, f"{key}-{field}", "asset", key, asset[field],
                    asset=key, field=field)
            add(variant, requirement, f"{key}-bytes", "bytes", key, asset["fixture_sha256"], asset=key)
        for actor in ("TmapExecutionActor.ini", "AnalysisArgs.ini"):
            add(variant, "R08", actor, "args", "alignment", "no --repair-min-freq option", path=actor)
        add(variant, "R18", "annotator", "ini", "annotator", contract["annotator"],
            path="AnnotatorActor.ini", field="annotator.functional.all.alt.alleles")
        if variant == "fusion":
            add(variant, "R18", "fusion-threshold", "ini", "rna", contract["fusion_threshold"],
                path="RNACountsActor.ini", field="fusions.min.normalized.read.count.non.targeted")
        for path, content in contract["scripts"].items():
            add(variant, "R14", Path(path).name, "script", "shared-cnv", digest(content.encode()), path=path)
        add(variant, "R20", "report-version", "manifest", "report", contract["report_version"], field="report_version")
        for name, requirement in (("passing", "R19"), ("suppressed", "R19"), ("msi-qcfail", "R17")):
            add(variant, requirement, name, "qc", "cnv-output" if requirement == "R19" else "msi-output",
                "plot_present" if name == "passing" else
                "expected_suppression" if name == "suppressed" else "completed_with_MSI-QCFail", case=name)
    return tests


def fixture_path(root: Path, scenario: str, variant: str, path: str) -> Path:
    base = (root / "fixtures" / scenario / variant).resolve()
    candidate = (base / path).resolve()
    if candidate != base and base not in candidate.parents:
        raise ValueError("Fixture reference escapes the sandbox")
    return candidate


def dependencies(spec: dict, manifest: dict) -> list[str]:
    if spec["kind"] in ("manifest", "asset"):
        return ["manifest.json"]
    if spec["kind"] == "bytes":
        return ["manifest.json", manifest["assets"][spec["asset"]]["file"]]
    if spec["kind"] == "qc":
        return ["outputs.json"]
    return [spec["path"]]


def ini_values(text: str) -> dict:
    return dict(line.split("=", 1) for line in text.splitlines()
                if "=" in line and not line.lstrip().startswith("#"))


def observe(root: Path, scenario: str, spec: dict, contract: dict) -> dict:
    variant = spec["variant"]
    manifest = load(fixture_path(root, scenario, variant, "manifest.json"))
    kind = spec["kind"]
    actual = None
    output = None
    detail = ""
    try:
        if kind == "manifest":
            actual = manifest[spec["field"]]
        elif kind == "asset":
            actual = manifest["assets"][spec["asset"]][spec["field"]]
        elif kind == "bytes":
            path = manifest["assets"][spec["asset"]]["file"]
            actual = digest(fixture_path(root, scenario, variant, path).read_bytes())
            detail = "SHA-256 of actual synthetic bytes; NOT ticket MD5 validation of released bytes."
        elif kind == "script":
            actual = digest(fixture_path(root, scenario, variant, spec["path"]).read_bytes())
        elif kind == "ini":
            actual = ini_values(fixture_path(root, scenario, variant, spec["path"]).read_text())[spec["field"]]
        elif kind == "args":
            values = ini_values(fixture_path(root, scenario, variant, spec["path"]).read_text())
            args = (json.loads(values["AnalysisArgs"])["alignmentargs"] if spec["path"] == "AnalysisArgs.ini"
                    else values["tmap.custom.tmap.args"])
            forbidden = re.search(r"(?:^|\s)--repair-min-freq(?:[=\s]|$)", args)
            actual = args if forbidden else spec["expected"]
            detail = "Parsed this argument source independently; effective runtime command not executed."
        elif kind == "qc":
            output = load(fixture_path(root, scenario, variant, "outputs.json"))[spec["case"]]
            if spec["case"] == "msi-qcfail":
                actual = ("completed_with_MSI-QCFail" if output["pipeline"] == "completed"
                          and output["msi_qc"] == "MSI-QCFail" else json.dumps(output))
            elif output["cnv_qc"] == "fail" and not output["plot_present"]:
                actual = "expected_suppression"
            elif output["cnv_qc"] == "pass" and output["plot_present"]:
                actual = "plot_present"
            else:
                actual = "unexpected_output:" + json.dumps(output, sort_keys=True)
            detail = json.dumps(output, sort_keys=True) + "; simulated output, not a pipeline execution."
        else:
            raise ValueError(f"Unsupported validator: {kind}")
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as error:
        actual = f"MISSING_OR_INVALID_EVIDENCE: {error}"
        detail = "Required fixture evidence is absent or malformed; no success fallback."
    files = dependencies(spec, manifest)
    hashes = {}
    for path in files:
        target = fixture_path(root, scenario, variant, path)
        hashes[path] = digest(target.read_bytes()) if target.is_file() else "MISSING"
    # Requirement-scoped values avoid invalidating a kit assertion for an unrelated manifest edit.
    if kind in ("manifest", "asset"):
        semantic_input = actual
    elif kind == "bytes":
        semantic_input = {"reference": manifest["assets"][spec["asset"]]["file"], "sha256": actual}
    elif kind == "qc":
        semantic_input = output
    else:
        semantic_input = hashes
    fingerprint = digest(json.dumps({"input": semantic_input, "requirement_revision":
                                    contract["revisions"][spec["requirement"]],
                                    "expected": spec["expected"], "environment": ENVIRONMENT},
                                   sort_keys=True).encode())
    return {**spec, "observed": actual, "status": "pass" if actual == spec["expected"] else "fail",
            "detail": detail, "fingerprint": fingerprint, "dependency_hashes": hashes,
            "requirement_revision": contract["revisions"][spec["requirement"]],
            "source_revision": contract["source_revisions"][variant]}


def validate(root: Path, scenario: str) -> list[dict]:
    contract = load(root / "contracts" / f"{scenario}.json")
    return [observe(root, scenario, spec, contract) for spec in specifications(contract)]


def current_results(root: Path, scenario: str, run: dict) -> list[dict]:
    fresh = {r["id"]: r for r in validate(root, scenario)}
    results = copy.deepcopy(run["results"])
    for result in results:
        if result["fingerprint"] != fresh[result["id"]]["fingerprint"]:
            result["recorded_status"] = result["status"]
            result["status"] = "stale"
            result["stale_reason"] = "Requirement, expected contract, dependency bytes/value, or environment changed."
    return results


def execute(root: Path, scenario: str, state: dict) -> dict:
    started = stamp()
    timer = time.perf_counter()
    results = validate(root, scenario)
    run = {"id": f"local-{uuid.uuid4().hex[:10]}", "scenario": scenario,
           "started_at": started, "finished_at": stamp(),
           "duration_ms": round((time.perf_counter() - timer) * 1000, 3),
           "environment": ENVIRONMENT, "results": results,
           "scope": "Actual local validation of synthetic fixture bytes; QC outputs are simulated"}
    state["runs"].append(run)
    return run


def mutate(root: Path, scenario: str):
    """Generation only. Runtime validators never consult scenario expectations."""
    path = lambda variant, name: fixture_path(root, scenario, variant, name)
    if scenario in ("wrong-kit", "wrong-primer", "baseline-revision", "report-version"):
        variant = "fusion" if scenario == "wrong-primer" else "dna"
        manifest = load(path(variant, "manifest.json"))
        if scenario == "wrong-kit":
            manifest["panel_kit"] = "A47017"
        elif scenario == "wrong-primer":
            manifest["dna_pool_2"] = "100093901"
        elif scenario == "baseline-revision":
            manifest["assets"]["R12"]["revision"] = "synthetic-previous-baseline-revision"
        else:
            manifest["report_version"] = "0.0.2"
        save(path(variant, "manifest.json"), manifest)
    elif scenario == "repair-flag":
        path("fusion", "AnalysisArgs.ini").write_text(
            'AnalysisArgs={"alignmentargs":"tmap --profile-amp --repair-min-freq 30"}\n')
    elif scenario == "stale-script":
        path("fusion", "Pipeline/bin/copynumber_exon_plots.py").write_text("synthetic CNV plots revision 2\n")
    elif scenario == "missing-plot":
        outputs = load(path("dna", "outputs.json"))
        outputs["passing"]["plot_present"] = False
        save(path("dna", "outputs.json"), outputs)


def generate(root: Path = DEFAULT_DATA) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    contract = make_contract()
    control = root / "fixtures" / "control"
    for variant in VARIANTS:
        folder = control / variant
        folder.mkdir(parents=True, exist_ok=True)
        assets = copy.deepcopy(contract["assets"])
        for key, asset in assets.items():
            content = (f"SYNTHETIC NON-INSTALLABLE FIXTURE\n{key}\n{asset['file']}\n").encode()
            if key == "R13":
                content = b'{"synthetic": true, "exon_genes": ["BRCA1", "BRCA2"]}\n'
            target = folder / asset["file"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            contract["assets"][key]["fixture_sha256"] = digest(content)
            asset["fixture_sha256"] = digest(content)
            md5_options = {"usedforsecurity": False} if sys.version_info >= (3, 9) else {}
            asset["fixture_md5"] = hashlib.md5(content, **md5_options).hexdigest()
            asset["bytes_origin"] = "synthetic_placeholder_not_original_asset"
        manifest = {**contract["dna"], "assets": assets, "report_version": contract["report_version"],
                    "variant": variant, "installable": False}
        if variant == "fusion":
            manifest.update({"rna_" + k: v for k, v in contract["rna"].items()})
        save(folder / "manifest.json", manifest)
        for name, text in {
            "TmapExecutionActor.ini": "tmap.custom.tmap.args=--profile-amp --ovr-candeval\n",
            "AnalysisArgs.ini": 'AnalysisArgs={"alignmentargs":"tmap --profile-amp --ovr-candeval"}\n',
            "AnnotatorActor.ini": "annotator.functional.all.alt.alleles=false\n",
            **({"RNACountsActor.ini": "fusions.min.normalized.read.count.non.targeted=0.001\n"}
               if variant == "fusion" else {}), **contract["scripts"],
        }.items():
            target = folder / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        save(folder / "outputs.json", {
            "passing": {"pipeline": "completed", "cnv_qc": "pass", "mapd": 0.2, "plot_present": True},
            "suppressed": {"pipeline": "completed", "cnv_qc": "fail", "mapd": 0.7, "plot_present": False},
            "msi-qcfail": {"pipeline": "completed", "msi_qc": "MSI-QCFail", "sample_qc": "fail"},
        })
    state = {"schema_version": 1, "release": "IRS-65265", "generated_at": stamp(),
             "runs": [], "reviews": [], "parameter_changes": [], "pending_patches": {}}
    for scenario, _, _ in SCENARIOS:
        if scenario != "control":
            for source in control.rglob("*"):
                if source.is_file():
                    target = root / "fixtures" / scenario / source.relative_to(control)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
        save(root / "contracts" / f"{scenario}.json", contract)
        mutate(root, scenario)
        execute(root, scenario, state)
    save(root / "source-checks.json", source_checks())
    save(root / "state.json", state)
    events = []
    for run in state["runs"]:
        for index, result in enumerate(run["results"]):
            events.append({"id": len(events) + 1, "run_id": run["id"], "test_id": result["id"],
                           "requirement": result["requirement"], "scenario": run["scenario"],
                           "sequence": index, "event": "fixture_assertion", "status": result["status"],
                           "execution_mode": result["execution_mode"], "observed": result["observed"],
                           "origin": "generated_correlated_fixture_log_not_historical_instrument_log"})
    (root / "fixture-events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    save(root / "scenario-expectations.json", {
        "origin": "generator_oracle_used_only_by_tests_not_the_runner",
        "failures": {"control": [], "wrong-kit": ["dna:panel_kit"],
                     "wrong-primer": ["fusion:dna_pool_2"], "baseline-revision": ["dna:R12-revision"],
                     "repair-flag": ["fusion:AnalysisArgs.ini"],
                     "stale-script": ["fusion:copynumber_exon_plots.py"],
                     "report-version": ["dna:report-version"], "missing-plot": ["dna:passing"],
                     "stale-pass": []}})
    return {"tests": len(specifications(contract)), "fixture_events": len(events),
            "scenarios": len(SCENARIOS)}


class Sentinel:
    def __init__(self, root: Path = DEFAULT_DATA):
        self.root = root.resolve()
        if not (root / "state.json").exists():
            generate(root)

    def scenario(self, scenario: str):
        if scenario not in {s[0] for s in SCENARIOS}:
            raise ValueError("Unknown sandbox scenario")

    def state(self) -> dict:
        return load(self.root / "state.json")

    def view(self, scenario: str) -> dict:
        self.scenario(scenario)
        state = self.state()
        runs = [r for r in state["runs"] if r["scenario"] == scenario]
        latest = copy.deepcopy(runs[-1])
        latest["results"] = current_results(self.root, scenario, latest)
        summary = dict(Counter(r["status"] for r in latest["results"]))
        contract = load(self.root / "contracts" / f"{scenario}.json")
        shared = []
        for path in contract["scripts"]:
            hashes = {v: digest(fixture_path(self.root, scenario, v, path).read_bytes()) for v in VARIANTS}
            shared.append({"path": path, "hashes": hashes, "same_bytes": hashes["dna"] == hashes["fusion"]})
        return {"scenario": scenario, "scenarios": [{"id": a, "name": b, "description": c} for a, b, c in SCENARIOS],
                "latest": latest, "summary": summary, "test_count": len(latest["results"]),
                "runs": [{**{k: v for k, v in r.items() if k != "results"},
                          "summary": dict(Counter(item["status"] for item in
                                                 (latest["results"] if r["id"] == latest["id"] else r["results"])))}
                         for r in runs],
                "reviews": [r for r in state["reviews"] if r["scenario"] == scenario],
                "parameter_changes": [r for r in state["parameter_changes"] if r["scenario"] == scenario],
                "shared_fixtures": shared, "contract": contract,
                "source_checks": load(self.root / "source-checks.json"),
                "run_events": [{"run_id": latest["id"], "test_id": r["id"],
                                "requirement": r["requirement"], "status": r["status"],
                                "execution_mode": r["execution_mode"], "observed": r["observed"]}
                               for r in latest["results"]],
                "fixture_event_count": len((self.root / "fixture-events.jsonl").read_text().splitlines())}

    def run(self, scenario: str) -> dict:
        self.scenario(scenario)
        state = self.state()
        run = execute(self.root, scenario, state)
        save(self.root / "state.json", state)
        return run

    def preview(self, scenario: str, test_id: str) -> dict:
        self.scenario(scenario)
        contract = load(self.root / "contracts" / f"{scenario}.json")
        spec = next((r for r in specifications(contract) if r["id"] == test_id), None)
        if spec is None:
            raise ValueError("Unknown test")
        observed = observe(self.root, scenario, spec, contract)
        if observed["status"] != "fail":
            raise ValueError("A patch is only proposed for a currently observed failure")
        variant = spec["variant"]
        kind = spec["kind"]
        path = "manifest.json" if kind in ("asset", "manifest") else spec.get("path", "outputs.json")
        target = fixture_path(self.root, scenario, variant, path)
        before = target.read_text()
        if kind in ("asset", "manifest"):
            content = json.loads(before)
            if kind == "asset":
                content["assets"][spec["asset"]][spec["field"]] = spec["expected"]
            else:
                content[spec["field"]] = spec["expected"]
            after = json.dumps(content, indent=2) + "\n"
        elif kind == "script":
            after = contract["scripts"][path]
        elif kind == "args":
            values = ini_values(before)
            if path == "AnalysisArgs.ini":
                arguments = json.loads(values["AnalysisArgs"])
                arguments["alignmentargs"] = re.sub(
                    r"(?:\s+)?--repair-min-freq(?:\s+|=)\S+", "", arguments["alignmentargs"])
                after = re.sub(r"(?m)^AnalysisArgs=.*$",
                               lambda _: "AnalysisArgs=" + json.dumps(arguments, separators=(",", ":")), before)
            else:
                arguments = re.sub(r"(?:\s+)?--repair-min-freq(?:\s+|=)\S+", "",
                                   values["tmap.custom.tmap.args"])
                after = re.sub(r"(?m)^tmap\.custom\.tmap\.args=.*$",
                               lambda _: "tmap.custom.tmap.args=" + arguments, before)
        elif kind == "ini":
            after = re.sub(r"(?m)^" + re.escape(spec["field"]) + r"=.*$",
                           spec["field"] + "=" + spec["expected"], before)
        elif kind == "qc":
            content = json.loads(before)
            content[spec["case"]]["plot_present"] = True
            after = json.dumps(content, indent=2) + "\n"
        else:
            raise ValueError("No safe automatic correction for this evidence; engineer investigation needed")
        if after == before:
            raise ValueError("No safe patch could be derived from the observed file")
        proposal = {"id": uuid.uuid4().hex, "scenario": scenario, "test_id": test_id,
                    "variant": variant, "path": path, "before_sha256": digest(before.encode()),
                    "after": after, "created_at": stamp(), "requirement": spec["requirement"],
                    "source": evidence()["excerpts"][spec["requirement"]],
                    "diff": "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                                        fromfile=f"{variant}/{path}", tofile=f"{variant}/{path}")),
                    "warning": "Sandbox-only correction. Restoring a synthetic output does not repair or run a real pipeline."}
        state = self.state()
        state["pending_patches"][proposal["id"]] = proposal
        save(self.root / "state.json", state)
        return proposal

    def apply(self, proposal_id: str, reviewer: str) -> dict:
        if not reviewer.strip():
            raise ValueError("A named sandbox reviewer is required")
        state = self.state()
        proposal = state["pending_patches"].get(proposal_id)
        if not proposal:
            raise ValueError("Unknown or already applied proposal")
        target = fixture_path(self.root, proposal["scenario"], proposal["variant"], proposal["path"])
        if digest(target.read_bytes()) != proposal["before_sha256"]:
            raise ValueError("File changed since preview. Review a fresh patch.")
        target.write_text(proposal["after"])
        review = {k: v for k, v in proposal.items() if k != "after"}
        review.update({"reviewer": reviewer.strip(), "approved_at": stamp(),
                       "after_sha256": digest(target.read_bytes()), "status": "applied_sandbox_only"})
        state["reviews"].append(review)
        del state["pending_patches"][proposal_id]
        save(self.root / "state.json", state)
        return review

    def parameter_preview(self, scenario: str) -> dict:
        self.scenario(scenario)
        contract = load(self.root / "contracts" / f"{scenario}.json")
        return {"requirement": "R18", "before": contract["fusion_threshold"], "after": "0.002",
                "scope": "DNA+Fusion / RNACountsActor.ini; R18 revision also affects annotator evidence in both variants",
                "status": "proposed_synthetic_requirement_revision_not_a_real_product_decision",
                "source": evidence()["excerpts"]["R18"],
                "inference": "Shared requirement-family revision requires R18 retests; unrelated R01/R08 evidence is preserved.",
                "affected_tests": [t["id"] for t in specifications(contract) if t["requirement"] == "R18"]}

    def parameter_change(self, scenario: str, reviewer: str) -> dict:
        self.scenario(scenario)
        if not reviewer.strip():
            raise ValueError("A named sandbox reviewer is required")
        contract_path = self.root / "contracts" / f"{scenario}.json"
        contract = load(contract_path)
        if contract["fusion_threshold"] != "0.001":
            raise ValueError("Sandbox parameter revision already applied; reset to repeat")
        before = self.view(scenario)
        contract["fusion_threshold"] = "0.002"
        contract["revisions"]["R18"] += 1
        save(contract_path, contract)
        change = {"id": uuid.uuid4().hex, "scenario": scenario, "requirement": "R18",
                  "before": "0.001", "after": "0.002", "reviewer": reviewer.strip(),
                  "approved_at": stamp(), "kind": "synthetic_sandbox_requirement_revision",
                  "invalidated_tests": [r["id"] for r in before["latest"]["results"] if r["requirement"] == "R18"],
                  "source_excerpt": evidence()["excerpts"]["R18"],
                  "note": "Original release requirement unchanged. Parameter file is NOT silently modified."}
        state = self.state()
        state["parameter_changes"].append(change)
        save(self.root / "state.json", state)
        return change

    def export(self, scenario: str) -> dict:
        view = self.view(scenario)
        report = {"schema_version": 1, "exported_at": stamp(), "release": "IRS-65265",
                  "disposition": "DRAFT / synthetic sandbox; not release approval",
                  "evidence": evidence(), "sandbox": view,
                  "audit_runs": [r for r in self.state()["runs"] if r["scenario"] == scenario],
                  "savings": {"production_savings": None, "status": "unmeasured_requires_pilot"},
                  "remaining_gaps": evidence()["limitations"] + [evidence()["real_assembly"]]}
        save(self.root / "exports" / f"{scenario}-evidence.json", report)
        return report

    def bundle(self, scenario: str) -> Path:
        self.scenario(scenario)
        target = self.root / "exports" / f"{scenario}-SYNTHETIC-NON-INSTALLABLE.zip"
        target.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("NOT_AN_ADF.txt", "SYNTHETIC / NON-INSTALLABLE / NO SCIENTIFIC VALIDATION\n")
            folder = self.root / "fixtures" / scenario
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    archive.write(path, str(path.relative_to(folder)))
        return target


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("generate", "run", "export", "source-checks"))
    parser.add_argument("--scenario", default="wrong-primer")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()
    if args.command == "generate":
        print(json.dumps(generate(args.data), indent=2))
    elif args.command == "source-checks":
        print(json.dumps(source_checks(), indent=2))
    else:
        engine = Sentinel(args.data)
        if args.command == "run":
            result = engine.run(args.scenario)
            print(json.dumps({"run_id": result["id"], "duration_ms": result["duration_ms"],
                              "results": dict(Counter(r["status"] for r in result["results"]))}, indent=2))
        else:
            report = engine.export(args.scenario)
            print(json.dumps({"export": str(args.data / "exports" / f"{args.scenario}-evidence.json"),
                              "run_id": report["sandbox"]["latest"]["id"]}, indent=2))
