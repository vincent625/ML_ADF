"""Verify that this add-on leaves the recorded campaign and supplied project intact."""
import hashlib
import json
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def capture(source_root, original_root, output):
    source_root, original_root = Path(source_root), Path(original_root)
    frozen = json.loads((source_root / 'runs/frozen/manifest.json').read_text())
    files = dict(frozen['source_versions'])
    files.update(frozen['feature_files'])
    files.update({row['path']: row['sha256'] for row in frozen['model_files']})
    for name in ('runs/frozen/manifest.json', 'data/labels/weak_actions.jsonl',
                 'runs/benchmark/final_results.json', 'exports/verification.json'):
        files[name] = sha256(source_root / name)
    receipt = json.loads((source_root / 'exports/verification.json').read_text())
    files['exports/adf-sentinel-evidence.zip'] = receipt['archive_sha256']
    original = {str(p.relative_to(original_root)): sha256(p)
                for p in sorted(original_root.rglob('*')) if p.is_file()}
    result = {'campaign_id': frozen['freeze_id'], 'source_root': str(source_root),
              'original_root': str(original_root), 'campaign_files': files,
              'original_files': original}
    Path(output).write_text(json.dumps(result, indent=2) + '\n')
    return result


def verify(manifest):
    manifest = json.loads(Path(manifest).read_text())
    failures = []
    for group, root_key in (('campaign_files', 'source_root'), ('original_files', 'original_root')):
        for name, expected in manifest[group].items():
            path = Path(manifest[root_key]) / name
            if not path.is_file() or sha256(path) != expected:
                failures.append({'group': group, 'path': name})
    originals = {str(p.relative_to(manifest['original_root']))
                 for p in Path(manifest['original_root']).rglob('*') if p.is_file()}
    extra = sorted(originals - manifest['original_files'].keys())
    result = {'status': 'passed' if not failures and not extra else 'failed',
              'campaign_id': manifest['campaign_id'],
              'campaign_files_checked': len(manifest['campaign_files']),
              'original_files_checked': len(manifest['original_files']),
              'mismatches': failures, 'extra_original_files': extra}
    return result
