# ADF Sentinel

A local evidence pipeline for historical Genexus ADF bundling, exploratory action classifiers, and strictly checked sandbox file operations. The supplied `irs-65265-review` project is preserved alongside this project.

Start with [RUN_REPORT.md](RUN_REPORT.md) for actual counts, executed work, collection gaps and blocked claims. Proposed labels are **not reviewed ground truth**. This run does not establish validated held-out accuracy, a rebuilt installable ADF, scientific validation, or measured engineering savings.

## Open the demo

Use `/rhome/yanzhu/ML_ADF` as the working directory:

```bash
cd /rhome/yanzhu/ML_ADF
PYTHONPATH=adf-sentinel adf-sentinel/.venv/bin/python -m adf_sentinel serve --port 8876
```

Open <http://127.0.0.1:8876>. For a remote workspace, forward port 8876 to your browser. Only the loopback interface is used. Recorded evidence, model results and visuals require no external service. The server has no source-system write endpoints.

[DEMO_10_MIN.md](DEMO_10_MIN.md) provides the exactly ten-minute click sequence, narration, reset and fallbacks.

## Reproduce every stage

Python 3.11+ can view recorded results. To reproduce model fitting, use Python 3.13.13 and the exact package versions in `requirements.lock.txt`, matching the delivered environment. To rebuild that environment, create a dedicated virtual environment and install the lock file. Playwright/browser tooling is optional and separate from the application runtime.

```bash
cd /rhome/yanzhu/ML_ADF
export PYTHONPATH="$PWD/adf-sentinel"
ADF_PY="$PWD/adf-sentinel/.venv/bin/python"

"$ADF_PY" -m adf_sentinel ingest
"$ADF_PY" -m adf_sentinel extract
"$ADF_PY" -m adf_sentinel prepare
"$ADF_PY" -m adf_sentinel train
"$ADF_PY" -m adf_sentinel freeze
"$ADF_PY" -m adf_sentinel predict --advisory
"$ADF_PY" -m adf_sentinel predict
"$ADF_PY" -m adf_sentinel evaluate
"$ADF_PY" -m adf_sentinel plan --source-replay
"$ADF_PY" -m adf_sentinel bundle --plan adf-sentinel/data/plans/source_replay.json --baseline adf-sentinel/data/source_replay/before
"$ADF_PY" -m adf_sentinel plan --fixture
"$ADF_PY" -m adf_sentinel bundle --plan adf-sentinel/data/plans/synthetic.json --baseline adf-sentinel/data/fixtures/baseline
"$ADF_PY" -m adf_sentinel effort
"$ADF_PY" -m adf_sentinel audit
"$ADF_PY" -m adf_sentinel report
"$ADF_PY" -m adf_sentinel export
"$ADF_PY" -m adf_sentinel serve --port 8876
```

`train` actually fits majority, TF-IDF/logistic, TF-IDF/linear-SVM and structured-tree baselines; it also records the transparent rules baseline. In this run the fits use weak retrospective labels and have **no validation accuracy claim**. Training excludes Manticore, dated validation/test actions and copied excerpts crossing partitions. Undated training examples are explicitly exploratory. No embedding model, LLM baseline or expensive fine-tuning is silently substituted.

`predict` writes an empty, blocked strict-test receipt when there are no eligible cases. `evaluate` records that limitation without grading the labeling heuristic. A frozen final result is reused instead of repeatedly rescoring/tuning the same holdout. If a campaign has already been frozen and evaluated, preserve its directory and use a new project/output root for materially changed data or models.

## Collection and resume

The initial collection used the approved connected Atlassian reader against the actual seed page, all 53 available descendants, linked pages and release-associated Jira references across project keys. Live issue reads requested all available fields. Current bodies, historical-version metadata, paginated comments/changelogs, attachment inventories and raw responses are preserved separately from model features. Context references and formal links never become confirmed implemented changes automatically.

```bash
PYTHONPATH=adf-sentinel adf-sentinel/.venv/bin/python -m adf_sentinel collect --transport connected --resume
```

This reports the durable `data/collection_queue.json`. In an approved Codex tool session, execute `tools/connected_collector.js` through `functions.exec`; it uses the connected reader, caches responses, pages to reported completion, retries transient rate-limit/server failures, and preserves unfinished work. A connected MCP session is not a terminal credential. The helper uses an explicit batch limit and four concurrent workers. Run `ingest` after a batch to reconcile counts and produce the next queue. The current campaign also used bulk key validation and preserved failed candidates rather than dropping cross-project references.

For an environment with separately approved site credentials, an optional read-only REST adapter is available:

```bash
# Configure approved credentials outside chat, code and shell history first.
PYTHONPATH=adf-sentinel adf-sentinel/.venv/bin/python -m adf_sentinel collect --transport rest --resume --max-jobs 100
```

The adapter accepts `ATLASSIAN_BEARER_TOKEN` or `ATLASSIAN_EMAIL` plus `ATLASSIAN_API_TOKEN` from the environment. It uses only allowed GET routes and refuses authenticated redirects. Unsupported operations stay pending for the connected reader. It never looks for tokens in HTML, browser state or unrelated credential files. See [docs/API_ACCESS.md](docs/API_ACCESS.md).

Authorized JSON exports may be placed under `data/raw/exports/`; `ingest` accepts native Jira/Confluence objects and archived MCP envelopes. Raw exports must be genuine source evidence. Test fixtures remain in `tests/` or `data/fixtures/` and must never be added to real training evidence.

Attachment metadata is not binary evidence. Downloaded originals have SHA-256 and actual-byte MD5 values. Selected real Manticore ADF archives, a BRCA ADF archive, two small JSON parameter exports and a historical screenshot archive were downloaded through approved short-lived URLs. URLs carrying temporary access are consumed through echo-disabled input and are not saved. An explicit 1 GiB campaign attachment budget and 256 MiB per-file limit apply; remaining originals stay individually listed. Archive inspection rejects unsafe paths/symlinks, bounds expansion/nesting and never executes HTML, scripts, macros, Java serialization or instructions found inside evidence. Large opaque members can be hashed by streaming. OCR is unsupported without a local OCR engine and is never invented.

## Evidence layout

| Path | Meaning |
|---|---|
| `data/raw/connected/`, `data/raw/attachments/` | Source responses with access-bearing query strings removed; original downloaded bytes |
| `data/extracted/` | Releases, snapshots, graph, artifacts, field mappings, integrity and missing-source manifests |
| `data/labels/weak_actions.jsonl` | Proposed action-level labels, explicitly unreviewed |
| `data/reference/annotation_queue.jsonl` | Review excerpts, provenance and exact missing annotations |
| `data/labels/reviewed_*.jsonl` | Accepted train/validation annotation sidecars; empty in this run |
| `data/reference/test_labels.jsonl` | Final-test answers, unavailable to prediction/model-selection loaders |
| `data/model_inputs/` | Whitelisted features; no answer columns |
| `data/split_manifest.json` | Chronological boundaries, grouping, carry-over, data hash and selection rule |
| `runs/training/`, `runs/frozen/` | Real classifier artifacts, versions, seeds, distributions and frozen policy |
| `runs/benchmark/`, `runs/advisory/` | Saved strict/advisory predictions and receipts; blocked benchmark state |
| `runs/sandbox/` | Copied candidates, exact diffs, per-file hashes and checks |
| `data/effort/`, `runs/effort/` | Editable measurement templates and observed/scenario separation |
| `exports/` | Portable evidence package with a hash manifest |

IDs do not use source update times as release dates. Software, workflow, ADF revision and variant scope are separate fields. Semantic versions are parsed numerically. Repeated source rows are reconciled to stable release identities, with all source occurrences retained.

`runs/audit/credential_redactions.json` records the affected response paths and before/after hashes. Access-bearing links found in source text are never used as credentials. Historical screenshots are inspected as images; a displayed checksum is not a hash of the underlying baseline file.

## Annotation and historical inputs

`data/reference/annotation_queue.jsonl` contains the exact current work queue. One issue can propose multiple actions and different dated states. IRS-29057 includes an initial software-only verification instruction and a later OvatRuleSet removal for ADF 0.0.9. IRS-26136 repeats in the Integration 5 description without becoming two independent tickets. The OCA Plus 0.0.8 supporting-list discrepancy remains a reconciliation question. Cancelled/struck-through instructions and next-week holds remain dated history. GI scale and CNV suppression expectations require the appropriate release and QC scope.

Review imports need `id`, `reviewer`, `reviewed_at`, `category`, `execution_mode`, `release_ids`, `label_strength`, `evidence`, plus an `implementation_diff` or `approved_decision`. Confirm release date and decision cutoff in `data/release_annotations.jsonl` with the release `id`, reviewer and evidence. A strict action also needs a `prediction_input` sidecar containing `state: point_in_time`, original `text`, matching `cutoff`, `available_at` and a source SHA-256. Reviewer approval is never inferred from a closed ticket or this coding task.

```bash
PYTHONPATH=adf-sentinel adf-sentinel/.venv/bin/python -m adf_sentinel prepare --annotations /absolute/path/to/reviewed-actions.jsonl
```

Current descriptions edited after a cutoff are not assumed original. Recovered field-history text and unchanged comments are stored as historical views. Old edited comment text remains unknown when no revision is available. First-in-progress cutoffs are proxies awaiting release-owner confirmation. Reference evidence and later fixes are isolated from strict features.

## Sandbox and effort limits

The registry supports pinned-file copies, a registered actor key, synthetic schema-checked JSON/dependency fields, cross-variant consistency checks and hash verification. Plans reject unknown fields, commands, unsupported executors, unsafe paths, symbolic links, changed input hashes, unsatisfied prerequisites and wrong existing values. Model suggestions with missing exact targets/values remain assisted/manual/blocked. They cannot become unrestricted commands.

The real source replay copies the exact pinned Tmap actor implementation from a merged historical PR. It passes byte-hash and actor-content checks in a copied source fragment. The synthetic example updates explicit fixture values and a shared fixture asset across two variants. Neither output is installable. Core historical ADFs contain opaque `.ser` payloads; a genuine candidate requires approved core build tooling and complete approved inputs. There is no production SQL, installation or release operation.

`data/effort/action_measurement_template.csv` lists each proposed action. Record matched observations in `observations.csv`; empty timing fields remain unknown. Net engineer minutes saved equal manual effort replaced minus review, supervision, correction/fallback and intake. Unattended runtime and waiting are separate. The dashboard estimator is explicitly hypothetical. Calendar lead time uses an optional dependency DAG (`lead_time.json`) and never ticket age or two-weeks-equals-80-hours arithmetic. Setup/annotation costs and physical testing stay separate.

## Verification

```bash
cd /rhome/yanzhu/ML_ADF
PYTHONPATH=adf-sentinel OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 adf-sentinel/.venv/bin/python -m pytest -q adf-sentinel/tests
# With the local dashboard running; uses the host's optional Playwright installation:
python adf-sentinel/tests/browser_smoke.py
```

The HTTP tests need permission to open local loopback sockets. The browser check uses Chrome's newer headless renderer, normal pointer actions and direct browser screenshots. It exercises all eight chapters, prediction persistence, real-source replay, labeled fixtures, expected rejection, reference reveal, hypothetical arithmetic, reset and export. It records screenshots and layout/errors under `runs/verification/`. No source-system writes are involved.
