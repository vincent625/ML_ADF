"""Prediction boundary: no label/reference readers, retrieval, or source-system clients."""
from __future__ import annotations

import json
import re
from pathlib import Path

ALLOWED = {"id", "issue_key", "release_id", "family", "release_date", "partition", "episode_group",
           "text", "input_state", "cutoff", "source", "synthetic"}


def input_rows(path, input_root):
    path, input_root = Path(path).resolve(), Path(input_root).resolve()
    if not path.is_relative_to(input_root):
        raise ValueError("Prediction inputs must come from the isolated model_inputs directory")
    with path.open() as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    for row in rows:
        if set(row) - ALLOWED:
            raise ValueError("Label/reference or unsupported fields in prediction input")
        if not isinstance(row.get("text"), str):
            raise ValueError("Missing prediction text")
    return rows


def structured_features(texts):
    import numpy as np
    return np.array([[len(t), len(t.split()), len(re.findall(r"\b\w+\.(?:ini|json|py|bed|sh|vcf)\b", t)),
                      len(re.findall(r"\d+\.\d+\.\d+", t)), len(re.findall(r"\b(?:dna|rna|fusion|ffpe)\b", t, re.I)),
                      int(bool(re.search(r"\b(?:missing|unknown|pending|ambiguous)\b", t, re.I)))] for t in texts], dtype=float)


def predict_rows(rows, fitted, model_name, mode="advisory_only"):
    if not rows:
        return []
    texts = [r["text"] for r in rows]
    X = structured_features(texts) if model_name == "structured_tree" else texts
    category = fitted["category"].predict(X)
    execution = fitted["execution_mode"].predict(X)
    scores = None
    score_kind = "unavailable"
    classifier = fitted["category"]
    if hasattr(classifier, "predict_proba"):
        scores = classifier.predict_proba(X).max(axis=1)
        score_kind = "uncalibrated_classifier_score_not_probability_of_correctness"
    elif hasattr(classifier, "decision_function"):
        margins = classifier.decision_function(X)
        scores = abs(margins) if margins.ndim == 1 else margins.max(axis=1)
        score_kind = "uncalibrated_margin"
    outputs = []
    for i, row in enumerate(rows):
        outputs.append({"id": row["id"], "issue_key": row["issue_key"], "release_id": row["release_id"],
                        "family": row["family"], "predicted_category": str(category[i]),
                        "predicted_execution_mode": str(execution[i]), "routing_mode": "assisted_review",
                        "automatic_eligible": False, "automation_reason": "Exact approved plan and validated class threshold required",
                        "score": float(scores[i]) if scores is not None else None, "score_kind": score_kind,
                        "input_state": row["input_state"], "prediction_status": mode,
                        "plan": {"target": None, "value": None, "version": None, "variant_scope": [], "prerequisites": ["Engineer review", "Approved exact inputs and verification contract"], "executable": False}})
    return outputs
