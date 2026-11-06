"""Synthetic fixtures verify behavior; they are excluded from all real model results."""
import copy
import io
import json
import stat
import zipfile
from pathlib import Path

import pytest

from adf_sentinel.artifacts import archive_records
from adf_sentinel.collect import next_page
from adf_sentinel.common import digest, payload, read_json, read_jsonl, semver, write_json, write_jsonl
from adf_sentinel.common import clean_url
from adf_sentinel.dataset import action_proposals, confluence_page_id, ingest, prediction_snapshot, prepare, release_tables
from adf_sentinel.effort import critical_path, net_minutes, report
from adf_sentinel.learning import make_model, precision_coverage
from adf_sentinel.plans import execute, seed_fixtures, validate_plan
from adf_sentinel.predictor import input_rows


def test_payload_prefers_actual_mcp_data_over_ui_card():
    response = {"content": [{"type": "text", "text": json.dumps({"data": {"issues": [{"key": "OTHER-12", "fields": {"summary": "SYNTHETIC"}}]}})}],
                "structuredContent": {"issues": ["OTHER-12"]}}
    assert payload(response)["issues"][0]["fields"]["summary"] == "SYNTHETIC"
    assert payload({"content": [{"type": "text", "text": "Action completed."}], "structuredContent": {"sha": "pinned"}}) == {"sha": "pinned"}


def test_pagination_respects_actual_rows_and_reported_total():
    first = {"startAt": 0, "maxResults": 20, "total": 23, "comments": [{"id": i} for i in range(20)]}
    assert next_page(first, "listJiraIssueComments", {"issueIdOrKey": "SYN-1", "maxResults": 100})["startAt"] == 20
    assert next_page({"startAt": 20, "total": 23, "comments": [{"id": i} for i in range(3)]}, "listJiraIssueComments", {}) is None
    assert next_page({"startAt": 0, "total": 51, "isLast": False, "values": [{}] * 50}, "listJiraIssueChangelogs", {})["startAt"] == 50


def test_stalled_and_cyclic_pagination_are_not_silently_complete():
    with pytest.raises(ValueError, match="stalled"):
        next_page({"total": 2, "comments": []}, "listJiraIssueComments", {})
    with pytest.raises(ValueError, match="Repeated"):
        next_page({"_links": {"next": "/pages?cursor=again"}}, "listConfluenceAttachments", {"cursor": "again"})
    assert next_page({"isLast": False, "nextPageToken": "p2"}, "searchJiraIssuesUsingJql", {})["nextPageToken"] == "p2"


def page_html():
    return """<h2>DNA and Fusions</h2><table data-local-id="table-stable"><tr><th>Date</th><th>ADF name and version</th><th>Genexus SW version</th><th>Changes</th><th>Jira tickets</th></tr>
    <tr data-local-id="r1"><td>2022-01-03</td><td>Panel-w1.0.0-DNA-SW_7.0-v0.0.9</td><td>7.0</td><td>SYNTHETIC baseline</td><td><a href="https://example.invalid/SYN-1">SYN-1</a></td></tr>
    <tr data-local-id="r2"><td>2023-02-04</td><td>Panel-w1.0.0-DNA-SW_7.0-v0.0.10</td><td>7.0</td><td>SYNTHETIC updated baseline</td><td>SYN-1 CROSS-2</td></tr></table>"""


def test_release_identity_preserves_versions_and_source_date():
    page = {"id": "123", "title": "SYNTHETIC Panel ADF 7.0 change tracking", "body": {"value": page_html()}, "metadata": {"version": {"number": 5, "createdAt": "2026-10-31"}}}
    rows, _ = release_tables(page, {"path": "fixture", "sha256": "fixture"})
    assert len(rows) == 2
    assert rows[0]["software_version"] == "7.0"
    assert rows[0]["workflow_version"] == "1.0.0"
    assert rows[0]["adf_revision"] == "0.0.9"
    assert rows[0]["release_date"] == "2022-01-03"
    assert semver(rows[0]["adf_revision"]) < semver(rows[1]["adf_revision"])
    assert set(rows[1]["listed_issue_keys"]) == {"SYN-1", "CROSS-2"}
    page["metadata"]["version"]["number"] = 6
    newer, _ = release_tables(page, {"path": "fixture", "sha256": "new"})
    assert newer[0]["id"] == rows[0]["id"]


def test_workflow_version_is_not_invented_as_adf_revision():
    body = '<table><tr><th>ADF Full Name</th><th>Changes</th></tr><tr><td>Panel-GX7-w6.0.0-DNA-SW_6.8.zip</td><td>SYNTHETIC</td></tr></table>'
    rows, _ = release_tables({"id": "123", "title": "SYNTHETIC 6.8 ADF", "body": {"value": body}}, {"path": "fixture", "sha256": "fixture"})
    assert rows[0]["workflow_version"] == "6.0.0"
    assert rows[0]["adf_revision"] is None and rows[0]["revision_ambiguous"]


def test_hidden_link_destinations_and_credential_query_redaction(tmp_path):
    raw = tmp_path / "data/raw/exports"
    write_json(raw / "issue.json", {"key": "SYN-1", "fields": {"description": '<p>See <a href="https://jira.example.invalid/browse/OTHER-22">the dependency</a></p>', "comment": {"total": 0, "comments": []}}})
    ingest(tmp_path)
    edges = read_jsonl(tmp_path / "data/extracted/reference_edges.jsonl")
    assert any(e["target"] == "OTHER-22" and e["type"] == "smart_link_reference" for e in edges)
    assert clean_url("https://user:placeholder@example.invalid/path?token=placeholder&version=3") == "https://example.invalid/path?version=3"


def test_legacy_confluence_remote_links_remain_in_the_frontier(tmp_path):
    from adf_sentinel.common import SITE
    assert confluence_page_id(SITE + "/wiki/pages/viewpage.action?pageId=123") == "123"
    assert confluence_page_id("/wiki/spaces/IRS/pages/456/title") == "456"
    assert confluence_page_id("https://other.example.invalid/wiki/pages/999/title") is None
    raw = tmp_path / "data/raw/exports"
    write_json(raw / "issue.json", {"key": "SYN-1", "fields": {"description": "SYNTHETIC context", "comment": {"total": 0, "comments": []}}})
    write_json(raw / "remote_SYN-1.json", {"operation": "listJiraIssueRemoteIssueLinks", "resource": "SYN-1", "data": [{"object": {"url": SITE + "/wiki/pages/viewpage.action?pageId=123"}}]})
    write_json(raw / "history.json", {"operation": "listJiraIssueChangelogs", "resource": "SYN-1", "data": {"total": 0, "values": []}})
    ingest(tmp_path)
    jobs = read_json(tmp_path / "data/collection_queue.json")
    assert any(j["operation"] == "getConfluenceContent" and j["resource"] == "page:123" for j in jobs)
    assert any(e["target"] == "page:123" and e["type"] == "confluence_remote_link" for e in read_jsonl(tmp_path / "data/extracted/reference_edges.jsonl"))
    assert read_jsonl(tmp_path / "data/extracted/issues.jsonl")[0]["completeness"]["history"] == "collected"


def test_malformed_checks_and_nonstring_prerequisites_reject_before_mutation(tmp_path):
    plan = seed_fixtures(tmp_path)
    plan["actions"][0]["checks"] = [{"kind": "json_value"}]
    with pytest.raises(ValueError, match="missing"):
        execute(plan, tmp_path / "data/fixtures/baseline", tmp_path)
    assert not (tmp_path / "runs/sandbox").exists()


def test_edited_comments_are_not_backdated_and_field_history_can_recover_text():
    fields = {"created": "2020-01-01T00:00:00Z", "updated": "2026-01-01T00:00:00Z", "description": "LATER ANSWER", "summary": "EDITED TITLE"}
    comments = [{"id": "1", "created": "2020-01-01T00:00:00Z", "updated": "2026-01-01T00:00:00Z", "body": "LATER COMMENT ANSWER"},
                {"id": "2", "created": "2021-01-01T00:00:00Z", "updated": "2021-01-01T00:00:00Z", "body": "Original prerequisite"}]
    histories = [{"created": "2024-01-01T00:00:00Z", "items": [{"field": "description", "fromString": "Original requirement", "toString": "LATER ANSWER"}]}]
    view = prediction_snapshot(fields, comments, histories, "2022-01-01T00:00:00Z")
    assert "Original requirement" in view["text"] and "Original prerequisite" in view["text"]
    assert "LATER" not in view["text"] and "EDITED TITLE" not in view["text"]
    assert view["state"] == "point_in_time_partial"
    assert prediction_snapshot(fields, comments, histories, None)["text"] == ""


def test_mixed_ticket_and_struck_through_instructions_remain_separate():
    source = {"path": "SYNTHETIC", "sha256": "0" * 64, "locator": "description"}
    issue = {"key": "SYN-1", "fields": {"updated": "2026-01-01", "description": "<p>Verify the software-only rules. This is not a ADF change.</p><p>Remove baseline.txt.</p><p><s>Use alternative.txt as the reference.</s></p>"}, "comments": []}
    rows = action_proposals(issue, {"release-fixture"}, {"description": source})
    assert any(r["category"] == "verification_only" for r in rows)
    assert any(r["category"] == "approved_file" for r in rows)
    assert any(r["execution_mode"] == "blocked" and r["historical_state"].startswith("struck_through") for r in rows)
    assert all(r["reviewer_state"] == "unreviewed" and r["target"] is None for r in rows)


def test_ingest_deduplicates_cycles_and_release_associations(tmp_path):
    raw = tmp_path / "data/raw/exports"
    page = {"type": "page", "id": "123", "title": "SYNTHETIC Panel 7.0 ADF", "body": {"value": page_html()}, "metadata": {"version": {"number": 1}}}
    write_json(raw / "page.json", page)
    for key, mention in [("SYN-1", "CROSS-2"), ("CROSS-2", "SYN-1")]:
        write_json(raw / (key + ".json"), {"id": key, "key": key, "fields": {"summary": "SYNTHETIC investigate config", "description": "Verify config.json and investigate " + mention,
                   "created": "2020-01-01", "updated": "2026-01-01", "comment": {"comments": [], "total": 0}, "attachment": []}})
    result = ingest(tmp_path)
    assert result["validated_issues"] == 2
    issues = read_jsonl(tmp_path / "data/extracted/issues.jsonl")
    assert len(next(r for r in issues if r["issue_key"] == "SYN-1")["release_ids"]) == 2
    jobs = read_json(tmp_path / "data/collection_queue.json")
    assert not any(j["operation"] == "getJiraIssue" and j["resource"] in {"SYN-1", "CROSS-2"} for j in jobs)
    ready = prepare(tmp_path)
    assert ready["integrity"]["reviewed_labels"] == 0
    assert not ready["integrity"]["primary_performance_claim_permitted"]


def test_archive_paths_hashes_and_no_script_execution(tmp_path):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("nested/config.json", '{"SYNTHETIC":true}')
        z.writestr("../escape.txt", "unsafe")
        z.writestr("script.py", "raise RuntimeError('DO NOT EXECUTE')")
        link = zipfile.ZipInfo("link")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        z.writestr(link, "../escape.txt")
    rows = archive_records(stream.getvalue())
    assert next(r for r in rows if r["path"] == "nested/config.json")["sha256"] == digest(b'{"SYNTHETIC":true}')
    assert next(r for r in rows if r["path"] == "../escape.txt")["state"] == "partial"
    assert next(r for r in rows if r["path"] == "link")["state"] == "partial"
    assert "DO NOT EXECUTE" in next(r for r in rows if r["path"] == "script.py")["text"]
    assert not (tmp_path / "escape.txt").exists()


@pytest.mark.parametrize("name", ["tfidf_logistic", "tfidf_svm", "structured_tree"])
def test_training_is_reproducible_and_does_not_fit_future_text(name):
    from adf_sentinel.predictor import structured_features
    texts = ["SYNTHETIC copy alpha file", "SYNTHETIC replace beta file", "SYNTHETIC investigate numerical fault", "SYNTHETIC investigate parser failure"] * 3
    labels = ["approved_file", "approved_file", "investigation_code", "investigation_code"] * 3
    X = structured_features(texts) if name == "structured_tree" else texts
    a, b = make_model(name, labels), make_model(name, labels)
    a.fit(X, labels)
    b.fit(X, labels)
    assert list(a.predict(X)) == list(b.predict(X))
    if name.startswith("tfidf"):
        assert "futuresecretanswer" not in a.named_steps["tfidf"].vocabulary_
        a.predict(["futuresecretanswer"])
        assert "futuresecretanswer" not in a.named_steps["tfidf"].vocabulary_


def test_prediction_loader_rejects_reference_paths_and_answer_columns(tmp_path):
    inputs = tmp_path / "model_inputs"
    outside = tmp_path / "reference/labels.jsonl"
    write_jsonl(outside, [{"id": "SYNTHETIC", "text": "answer", "category": "approved_file"}])
    with pytest.raises(ValueError, match="isolated"):
        input_rows(outside, inputs)
    path = inputs / "test.jsonl"
    write_jsonl(path, [{"id": "SYNTHETIC", "text": "input", "category": "approved_file"}])
    with pytest.raises(ValueError, match="Label/reference"):
        input_rows(path, inputs)


def test_thresholds_require_observed_support_and_exact_correct_plans():
    cases = [{"score": x, "schema_valid": True, "approved_inputs_complete": True, "exact_plan_correct": True} for x in [.13,.28,.42,.64,.82]]
    rows = precision_coverage(cases)
    assert rows[0]["threshold"] == .13 and rows[0]["eligible"]
    assert not rows[-1]["eligible"]
    cases[0]["exact_plan_correct"] = False
    assert not any(r["eligible"] for r in precision_coverage(cases))


def test_sandbox_correct_copy_parameter_checks_and_idempotency(tmp_path):
    plan = seed_fixtures(tmp_path)
    result = execute(plan, tmp_path / "data/fixtures/baseline", tmp_path)
    assert result["status"] == "passed" and result["synthetic"]
    assert result["originals_preserved"] and len(result["changed_files"]) == 4
    assert read_json(tmp_path / "data/fixtures/baseline/DNA/config.json")["parameters"]["threshold"] == .2
    assert all(check["passed"] for check in result["checks"])
    assert execute(plan, tmp_path / "data/fixtures/baseline", tmp_path)["reused"]


@pytest.mark.parametrize("target", ["../outside", "/tmp/outside", "DNA/../../outside", "DNA\\outside", "DNA/./config.json"])
def test_unsafe_target_paths_are_rejected(tmp_path, target):
    plan = seed_fixtures(tmp_path)
    plan["actions"][0]["target"] = target
    with pytest.raises(ValueError):
        execute(plan, tmp_path / "data/fixtures/baseline", tmp_path)
    assert not (tmp_path / "runs/sandbox").exists()


def test_unknown_commands_missing_inputs_and_changed_bytes_are_rejected(tmp_path):
    original = seed_fixtures(tmp_path)
    for mutate in [lambda p: p["actions"][0].update(command="echo forbidden"),
                   lambda p: p["actions"][0].update(type="shell_command"),
                   lambda p: p["actions"][0].update(variant="synthetic-DNA+Fusion"),
                   lambda p: p["prerequisites"][0].update(satisfied="true"),
                   lambda p: p["prerequisites"][0].update(satisfied=False),
                   lambda p: p["actions"][0].update(before_sha256="0"*64)]:
        plan = copy.deepcopy(original)
        mutate(plan)
        with pytest.raises(ValueError):
            execute(plan, tmp_path / "data/fixtures/baseline", tmp_path)
    (tmp_path / "data/fixtures/approved/shared.txt").write_text("SYNTHETIC changed after proposal")
    with pytest.raises(ValueError, match="Pinned"):
        execute(original, tmp_path / "data/fixtures/baseline", tmp_path)


def test_symlinks_and_stale_candidate_results_are_rejected(tmp_path):
    plan = seed_fixtures(tmp_path)
    path = tmp_path / "data/fixtures/baseline/DNA/shared.txt"
    path.unlink()
    path.symlink_to(tmp_path / "data/fixtures/approved/shared.txt")
    with pytest.raises(ValueError, match="symbolic"):
        execute(plan, tmp_path / "data/fixtures/baseline", tmp_path)


def test_failed_check_is_not_reclassified_as_a_pass(tmp_path):
    plan = seed_fixtures(tmp_path)
    plan["actions"][0]["checks"][0]["value"] = .8
    result = execute(plan, tmp_path / "data/fixtures/baseline", tmp_path)
    assert result["status"] == "failed" and result["originals_preserved"]
    assert any(not c["passed"] for c in result["checks"])


def test_effort_requires_observations_and_handles_rework_losses(tmp_path):
    assert net_minutes({"manual_replaced_minutes": ""}) is None
    row = dict(manual_replaced_minutes=20, review_minutes=5, supervision_minutes=3, correction_minutes=15, intake_minutes=2)
    assert net_minutes(row) == -5
    assert report(tmp_path)["measured_net_minutes"] is None
    tasks = [{"id": "a", "duration_hours": 2}, {"id": "b", "duration_hours": 1, "wait_hours": 3}, {"id": "c", "duration_hours": 1, "depends_on": ["a", "b"]}]
    assert critical_path(tasks)["elapsed_hours"] == 5
    with pytest.raises(ValueError, match="Cyclic"):
        critical_path([{"id": "a", "duration_hours": 1, "depends_on": ["a"]}])


def test_frozen_blocked_campaign_reuses_artifacts_and_rejects_tampering(tmp_path):
    from adf_sentinel.learning import train, freeze, predict, evaluate
    feature_dir = tmp_path / "data/model_inputs"
    rows, labels = [], []
    for i in range(12):
        aid = "synthetic-" + str(i)
        category = "approved_file" if i % 2 else "investigation_code"
        rows.append({"id": aid, "issue_key": "SYN-"+str(i), "release_id": "synthetic-release", "family": "SYNTHETIC",
                     "partition": "train", "text": "SYNTHETIC copy approved file" if i % 2 else "SYNTHETIC investigate code fault", "input_state": "synthetic_fixture", "synthetic": True})
        labels.append({"id": aid, "category": category, "execution_mode": "assisted_review"})
    write_jsonl(feature_dir / "retrospective.jsonl", rows)
    for partition in ["train", "validation", "test"]:
        write_jsonl(feature_dir / ("strict_"+partition+".jsonl"), [])
    write_jsonl(tmp_path / "data/labels/weak_actions.jsonl", labels)
    write_json(tmp_path / "data/split_manifest.json", {"data_hash": "SYNTHETIC_FIXTURE_ONLY", "blocking_reasons": ["SYNTHETIC test of blocking"]})
    trained = train(tmp_path)
    assert trained["status"] == "exploratory_fits_completed"
    assert all(m.get("validation") is None for m in trained["models"])
    frozen = freeze(tmp_path)
    assert not frozen["automatic_execution_enabled"]
    assert predict(tmp_path, strict=True)["count"] == 0
    result = evaluate(tmp_path)
    assert result["status"] == "blocked" and result["metrics"] is None
    assert train(tmp_path)["reused_locked_artifacts"]
    assert freeze(tmp_path)["freeze_id"] == frozen["freeze_id"]
    assert evaluate(tmp_path)["reused_locked_result"]
    (feature_dir / "strict_test.jsonl").write_text('{"text":"tampered answer"}\n')
    with pytest.raises(ValueError, match="feature file"):
        predict(tmp_path, strict=True)
