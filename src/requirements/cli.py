"""Command-line entry point for the requirements traceability agent."""

import argparse
import json
from pathlib import Path

from .models import Artifact
from .traceability import build_traceability_matrix


def main() -> None:
    """Read a ticket and artifact manifest, then emit a traceability matrix."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticket", type=Path, help="Ticket Markdown file")
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--version")
    parser.add_argument(
        "--artifacts",
        type=Path,
        help="JSON array containing name, source, checksum, owner, and release_targets",
    )
    parser.add_argument("--output", type=Path, help="Write JSON to this file")
    args = parser.parse_args()

    artifact_data = json.loads(args.artifacts.read_text()) if args.artifacts else []
    artifacts = [Artifact(**item) for item in artifact_data]
    matrix = build_traceability_matrix(
        args.ticket.read_text(),
        release_id=args.release_id,
        version=args.version,
        artifacts=artifacts,
    )
    output = json.dumps(matrix.to_dict(), indent=2) + "\n"
    if args.output:
        args.output.write_text(output)
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
