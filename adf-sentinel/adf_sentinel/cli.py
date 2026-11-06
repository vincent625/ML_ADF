from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from .common import ROOT, atomic_text, now, read_json, read_jsonl, write_json


def main(argv=None):
    parser = argparse.ArgumentParser(description="ADF Sentinel: local read-only evidence workflow and sandbox replay")
    parser.add_argument("--root", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ingest", help="Normalize saved connected-reader responses or authorized JSON exports")
    collect = commands.add_parser("collect", help="Resume read-only collection or emit the connected-reader work queue")
    collect.add_argument("--transport", choices=["connected", "rest", "export"], default="connected")
    collect.add_argument("--resume", action="store_true")
    collect.add_argument("--retry", action="store_true")
    collect.add_argument("--max-jobs", type=int)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--annotations", type=Path)
    for name in ["extract", "train", "freeze", "evaluate", "audit", "effort", "status", "export", "report"]:
        commands.add_parser(name)
    predict = commands.add_parser("predict")
    predict.add_argument("--advisory", action="store_true")
    plan = commands.add_parser("plan")
    plan.add_argument("--source-replay", action="store_true")
    plan.add_argument("--fixture", action="store_true")
    plan.add_argument("--action-id")
    bundle = commands.add_parser("bundle")
    bundle.add_argument("--plan", type=Path, required=True)
    bundle.add_argument("--baseline", type=Path, required=True)
    serve = commands.add_parser("serve")
    serve.add_argument("--port", type=int, default=8876)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    start = time.perf_counter()
    if args.command == "ingest":
        from .dataset import ingest
        result = ingest(root)
        result = {k: v for k, v in result.items() if k not in {"unexpanded_frontier", "collection_errors"}}
    elif args.command == "collect":
        from .collect import collect
        result = collect(root, args.transport, args.retry, args.max_jobs)
    elif args.command == "prepare":
        from .dataset import prepare
        prepared = prepare(root, args.annotations)
        result = {"status": prepared["status"], "integrity": prepared["integrity"],
                  "benchmark_status": prepared["split"]["benchmark_status"], "blocking_reasons": prepared["split"]["blocking_reasons"]}
    elif args.command == "extract":
        from .artifacts import extract_downloads
        result = extract_downloads(root)
    elif args.command == "train":
        from .learning import train
        trained = train(root)
        result = {k: trained.get(k) for k in ["status", "scope", "versions", "primary_winner", "primary_winner_reason", "advisory_model"]}
        result["models"] = [{k: m.get(k) for k in ["model", "status", "training_rows", "runtime_seconds", "reason"]} for m in trained.get("models", [])]
    elif args.command == "freeze":
        from .learning import freeze
        result = freeze(root)
    elif args.command == "predict":
        from .learning import predict
        result = predict(root, strict=not args.advisory)
    elif args.command == "evaluate":
        from .learning import evaluate
        result = evaluate(root)
    elif args.command == "plan":
        from .plans import seed_fixtures, source_replay_plan
        if args.source_replay:
            result = source_replay_plan(root)
        elif args.fixture:
            result = seed_fixtures(root)
        else:
            candidates = [r for r in read_jsonl(root / "data/labels/weak_actions.jsonl") if r["id"] == args.action_id]
            if not candidates:
                raise ValueError("Specify --source-replay, --fixture, or an existing --action-id")
            row = candidates[0]
            result = {"action_id": row["id"], "category_proposal": row["category"], "status": "assisted_review",
                      "target": None, "value": None, "version": None, "variant_scope": [],
                      "prerequisites": row["prerequisites"], "reason": "Exact approved target/value/verification unavailable; no executable plan invented"}
    elif args.command == "bundle":
        from .plans import execute
        result = execute(read_json(args.plan), args.baseline, root)
    elif args.command == "effort":
        from .effort import report
        result = report(root)
    elif args.command == "audit":
        from .audit import run_audit
        result = run_audit(root)
    elif args.command == "report":
        from .handoff import sources_and_report
        result = sources_and_report(root)
    elif args.command == "status":
        from .server import snapshot
        result = snapshot(root, compact=True)
    elif args.command == "export":
        from .server import export_evidence
        result = export_evidence(root)
    else:
        from .server import serve
        serve(root, args.port)
        return
    stage = {"stage": args.command, "finished_at": now(), "runtime_seconds": time.perf_counter() - start,
             "status": result.get("status", "completed"), "scope": "local_pipeline_runtime_not_engineering_effort"}
    destination = root / "runs/stages.jsonl"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a") as stream:
        stream.write(json.dumps(stage) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
