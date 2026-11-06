# Integration findings and practical limits

## Upstream implementation

The pinned repository implements a small deterministic requirements traceability slice. It extracts numbered Markdown items/headings, assigns sequential requirement IDs, and matches manifest artifact names by case-insensitive substring. It does not verify artifact bytes, checksum fields, ownership or release targets. Test/dependency mappings begin empty. The CLI assumes its input has already been sanitized.

The upstream tree had no `tests/` directory despite its README test command. This handoff adds four focused requirements checks, including a relocated CLI example, without changing the upstream implementation. The substring behavior can match `Fixture.bed` inside `Fixture.bed.backup`; do not treat the resulting link as validated artifact identity.

## Relationship to the local work

The historical Sentinel study adds source collection, provenance, proposed labels, exploratory fits and narrow file-operation checks. The review workbench makes selected historical evidence and missing change details accessible. The original evidence lab demonstrates synthetic review/fix/retest and stale-evidence behavior.

These schemas are not automatically connected. A requirements matrix cannot establish exact file paths, approved old/new values, immutable source versions, complete variant coverage, test acceptance, or a current approval by itself. The top-level diagram marks the remaining handoffs.

## Corpus scope

4,922 denotes excerpts, not tickets. There are 550 distinct source issue keys for those excerpts, 582 release-listed issues, and 2,460 collected issues. All excerpts remain unreviewed. Software, verification, administrative and investigation text can remain in release-listed issues. A strict ADF-only development dataset is still missing.

The 197 narrow quality flags are candidates for review. No corrected labels or adjusted category totals were invented. Investigation's 51.1% is a share of excerpts, not hours or proven manual work.

## Dates and effort

Upstream `docs/upstream/04-current-status.md` gives September 7–October 27, 2026 and calls the total 37 elapsed days. Calendar subtraction gives 50 elapsed days, or 51 counting both endpoints. The source does not explain its 37-day figure. The planned bundling/sanity periods and roadmap targets do not establish engineer-hours or time saved.

## Publication and relocation

The upload copy excludes raw source caches, complete historical text datasets, fitted model binaries and the old evidence ZIP. Curated report text is sanitized; source code is preserved. See `PACKAGE_SCOPE.md` and the copy manifest for exact handling. Original private inputs and hashes remain local.

Archived receipts may contain original-machine paths. They document prior executions; recommended commands use the current repository root. The workbench viewer and draft checks work with packaged results. Rebuilding its historical packets or rerunning the full campaign needs excluded authorized data. The original workbench preservation baseline describes the full private campaign and must not be recaptured to hide missing inputs.

Browser scripts require optional Playwright/Chrome; some original scripts assume `/usr/bin/google-chrome` and fixed loopback ports. Standard-library tests and the recommended app do not need a browser installation.
