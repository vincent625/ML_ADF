# ADF Sentinel: IRS-65265 evidence lab

A runnable, offline-first, 10-minute hackathon prototype. It checks actual local
synthetic fixture bytes, replays supplied interpretations, records reviewed
corrections, and invalidates evidence when its scoped dependencies change.
**It is not an ADF installer or a scientific pipeline.**

## Start / reset

Python 3.7+ is the only runtime dependency; no packages, credentials, build step,
or external services are required. Python 3.11+ is recommended for ongoing
security updates, but the existing Python 3.7 virtual environment can run the
demo without changing or reinstalling that environment.

```bash
cd /rhome/yanzhu/ML_ADF/irs-65265-review
python app.py --reset
```

Open <http://127.0.0.1:8765>. Stop with Ctrl+C. A subsequent `python app.py`
retains sandbox runs and reviews. Choose another port with `--port 8766`.
For VS Code Remote SSH, forward the chosen localhost port in the Ports panel.

Reset an already-running app with **Reset synthetic sandbox**, or stop it and
repeat `python app.py --reset`. Reset overwrites only known generated fixtures,
contracts, logs and sandbox audit state. Original supplied evidence is untouched.
Exported draft snapshots remain independently dated historical documents.
Do not reset from a second process while the app is running.

See [DEMO_10_MIN.md](./DEMO_10_MIN.md) for exact clicks, narration and fallbacks.

## What is delivered

- [app.py](./app.py): loopback-only standard-library HTTP server; no telemetry,
  credentials, external fonts, CDN dependencies, or live-model calls.
- [sentinel.py](./sentinel.py): reproducible generator, deterministic validators,
  scoped fingerprints, exact patch proposals, named review, retest, exports.
- [static/](./static/): projector-readable source, requirement, component,
  execution/triage, impact and export views; responsive plain HTML/CSS/JavaScript.
- [demo_data/](./demo_data/): generated fixture bytes for two variants across a
  passing control and eight counterfactual scenarios, separate contracts,
  source-check observations, recorded runs and correlated fixture events.
- [tests/test_sentinel.py](./tests/test_sentinel.py): focused release-loop tests.
- [tests/test_http.py](./tests/test_http.py): live ephemeral HTTP API checks.
- [tests/browser_smoke.py](./tests/browser_smoke.py): optional end-to-end browser
  verification, including all six chapters at laptop and narrow widths.
- [future-data.schema.json](./future-data.schema.json): future requirement
  revisions, executions, and failure/fix/retest episodes; not a training dataset.
- [live-source-verification.json](./live-source-verification.json): read-only
  metadata verification and the three selected pinned files read during this build.

### Reproduce without the UI

```bash
python sentinel.py generate
python sentinel.py source-checks
python sentinel.py run --scenario wrong-primer
python sentinel.py export --scenario wrong-primer
python -W error::ResourceWarning -m unittest discover -s tests -v
node --check static/app.js  # optional JavaScript syntax check; Node is not a runtime dependency
```

Synthetic cases deliberately fail; `run` reports these findings as JSON, not as
a claim of a passing release. Use `--data /some/dedicated/path` for an independent
sandbox. The generator does not delete directories recursively.

## Evidence and truth boundaries

The supplied originals are preserved. Read [REVIEW.md](./REVIEW.md) first.
The original uploaded Jira HTML, screenshots, browser-resource ZIP and actual
released ADF archives are **not present** in this review package. The adjacent
review ZIP just contains copies of these review files. Consequently:

- Genuine candidate assembly, installation and instrument execution are blocked.
- Binary baseline MD5 validation against the ticket remains blocked.
- Fixture assets are explicit synthetic placeholders, never reconstructed
  central-config files. Their SHA-256/MD5 values differ from the declared ticket
  strings. Declaration checks and actual synthetic-byte checks are separate.
- The toy ZIP is labeled **SYNTHETIC / NON-INSTALLABLE**, not a genuine ADF.

The ten supplied checks execute in a temporary copy using the original
[check_source_evidence.py](./check_source_evidence.py); original
[source-check-results.json](./source-check-results.json) is not rewritten.
They are ten captured-source observations, not installed-ADF tests.
The live authorized GitHub metadata matched pinned heads and inventories:
DNA 47, DNA+Fusion 46, report templates 10. Only selected file contents were read.
No upstream repository was modified.

### Records stay separate

| Record | Meaning |
|---|---|
| 20 requirement families | Engineer-review candidates, including inactive/inherited/history states |
| 10 stored AI interpretations | Credential-free replay of supplied candidates; no newly trained or live model |
| 10 source checks | Actual local execution against captured source evidence |
| 84 proposed/local cases | 78 actual local configuration/byte assertions and 6 assertions over simulated QC output |
| 756 correlated fixture events | 84 assertions x 9 fixture scenarios, generated from today's local runs, not historical instrument logs |
| 16 historical run links | Archived narrative references with source creation/update dates; not imported execution passes |
| Local runs / reviews | New run IDs, measured local timings, dependency hashes, exact approved patches |

The runner never consults
[scenario-expectations.json](./demo_data/scenario-expectations.json). That
separate generator oracle is only for verifying seeded mutations.
Expected values are read from explicit sandbox contracts; observations are
read from fixture bytes, independently of scenario names.

### Eight counterfactuals

1. Wrong DNA kit in DNA.
2. Wrong DNA pool 2 in DNA+Fusion, retaining RNA values.
3. Wrong referenced CNV baseline Git revision.
4. Repair option retained only in DNA+Fusion `AnalysisArgs` while the actor is correct.
5. Stale Fusion CNV plot-script bytes.
6. Wrong DNA report dependency version.
7. Unexpected missing CNV plot under explicitly passing CNV QC.
8. Prior pass becomes stale after approval of a synthetic parameter revision.

The eighth is an interactive sequence, not a seeded false failure: initially
84 assertions pass; approval invalidates 3 R18 assertions and retains 81
unrelated passes. The subsequent rerun finds one Fusion threshold mismatch.
Reviewing its local patch and rerunning returns 84 current fixture passes.
This `0.002` sandbox revision never changes the real R18 `0.001` requirement.

CNV suppression under failed QC is a passing conditional control. A completed
pipeline with MSI-QCFail retains the scientific/sample failure in its observation.
No behavior at MAPD = 0.5 is invented. In the missing-plot scenario, restoring a
synthetic output inventory is not represented as fixing an actual renderer.

### Fingerprints and review

Each test records its requirement revision, expected contract, scoped input,
source revision and environment. File SHA-256s are retained for audit, but a
kit change does not invalidate unrelated asset checks simply because they share
a manifest. QC fingerprints cover the relevant case, not unrelated output cases.
R18 contains both annotator and Fusion threshold decisions, so its family
revision conservatively invalidates all three mapped assertions.

Patch application requires a named review and the exact pre-review file hash.
Changed files require a fresh preview. Review does not silently retest: prior
evidence becomes stale; the user must run local checks again. Proposed patches,
approval diffs, original observations and later retests remain separate records.

## AI, coverage and future data

No approved live integration is configured. The app explicitly replays
[training-examples.jsonl](./training-examples.jsonl), with retrieved supporting
excerpts, proposed state/impact/test interpretations and unconfirmed hypotheses.
It does not pretend to have called a model. All pass/fail and hash calculations
are deterministic. No root cause is confirmed from a comment saying CNV and MSI
were updated together.

Unmapped R04 full actor refresh, inherited Tmap/OVAT provenance, VNS
ruleset-to-package mapping, and real artifact/runtime checks remain gaps.
Different VNS version namespaces are not automatically called incompatible.
The saved Xray state is a mapping gap, not proof no testing happened.

For future evaluation, group releases and related DNA/Fusion cases together,
split by release and time, preserve evidence-availability timestamps, and put
future fixes/resolution comments in label-only fields. The ten examples from
one release cannot support generalization claims.

## Verification

The automated suite verifies all eight counterfactual sequences, exact reviewed
fixes and retests, byte/declaration separation, both alignment locations, QC
controls, no invented MAPD boundary, stale-pass invalidation, preservation of
unrelated results, source-count reconciliation, unchanged original evidence,
export/run equality and toy-bundle byte equality.

Live HTTP exercise also verifies patch/review/rerun, export identity and selective
invalidation. See [VERIFICATION.json](./VERIFICATION.json) for final recorded
checks and browser-layout verification details.

The optional browser check requires Playwright and Chromium, not used by the app:
run this tooling in a modern Python environment, not the legacy Python 3.7 venv.

```bash
# With the app running in a disposable/resettable sandbox:
python -m pip install playwright
python -m playwright install chromium
python tests/browser_smoke.py
```

This check resets the sandbox and exercises real clicks, review dialogs,
conditional QC, stale-evidence handling and evidence downloads. It records
screenshots and browser results in [demo_data/verification/](./demo_data/verification/).

Measured milliseconds describe this local validator only. The real schedule is
planned elapsed time: Bundle Sep 16-29, 2026 (2w), Sanity Sep 30-Oct 6 (1w),
then separate Mol Bio runs and analysis. No production labor or AI savings have
been measured.
