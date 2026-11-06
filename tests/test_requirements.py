"""New handoff checks for the unchanged upstream requirements slice."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.requirements.extractor import extract_requirements
from src.requirements.models import Artifact
from src.requirements.traceability import build_traceability_matrix

ROOT = Path(__file__).resolve().parents[1]


class RequirementsHandoffTests(unittest.TestCase):
    def test_unnumbered_material_stays_unresolved(self):
        result = build_traceability_matrix('Please consider a future change.', release_id='DEMO')
        self.assertEqual(result.requirements, [])
        self.assertIn('No explicit numbered requirements were extracted', result.unresolved_items)
        self.assertEqual(result.approval_status, 'pending')

    def test_numbered_items_preserve_source_and_unstructured_details(self):
        result = extract_requirements('Requirement 7: Review actor.ini\n- Confirm release scope\n2. Verify a result\n')
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].source, 'ticket:7 (line 1)')
        self.assertIn('requires review', result[0].ambiguities[0])
        self.assertEqual(result[0].approval_status, 'pending')

    def test_manifest_names_do_not_verify_bytes_or_map_tests(self):
        artifact = Artifact(name='actor.ini', source='https://example.test/actor.ini', checksum='sha256:unverified')
        result = build_traceability_matrix('1. Review actor.ini', release_id='DEMO', artifacts=[artifact])
        self.assertEqual(result.requirements[0].bundle_components, ['actor.ini'])
        self.assertEqual(result.requirements[0].mapped_tests, [])
        self.assertEqual(result.requirements[0].dependencies, [])
        self.assertEqual(result.approval_status, 'pending')
        self.assertIn('REQ-001 has no mapped test', result.unresolved_items)

    def test_documented_cli_runs_from_the_relocated_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / 'traceability.json'
            result = subprocess.run([
                sys.executable, '-m', 'src.requirements.cli', 'examples/ticket.md',
                '--release-id', 'IRS-65265-DEMO', '--version', 'v0.0.3',
                '--artifacts', 'examples/artifacts.json', '--output', str(destination),
            ], cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            matrix = json.loads(destination.read_text())
            self.assertEqual(len(matrix['requirements']), 3)
            self.assertEqual(matrix['approval_status'], 'pending')
            self.assertTrue(all(row['approval_status'] == 'pending' for row in matrix['requirements']))
            self.assertEqual(matrix['requirements'][0]['bundle_components'], ['TmapExecutionActor.ini'])
            self.assertEqual(matrix['requirements'][1]['bundle_components'], ['Oncomine_Focus_v2.20260625.hotspots.bed'])
            self.assertTrue(all(not row['mapped_tests'] for row in matrix['requirements']))


if __name__ == '__main__':
    unittest.main()
