# Evidence packets

`evidence_packets.py` collects existing local evidence into bounded, readable review packets. It uses only Python's standard library and does not alter the source campaign or contact upstream systems.

Run from `/rhome/yanzhu/ML_ADF`:

```bash
python adf-review-workbench/evidence_packets.py --source adf-sentinel --output adf-review-workbench/results/packets --issues IRS-65265 IRS-29057 IRS-57322 IRS-66772
```

The callable interface is `build_packets(source_root: Path, output_root: Path, issue_keys: list[str]) -> list[dict]`. Each returned packet is also written as `<issue_key>.json` and `<issue_key>.md`; `index.json` lists the packets and coverage counts.

Each packet contains the current description, dated comment timeline, proposed unreviewed action excerpts, candidate release associations, partial historical views, artifact references, missing-input questions and input-file SHA-256 hashes. Local raw-source hashes are checked where source provenance exists. A linked issue does not prove an implemented change; a historical implementation does not grant new approval.

Comments retain both creation and update dates. Distinct instructions from different dates are retained separately. In particular, the IRS-29057 software-upgrade verification instruction and later ADF 0.0.9 ruleset removal remain separate dated events.

Output is deliberately bounded: 40 comments with up to 6,000 characters each; 42 action excerpts with at most six per proposed category; 12 release associations; six historical views; 16 artifact references. Counts show available versus displayed records and excerpt truncation. Current descriptions are capped at 10,000 characters. All counts refer to the cached, partial source snapshot. Full originals remain accessible through source references.

Generated text removes credential-like parenthetical pairs, common credential assignments, HTTP authorization strings, URL user information and all query parameters except numeric Jira comment IDs. Rendering applications should still escape text and permit only HTTP(S) source links. Source evidence itself remains unchanged.

The five confirmation questions are review prompts, not claims that every source lacks the answer. The engineer must reconcile action-level release scope, exact changes, approval, acceptance checks and chronology. This add-on does not assemble or release an ADF.

Focused tests cover chronological history, provenance hashes, Unicode JSONL text, credentials, balanced excerpt limits, missing records, path traversal and source-project preservation:

```bash
python -m unittest discover -s adf-review-workbench/tests -p test_evidence_packets.py
```
