"""Verify repository file hashes, packaging exclusions, and README image paths."""
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def verify():
    manifest = json.loads((ROOT / 'PACKAGE_MANIFEST.json').read_text())
    errors = []
    for item in manifest['files']:
        relative = PurePosixPath(item['path'])
        if relative.is_absolute() or '..' in relative.parts:
            errors.append('Unsafe manifest path')
            continue
        path = ROOT / str(relative)
        if path.is_symlink() or not path.is_file():
            errors.append('Missing or linked file: ' + str(relative))
        elif path.stat().st_size != item['bytes'] or sha256(path) != item['sha256']:
            errors.append('File mismatch: ' + str(relative))
    images = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', (ROOT / 'README.md').read_text())
    for target in images:
        if '://' in target or target.startswith('/'):
            errors.append('README image must be repository relative: ' + target)
        elif not (ROOT / target).is_file():
            errors.append('Missing README image: ' + target)
    for path in ROOT.rglob('*'):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if '.git' in relative.parts or '__pycache__' in relative.parts:
            continue
        if path.name == '.env' or (path.name.startswith('.env.') and path.name != '.env.example'):
            errors.append('Local credential configuration present: ' + str(relative))
        if path.suffix in {'.joblib', '.pem', '.key'}:
            errors.append('Excluded private or model artifact present: ' + str(relative))
        if path.stat().st_size >= 100 * 1024 * 1024:
            errors.append('File exceeds normal GitHub file-size limit: ' + str(relative))
    return {
        'status': 'passed' if not errors else 'failed',
        'files_checked': len(manifest['files']), 'readme_images_checked': len(images),
        'errors': errors, 'manifest_scope': manifest['scope'],
    }


if __name__ == '__main__':
    result = verify()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['status'] == 'passed' else 1)
