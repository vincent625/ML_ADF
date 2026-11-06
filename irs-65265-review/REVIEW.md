# IRS-65265: evidence for ADF automation and ML

The strongest starting point is a source-grounded release assistant: interpret requirements and decisions, pin the approved components, assemble the two ADF variants, run deterministic checks, and maintain traceable test evidence. The supplied release is a useful development and evaluation case. It does not, by itself, establish enough independent labeled examples to train and evaluate a reliable new failure-prediction or root-cause model.

## Evidence actually reviewed

- Uploaded main HTML: the Manticore ADF v0.0.3 description, current visible fields, five loaded comments, attachment metadata, and embedded Jira response data. The original HTML SHA-256 is recorded in source-coverage.json.
- Uploaded browser-resource ZIP: 101 non-Mac-metadata files, including cached page assets and screenshots. Extracted 33 named image references; 32 have readable screenshot dimensions and one is a small placeholder. OCR was run on the 32 readable images. The schedule, a run-setup screenshot, and a failed-QC result screenshot were also inspected visually. OCR is discovery evidence, not ground truth for scientific values.
- Saved Xray frame: explicitly displays UNCOVERED and no tests associated with this issue. This establishes the saved panel's state, not that no testing occurred elsewhere.
- DNA release PR #3: changed-file inventory of 47 entries and selected patches, plus a pinned parameter-validation source excerpt.
- DNA+Fusion release PR #6: changed-file inventory of 46 entries and selected patches, plus the pinned RNACountsActor.ini content.
- Report-template PR #62: inventory of 10 added files and its source diff. A pinned exon-CNV visualization-template excerpt from the DNA ADF repository was also reviewed.

Source links:

- https://github.com/thermofisher/csd-adf-gx-manticore-v2-dna-70/pull/3
- https://github.com/thermofisher/csd-adf-gx-manticore-v2-dnafus-70/pull/6
- https://github.com/thermofisher/csd-gx-rb-template-scripts/pull/62

The review is selective source analysis. Listing a changed file does not mean its full contents were inspected. Binary MSI, H5, DEB, and released ADF ZIP contents were not validated.

## The actual bottleneck is documented

The saved schedule shows Bundle, September 16-29, 2026, labeled 2w, followed by Sanity Testing, September 30-October 6, labeled 1w. Later Mol Bio runs and data analysis are separate schedule phases. These are planned elapsed durations, not a measured three weeks of continuous engineering labor.

The comments show the rework mechanism: an earlier bundle was removed, parameter changes required rebundling, and later candidates were exercised through N2R, B2R, assay-copy, MSI-High, and MSI-QCFail cases. An earlier comment was edited on October 1; a training chronology cannot assume its current text was present on its September 24 creation date.

## Concrete automation opportunities

| Evidence from this release | Automation | Appropriate mechanism |
|---|---|---|
| DNA panel kit A40014056 and primer pools 100200225/100200226 replace crossed-out placeholders | Check both ADF variants and rendered run setup while preserving valid RNA values | Structured contract extraction, followed by exact checks |
| SVB, target BED, hotspot, CNV baseline, CNV JSON, and MSI baseline have named files and ticket MD5 values | Pin inputs; check references and hash actual packaged bytes | Manifest builder and deterministic integrity checks |
| Repair flag must be removed from actor arguments and AnalysisArgs alignment arguments | Check both sources in both variants, then inspect effective runtime commands | INI/JSON/argument parsers |
| CNV code and MSI assets must appear in DNA-only and DNA+Fusion | Check approved shared-component parity; retain intentional variant differences | Content-addressed comparison and scoped tests |
| OVAT, VNS, and report packages are dependencies | Resolve and pin the specific artifact/version mapping | Explicit dependency contracts; ruleset and package version namespaces remain distinct |
| Rebundling follows parameter updates | Detect changed dependencies and invalidate only the affected previous evidence | Bundle/requirement/test/environment fingerprints |
| B2R CNV plotting and MSI-QCFail failures are reported resolved after updates | Build failure episodes linking observations, commits, fixes, and retests | Evidence retrieval and AI-assisted triage; confirmed labels need logs |
| CNV plots can be suppressed when CNV QC fails | Distinguish an expected missing output from an unexpected failure | QC-aware assertions using the accepted decision |
| Comments contain test evidence but the saved Xray panel is uncovered | Surface unmapped requirements and link real executions to them | Traceability graph and coverage checker |

Ten narrow checks were executed against the captured PR source evidence; all ten observed the expected facts. They cover kit/primer literals, repair-flag removal at both settings locations, declared hotspot hashes, the fusion threshold, and matching Git blob identities for five monitored shared components. See source-check-results.json and check_source_evidence.py. This is not an executed Genexus sanity suite or proof that the released ZIPs contain those source revisions.

## Details the AI must interpret correctly

1. Preserve requirement states. The alternative TVC proposal is crossed out and described as unnecessary. The alternative Tmap is described as already bundled in v0.0.2. Piercing workflow and minimum-read/sample-limit sections are crossed out; retain them as history and confirm the effective release contract before treating their values as current requirements.
2. Follow explicit release decisions. The hotspot discussion selects the Motorhead file for v0.0.3 and defers Manticore-specific additions to pre-V&V. Selecting a file solely because its name sounds newer or more assay-specific would ignore that decision.
3. Respect QC context. An earlier comment reports missing plots under MAPD QC failure; a later comment records agreement that suppression is acceptable when CNV QC fails. Missing plots alone cannot be the failure label. The exact behavior at MAPD = 0.5 is not fully established by those comments.
4. A valid MSI-QCFail test can finish successfully while reporting MSI QC failure. Pipeline completion and scientific/sample-QC status are different assertions.
5. Do not confuse diff size with variant divergence. DNA and Fusion CNV patches have very different change counts, but their final Git blob IDs match for monitored shared scripts. Their starting baselines differ.
6. Do not infer a conflict from VNS ruleset 2.2.2 and package version 1.22.0 without checking the mapping between those version namespaces.
7. Derive a reviewed acceptance contract. The saved Acceptance Criteria field is empty; useful requirements and decisions currently sit in the description, comments, and linked implementation.

## Candidate ML datasets

| Task | X: inputs available at decision time | Y: labels to curate | What is available now |
|---|---|---|---|
| Requirement interpretation | Description with strike-through, dated comments, scope and source revisions | Active/inherited/cancelled/deferred state; approved parameter/asset contract | 20 candidate requirement families extracted; engineer review required |
| Change-to-test mapping | Reviewed contract, changed components, dependency graph, workflow variant | Relevant approved test IDs and required case types | Candidate mappings can be drafted; full tests/executions are missing |
| Failure triage | Failed assertion, logs, QC state, component versions, prior cases known at that time | Confirmed cause, corrective commit, successful retest | Narrative episodes and screenshots; insufficient confirmed causal labels |
| Expected-output classification | Workflow, CNV/MSI QC state, applicable policy and output inventory | Expected suppression, unexpected missing output, or incomplete evidence | A useful policy example exists; raw case results still needed |

training-examples.jsonl contains ten candidate records linked to this real release. Their labels are explicitly marked for engineer review. Several are proposed mappings or weak narrative labels, not confirmed root causes. They are not ten independent releases and are not a trained model.

For a first hackathon prototype, use retrieval over the supplied evidence with a pretrained model to interpret and explain. Use deterministic code for hashes, parameter assertions, package assembly, and pass/fail. As more historical releases are collected, curate one record per requirement revision, test execution, or failure episode. Preserve source dates, changed components, bundle hashes, fixing commits, and retests.

Evaluate future ML with release-level and time-based holdouts. Related DNA/Fusion cases, copies of the same screenshot, linked tickets, and later resolution comments must not leak across train/test boundaries. For root-cause prediction, a future fixing commit or resolution comment belongs in the target/label evidence, not in the inputs to a historical prediction.

## What remains missing

The snapshot has five loaded comments, while its embedded count is eleven and hasNextPage is true. The visible attachment badge says 67, while embedded issue metadata says 65; ten attachment metadata records were captured. A fresh full export is needed to reconcile counts. The page-resource ZIP is not the attachment download collection.

The 60 distinct business URLs comprise 19 Jira issue URLs (the main issue plus 18 related issues), 23 GitHub URLs, two JFrog URLs, and 16 Genexus result URLs. linked-sources.csv records each address and source location. Some GitHub references were resolved through the three release PRs; the central config repository and one config file returned 404. The OVAT JFrog page and representative internal Genexus result URL could not be retrieved. Linked Jira ticket contents are not included in the saved main page.

Highest-priority additional uploads:

1. Genexus-Oncomine-Focus-v2-GX7-w1.0.0-DNA-SW_7.0-v0.0.3.zip
2. Genexus-Oncomine-Focus-v2-GX7-w1.0.0-DNAandFusions-SW_7.0-v0.0.3.zip
3. testing_screenshot_for_v03.zip
4. An all-fields CSV with all eleven comments and the relevant linked tickets, especially MSI QC, report behavior, and parameter-change tickets.

For execution-based ML labels, also obtain exported run logs, output inventories, QC metrics, expected results, and failure/retest records. Screenshots can help locate evidence but cannot replace all of those structured records.

## Hackathon demonstration

Show one connected release: the real two-week/one-week schedule; extraction of active and superseded requirements; the two ADF variants and report dependency; a deliberately introduced config error caught by exact checks; context-aware handling of failed CNV/MSI QC; a reviewed local fix and rerun; a parameter change invalidating affected evidence; and an export that keeps unresolved evidence visible.

Use counterfactual defects only in copied fixtures and label them synthetic. Historical screenshots and narrative outcomes must be labeled replay. Never present a toy runtime as measured production cycle-time reduction. The source-grounded Codex build prompt is included as CODEX_PROMPT.txt.
