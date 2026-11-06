import copy
import hashlib
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from sentinel import BASE, SCENARIOS, Sentinel, digest, evidence, generate, load, save, source_checks, validate


class ReleaseLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.storage = tempfile.TemporaryDirectory(prefix="sentinel-tests-")
        cls.seed = Path(cls.storage.name) / "seed"
        cls.generated = generate(cls.seed)

    @classmethod
    def tearDownClass(cls):
        cls.storage.cleanup()

    def setUp(self):
        import shutil
        self.directory = tempfile.TemporaryDirectory(prefix="sentinel-case-")
        self.root = Path(self.directory.name) / "data"
        shutil.copytree(self.seed, self.root)
        self.engine = Sentinel(self.root)

    def tearDown(self):
        self.directory.cleanup()

    def test_proposed_case_and_correlated_event_thresholds(self):
        self.assertLessEqual(self.generated["tests"], 96)
        self.assertGreater(self.generated["tests"], 50)
        self.assertTrue(500 <= self.generated["fixture_events"] <= 1500)
        events = [json.loads(s) for s in (self.root / "fixture-events.jsonl").read_text().splitlines()]
        runs = {r["id"]: r for r in self.engine.state()["runs"]}
        for event in events:
            self.assertIn(event["run_id"], runs)
            self.assertIn(event["test_id"], {r["id"] for r in runs[event["run_id"]]["results"]})

    def test_all_eight_counterfactuals_and_passing_controls(self):
        expected = load(self.root / "scenario-expectations.json")["failures"]
        for scenario, _, _ in SCENARIOS:
            with self.subTest(scenario=scenario):
                failures = [r["id"] for r in validate(self.root, scenario) if r["status"] == "fail"]
                self.assertEqual(failures, expected[scenario])
        self.engine.parameter_change("stale-pass", "Test Engineer")
        current = self.engine.view("stale-pass")
        self.assertEqual(current["summary"]["stale"], 3)

    def test_runner_independent_of_oracle(self):
        (self.root / "scenario-expectations.json").unlink()
        result = validate(self.root, "wrong-primer")
        self.assertEqual([r["id"] for r in result if r["status"] == "fail"], ["fusion:dna_pool_2"])

    def test_every_reviewed_seeded_fix_changes_behavior(self):
        for scenario, _, _ in SCENARIOS[1:-1]:
            with self.subTest(scenario=scenario):
                failure = next(r for r in validate(self.root, scenario) if r["status"] == "fail")
                proposal = self.engine.preview(scenario, failure["id"])
                self.assertIn("---", proposal["diff"])
                before = self.engine.view(scenario)["latest"]["id"]
                self.engine.apply(proposal["id"], "Test Engineer")
                self.assertEqual(self.engine.view(scenario)["summary"].get("stale"), 1)
                run = self.engine.run(scenario)
                self.assertNotEqual(run["id"], before)
                self.assertTrue(all(r["status"] == "pass" for r in run["results"]))

    def test_named_review_required_and_proposal_single_use(self):
        proposal = self.engine.preview("wrong-primer", "fusion:dna_pool_2")
        with self.assertRaises(ValueError):
            self.engine.apply(proposal["id"], "")
        self.engine.apply(proposal["id"], "Engineer")
        with self.assertRaises(ValueError):
            self.engine.apply(proposal["id"], "Engineer")

    def test_patch_rejects_file_changed_since_review(self):
        proposal = self.engine.preview("wrong-primer", "fusion:dna_pool_2")
        target = self.root / "fixtures/wrong-primer/fusion/manifest.json"
        target.write_text(target.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "changed since preview"):
            self.engine.apply(proposal["id"], "Engineer")

    def test_qc_suppression_and_completed_msi_qcfail_are_distinct(self):
        results = validate(self.root, "control")
        for variant in ("dna", "fusion"):
            suppression = next(r for r in results if r["id"] == f"{variant}:suppressed")
            msi = next(r for r in results if r["id"] == f"{variant}:msi-qcfail")
            self.assertEqual(suppression["status"], "pass")
            self.assertEqual(msi["status"], "pass")
            self.assertIn('"sample_qc": "fail"', msi["detail"])
            self.assertEqual(msi["execution_mode"], "simulated_pipeline_behavior")

    def test_no_invented_mapd_boundary(self):
        path = self.root / "fixtures/control/dna/outputs.json"
        data = load(path)
        data["suppressed"]["mapd"] = 0.5
        save(path, data)
        results = validate(self.root, "control")
        self.assertEqual(next(r for r in results if r["id"] == "dna:suppressed")["status"], "pass")

    def test_selective_invalidation_and_parameter_fix_retest(self):
        before = self.engine.view("stale-pass")
        change = self.engine.parameter_change("stale-pass", "Engineer")
        self.assertEqual(len(change["invalidated_tests"]), 3)
        after = self.engine.view("stale-pass")
        self.assertEqual(after["summary"]["pass"], before["summary"]["pass"] - 3)
        self.assertTrue(all(r["requirement"] == "R18" for r in after["latest"]["results"] if r["status"] == "stale"))
        self.assertEqual(load(self.root / "contracts/control.json")["fusion_threshold"], "0.001")
        run = self.engine.run("stale-pass")
        failures = [r for r in run["results"] if r["status"] == "fail"]
        self.assertEqual([r["id"] for r in failures], ["fusion:fusion-threshold"])
        patch = self.engine.preview("stale-pass", failures[0]["id"])
        self.engine.apply(patch["id"], "Engineer")
        self.assertTrue(all(r["status"] == "pass" for r in self.engine.run("stale-pass")["results"]))

    def test_byte_hash_is_independent_of_declared_ticket_md5(self):
        path = self.root / "fixtures/control/dna/CNV"
        baseline = next(path.glob("*.h5"))
        baseline.write_bytes(b"tampered")
        results = validate(self.root, "control")
        self.assertEqual(next(r for r in results if r["id"] == "dna:R12-bytes")["status"], "fail")
        self.assertEqual(next(r for r in results if r["id"] == "dna:R12-declared_md5")["status"], "pass")

    def test_fixture_md5_matches_actual_synthetic_bytes(self):
        for variant in ("dna", "fusion"):
            folder = self.root / "fixtures/control" / variant
            manifest = load(folder / "manifest.json")
            for asset in manifest["assets"].values():
                content = (folder / asset["file"]).read_bytes()
                self.assertEqual(asset["fixture_md5"], hashlib.new("md5", content).hexdigest())

    def test_both_alignment_sources_independently_checked(self):
        result = {r["id"]: r for r in validate(self.root, "repair-flag")}
        self.assertEqual(result["fusion:AnalysisArgs.ini"]["status"], "fail")
        self.assertEqual(result["fusion:TmapExecutionActor.ini"]["status"], "pass")

    def test_real_evidence_not_modified_by_source_check(self):
        names = ["source-check-results.json", "github-review-data.json", "requirements-candidates.json"]
        before = {n: digest((BASE / n).read_bytes()) for n in names}
        observed = source_checks()
        self.assertEqual(observed["observed"], 10)
        self.assertEqual(before, {n: digest((BASE / n).read_bytes()) for n in names})

    def test_source_counts_reconcile_and_states_remain_candidates(self):
        data = evidence()
        self.assertEqual(len(data["requirements"]), 20)
        self.assertEqual(len(data["ai_replay"]), 10)
        self.assertEqual(len(data["links"]), len({r["url"] for r in data["links"]}))
        self.assertEqual(data["url_counts"], data["coverage"]["url_types"])
        self.assertEqual([r["inventory_count"] for r in data["prs"]], [47, 46, 10])
        states = {r["id"]: r["state"] for r in data["requirements"]}
        self.assertEqual(states["R05"], "cancelled")
        self.assertEqual(states["R06"], "inherited")
        self.assertIn("historical", states["R15"])
        self.assertIn("Motorhead", next(r for r in data["requirements"] if r["id"] == "R09")["expected"]["decision"])

    def test_export_matches_exact_current_run_and_preserves_history(self):
        self.engine.run("wrong-primer")
        view = self.engine.view("wrong-primer")
        export = self.engine.export("wrong-primer")
        self.assertEqual(export["sandbox"]["latest"], view["latest"])
        self.assertEqual(export["sandbox"]["summary"], dict(Counter(r["status"] for r in view["latest"]["results"])))
        self.assertEqual(len(export["evidence"]["history"]), 16)
        self.assertIsNone(export["savings"]["production_savings"])
        self.assertEqual(export, load(self.root / "exports/wrong-primer-evidence.json"))

    def test_non_installable_bundle_hashes_match_fixture_bytes(self):
        import zipfile
        archive = self.engine.bundle("control")
        with zipfile.ZipFile(archive) as handle:
            self.assertIn("NON-INSTALLABLE", handle.read("NOT_AN_ADF.txt").decode())
            for name in handle.namelist():
                if name != "NOT_AN_ADF.txt":
                    self.assertEqual(handle.read(name), (self.root / "fixtures/control" / name).read_bytes())

    def test_reset_reproducible_fixture_bytes_and_source_preservation(self):
        original = digest((BASE / "requirements-candidates.json").read_bytes())
        before = digest((self.root / "fixtures/control/dna/manifest.json").read_bytes())
        copied_fixture = self.root / "fixtures/wrong-primer/fusion/manifest.json"
        copied_before = copied_fixture.read_bytes()
        copied_fixture.write_text("{}\n")
        self.engine.parameter_change("control", "Engineer")
        generate(self.root)
        self.assertEqual(before, digest((self.root / "fixtures/control/dna/manifest.json").read_bytes()))
        self.assertEqual(copied_before, copied_fixture.read_bytes())
        self.assertEqual(original, digest((BASE / "requirements-candidates.json").read_bytes()))
        self.assertEqual(self.engine.view("control")["contract"]["fusion_threshold"], "0.001")

    def test_unknown_scenario_and_unsafe_reference_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.view("../../escape")
        data = load(self.root / "fixtures/control/dna/manifest.json")
        data["assets"]["R12"]["file"] = "../../../../outside"
        save(self.root / "fixtures/control/dna/manifest.json", data)
        with self.assertRaisesRegex(ValueError, "escapes"):
            validate(self.root, "control")


if __name__ == "__main__":
    unittest.main()
