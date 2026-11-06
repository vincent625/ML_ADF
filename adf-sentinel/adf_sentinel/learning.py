from __future__ import annotations

import collections
import importlib.metadata
import json
import os
import platform
import time
from pathlib import Path

from .common import ROOT, TAXONOMY, digest, file_hash, now, read_json, read_jsonl, write_json, write_jsonl
from .dataset import propose_category
from .predictor import input_rows, predict_rows, structured_features

SEED = 7341
SELECTION_RULE = "Require defensible reviewed chronological validation; maximize correct exact executable plans with zero incorrect automatic plans and >=5 validation cases per enabled class, then macro-F1, then lower runtime. Otherwise advisory only, automatic execution disabled."


def versions():
    result = {"python": platform.python_version()}
    for name in ["numpy", "scipy", "scikit-learn", "joblib"]:
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = "unavailable"
    return result


def make_model(name, y, C=1.0, depth=4):
    from sklearn.dummy import DummyClassifier
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.svm import LinearSVC
    from sklearn.tree import DecisionTreeClassifier
    if name == "majority" or len(set(y)) < 2:
        # Dummy needs a two-dimensional feature matrix, unlike text pipelines.
        from sklearn.preprocessing import FunctionTransformer
        return Pipeline([("shape", FunctionTransformer(text_shape)), ("clf", DummyClassifier(strategy="most_frequent", random_state=SEED))]) if name != "structured_tree" else DummyClassifier(strategy="most_frequent", random_state=SEED)
    if name == "structured_tree":
        return DecisionTreeClassifier(max_depth=depth, min_samples_leaf=3, random_state=SEED)
    clf = LogisticRegression(C=C, max_iter=2000, random_state=SEED) if name == "tfidf_logistic" else LinearSVC(C=C, random_state=SEED, max_iter=10000)
    return Pipeline([("tfidf", TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=1, max_features=20000,
                                              strip_accents="unicode", sublinear_tf=True)), ("clf", clf)])


def text_shape(texts):
    import numpy as np
    return np.zeros((len(texts), 1))


def class_metrics(true, predicted, labels=TAXONOMY):
    from sklearn.metrics import classification_report, confusion_matrix, f1_score
    return {"correct": sum(a == b for a, b in zip(true, predicted)), "total": len(true),
            "macro_f1": float(f1_score(true, predicted, labels=labels, average="macro", zero_division=0)),
            "classes": classification_report(true, predicted, labels=labels, output_dict=True, zero_division=0),
            "confusion_matrix": confusion_matrix(true, predicted, labels=labels).tolist(), "class_order": labels}


def plan_equal(predicted, reference):
    fields = ["action_type", "target", "value", "version", "variant_scope", "prerequisites", "checks"]
    return all(predicted.get(field) == reference.get(field) for field in fields)


def precision_coverage(scored_cases):
    """Thresholds come from observed validation scores, never arbitrary percentages."""
    rows = []
    for threshold in sorted({r["score"] for r in scored_cases if r.get("score") is not None}):
        selected = [r for r in scored_cases if r.get("score") is not None and r["score"] >= threshold and r.get("schema_valid") and r.get("approved_inputs_complete")]
        correct = sum(bool(r.get("exact_plan_correct")) for r in selected)
        rows.append({"threshold": threshold, "correct": correct, "attempted": len(selected),
                     "precision": correct / len(selected) if selected else None,
                     "coverage": len(selected) / len(scored_cases) if scored_cases else None,
                     "eligible": len(selected) >= 5 and correct == len(selected)})
    return rows


def train(root=ROOT):
    root = Path(root)
    output = root / "runs/training"
    manifest = read_json(root / "data/split_manifest.json")
    if not manifest:
        raise ValueError("Run prepare before training")
    if (root / "runs/benchmark/final_results.json").exists():
        previous = read_json(output / "comparison.json", {})
        if previous.get("data_hash") != manifest.get("data_hash") or previous.get("versions") != versions():
            raise ValueError("This evaluated campaign is locked; preserve it and use a new campaign root")
        if any(file_hash(root / item["path"]) != item["sha256"] for item in previous.get("model_files", [])):
            raise ValueError("Locked model artifacts changed")
        return {**previous, "reused_locked_artifacts": True}
    integrity = read_json(root / "data/extracted/integrity.json", {})
    if any(v is False for k, v in integrity.items() if k not in {"primary_performance_claim_permitted"}):
        raise ValueError("Integrity checks failed before training")
    # Final-test answers are deliberately not opened by training/model selection.
    training_labels = {r["id"]: r for part in ["train", "validation"] for r in read_jsonl(root / f"data/labels/reviewed_{part}.jsonl")}
    strict_train = input_rows(root / "data/model_inputs/strict_train.jsonl", root / "data/model_inputs")
    strict_val = input_rows(root / "data/model_inputs/strict_validation.jsonl", root / "data/model_inputs")
    strict_ok = bool(strict_train and strict_val and len({training_labels[r["id"]]["category"] for r in strict_train}) >= 2)
    exploratory = not strict_ok
    if exploratory:
        source = input_rows(root / "data/model_inputs/retrospective.jsonl", root / "data/model_inputs")
        # Dated validation/test rows and all Manticore cases stay out of exploratory fitting.
        rows = [r for r in source if r["partition"] in {"train", "undated"} and r["family"] != "Manticore OFAv2"]
        labels = {r["id"]: r for r in read_jsonl(root / "data/labels/weak_actions.jsonl")}
        validation = []
        scope = "exploratory_weak_labels_retrospective_no_accuracy_claim"
    else:
        rows, validation, labels = strict_train, strict_val, training_labels
        scope = "reviewed_point_in_time"
    rows = [r for r in rows if r["id"] in labels]
    if not rows:
        result = {"status": "blocked", "reason": "No training cases", "versions": versions()}
        write_json(output / "comparison.json", result)
        return result
    import joblib
    from sklearn.metrics import f1_score
    comparison = []
    model_files = []
    for name in ["majority", "rules", "tfidf_logistic", "tfidf_svm", "structured_tree"]:
        configurations = [{"C": .5}, {"C": 2.0}] if not exploratory and name in {"tfidf_logistic", "tfidf_svm"} else [{}]
        candidates = []
        for config in configurations:
            start = time.perf_counter()
            fitted = {}
            if name != "rules":
                texts = [r["text"] for r in rows]
                X = structured_features(texts) if name == "structured_tree" else texts
                for target in ["category", "execution_mode"]:
                    y = [labels[r["id"]][target] for r in rows]
                    clf = make_model(name, y, **config)
                    clf.fit(X, y)
                    fitted[target] = clf
            elapsed = time.perf_counter() - start
            metrics = None
            if validation:
                if name == "rules":
                    predicted = [propose_category(r["text"]) for r in validation]
                else:
                    predicted = [p["predicted_category"] for p in predict_rows(validation, fitted, name)]
                metrics = class_metrics([labels[r["id"]]["category"] for r in validation], predicted)
                metrics["by_family"] = {}
                metrics["by_release"] = {}
                for grouping, dest in [("family", "by_family"), ("release_id", "by_release")]:
                    for group in sorted({r[grouping] for r in validation}):
                        idx = [i for i, r in enumerate(validation) if r[grouping] == group]
                        metrics[dest][group] = class_metrics([labels[validation[i]["id"]]["category"] for i in idx], [predicted[i] for i in idx])
            candidates.append((metrics["macro_f1"] if metrics else 0, config, fitted, elapsed, metrics))
        _, config, fitted, elapsed, metrics = max(candidates, key=lambda c: (c[0], -c[3]))
        model_path = output / "models" / (name + ".joblib")
        if name != "rules":
            model_path.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(fitted, model_path)
            model_files.append({"name": name, "path": str(model_path.relative_to(root)), "sha256": file_hash(model_path)})
        comparison.append({"model": name, "status": "trained_exploratory" if exploratory and name != "rules" else "implemented_rules_no_training" if name == "rules" else "trained",
                           "scope": scope, "training_rows": len(rows), "training_releases": len({r["release_id"] for r in rows}),
                           "runtime_seconds": elapsed, "configuration": config, "validation": metrics,
                           "exact_plan_metrics": None, "automation_precision": None, "coverage": None,
                           "reason": "No reviewed validation or exact-plan labels; heuristic agreement is not supervised accuracy" if exploratory else "Exact plan selection remains gated on approved structured plans"})
    comparison.extend([
        {"model": "pretrained_embeddings_classifier", "status": "blocked", "reason": "No approved pinned local embedding model configured; no remote embedding service invoked"},
        {"model": "llm_few_shot_retrieval", "status": "blocked", "reason": "No approved callable LLM baseline/configuration; this coding assistant is not logged as a trained evaluation model"},
    ])
    valid_models = [m for m in comparison if m.get("validation")]
    selected = max(valid_models, key=lambda m: (m["validation"]["macro_f1"], -m["runtime_seconds"]))["model"] if valid_models else None
    # All executable-plan counts are currently zero; classification breaks the advisory tie.
    report = {"status": "exploratory_fits_completed" if exploratory else "trained", "scope": scope,
              "models": comparison, "versions": versions(), "seed": SEED,
              "selection_rule": SELECTION_RULE, "train_ids": [r["id"] for r in rows],
              "train_release_ids": sorted({r["release_id"] for r in rows}),
              "category_distribution": dict(collections.Counter(labels[r["id"]]["category"] for r in rows)),
              "mode_distribution": dict(collections.Counter(labels[r["id"]]["execution_mode"] for r in rows)),
              "training_data_hash": digest(rows), "label_hash": digest([labels[r["id"]] for r in rows]),
              "split_hash": file_hash(root / "data/split_manifest.json"), "data_hash": manifest["data_hash"],
              "fit_feature_policy": "TF-IDF fit only on training text. Structured features: text length, word/file/version/variant counts, missing-input wording. No status, resolution, post-cutoff retrieval, or label columns.",
              "calibration": "No classifier score is a validated probability; SVM uses raw margins", "model_files": model_files,
              "primary_winner": selected, "primary_winner_reason": "Selected on reviewed chronological validation for advisory routing; automatic execution remains disabled" if selected else "Defensible reviewed validation unavailable",
              "advisory_model": "tfidf_logistic", "advisory_selection": "Predeclared runnable default, not a validation winner",
              "automation_thresholds": {category: None for category in TAXONOMY}}
    write_json(output / "comparison.json", report)
    return report


def freeze(root=ROOT):
    root = Path(root)
    report = read_json(root / "runs/training/comparison.json")
    split = read_json(root / "data/split_manifest.json")
    if not report or not split:
        raise ValueError("Prepare and train before freezing")
    if report.get("data_hash") != split.get("data_hash"):
        raise ValueError("Training data changed; retrain before freezing")
    manifest_path = root / "runs/frozen/manifest.json"
    previous = read_json(manifest_path)
    fingerprints = {"adf_sentinel/" + p.name: file_hash(p) for p in sorted(Path(__file__).parent.glob("*.py"))}
    files = report.get("model_files", [])
    frozen = {"created_at": now(), "data_hash": split["data_hash"], "training_hash": file_hash(root / "runs/training/comparison.json"),
              "split_hash": file_hash(root / "data/split_manifest.json"), "model_files": files,
              "source_versions": fingerprints, "seed": SEED, "versions": versions(),
              "feature_files": {str(p.relative_to(root)): file_hash(p) for p in sorted((root / "data/model_inputs").glob("*.jsonl"))},
              "primary_winner": report.get("primary_winner"), "advisory_model": report.get("advisory_model"),
              "selection_rule": SELECTION_RULE, "thresholds": report.get("automation_thresholds", {}),
              "retrieval_snapshot": "none", "prompt_snapshot": "none", "executor_version": "1",
              "status": "validated_advisory_only" if report.get("primary_winner") else "advisory_only_primary_benchmark_blocked", "automatic_execution_enabled": False,
              "limits": split.get("blocking_reasons", []) + ["Exact executable-plan validation labels unavailable"]}
    frozen["freeze_id"] = digest({k: v for k, v in frozen.items() if k != "created_at"})
    if previous and (root / "runs/benchmark/final_results.json").exists() and previous["freeze_id"] != frozen["freeze_id"]:
        raise ValueError("Frozen campaign already evaluated; do not overwrite it after reference reveal")
    if previous and previous["freeze_id"] == frozen["freeze_id"]:
        return previous
    write_json(manifest_path, frozen)
    return frozen


def predict(root=ROOT, strict=True):
    root = Path(root)
    frozen = read_json(root / "runs/frozen/manifest.json")
    if not frozen:
        raise ValueError("Freeze model artifacts before predictions")
    for path, expected in frozen.get("source_versions", {}).items():
        if file_hash(Path(__file__).parent / Path(path).name) != expected:
            raise ValueError("Frozen prediction/executor source changed; preserve the campaign and refreeze before evaluation")
    for path, expected in frozen.get("feature_files", {}).items():
        if file_hash(root / path) != expected:
            raise ValueError("Frozen feature file changed")
    import joblib
    for entry in frozen["model_files"]:
        if file_hash(root / entry["path"]) != entry["sha256"]:
            raise ValueError("Frozen model artifact changed")
    model_name = (frozen.get("primary_winner") or frozen["advisory_model"]) if strict else frozen["advisory_model"]
    if model_name == "rules":
        # Persisted, frozen source implements this deterministic baseline; no weights exist.
        fitted = None
    else:
        entry = next(e for e in frozen["model_files"] if e["name"] == model_name)
        fitted = joblib.load(root / entry["path"])
    if strict:
        rows = input_rows(root / "data/model_inputs/strict_test.jsonl", root / "data/model_inputs")
    else:
        rows = input_rows(root / "data/model_inputs/retrospective.jsonl", root / "data/model_inputs")
        # Manticore was excluded from all fitting, but lacks reviewed truth/decision-time snapshots.
        rows = [r for r in rows if r["family"] == "Manticore OFAv2" or r["partition"] == "test"]
    predictions = predict_rows(rows, fitted, model_name, "strict_pending_reference" if strict else "retrospective_advisory_no_benchmark_claim") if fitted else [
        {"id": r["id"], "issue_key": r["issue_key"], "release_id": r["release_id"], "family": r["family"], "predicted_category": propose_category(r["text"]),
         "predicted_execution_mode": "assisted_review", "routing_mode": "assisted_review", "automatic_eligible": False,
         "automation_reason": "No validated exact executable plan", "score": None, "score_kind": "rules_no_confidence", "input_state": r["input_state"],
         "prediction_status": "strict_pending_reference", "plan": {"target": None, "value": None, "version": None, "variant_scope": [], "prerequisites": ["Engineer review"], "executable": False}} for r in rows]
    target = root / ("runs/benchmark/predictions.jsonl" if strict else "runs/advisory/predictions.jsonl")
    existing = target.exists()
    if strict and existing:
        previous = read_jsonl(target)
        if digest(previous) != digest(predictions):
            raise ValueError("Persisted final-test predictions cannot be changed")
    write_jsonl(target, predictions)
    receipt = {"saved_at": now(), "freeze_id": frozen["freeze_id"], "prediction_sha256": file_hash(target), "count": len(predictions),
               "input_hash": digest(rows), "kind": "strict" if strict else "retrospective_advisory",
               "strict_performance_claim_permitted": bool(strict and predictions and frozen.get("primary_winner")),
               "status": "persisted" if predictions else "blocked_no_eligible_strict_test_cases"}
    write_json(target.with_suffix(".receipt.json"), receipt)
    return receipt


def evaluate(root=ROOT):
    root = Path(root)
    path = root / "runs/benchmark/final_results.json"
    previous = read_json(path)
    frozen = read_json(root / "runs/frozen/manifest.json")
    receipt = read_json(root / "runs/benchmark/predictions.receipt.json")
    if not receipt or not frozen or receipt["freeze_id"] != frozen["freeze_id"]:
        raise ValueError("Persist final-test predictions from the frozen model before opening reference labels")
    predictions_path = root / "runs/benchmark/predictions.jsonl"
    if file_hash(predictions_path) != receipt["prediction_sha256"]:
        raise ValueError("Prediction receipt hash mismatch")
    if previous:
        if previous["freeze_id"] != frozen["freeze_id"] or previous["prediction_sha256"] != receipt["prediction_sha256"]:
            raise ValueError("Locked benchmark campaign or prediction receipt changed")
        return {**previous, "reused_locked_result": True}
    result = {"evaluated_at": now(), "freeze_id": frozen["freeze_id"], "prediction_sha256": receipt["prediction_sha256"],
              "status": "blocked", "eligible_strict_test_actions": receipt["count"], "correct": None, "total": None,
              "metrics": None, "strict_unseen": None, "carry_over": None, "confidence_intervals": None,
              "reasons": frozen["limits"], "labels_opened_for_scoring": False,
              "note": "No validated holdout accuracy, automation precision, execution success, or human-effort savings is claimed."}
    if frozen.get("primary_winner") and receipt["count"]:
        # Answers become visible to evaluation only after immutable predictions have been checked.
        reference = {r["id"]: r for r in read_jsonl(root / "data/reference/test_labels.jsonl")}
        predictions = read_jsonl(predictions_path)
        if any(p["id"] not in reference for p in predictions):
            raise ValueError("Final-test references are incomplete; do not score a convenient subset")
        true = [reference[p["id"]]["category"] for p in predictions]
        metrics = class_metrics(true, [p["predicted_category"] for p in predictions])
        groups = {p["release_id"] for p in predictions}
        metrics["by_release"] = {g: class_metrics([reference[p["id"]]["category"] for p in predictions if p["release_id"] == g], [p["predicted_category"] for p in predictions if p["release_id"] == g]) for g in groups}
        metrics["by_family"] = {g: class_metrics([reference[p["id"]]["category"] for p in predictions if p["family"] == g], [p["predicted_category"] for p in predictions if p["family"] == g]) for g in {p["family"] for p in predictions}}
        result.update(status="evaluated_advisory_classifier", correct=metrics["correct"], total=metrics["total"], metrics=metrics,
                      strict_unseen={"correct": metrics["correct"], "total": metrics["total"], "release_count": len(groups)},
                      carry_over={"status": "excluded_from_unseen_counts", "occurrences": len(read_jsonl(root / "data/reference/carry_over.jsonl"))},
                      labels_opened_for_scoring=True, automation_attempted=0, automation_coverage=0.0,
                      automation_precision=None, exact_executable_plan_correctness=None, execution_success=None,
                      uncertainty_reason="Too few test releases for a useful release-level interval" if len(groups) < 5 else "Release-level bootstrap should be added before making interval claims",
                      note="Advisory category performance only. All executable plans abstain; no bundling or savings performance is inferred.")
    # Weak, self-generated labels never enter this scoring branch.
    write_json(path, result)
    return result
