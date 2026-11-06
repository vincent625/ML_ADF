"""Run the packaged component checks from any working directory."""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-sentinel', action='store_true',
                        help='Also run the optional pytest/model stack checks')
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'results/current-checks.json')
    args = parser.parse_args()
    suites = [
        ('requirements', ROOT, [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v']),
        ('review_workbench', ROOT, [sys.executable, '-m', 'unittest', 'discover',
                                  '-s', 'adf-review-workbench/tests', '-v']),
        ('synthetic_evidence_lab', ROOT / 'irs-65265-review',
         [sys.executable, '-W', 'error::ResourceWarning', '-m', 'unittest', 'discover', '-s', 'tests', '-v']),
    ]
    if args.include_sentinel:
        suites.append(('sentinel', ROOT, [
            sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', 'adf-sentinel/tests',
        ]))
    results = []
    for name, cwd, command in suites:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
        env['PYTHONPATH'] = os.pathsep.join([str(ROOT / 'adf-sentinel'), str(cwd), str(ROOT)])
        started = time.monotonic()
        completed = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)
        print(name + ': ' + ('passed' if completed.returncode == 0 else 'FAILED'), flush=True)
        if completed.returncode:
            print(completed.stdout + completed.stderr, flush=True)
        results.append({
            'suite': name, 'status': 'passed' if completed.returncode == 0 else 'failed',
            'return_code': completed.returncode, 'runtime_seconds': round(time.monotonic() - started, 3),
            'command': [Path(command[0]).name] + command[1:],
            'cwd': str(cwd.relative_to(ROOT)) or '.',
            'stdout': completed.stdout, 'stderr': completed.stderr,
        })
    result = {
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'status': 'passed' if all(r['return_code'] == 0 for r in results) else 'failed',
        'scope': 'Local packaged code and synthetic HTTP/model tests; no source-system writes or scientific validation',
        'suites': results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'suites': len(results), 'output': str(args.output)}, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
