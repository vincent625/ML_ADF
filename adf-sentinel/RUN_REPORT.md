# ADF Sentinel: execution report

Generated 2026-11-01T06:12:36.307563+00:00 (UTC). User-facing run date: October 31, 2026, America/Los_Angeles.

The project is implemented and runs locally. Collection is partial. Reviewed labels, a validated unseen benchmark, a genuine rebuilt ADF, and measured engineering savings are not established.

## Actually collected and run

| Evidence / result | Recorded count or state |
|---|---|
| Confluence pages read | 79 |
| Distinct release identities / families | 287 / 18 |
| Validated Jira issue records | 2460 |
| Issues explicitly associated with release rows | 582 |
| Unique referenced issue candidates | 6757 |
| Recorded source graph edges | 96243 |
| Complete comments / field histories / remote links | 2328 / 581 / 581 |
| Original attachments downloaded / metadata records | 10 / 19146 |
| Historical issue views / unconfirmed cutoff proxies | 222 / 93 |
| Proposed action labels / reviewed labels | 4922 / 0 |
| Fitted model baselines | 4 |
| Remaining reader requests | 5519 |
| Frozen strict benchmark | blocked |
| Measured engineer minutes saved | Not measured |

The source graph distinguishes release listings, mentions, formal link directions, and parent relationships. Context issues are not silently promoted to implemented changes. Failed validation cannot distinguish a missing issue from inaccessible content. All such candidates are retained.

## Learning and temporal scope

Training scope: `exploratory_weak_labels_retrospective_no_accuracy_claim`. The majority, TF-IDF logistic regression, TF-IDF SVM and structured-tree models use the same training rows; a transparent rules baseline is also implemented. Weak-label fits are exploratory. No agreement with the labeling rules is reported as accuracy. Approved pinned embedding and callable LLM baseline configurations are missing.

Release-index dates define the chronological map. Undated releases are separate. First release-ticket transitions to In Progress are explicitly unconfirmed bundling-start proxies. Edited comments are not back-dated. Recovered description history is kept separate from current retrospective inputs. Strict action inputs require confirmed cutoffs, historical evidence and reviewed truth. Final-test label files are not read by the predictor or training/model selection.

## Executed sandbox scope

- **synthetic_fixture**: 4 action(s), 6 deterministic checks, passed; originals preserved: True. Runtime 0.0764 seconds. Candidate: `runs/sandbox/0b4c92a31b3438a045c8/candidate`.
- **pinned_source_fragment_replay**: 1 action(s), 3 deterministic checks, passed; originals preserved: True. Runtime 0.0508 seconds. Candidate: `runs/sandbox/fb888a2792a7aeea64b5/candidate`.

The real replay uses actual before/after bytes pinned to the merged IRS-65265 implementation. It is one source file, not a rebuilt Genexus ADF. Synthetic fixtures are explicitly labeled and excluded from historical model claims. Real historical ADF archive hashes are computed from downloaded bytes, with ZIP-content comparison independent of archive timestamps. Serialized core payloads are never executed or deserialized.

## Verification

```json
{
  "browser": {
    "status": "passed",
    "browser_version": "123.0.6312.122",
    "checked_at": "2026-11-01T06:11:54Z",
    "chapters": 8,
    "viewports": [
      {
        "width": 1440,
        "height": 1000,
        "chapters": 8,
        "horizontal_overflow": false
      },
      {
        "width": 960,
        "height": 800,
        "chapters": 8,
        "horizontal_overflow": false
      },
      {
        "width": 390,
        "height": 844,
        "chapters": 8,
        "horizontal_overflow": false
      }
    ],
    "pointer_action_mode": "normal pointer actions with visibility and stability checks",
    "screenshot_method": "Chrome DevTools direct capture",
    "page_errors": [],
    "external_requests": [],
    "interactions": [
      "family graph",
      "issue search",
      "frozen advisory prediction persistence",
      "pinned-source replay",
      "expected precondition rejection",
      "labeled fixture replay",
      "gated reference reveal",
      "hypothetical effort arithmetic",
      "view reset",
      "evidence export"
    ],
    "scope": "Local UI and source/fixture operations; no scientific or physical validation"
  },
  "captured_release_pr_source_checks": {
    "evidence": "runs/verification/captured_source_checks.json",
    "observed": 10,
    "scope": "Captured release PR source evidence only",
    "total": 10
  },
  "frozen_integrity": {
    "feature_files": 4,
    "freeze_id": "59cc07c60d9ebcc93be4fb8d7ddb6137e64b13c9fc0a6d70e95f73d1b98668fe",
    "model_files": 4,
    "source_files": 14,
    "status": "matched"
  },
  "historical_archive_checksum_declarations": {
    "checked": 6,
    "matched": 6,
    "scope": "Actual ZIP byte hashes; no internal baseline or scientific equivalence claim"
  },
  "historical_png_integrity": {
    "decoded": 27,
    "scope": "Image format integrity only; no OCR or underlying baseline hash claim"
  },
  "pinned_git_blob_checks": {
    "passed": 2,
    "scope": "Exact source bytes, not scientific validation",
    "total": 2
  },
  "sandbox_runs": [
    {
      "originals_preserved": true,
      "run_id": "0b4c92a31b3438a045c8",
      "scope": "synthetic_fixture",
      "status": "passed"
    },
    {
      "originals_preserved": true,
      "run_id": "fb888a2792a7aeea64b5",
      "scope": "pinned_source_fragment_replay",
      "status": "passed"
    }
  ],
  "scientific_or_physical_validation_performed": false,
  "supplied_originals": {
    "files": 320,
    "status": "unchanged"
  },
  "unit_and_local_http": {
    "evidence": "runs/verification/unit.json",
    "failed": 0,
    "passed": 31,
    "runtime_seconds": 7.9,
    "status": "passed"
  },
  "upstream_writes_performed": false,
  "verified_at": "2026-11-01T06:12:36.299965+00:00"
}
```

Focused tests exercise pagination, resume/cycle/dedup behavior, independent version fields, cutoffs, train-only vocabulary, prediction/reference separation, copied-file execution, exact hashes, preconditions, unsupported operations, expected failures, local HTTP safeguards and effort arithmetic. Browser verification, when present above, checks actual clicks and responsive layout; structural checks do not establish scientific validation.

## Exact remaining work

1. Resume `data/collection_queue.json`; inspect `data/collection_failures.json` and `data/extracted/missing_sources.json`. The attachment-download budget is explicit, and every uncollected original remains listed. Deeper contextual frontiers require release relevance review rather than expansion through unrelated generic containers.
2. Review `data/reference/annotation_queue.jsonl`: establish independent action boundaries, release/variant scope, approved exact values/targets, implementation/released-byte evidence, verification outcomes and disagreements. Supply confirmed release chronology in `data/release_annotations.jsonl` and reviewed action imports through `prepare --annotations`.
3. Supply approved serialized-core build tooling and any remaining required inputs before claiming real candidate assembly. No installation, instrument run or release was authorized or performed.
4. Record matched manual/assisted observations in `data/effort/observations.csv`. The per-action template is editable. Runtime measurements are not engineer time saved; two elapsed weeks are not 80 engineer hours. Calendar dependencies and physical testing remain separate.

The original `irs-65265-review` project is preserved. The local dashboard and evidence export require no external service once results are recorded.
