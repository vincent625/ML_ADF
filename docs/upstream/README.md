# ADF Sentinel requirements traceability
Hackathon code base for ADF Sentinel.

## Requirements traceability agent

The first application slice extracts explicitly numbered requirements from a
sanitized ticket Markdown file and links exact artifact names from a JSON
manifest. It produces a pending, engineer-reviewable traceability matrix and
does not publish bundles or invent requirements from unstructured prose.

Run it from the repository root:

```bash
python -m src.requirements.cli path/to/ticket.md \
  --release-id ADF-3 \
  --version v0.0.3 \
  --artifacts path/to/artifacts.json \
  --output traceability.json
```

The artifact manifest is a JSON array:

```json
[
  {
    "name": "Oncomine_SVB.bed",
    "source": "https://example.test/Oncomine_SVB.bed",
    "checksum": "md5:...",
    "owner": "release-team",
    "release_targets": ["dna-fusion", "dna-only"]
  }
]
```

Run the tests with:

```bash
python -m unittest discover -s tests -v
```
