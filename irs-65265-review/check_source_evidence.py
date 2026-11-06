"""Inspect captured PR evidence; this does not validate an installed ADF."""
from pathlib import Path
import json
import re

BASE = Path(__file__).resolve().parent
data = json.loads((BASE / 'github-review-data.json').read_text())
checks = []

def patch(kind, suffix):
    return next(f['patch'] or '' for f in data[kind]['selected_patch_evidence']
                if f['path'].endswith(suffix))

def added(text):
    return '\n'.join(l[1:] for l in text.splitlines() if l.startswith('+') and not l.startswith('+++'))

def record(identifier, label, result, scope):
    checks.append({'id': identifier, 'check': label, 'result': 'observed' if result else 'not_observed',
                   'scope': scope, 'evidence_level': 'source_only_not_deployed_bundle_validation'})

for kind in ['dna', 'fusion']:
    record(kind + '-kit', 'DNA panel kit A40014056 present in added source',
           'A40014056' in added(patch(kind, '/KitPart.json')), kind)
    pools = added(patch(kind, '/KitConsumable.json'))
    record(kind + '-primers', 'DNA primer part numbers 100200225 and 100200226 present',
           all(p in pools for p in ['100200225', '100200226']), kind)
    tmap = added(patch(kind, '/TmapExecutionActor.ini'))
    alignment = added(patch(kind, '/AnalysisArgs.ini'))
    record(kind + '-tmap', 'Repair flag removed from actor and AnalysisArgs source settings',
           'tmap.custom.tmap.args=' in tmap and '--repair-min-freq' not in tmap
           and 'AnalysisArgs=' in alignment and '--repair-min-freq' not in alignment, kind)
    record(kind + '-hotspot-declaration', 'Declared hotspot MD5 matches ticket value',
           '0dd74ce6ac67b1a1be4784d0f745c749' in added(patch(kind, '/Region-Hotspot.json')),
           kind + ': declaration checked; actual BED bytes not hashed')

fusion_text = data['fusion_parameter_snapshot']['content']
params = dict(l.split('=', 1) for l in fusion_text.splitlines() if '=' in l and not l.startswith('#'))
record('fusion-normalized-threshold', 'Fusion non-targeted normalized threshold equals 0.001',
       params.get('fusions.min.normalized.read.count.non.targeted') == '0.001', 'fusion pinned PR head')

monitored = ['Pipeline/bin/MSI_IR', 'Pipeline/bin/copynumber_exon_finalize.py',
             'Pipeline/bin/copynumber_exon_plots.py',
             'CNV/Oncomine_Focus_v2_4.0.20260903_Manticore_cnv.h5',
             'TVC_Mask_Bed/Oncomine_Focus_v2_Gx_hg19_09_03_2026.msi.h5']
shared = {v['path']: v for v in data['shared_component_comparison']}
record('shared-components', 'Five monitored common components have matching Git blob IDs',
       all(p in shared and shared[p]['sameGitBlob'] for p in monitored),
       'GitHub PR file metadata; this does not establish scientific equivalence')

result = {'scope': 'Captured release PR source evidence only',
          'not_performed': ['Assembling or installing the released ZIPs', 'Instrument testing',
                            'Running the full Genexus pipeline', 'Hashing the binary baselines against ticket MD5 values'],
          'observed': sum(c['result'] == 'observed' for c in checks), 'total': len(checks), 'checks': checks}
(BASE / 'source-check-results.json').write_text(json.dumps(result, indent=2))
print(json.dumps({'observed': result['observed'], 'total': result['total'], 'scope': result['scope']}))
if result['observed'] != result['total']:
    raise SystemExit(1)
