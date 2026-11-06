# Measure where time goes

The current campaign has no measured human-time observations. Its category counts suggest investigation and clarification deserve attention; they do not establish a time ranking or a savings percentage.

Use a small representative sample of real changes spanning investigation, parameter changes, files, dependencies, and variant scope. Define the same completion milestone for manual and assisted work before timing. For example, “reviewable change record with source evidence and open questions” measures preparation; it does not claim completed bundling, installation, or scientific validation.

## Recording observations

Use `templates/time_observations.csv`. Record one `manual` and one `assisted` observation with a shared `pair_id`. The `action_id`, `scope`, and `milestone` must match exactly. Use a timezone-bearing ISO timestamp such as `2026-11-03T10:00:00-08:00`; record the actual observer and `completion_state=completed`.

Record active engineer minutes in each phase:

- `search_minutes`: finding and comparing source material.
- `clarification_minutes`: active questions and discussion resolving requirements.
- `investigation_minutes`: reproducing behavior and finding the technical cause.
- `edit_minutes`: preparing exact changes.
- `review_minutes`: reviewing evidence, the proposed change and its results.
- `supervision_minutes`: active intervention while a tool runs.
- `rework_minutes`: correcting mistakes and manual fallback.
- `intake_minutes`: entering or cleaning the input record.

Record `wait_minutes` separately: dependency, approval, unattended build or resource waiting is not hands-on engineer effort. Record `setup_minutes` separately for one-time tooling or annotation setup, without counting it in an active phase a second time. A measured zero is `0`; an unknown duration must be left empty. Empty, negative, infinite or nonnumeric durations make the pair ineligible for savings arithmetic.

Avoid overlapping active timers. Keep the original inputs and acceptance checks fixed. Record execution order and known learning or carryover effects in the pilot notes; a second pass through the same task can be faster because the engineer already knows the answer. Counterbalance task/order where feasible. The resulting paired differences describe this sample, not a validated causal estimate or a projection for every release.

## Calculation and interpretation

`summarize_observations(path)` in `bottlenecks.py` returns complete matched pairs, excluded rows/pairs with reasons, active minutes by phase, waiting and setup. Net active minutes saved are manual active minutes minus assisted active minutes, including assisted review, supervision, intake and rework. Negative savings are retained. One-time setup is shown separately; any amortization decision must state its chosen workload and assumptions. Summed waiting is descriptive and is not an estimate of calendar lead time when steps run in parallel.

The blank template returns `unknown_no_observations` and `net_active_minutes_saved=null`. It never turns missing observations into zero savings. Incomplete or mismatched pairs are excluded visibly. A mixed file may report valid pairs while flagging excluded ones; do not present the valid subset as the full pilot.

Run from `/rhome/yanzhu/ML_ADF`:

```bash
python adf-review-workbench/bottlenecks.py --source adf-sentinel --output adf-review-workbench/results
```

The report reads cached source evidence and writes only the new workbench results. It does not alter the original labels, models, frozen benchmark, evidence archive, or source systems.
