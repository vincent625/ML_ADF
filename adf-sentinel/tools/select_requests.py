import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--limit", type=int, default=100)
parser.add_argument("--operation", action="append", default=[])
args = parser.parse_args()
if not 1 <= args.limit <= 2000:
    raise SystemExit("Choose an explicit batch size from 1 to 2000")
root = Path(__file__).resolve().parents[1]
queue = json.loads((root / "data/collection_queue.json").read_text())
selected = [j for j in queue if not args.operation or j["operation"] in args.operation][:args.limit]
print(json.dumps(selected))
