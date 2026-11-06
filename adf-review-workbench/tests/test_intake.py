"""Meaningful readiness and approval-boundary checks, using synthetic records."""

import copy
import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "intake.py"
SPEC = importlib.util.spec_from_file_location("workbench_intake", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
validate_record = MODULE.validate_record


def investigation():
    return {
        "schema_version": 1, "id": "synthetic-investigation", "issue_key": "DEMO-1",
        "source_links": ["https://example.org/issues/DEMO-1"],
        "evidence": [{"kind": "source_requirement", "url": "https://example.org/issues/DEMO-1", "note": "Synthetic acceptance-test requirement."}],
        "release": "synthetic-release-1", "variants": ["synthetic-DNA"],
        "operation": "investigation", "question": "Which configuration changed?",
        "acceptance_checks": ["Explain the difference using a reproducible comparison."],
        "reviewer_decision": {"status": "pending", "reviewer": None, "decided_at": None, "evidence_url": None, "note": None, "scope": "current_record"},
    }


def parameter():
    record = investigation()
    record.update({"operation": "parameter_metadata", "target_path": "fixture/parameters.json", "field": "/threshold", "expected_old_value": 0.2, "new_value": 0.4})
    return record


class IntakeTests(unittest.TestCase):
    def test_investigation_can_be_review_ready_without_being_executable(self):
        result = validate_record(investigation())
        self.assertTrue(result["review_ready"])
        self.assertEqual(result["missing_fields"], [])
        self.assertEqual(result["approval_status"], "pending")
        self.assertFalse(result["human_approval_present"])
        self.assertFalse(result["execution_enabled"])

    def test_unknown_details_stay_missing(self):
        record = parameter()
        record.update({"release": None, "variants": [], "expected_old_value": None, "new_value": None})
        result = validate_record(record)
        self.assertFalse(result["review_ready"])
        self.assertEqual(set(result["missing_fields"]), {"release", "variants", "expected_old_value", "new_value"})

    def test_paths_reject_traversal_absolute_windows_and_control_characters(self):
        for path in ("../../params.json", "/etc/passwd", "C:/config.json", "a\\b", "a//b", "a/./b", "a\nb"):
            with self.subTest(path=path):
                record = parameter()
                record["target_path"] = path
                result = validate_record(record)
                self.assertFalse(result["review_ready"])
                self.assertIn("target_path", [item["field"] for item in result["invalid_fields"]])

    def test_historical_implementation_and_closed_ticket_are_not_approval(self):
        record = investigation()
        record["evidence"][0]["kind"] = "historical_implementation"
        record["evidence"][0]["note"] = "Historical issue was closed and its pull request merged."
        result = validate_record(record)
        self.assertTrue(result["review_ready"])
        self.assertEqual(result["approval_status"], "pending")
        self.assertFalse(result["human_approval_present"])
        record["reviewer_decision"] = {"status": "approved", "reviewer": "test reviewer", "decided_at": "2026-01-01T10:00:00Z", "evidence_url": "https://example.org/decisions/1", "note": "Synthetic example only", "scope": "historical_implementation"}
        result = validate_record(record)
        self.assertEqual(result["approval_status"], "invalid")
        self.assertFalse(result["human_approval_present"])

    def test_complete_recorded_approval_is_not_authenticated_or_executable(self):
        record = parameter()
        record["reviewer_decision"] = {"status": "approved", "reviewer": "synthetic test reviewer", "decided_at": "2026-01-01T10:00:00+00:00", "evidence_url": "https://example.org/synthetic-decision", "note": "Unit test metadata only", "scope": "current_record"}
        result = validate_record(record)
        self.assertTrue(result["review_ready"])
        self.assertTrue(result["human_approval_present"])
        self.assertFalse(result["approval_is_authenticated"])
        self.assertFalse(result["execution_enabled"])
        record["reviewer_decision"]["decided_at"] = "2026-01-01T10:00:00"
        result = validate_record(record)
        self.assertEqual(result["approval_status"], "invalid")

    def test_approval_missing_provenance_is_invalid(self):
        record = parameter()
        record["reviewer_decision"]["status"] = "approved"
        result = validate_record(record)
        self.assertFalse(result["review_ready"])
        self.assertEqual(result["approval_status"], "invalid")
        self.assertIn("reviewer_decision.reviewer", result["missing_fields"])

    def test_unknown_top_level_and_nested_command_fields_are_rejected(self):
        for payload in ({"command": "do not execute"}, {"shell": "do not execute"}, {"execute": True}):
            record = parameter()
            record.update(payload)
            result = validate_record(record)
            self.assertFalse(result["review_ready"])
            self.assertFalse(result["execution_enabled"])
        record = investigation()
        record["evidence"][0]["command"] = "do not execute"
        self.assertFalse(validate_record(record)["review_ready"])

    def test_file_copy_requires_exact_hashes_and_nonfloating_revision(self):
        record = investigation()
        record.update({"operation": "file_replacement", "target_path": "fixture/asset.txt", "baseline_sha256": "a" * 64, "artifact": {"source_url": "https://example.org/immutable/asset.txt", "revision": "b" * 40, "sha256": "c" * 64}})
        self.assertTrue(validate_record(record)["review_ready"])
        record["artifact"]["sha256"] = "not-a-sha256"
        record["artifact"]["revision"] = "main"
        result = validate_record(record)
        fields = {item["field"] for item in result["invalid_fields"]}
        self.assertEqual(fields, {"artifact.sha256", "artifact.revision"})

    def test_shared_variants_require_coverage_without_assuming_equal_values(self):
        record = investigation()
        record.update({"operation": "shared_variant_change", "variants": ["DNA", "RNA"], "variant_targets": [{"variant": "DNA", "target_path": "dna/params.ini", "field": "example", "expected_old_value": 1, "new_value": 2}, {"variant": "RNA", "target_path": "rna/params.ini", "field": "example", "expected_old_value": 4, "new_value": 5}]})
        self.assertTrue(validate_record(record)["review_ready"])
        record["variant_targets"].pop()
        self.assertFalse(validate_record(record)["review_ready"])

    def test_dependency_and_retain_records_require_operation_specific_inputs(self):
        dependency = investigation()
        dependency.update({"operation": "dependency_pin", "target_path": "fixture/dependencies.json", "dependency": {"package": "example-package", "expected_version": "1.0", "new_version": "1.1"}})
        self.assertTrue(validate_record(dependency)["review_ready"])
        dependency["dependency"]["new_version"] = "latest"
        self.assertFalse(validate_record(dependency)["review_ready"])
        retained = investigation()
        retained.update({"operation": "retain_defer_block", "decision": "retain"})
        result = validate_record(retained)
        self.assertFalse(result["review_ready"])
        self.assertIn("expected_old_value", result["missing_fields"])

    def test_capability_urls_nonfinite_values_and_malformed_types_fail_closed(self):
        record = parameter()
        record["source_links"] = ["https://example.org/file?X-Amz-Signature=secret"]
        self.assertFalse(validate_record(record)["review_ready"])
        record = parameter()
        record["new_value"] = float("nan")
        self.assertFalse(validate_record(record)["review_ready"])
        for operation in ([], {}, 123):
            record = investigation()
            record["operation"] = operation
            self.assertFalse(validate_record(record)["review_ready"])
        record = investigation()
        record["reviewer_decision"]["status"] = {}
        self.assertEqual(validate_record(record)["approval_status"], "invalid")
        self.assertFalse(validate_record([])["review_ready"])

    def test_validation_does_not_mutate_input(self):
        record = investigation()
        expected = copy.deepcopy(record)
        validate_record(record)
        self.assertEqual(record, expected)


if __name__ == "__main__":
    unittest.main()
