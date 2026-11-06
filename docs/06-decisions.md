# Integration decisions

## November 6, 2026: source-preserving composition

- Preserve the requirements component’s Python source and supporting documentation under `docs/upstream/`.
- Keep the three local components as sibling directories so their file-relative runtime roots remain usable. This is repository composition, not an automatic end-to-end orchestrator.
- Add a combined README, exact-unit figures, sanitized numbered examples and new handoff checks. Preserve original component receipts with their execution dates and scope.
- Exclude full raw/text/model data from the upload copy because historical source material contains credentials and trained vocabulary may retain that text. Keep the original private campaign and export immutable locally.
- Use the workbench as the first quick start, with the synthetic evidence lab as the second. Neither requires a model, credentials or scientific settings.
- Preserve null values for unavailable accuracy and time savings. Category counts and local runtimes cannot substitute for those measurements.
- Do not infer an open-source license. Retain source identity and provenance in `NOTICE.md` and the copy manifest.

The original release-specific part-number decision remains in `docs/upstream/06-decisions.md`. It is historical context, not approval to use temporary values in a new release.
