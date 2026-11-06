from __future__ import annotations

import csv
from pathlib import Path

from .common import ROOT, now, read_json, write_json

FIELDS = ["action_id", "release_id", "scope", "completion_milestone", "manual_replaced_minutes", "review_minutes",
          "supervision_minutes", "correction_minutes", "intake_minutes", "unattended_runtime_minutes", "waiting_minutes",
          "measurement_kind", "measurement_source", "setup_minutes"]


def net_minutes(row):
    required = ["manual_replaced_minutes", "review_minutes", "supervision_minutes", "correction_minutes", "intake_minutes"]
    if any(row.get(k) in {None, ""} for k in required):
        return None
    values = {k: float(row[k]) for k in required}
    if any(v < 0 for v in values.values()):
        raise ValueError("Effort measurements cannot be negative")
    return values["manual_replaced_minutes"] - sum(values[k] for k in required[1:])


def critical_path(tasks):
    """Only explicit task durations/waits/availability, no ticket-age inference."""
    finished, visiting, by_id = {}, set(), {t["id"]: t for t in tasks}
    if len(by_id) != len(tasks):
        raise ValueError("Repeated task IDs")
    def finish(key):
        if key in finished:
            return finished[key]
        if key in visiting or key not in by_id:
            raise ValueError("Cyclic/missing lead-time dependency")
        visiting.add(key)
        t = by_id[key]
        dependency_finish = max((finish(k) for k in t.get("depends_on", [])), default=0)
        start = max(dependency_finish, float(t.get("available_after_hours", 0)))
        duration, wait = float(t["duration_hours"]), float(t.get("wait_hours", 0))
        if min(duration, wait, start) < 0:
            raise ValueError("Negative lead-time duration")
        finished[key] = start + duration + wait
        visiting.remove(key)
        return finished[key]
    for key in by_id:
        finish(key)
    return {"elapsed_hours": max(finished.values(), default=0), "task_completion_hours": finished}


def report(root=ROOT):
    root = Path(root)
    path = root / "data/effort/observations.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", newline="") as stream:
            csv.DictWriter(stream, fieldnames=FIELDS).writeheader()
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    measured, hypothetical, incomplete = [], [], []
    for row in rows:
        value = net_minutes(row)
        if value is None or not row.get("measurement_source") or not row.get("completion_milestone"):
            incomplete.append(row)
            continue
        if row.get("measurement_kind") == "observed":
            measured.append({**row, "net_minutes": value})
        else:
            hypothetical.append({**row, "net_minutes": value})
    lead = read_json(root / "data/effort/lead_time.json")
    lead_result = {**critical_path(lead["tasks"]), "kind": lead.get("kind", "hypothetical"), "source": lead.get("source")} if lead else None
    result = {"generated_at": now(), "measured_actions": len(measured), "measured_net_minutes": sum(r["net_minutes"] for r in measured) if measured else None,
              "measured_rows": measured, "hypothetical_rows": hypothetical, "incomplete_rows": incomplete,
              "lead_time": lead_result, "one_time_setup_minutes": sum(float(r.get("setup_minutes") or 0) for r in measured) if measured else None,
              "status": "measured" if measured else "blocked_no_human_touch_time_observations",
              "formula": "manual effort replaced - review - execution supervision - correction/rework - intake overhead",
              "scope": "Bundle-only at the same completion milestone; sanity/physical testing excluded unless explicitly included in a separate row scope",
              "measurements_needed": ["Timed manual replay at a defined milestone", "Proposal review and intake", "Execution supervision", "Correction and manual fallback", "Unchanged release work", "Wait/dependency/resource observations for calendar lead time"],
              "runtime_is_not_labor_saved": True}
    write_json(root / "runs/effort/report.json", result)
    return result
