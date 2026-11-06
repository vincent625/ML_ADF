import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "bottlenecks.py"
sys.path.insert(0, str(MODULE_PATH.parent))
spec = importlib.util.spec_from_file_location("workbench_bottlenecks", MODULE_PATH)
bottlenecks = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bottlenecks
spec.loader.exec_module(bottlenecks)


class TimingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "observations.csv"

    def row(self, mode, **updates):
        row = {
            "pair_id": "pair-a", "action_id": "action-a", "mode": mode,
            "scope": "review preparation", "milestone": "reviewable evidence record",
            "observer": "pilot engineer", "observed_at": "2026-11-03T10:00:00-08:00",
            "completion_state": "completed",
        }
        row.update({field: "0" for field in bottlenecks.MINUTE_FIELDS})
        row.update(updates)
        return row

    def write(self, rows):
        with self.path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=bottlenecks.CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def test_blank_template_means_unknown_not_zero(self):
        self.write([])
        result = bottlenecks.summarize_observations(self.path)
        self.assertEqual(result["status"], "unknown_no_observations")
        self.assertIsNone(result["net_active_minutes_saved"])
        self.assertIsNone(result["recorded_setup_minutes"])

    def test_matched_pair_includes_review_rework_and_intake_excludes_wait_setup(self):
        self.write([
            self.row("manual", search_minutes="15", edit_minutes="5", wait_minutes="120"),
            self.row("assisted", search_minutes="2", edit_minutes="1", review_minutes="3",
                     supervision_minutes="1", rework_minutes="2", intake_minutes="1",
                     wait_minutes="60", setup_minutes="100"),
        ])
        result = bottlenecks.summarize_observations(self.path)
        self.assertEqual(result["matched_pairs"], 1)
        self.assertEqual(result["manual_active_minutes"], 20)
        self.assertEqual(result["assisted_active_minutes"], 10)
        self.assertEqual(result["net_active_minutes_saved"], 10)
        self.assertEqual(result["recorded_setup_minutes"], 100)
        self.assertEqual(result["manual_wait_minutes"], 120)
        self.assertEqual(result["assisted_wait_minutes"], 60)

    def test_negative_savings_retained(self):
        self.write([self.row("manual", edit_minutes="1"), self.row("assisted", edit_minutes="5")])
        self.assertEqual(bottlenecks.summarize_observations(self.path)["net_active_minutes_saved"], -4)

    def test_missing_nonfinite_negative_durations_reject_whole_pair(self):
        for bad in ("", "nan", "inf", "-1", "word"):
            with self.subTest(bad=bad):
                self.write([self.row("manual"), self.row("assisted", review_minutes=bad)])
                result = bottlenecks.summarize_observations(self.path)
                self.assertEqual(result["matched_pairs"], 0)
                self.assertIsNone(result["net_active_minutes_saved"])
                self.assertEqual(len(result["invalid_rows"]), 1)
                self.assertEqual(len(result["rejected_pairs"]), 1)

    def test_mismatch_scope_milestone_action_and_duplicate_mode_rejected(self):
        updates = ({"scope": "installation"}, {"milestone": "installed"}, {"action_id": "action-b"})
        for update in updates:
            with self.subTest(update=update):
                self.write([self.row("manual"), self.row("assisted", **update)])
                result = bottlenecks.summarize_observations(self.path)
                self.assertEqual(result["matched_pairs"], 0)
                self.assertTrue(result["rejected_pairs"])
        self.write([self.row("manual"), self.row("manual")])
        self.assertEqual(bottlenecks.summarize_observations(self.path)["matched_pairs"], 0)

    def test_invalid_timestamp_and_incomplete_completion_rejected(self):
        for update in ({"observed_at": "2026-11-03T10:00:00"}, {"completion_state": "in_progress"}):
            with self.subTest(update=update):
                self.write([self.row("manual"), self.row("assisted", **update)])
                result = bottlenecks.summarize_observations(self.path)
                self.assertEqual(result["matched_pairs"], 0)
                self.assertTrue(result["invalid_rows"])

    def test_valid_subset_reports_exclusions(self):
        self.write([
            self.row("manual", edit_minutes="5"), self.row("assisted", edit_minutes="3"),
            self.row("manual", pair_id="unpaired"),
        ])
        result = bottlenecks.summarize_observations(self.path)
        self.assertEqual(result["status"], "partially_measured")
        self.assertEqual(result["matched_pairs"], 1)
        self.assertEqual(result["net_active_minutes_saved"], 2)
        self.assertEqual(result["rejected_pairs"][0]["pair_id"], "unpaired")


class EvidenceTests(unittest.TestCase):
    def test_review_flags_are_narrow_candidates(self):
        flagged = {"category": "defer_inherit_block", "text": "Threshold: Not Set"}
        self.assertEqual(bottlenecks._review_reasons(flagged), ["threshold_without_explicit_hold_word"])
        self.assertEqual(bottlenecks._review_reasons({**flagged, "text": "Hold this threshold change until next release"}), [])
        self.assertEqual(bottlenecks._review_reasons({"category": "dependency_pin", "text": "Please update the Jira fix version."}), ["jira_fix_version_may_be_administrative"])
        self.assertEqual(bottlenecks._review_reasons({"category": "investigation_code", "text": "Do you want to add anything else?"}), ["generic_clarification_may_not_be_implementation_action"])

    def test_report_counts_and_source_bytes_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            (source / "data/labels").mkdir(parents=True)
            (source / "runs/effort").mkdir(parents=True)
            actions = source / "data/labels/weak_actions.jsonl"
            rows = [
                {"id": "a", "issue_key": "IRS-1", "category": "investigation_code", "text": "Do you want to add anything else?", "reviewer_state": "unreviewed", "evidence": []},
                {"id": "b", "issue_key": "IRS-2", "category": "approved_file", "text": "copy\u2028the approved file", "reviewer_state": "unreviewed", "evidence": []},
            ]
            actions.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
            effort = source / "runs/effort/report.json"
            effort.write_text('{"status":"blocked","measured_actions":0,"measured_net_minutes":null}', encoding="utf-8")
            before = {path: path.read_bytes() for path in (actions, effort)}
            output = root / "workbench/results"
            report = bottlenecks.build_report(source, output)
            self.assertEqual(report["proposal_count"], 2)
            self.assertEqual(report["reviewed_labels"], 0)
            self.assertEqual(report["category_counts"][0]["percent"], 50)
            self.assertEqual(report["quality_review_flags"]["flag_count"], 1)
            self.assertIsNone(report["timing"]["net_active_minutes_saved"])
            self.assertTrue((output / "bottlenecks.json").exists())
            for path, content in before.items():
                self.assertEqual(path.read_bytes(), content)

    def test_capability_queries_and_credentials_removed(self):
        result = bottlenecks._safe_url("https://user:secret@example.com/ticket?token=secret&focusedCommentId=123&X-Amz-Signature=bad")
        self.assertEqual(result, "https://example.com/ticket?focusedCommentId=123")
        self.assertNotIn("secret", bottlenecks._safe_text("See https://example.com/a?token=secret now"))

    def test_inline_credentials_and_capability_fragments_removed(self):
        text = "(testadmin/ExampleSecret123!) password=ExampleSecret123! Bearer abcdefghijklmnop"
        sanitized = bottlenecks._safe_text(text)
        self.assertNotIn("ExampleSecret123", sanitized)
        self.assertNotIn("abcdefghijklmnop", sanitized)
        self.assertNotIn("ExampleSecret123", bottlenecks._safe_url("https://example.com/a#access_token=ExampleSecret123"))

    def test_outputs_cannot_be_nested_under_preserved_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            with self.assertRaisesRegex(ValueError, "outside the preserved source"):
                bottlenecks.build_report(source, source / "new-report")
            self.assertFalse((source / "new-report").exists())

    def test_both_output_symlinks_rejected_before_any_write(self):
        for name in ("bottlenecks.json", "bottlenecks.md"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                source, output = Path(directory) / "source", Path(directory) / "output"
                source.mkdir()
                output.mkdir()
                protected = source / "preserved.txt"
                protected.write_text("unchanged")
                (output / name).symlink_to(protected)
                with self.assertRaisesRegex(ValueError, "symbolic links"):
                    bottlenecks.build_report(source, output)
                self.assertEqual(protected.read_text(), "unchanged")
                other = "bottlenecks.md" if name.endswith("json") else "bottlenecks.json"
                self.assertFalse((output / other).exists())


if __name__ == "__main__":
    unittest.main()
