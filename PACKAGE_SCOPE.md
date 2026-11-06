# Curated upload scope

This repository copy combines the pinned upstream requirements extractor, ADF Sentinel source and recorded summaries, the preserved synthetic IRS-65265 review demo, and the separate review workbench. It is a curated handoff, with selected historical inputs deliberately omitted.

## Included

- Upstream `src/`, `AGENTS.md`, `.env.example`, `tasks/`; original README and project context under `docs/upstream/`.
- Sentinel source, configuration, tests, static UI, documentation, dependency locks, safe fixtures/plans/source replay, blank human-time observation fields, recorded aggregate receipts/checks, selected screenshots, figures, and spoken MP3/text.
- The local review workbench, four bounded sanitized packets, seven pending drafts, label-quality review flags and blank timing pilot.
- The supplied synthetic IRS-65265 review demonstration with cache and bytecode excluded.

## Excluded classes

- All .git metadata, virtual environments, Python bytecode and cache directories.
- Actual .env files and private credential material; the upstream empty .env.example is retained.
- All adf-sentinel/data/raw source-system responses, downloaded originals and cached HTTP state.
- All adf-sentinel/data/extracted full historical views, issues, graphs and attachment inventories.
- All adf-sentinel/data/labels, data/reference and data/model_inputs historical excerpts/features.
- All fitted .joblib/.pkl/.pickle models, whose vocabularies can retain historical source text.
- Full retrospective advisory prediction rows (their count/hash receipt is retained).
- Original frozen evidence ZIP and the old legacy source ZIP; neither is a substitute for this curated copy.
- Spoken-demo WAV; the MP3 and reading text are retained.

## Historical reproduction and provenance

Original campaign: `59cc07c60d9ebcc93be4fb8d7ddb6137e64b13c9fc0a6d70e95f73d1b98668fe`. Its original frozen manifest and run receipts retain original hashes. Omitted historical features, weak labels, reference annotations and fitted binaries are required to reproduce that historical model state. Restoring the full source graph also needs the original cached Jira/Confluence responses and any required attachment bytes under appropriate internal access.

The original historical evidence ZIP remains local and is not included. Its recorded SHA-256 is `f67af7c41b81fec4238c16550a9d35d310a57c10cb009d30044937967a255a35`. Its byte hashes verify provenance; they do not certify that historical source text is suitable for repository publication. Historical login strings were found in the larger corpus, so the curated copy uses bounded sanitized packets and aggregate results instead.

Copied textual results are sanitized using the workbench sanitizer. JSON/JSONL values are decoded before sanitization, so escaping does not conceal inline credentials. Source code, test literals and approved fixture bytes keep their original bytes. Copy provenance records original and copied hashes; a changed sanitized result is a derivative and does not replace or redefine the original frozen artifact.

The combined workbench can display its precomputed offline results. A fresh historical rebuild needs the omitted private inputs. Missing inputs must remain explicit; do not retrain or relabel the historical campaign as part of opening this handoff. Genuine ADF build tooling, complete approved inputs, independent scientific testing and release-owner approval remain separate prerequisites.

Repository and upstream documentation retain their existing ownership notices. No new license or permission to redistribute third-party assets is invented by this package.
