# ADF review workbench

This separate local prototype reduces repeated searching and makes missing change requirements visible. Three agents built the evidence packets, intake checks, and bottleneck/timing audit. The original ADF Sentinel campaign and supplied review project are preserved.

## Open the results

From `/rhome/yanzhu/ML_ADF`:

```bash
python adf-review-workbench/serve.py --port 8877
```

Open <http://127.0.0.1:8877>. For a remote workspace, forward port 8877. The server listens only on loopback. Source systems are not contacted. Draft checks happen in memory; downloads save a copy through the browser. There is no execution, approval, installation, or release endpoint.

`workbench.html` also opens as a standalone offline report. Evidence navigation and downloads work offline; checking edited drafts requires the local app above.

## Results

- Four real packets: IRS-65265, IRS-29057, IRS-57322, and IRS-66772.
- All 20 comments present in these cached issues are shown; source completeness metadata is retained separately.
- 39 of 65 proposed action excerpts and 20 of 68 artifact references are shown with explicit display limits.
- Seven pending draft records cover file replacement, parameter/metadata, dependency, shared profiles, investigation, verification, and retain/defer/block review.
- Every real draft currently has missing information. None is treated as approved or executable.
- All 4,922 weak-label excerpts were audited. 197 were flagged by narrow quality rules: 182 possible threshold/hold matches, 13 Jira fix-version administrative comments, and two generic clarification comments. These are review candidates, not confirmed corrections.
- A blank timing sheet and matched-comparison calculator keep active work, waiting, and setup separate. Human time savings remain unknown.

Start with `results/build-summary.json`, `results/bottlenecks.md`, or `results/packets/index.json`. `results/preservation.json` verifies the protected source, feature, model, campaign and export files plus all 320 supplied review files. This is a selected integrity check, not an assertion that every cached raw file was rehashed.

## Short demonstration

1. Open **Evidence packets** and select IRS-29057. Expand dated comments to see the earlier software-upgrade verification request and the later ADF revision instruction separately.
2. Open **Change checklist** and select the hotspot-file draft. Its missing revision, hashes, destination, scope and acceptance criteria stay visible.
3. Select the shared-profile draft. Each profile has its own target and values; the workbench does not assume identical values.
4. Open **Team results** to inspect label-quality review candidates.
5. Open **Timing pilot** and download the blank observation sheet before comparing real manual and assisted work.

## Rebuild and verify

The add-on uses Python's standard library. No dependency installation or model training is needed.

```bash
python adf-review-workbench/build_workbench.py
python -m unittest discover -s adf-review-workbench/tests -v
```

`build_workbench.py` reads the preserved snapshot and writes only this add-on's results. Do not capture a new preservation baseline to conceal a mismatch. No `adf-sentinel` ingest, training, freeze, export, or benchmark commands are needed.

Optional browser verification uses the host's existing Playwright and Chrome:

```bash
python adf-review-workbench/browser_check.py
```

The browser check uses local data and synthetic draft edits. Its test values are discarded; they are not proposed scientific settings or real approvals.

## Component guides

- `EVIDENCE.md`: provenance, chronology, display bounds, and credential redaction.
- `INTAKE.md`: change schema, missing-field checks, and approval boundaries.
- `PILOT.md`: matched timing observations and interpretation.

This prototype assembles review material and checks its completeness. Determining the correct fix, approving it, genuine ADF assembly, and scientific testing still need their respective owners and tools.
