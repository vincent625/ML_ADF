import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evidence_packets import build_packets, read_jsonl, sanitize_text, safe_url


class EvidencePacketsTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.base = Path(self.directory.name)
        self.source = self.base / 'source'
        self.output = self.base / 'output'
        self.source.mkdir()
        self.raw = self.source / 'raw.json'
        self.raw.write_text('{"real":true}')
        self.provenance = {'path': 'raw.json',
                           'sha256': hashlib.sha256(self.raw.read_bytes()).hexdigest(),
                           'url': 'https://example.test/browse/IRS-1'}

    def tearDown(self):
        self.directory.cleanup()

    def rows(self, relative, values):
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding='utf-8') as handle:
            for value in values:
                handle.write(json.dumps(value, ensure_ascii=False) + '\n')

    def seed(self, comments=None, actions=None):
        self.rows('data/extracted/issues.jsonl', [
            {'issue_key': 'IRS-1', 'summary': 'Test case',
             'description': 'One\u2028two', 'source': self.provenance,
             'comments': comments or [], 'release_ids': ['release1']}])
        self.rows('data/labels/weak_actions.jsonl', actions or [])
        self.rows('data/extracted/releases.jsonl', [
            {'id': 'release1', 'release_name': 'Historical v0.0.9',
             'listed_issue_keys': ['IRS-1'], 'cutoff_state': 'missing'}])

    def test_json_unicode_line_separator_preserved(self):
        self.seed()
        rows = list(read_jsonl(self.source / 'data/extracted/issues.jsonl'))
        self.assertEqual(rows[0]['description'], 'One\u2028two')

    def test_timeline_retains_distinct_dated_instructions_and_provenance(self):
        self.seed(comments=[
            {'id': 'later', 'created': '2022-06-14T12:00:00+0530',
             'updated': '2022-06-15T00:00:00Z', 'body': 'Removed ruleset in ADF 0.0.9',
             'source': self.provenance},
            {'id': 'earlier', 'created': '2022-05-09T10:00:00Z',
             'updated': '2022-05-09T10:00:00Z', 'body': 'Verify software upgrade',
             'source': self.provenance}])
        before = self.raw.read_bytes()
        packet = build_packets(self.source, self.output, ['IRS-1'])[0]
        self.assertEqual([item['id'] for item in packet['timeline']], ['earlier', 'later'])
        self.assertEqual(packet['timeline'][1]['updated'], '2022-06-15T00:00:00Z')
        self.assertTrue(packet['timeline'][0]['source']['source_hash_matches'])
        self.assertEqual(packet['evidence_state'], 'retrospective_unreviewed_no_new_approval')
        self.assertIn('approval', [item['key'] for item in packet['missing_inputs']])
        self.assertEqual(self.raw.read_bytes(), before)

    def test_url_and_inline_credential_redaction(self):
        text = ('https://someone:secret@example.test/a?token=secret&focusedCommentId=123 '
                '(testadmin/SecretTesting123!) password=hidden Bearer abcdefghijklmnop')
        result = sanitize_text(text)
        for sensitive in ('secret', 'SecretTesting123', 'hidden', 'abcdefghijklmnop'):
            self.assertNotIn(sensitive, result)
        self.assertIn('focusedCommentId=123', result)
        self.assertEqual(safe_url('javascript:alert(1)'), '')
        self.assertEqual(safe_url('https://example.test/x?X-Amz-Signature=abc'), 'https://example.test/x')

    def test_complete_quoted_credentials_are_redacted(self):
        cases = [
            'password="Synthetic Secret With Spaces" keep this context',
            "passwd='Synthetic Secret With Spaces' keep this context",
            '"api_key": "Synthetic Secret With Spaces" keep this context',
            'client_secret="Synthetic \\"Quoted\\" Secret With Spaces" keep this context',
            "authorization='Bearer Synthetic Secret With Spaces' keep this context",
        ]
        for text in cases:
            with self.subTest(text=text):
                result = sanitize_text(text)
                self.assertNotIn('Synthetic', result)
                self.assertNotIn('Secret', result)
                self.assertNotIn('With Spaces', result)
                self.assertIn('[redacted]', result)
                self.assertIn('keep this context', result)

    def test_coverage_counts_and_balanced_bounded_action_selection(self):
        actions = [{'id': str(index), 'issue_key': 'IRS-1', 'category': 'file',
                    'text': 'X' * 1800, 'reviewer_state': 'unreviewed'} for index in range(100)]
        actions += [{'id': 'different', 'issue_key': 'IRS-1', 'category': 'verification',
                     'text': 'A distinct review task'}]
        self.seed(actions=actions)
        packet = build_packets(self.source, self.output, ['IRS-1'])[0]
        self.assertEqual(packet['counts']['actions_available'], 101)
        self.assertEqual(packet['counts']['actions_shown'], 7)
        self.assertEqual(packet['counts']['truncated_actions_shown'], 6)
        self.assertIn('different', [item['id'] for item in packet['proposed_actions']])
        self.assertTrue((self.output / 'IRS-1.md').is_file())
        self.assertIn('Source retrieval status', (self.output / 'IRS-1.md').read_text())

    def test_invalid_keys_and_writes_inside_preserved_source_are_rejected(self):
        self.seed()
        with self.assertRaises(ValueError):
            build_packets(self.source, self.output, ['../../IRS-1'])
        with self.assertRaises(ValueError):
            build_packets(self.source, self.source / 'results', ['IRS-1'])

    def test_absent_issue_and_missing_inputs_remain_explicit(self):
        self.seed()
        packet = build_packets(self.source, self.output, ['IRS-2'])[0]
        self.assertFalse(packet['source_issue_available'])
        self.assertEqual(packet['counts']['comments_available'], 0)
        self.assertTrue(packet['missing_inputs'])
        index = json.loads((self.output / 'index.json').read_text())
        self.assertEqual(index['new_approvals'], 0)
        self.assertEqual(index['executed_changes'], 0)

    def test_output_file_symlink_cannot_overwrite_source(self):
        self.seed()
        self.output.mkdir()
        before = self.raw.read_bytes()
        (self.output / 'IRS-1.json').symlink_to(self.raw)
        with self.assertRaises(ValueError):
            build_packets(self.source, self.output, ['IRS-1'])
        self.assertEqual(self.raw.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
