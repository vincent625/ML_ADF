"""Cross-component privacy, temporal evidence, and approval-boundary checks."""

import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def module(name):
    spec = importlib.util.spec_from_file_location("cross_review_" + name, ROOT / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


evidence = module("evidence_packets")
bottlenecks = module("bottlenecks")
intake = module("intake")


class CrossReviewTests(unittest.TestCase):
    def test_both_excerpt_builders_remove_inline_and_link_credentials(self):
        cases = (
            ("password=UniqueSyntheticSecret123!", "UniqueSyntheticSecret123"),
            ('password="UniqueSynthetic Secret With Spaces"', "Secret With Spaces"),
            ("(testadmin/UniqueSyntheticSecret123!)", "UniqueSyntheticSecret123"),
            ("Bearer UniqueSyntheticBearer123456", "UniqueSyntheticBearer123456"),
            ("See https://example.test/#access_token=UniqueSyntheticFragment123", "UniqueSyntheticFragment123"),
        )
        for cleaner in (evidence.sanitize_text, bottlenecks._safe_text):
            for text, sensitive in cases:
                with self.subTest(cleaner=cleaner.__module__, text=text):
                    self.assertNotIn(sensitive, cleaner(text))

    def test_real_ovat_packet_retains_software_and_later_adf_instruction(self):
        packet = json.loads((ROOT / "results/packets/IRS-29057.json").read_text())
        comments = {str(row["id"]): row for row in packet["timeline"]}
        self.assertIn("1501891", comments)
        self.assertIn("1501934", comments)
        self.assertLess(
            evidence.chronological_key(comments["1501891"]),
            evidence.chronological_key(comments["1501934"]),
        )
        self.assertIn("6.7.17", comments["1501891"]["text"])
        self.assertIn("0.0.9", comments["1501934"]["text"])
        self.assertEqual(packet["evidence_state"], "retrospective_unreviewed_no_new_approval")

    def test_real_packets_distinguish_retrieved_and_displayed_comments(self):
        for path in (ROOT / "results/packets").glob("IRS-*.json"):
            packet = json.loads(path.read_text())
            metadata = packet["current_snapshot"]["completeness"]
            self.assertEqual(metadata["comments"], "collected")
            self.assertEqual(metadata["comments_retrieved"], metadata["comments_reported"])
            self.assertEqual(packet["counts"]["comments_available"], metadata["comments_retrieved"])
            self.assertLessEqual(packet["counts"]["comments_shown"], packet["counts"]["comments_available"])

    def test_real_demo_records_remain_pending_non_executable_and_reproducible(self):
        drafts = json.loads((ROOT / "results/draft-records.json").read_text())
        self.assertEqual(len(drafts), 7)
        for draft in drafts:
            check = intake.validate_record(draft["record"])
            self.assertEqual(check, draft["check"])
            self.assertEqual(check["approval_status"], "pending")
            self.assertFalse(check["human_approval_present"])
            self.assertFalse(check["execution_enabled"])
            self.assertFalse(check["approval_is_authenticated"])

    def test_real_timing_reports_have_no_unobserved_savings_claim(self):
        report = json.loads((ROOT / "results/bottlenecks.json").read_text())
        self.assertEqual(report["timing"]["matched_pairs"], 0)
        self.assertIsNone(report["timing"]["net_active_minutes_saved"])
        self.assertEqual(report["bottleneck_hypothesis"]["confidence"], "hypothesis_not_timed")


if __name__ == "__main__":
    unittest.main()
