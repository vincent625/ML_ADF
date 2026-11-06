# ADF Sentinel: exact 10-minute demonstration

## Before presenting

```bash
cd /rhome/yanzhu/ML_ADF/irs-65265-review
python app.py --reset
```

Open <http://127.0.0.1:8765>, preferably at 1366x900 or larger. For Remote SSH,
forward port 8765 first. There are no artificial waits, credentials, cloud calls,
or package installs. A rehearsal can use **Reset synthetic sandbox** in the
footer. All eight scenarios are copied, synthetic counterfactuals.

Do not spend spare time implying a physical run or genuine ADF build occurred.
Results arrive immediately because this is a local validator, not an instrument.

## 00:00-00:45 -- planned schedule and source gaps

**Clicks:** Open **01 Sources** (initial chapter).

**Say:** "The real plan allocated two elapsed weeks for bundling, September
16-29, and one for sanity, September 30-October 6. Mol Bio runs and analysis
follow separately. This is not three weeks of measured labor or demonstrated
AI savings."

Point to **5 / 11 comments**, attachment **67 vs 65**, ten captured metadata
records, saved Xray mapping gap and **BLOCKED** real assembly.

**Expected:** Sources list three pinned PRs with inventories 47 / 46 / 10.
Ten source observations remain separate from current fixture passes. The
original HTML/resource uploads and released ZIPs are missing from this package.

## 00:45-02:00 -- extract state, not just numbers

**Clicks:** **02 Requirements** -> **R05 Alternative TVC binary**. Then
**R09 Hotspot selection**. Optionally select **R06**, **R15**, **R16**.

**Say:** "These are 20 candidate families, not 20 approved active requirements.
The TVC replacement was cancelled. Tmap was inherited from v0.0.2. Crossed-out
piercing and read-limit text stays historical. The dated hotspot decision
explicitly selects Motorhead for v0.0.3, deferring Manticore-specific work."

Show the exact captured excerpt, candidate interpretation and stored AI replay
E02/E03. Expand the interpretation library for test proposals and uncertainty.

**Expected:** R05 is cancelled; no TVC replacement patch or invented test pass.
R09 selects `Oncomine_Focus_v2.20260625.hotspots.bed`. AI is visibly replay,
not a live model call or newly trained model.

## 02:00-03:00 -- both variants and three sources

**Clicks:** **03 Components**. Expand **Computed dependency edges** briefly.
If necessary return to **01 Sources** to show the full pins, then back.

**Say:** "DNA and DNA+Fusion share CNV/MSI dependencies, but RNA parameters
belong only to Fusion. Every assertion has a requirement, variant and component.
These sources are pinned; inventories alone do not prove full-content review or
what was installed."

**Expected:** 40 DNA and 44 Fusion cases, totaling 84. The source review
inventories are 47/46/10, not test counts.

## 03:00-04:00 -- final content, not diff size

**Clicks:** In **Counterfactual fixture**, choose **One shared script stale**.
Remain in **03 Components**.

**Say:** "The captured finalize-script diff sizes are 649 versus 11; the plot
script is 262 versus 51. Yet monitored final Git blobs match. Here I deliberately
made one Fusion fixture script stale. We compare actual final fixture bytes."

**Expected:** Captured source shows matching blob identity. Synthetic shared
comparison shows one drift, while the other shared script matches. This is not
a claim that a released ZIP contained a stale script.

## 04:00-05:30 -- exact local checks

**Clicks:** Choose **Wrong primer in one variant** -> **04 Run & triage** ->
**Run local checks**. Keep **Failures & stale evidence** selected.

**Say:** "The DNA pool 2 in this Fusion fixture is wrong. The validator reads the
manifest; it never reads scenario names as an answer key. RNA values remain
unchanged. The repair scenario independently checks the actor and AnalysisArgs."

**Expected:** 83 current passes, 1 failure, `fusion:dna_pool_2`.
Expected `100200226`; observed `100093901`. Actual local run ID and measured
milliseconds are displayed. The source checks remain ten source observations.

**Optional instead:** Choose **Repair flag in one argument source** and run.
Only `fusion:AnalysisArgs.ini` fails; `fusion:TmapExecutionActor.ini` passes.
Return to the primer scenario before the next segment if using the primary flow.

## 05:30-07:30 -- evidence, review, patch, retest, QC

**Clicks:** Inspect `fusion:dna_pool_2` if not already selected ->
**Preview minimal local patch**. Read the one-value diff, enter reviewer
`Demo engineer`, tick the exact-patch approval checkbox ->
**Approve & apply local patch** -> **Run local checks**.

**Say:** "This observed fixture mismatch is demonstrated. It does not establish
a production root cause. Nothing changes until a reviewer approves the exact
patch. The prior result becomes stale; review is not a new pass. We must retest."

**Expected:** Before rerun: 83 passes, 1 stale result. After rerun: 84 current
fixture passes, no failure, named review, exact diff and a new run ID.

**Clicks:** Set **Show cases** to **QC controls**. Inspect `dna:suppressed`,
then `dna:msi-qcfail`.

**Say:** "A missing CNV plot under failed CNV QC can be correct suppression.
A pipeline can finish while MSI/sample QC remains failed. A passing local
assertion does not turn scientific QC green. The MAPD 0.5 boundary remains
unspecified."

**Expected:** Suppression assertion passes with `cnv_qc: fail` and no plot.
MSI assertion passes with pipeline completed **and** `MSI-QCFail` /
sample QC failure. For contrast, **Unexpected missing plot** fails under
explicitly passing CNV QC; repairing that inventory is only synthetic replay.

## 07:30-08:45 -- requirement revision invalidates evidence

**Clicks:** Choose **Prior pass after a parameter change** ->
**05 Change impact**. Enter `Demo engineer`, tick synthetic-revision approval ->
**Approve sandbox parameter change** -> **Inspect evidence & rerun**.
Set **Show cases** to **Failures & stale evidence** if needed.

**Say:** "This is a proposed sandbox change, 0.001 to 0.002, not a new real
product requirement. R18 contains both annotator and Fusion threshold decisions,
so three mapped assertions become stale. Eighty-one unrelated passes remain
valid. We keep historical evidence instead of overwriting it."

**Expected:** 81 current passes, 3 stale. Click **Run local checks**:
83 pass, 1 fail (`fusion:fusion-threshold`). The file was not silently updated.
If time permits, preview, review, apply and rerun the threshold correction:
84 current fixture passes. No other scenario or original requirement is changed.

## 08:45-10:00 -- export the draft, not a release approval

**Clicks:** **06 Evidence export** -> **Export draft evidence JSON**.
Optionally click **Build synthetic toy ZIP**.

**Say:** "The export identifies the exact run, expected and observed values,
source pins, requirement revisions, file fingerprints, review decisions and
remaining gaps. Actual ADF assembly and installation remain blocked.
The toy ZIP is non-installable. Milliseconds are local validation timings,
not production cycle time. A real pilot must measure labor, review overhead,
elapsed time and escaped defects."

Point to the ten source observations, one-release AI-candidate limitation and
future data design. End at 10:00 without artificial waits or manufactured
all-green release claims.

**Expected:** JSON latest run ID matches the UI. Stale results remain stale if
not retested; real-artifact gaps remain present regardless of fixture passes.

## Reset

Use **Reset synthetic sandbox** and confirm. Or stop with Ctrl+C, then:

```bash
python app.py --reset
```

All known fixture mutations and sandbox revisions return to the initial state.
The default **Wrong primer in one variant** again has 83 passes and 1 failure.
Historical exported drafts retain their own run IDs and dates.

## Fallback replay / failure handling

- **No GitHub or model access:** Already the normal mode. Captured sources and
  stored interpretations support the entire demo offline. Explain the labels.
- **Integrated browser cannot reach a remote localhost:** Forward port 8765 in
  VS Code Remote SSH, or browse on the server's desktop. Never bind this
  unauthenticated demo to a public interface.
- **Browser unavailable:** Run `python sentinel.py generate`,
  `python sentinel.py run --scenario wrong-primer`, and
  `python sentinel.py export --scenario wrong-primer`. Show the fixture diff and
  the corresponding generated JSON; this is a CLI fallback, not a fabricated
  visual verification.
- **Bad/stale patch proposal:** Cancel it. Inspect the current file and request
  a new preview. The pre-review hash guard intentionally rejects changed bytes.
- **Parameter button already used:** Reset or select a fresh scenario.
- **Unexpected result:** Keep it visible, export it, and do not claim success.
  Deterministic tests are `python -m unittest discover -s tests -v`.

The captured historical run links are narrative replay only. They must never be
substituted for a newly measured pipeline, released-byte or physical-run result.
