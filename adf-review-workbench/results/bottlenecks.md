# Bottlenecks and time-reduction pilot

**Hypothesis:** investigation and clarifying exact release-specific changes consume the most engineer time. No human-time observations establish this ranking yet.

The source contains **4,922 unreviewed proposed excerpts** and **0 reviewed labels**. Counts are not hours or independent completed tasks.

| Proposed category | Excerpts | Share of excerpts |
|---|---:|---:|
| Investigation / code | 2,513 | 51.1% |
| Verification | 868 | 17.6% |
| Parameter / metadata | 705 | 14.3% |
| Add / replace file | 414 | 8.4% |
| Defer / retain / block | 265 | 5.4% |
| Dependency version | 144 | 2.9% |
| Shared variant change | 13 | 0.3% |

## Recommended work

1. **Prepare one evidence packet per change.** Reduce repeated searching with dated source excerpts, prior implementation links, release associations and explicit unanswered questions. Engineer: Confirm release applicability and resolve changing or conflicting instructions.

2. **Require a complete change record.** Capture exact target, approved old/new value or pinned artifact, affected variants and acceptance checks before handoff. Engineer: Approve intended values, scope and acceptance criteria; historical status does not approve a new execution.

3. **Run routine checks immediately.** After approval, use registered operations and check expected values, hashes, paths and affected variants; expose a reviewable diff. Engineer: Review changes and separate structural checks from scientific/physical validation. Current real executor coverage is narrow.

4. **Prepare reproducible debugging evidence.** Collect last-known-working versus candidate differences and approved regression results so investigation begins with a reproducible case. Engineer: Determine and validate the fix; source collection alone cannot establish root cause.

## Label quality review

**197 excerpts** match narrow patterns worth review. These are candidates, not confirmed errors, relabeled examples, or proof that all remaining labels are correct.

- `generic_clarification_may_not_be_implementation_action`: 2 candidate excerpts.
- `jira_fix_version_may_be_administrative`: 13 candidate excerpts.
- `threshold_without_explicit_hold_word`: 182 candidate excerpts.

Examples (source statements remain historical):

- `action_5075e2d3d7e6402758f6` / [IRS-11380](https://lsg-thermofisher.atlassian.net/browse/IRS-11380?focusedCommentId=1465349): Do you want to add anything else? — `generic_clarification_may_not_be_implementation_action`.
- `action_d3f8ca036b5d427fc350` / [IRS-11380](https://lsg-thermofisher.atlassian.net/browse/IRS-11380?focusedCommentId=1465360): Please clarify if the below is correct, or if changes are needed. — `generic_clarification_may_not_be_implementation_action`.
- `action_70eee5f8eee1666e6f08` / [IRS-14098](https://lsg-thermofisher.atlassian.net/browse/IRS-14098?focusedCommentId=1591292): Would you please update the fix version and assign back to me? — `jira_fix_version_may_be_administrative`.
- `action_00f30e3617857ebd7f60` / [IRS-14098](https://lsg-thermofisher.atlassian.net/browse/IRS-14098?focusedCommentId=1591293): Updated the fix version to 6.2.0. — `jira_fix_version_may_be_administrative`.
- `action_0616b0bccb0b8d1870b0` / [IRS-14628](https://lsg-thermofisher.atlassian.net/browse/IRS-14628?focusedCommentId=1588614): Hi [person] I just noticed that the fix version is "6.3.11" but this ticket is for v6.2 BRCA ADFs update. — `jira_fix_version_may_be_administrative`.
- `action_a73045af921f1741b9c3` / [IRS-15588](https://lsg-thermofisher.atlassian.net/browse/IRS-15588?focusedCommentId=1584445): Checked with [person] to confirm that the change will be ready for test in today's build, updated the fix version. — `jira_fix_version_may_be_administrative`.
- `action_5632f6c8adbbc03d31bb` / [IRS-14790](https://lsg-thermofisher.atlassian.net/browse/IRS-14790): Currently user can set QC thresholds and parameter values independently which is causing confusion in case QC thresholds and parameter values are not in sync. — `threshold_without_explicit_hold_word`.
- `action_f2b42a0d4ce5f794f588` / [IRS-14790](https://lsg-thermofisher.atlassian.net/browse/IRS-14790): Software needs to restrict user from setting different values for parameters and QC thresholds. — `threshold_without_explicit_hold_word`.
- `action_d98e09039a17b37f8db7` / [IRS-14790](https://lsg-thermofisher.atlassian.net/browse/IRS-14790): The parameter value set on parameters tab ( default or user edited ) should be set as a QC threshold for corresposning Sample QC metric. — `threshold_without_explicit_hold_word`.
- `action_b1fa1e5d047a950c01dd` / [IRS-14790](https://lsg-thermofisher.atlassian.net/browse/IRS-14790): User should be able to see the updated threshold on QC tab and shouldn’t be allowed to edit the threshold. — `threshold_without_explicit_hold_word`.

## Timing result

Status: `unknown_no_observations`. Matched pairs: 0. **Hours saved remain unknown** until complete comparable observations are recorded.

Record active effort by phase, waiting separately, and setup separately. Compare the same action, scope and predeclared completion milestone. Missing duration fields remain unknown and invalidate that pair. See `PILOT.md`.

## Source integrity

- `/rhome/yanzhu/ML_ADF/adf-sentinel/data/labels/weak_actions.jsonl` — SHA-256 `3322319863e7e86708ca037a8daa2ad45c81098fb431216251ca8ce152f8029b`.
- `/rhome/yanzhu/ML_ADF/adf-sentinel/runs/effort/report.json` — SHA-256 `bd6148e9082be08582ad6afd30dc7c0c9cf05c08adb918ec26b72c10b0b75076`.
