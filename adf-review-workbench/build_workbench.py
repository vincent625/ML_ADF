"""Assemble a separate review workbench from preserved historical evidence."""
import argparse
import copy
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from bottlenecks import build_report
from evidence_packets import DEFAULT_ISSUES, build_packets, sanitize
from intake import validate_record
from preservation import verify

ROOT = Path(__file__).resolve().parent


def make_drafts(packets):
    template = json.loads((ROOT / 'templates/change_record.json').read_text())
    by_key = {packet['issue_key']: packet for packet in packets}
    specs = [
        ('hotspot-file', 'IRS-65265', 'file_replacement', 'Hotspot file replacement',
         'The historical comment requests a hotspot file. Its immutable revision, hash, destination and current applicability still need confirmation.',
         '2899737'),
        ('panelkit-number', 'IRS-65265', 'parameter_metadata', 'PanelKit part number',
         'The issue requests a PanelKit part-number update. The exact field, current value and replacement value are not supplied by this draft.',
         None),
        ('wrapper-version', 'IRS-66772', 'dependency_pin', 'VNS wrapper version',
         'The description requests VNS wrapper 1.20.6. The previous version, exact destination, package identity and applicability still need confirmation.',
         None),
        ('both-profiles', 'IRS-57322', 'shared_variant_change', 'RNA and DNA profile change',
         'The issue names both primer profiles. Separate target paths and approved values are required for each; equality is not assumed.',
         None),
        ('ovat-investigation', 'IRS-29057', 'investigation', 'Investigate OVAT behavior',
         'Prepare the evidence and diagnostic question. An engineer must confirm the affected release, root cause and acceptance criteria.',
         None),
        ('ovat-verification', 'IRS-29057', 'verification', 'Verify OVAT after upgrade',
         'This dated comment requests software-upgrade verification. Later instructions concern a different ADF revision; confirm which milestone applies.',
         '1501891'),
        ('retain-actor', 'IRS-65265', 'retain_defer_block', 'Retain the actor setting',
         'A historical comment says to retain VariantCallerActor.run=1 in v0.0.3. This remains reference evidence rather than approval for a new release.',
         '2912743'),
    ]
    results = []
    for suffix, key, operation, label, explanation, comment in specs:
        packet = by_key[key]
        record = copy.deepcopy(template)
        url = packet['source_url'] + ('?focusedCommentId=' + comment if comment else '')
        record.update(id=key.lower() + '-' + suffix, issue_key=key, operation=operation,
                      source_links=[url], evidence=[{
                          'kind': 'historical_decision' if suffix == 'retain-actor' else 'source_requirement',
                          'url': url, 'note': explanation,
                      }])
        if suffix == 'hotspot-file':
            record['artifact'] = {
                'source_url': 'https://github.com/thermofisher/csd-motorcore-config-files/blob/main/Motorhead/Oncomine_Focus_v2.20260625.hotspots.bed',
                'revision': None, 'sha256': None,
            }
        elif suffix == 'wrapper-version':
            record['dependency'] = {'package': 'VNS wrapper', 'expected_version': None, 'new_version': '1.20.6'}
        elif suffix == 'both-profiles':
            record['variants'] = ['primer_profile_RNA', 'primer_profile_DNA']
            record['variant_targets'] = [
                {'variant': variant, 'target_path': None, 'field': 'maxSamplePerPool',
                 'expected_old_value': None, 'new_value': None}
                for variant in record['variants']
            ]
        elif suffix == 'ovat-investigation':
            record['question'] = 'What causes the reported incorrect OVAT annotation with alternate coding syntax, and which fix and regression tests apply to the intended release?'
        elif suffix == 'ovat-verification':
            record['question'] = 'Which clean-server software-upgrade test and expected OVAT ruleset results apply to this dated request?'
        elif suffix == 'retain-actor':
            record.update(release='v0.0.3 (historical comment; confirm applicability)',
                          field='VariantCallerActor.run', expected_old_value=1, decision='retain',
                          question='Does the historical retain decision apply to the release now being reviewed?')
        record = sanitize(record)
        results.append({'label': label, 'explanation': explanation,
                        'record': record, 'check': validate_record(record)})
    return results


def build(source_root):
    source_root = Path(source_root).resolve()
    packets = build_packets(source_root, ROOT / 'results/packets', DEFAULT_ISSUES)
    report = build_report(source_root, ROOT / 'results')
    records = make_drafts(packets)
    preservation = verify(ROOT / 'results/preservation-baseline.json')
    if preservation['status'] != 'passed':
        raise ValueError('Preserved campaign integrity check failed')
    (ROOT / 'results/preservation.json').write_text(json.dumps(preservation, indent=2) + '\n')
    data = {
        'generated_at': datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(timespec='seconds'),
        'packets': packets, 'bottlenecks': report, 'records': records,
        'preservation': preservation,
        'team': [
            {'role': 'Agent 1 · evidence', 'title': 'Put the context in one place',
             'result': 'Four real issue packets with source-linked comments, historical instructions, proposed actions and explicit open questions.'},
            {'role': 'Agent 2 · change intake', 'title': 'Make missing details visible',
             'result': 'Seven review drafts checked for exact targets, values, versions, variant scope and approval metadata. No changes executed.'},
            {'role': 'Agent 3 · bottlenecks', 'title': 'Audit the hypothesis and measure',
             'result': 'Audited 4,922 excerpts, flagged 197 review candidates, and prepared matched timing observations without inventing savings.'},
        ],
    }
    (ROOT / 'results/workbench-data.json').write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    # JSON is inert script data. Escaping "<" prevents source text closing the script tag.
    payload = json.dumps(data, ensure_ascii=True).replace('<', r'\u003c').replace('>', r'\u003e').replace('&', r'\u0026')
    html = (ROOT / 'ui.html').read_text().replace('__INLINE_DATA__', payload)
    (ROOT / 'workbench.html').write_text(html)
    (ROOT / 'results/draft-records.json').write_text(json.dumps(records, indent=2, ensure_ascii=False) + '\n')
    summary = {
        'packets': len(packets), 'comments_shown': sum(p['counts']['comments_shown'] for p in packets),
        'actions_shown': sum(p['counts']['actions_shown'] for p in packets),
        'actions_available': sum(p['counts']['actions_available'] for p in packets),
        'drafts': len(records), 'review_ready': sum(r['check']['review_ready'] for r in records),
        'new_approvals': 0, 'executed_changes': 0, 'flagged_excerpts': report['quality_review_flags']['flag_count'],
        'measured_minutes_saved': None, 'preservation': preservation['status'],
    }
    (ROOT / 'results/build-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT.parent / 'adf-sentinel')
    args = parser.parse_args()
    print(json.dumps(build(args.source), indent=2))
