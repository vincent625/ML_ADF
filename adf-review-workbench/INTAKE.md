# Review intake

`intake.py` prepares a precise record for review. It never executes a change and never turns a historical ticket, merged pull request, or source requirement into a new approval. The existing ADF Sentinel campaign and its inputs remain unchanged.

Copy `templates/change_record.json` and fill what is actually known. Keep unknown values `null` and unknown lists empty. Pending decisions are expected: a complete pending record can be ready for human review.

```bash
cd /rhome/yanzhu/ML_ADF
python adf-review-workbench/intake.py --record /absolute/path/to/record.json
python -m unittest discover -s adf-review-workbench/tests -p test_intake.py -v
```

The Python interface is `validate_record(record: dict) -> dict`. It returns `missing_fields`, `invalid_fields`, `review_ready`, `approval_status`, `human_approval_present`, `next_step`, and `execution_enabled: false`. Approval metadata is supplied by the record author, **not authenticated by this tool**; `approval_is_authenticated` remains false. This is a completeness check, not an executor authorization gate or a check of scientific correctness.

Every record needs schema version 1, an ID, issue key, source links, evidence, release, explicit variant scope, operation, acceptance criteria, and a reviewer-decision object. Evidence entries use:

```json
{
  "kind": "source_requirement",
  "url": "https://example.org/source",
  "note": "What this specific source supports",
  "source_sha256": null
}
```

`source_sha256` is optional and may be omitted or null; when supplied it must be SHA-256. Other evidence kinds are `historical_implementation`, `historical_decision`, `test_result`, and `current_decision`. The historical kinds remain reference evidence. An issue/release association does not establish that an instruction was implemented or approved for that release.

| Operation | Additional required information |
|---|---|
| `file_replacement` | Relative `target_path`, expected `baseline_sha256`, and `artifact: {source_url, revision, sha256}`. Floating `main`, `master`, `HEAD`, and `latest` revisions are rejected. |
| `parameter_metadata` | Relative `target_path`, exact `field`, `expected_old_value`, and `new_value`. |
| `dependency_pin` | Relative `target_path` and `dependency: {package, expected_version, new_version}`. Common floating aliases are rejected. |
| `shared_variant_change` | `variant_targets` entries containing `variant`, relative `target_path`, `field`, `expected_old_value`, and `new_value`, covering exactly the named variants. Values may differ between variants. |
| `investigation` | A specific `question` and acceptance criteria. An exact file change is not required while the investigation is being defined. |
| `verification` | A relative `target_path`, specific `question`, and acceptance criteria. Criteria are recorded, not executed. |
| `retain_defer_block` | Specific `question` and `decision: retain`, `defer`, or `block`. A retain decision also specifies `target_path`, `field`, and `expected_old_value`. |

A pending `reviewer_decision` contains status `pending`, null reviewer/date/evidence, optional note, and scope `current_record`. A recorded `approved`, `rejected`, or `deferred` decision needs a reviewer, timezone-bearing ISO date-time, evidence URL, note, and scope `current_record`. These fields do not establish the reviewer's identity or authority. All returned records remain non-executable; separate supported tooling, input-byte verification, scope checks, and applicable human decisions are required downstream.

Unknown fields, command fields, unsafe paths, malformed hashes, nonfinite parameter values, and credential-bearing source URLs are rejected. Relative paths are checked lexically; no filesystem is opened, so symlink/file existence checks are outside this intake tool. Hashes and cited claims are not verified against source bytes here. A complete record does not establish a buildable, installable, or scientifically validated ADF.
