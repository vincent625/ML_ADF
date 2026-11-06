IRS-65265 review package

Start with REVIEW.md. CODEX_PROMPT.txt is the source-grounded build prompt.
linked-sources.csv inventories 60 business URLs from the saved page.
requirements-candidates.json contains 20 proposed requirement families, including inactive/history states.
training-examples.jsonl contains 10 review candidates from one release, not a trained model.
source-check-results.json records ten narrow observations against captured GitHub PR source evidence.
check_source_evidence.py reproduces those observations using github-review-data.json.
source-coverage.json records coverage and snapshot limitations.
comments.json contains the five loaded comments with source IDs and creation/update times.
visible-attachment-metadata.json lists the ten captured attachment metadata records.

All source observations and proposed training labels have explicit scope limitations. No Genexus run,
physical instrument test, released-ADF installation, or binary-baseline checksum validation was executed.
The original uploads, raw browser state, screenshots, and whole repositories are not redistributed here.
