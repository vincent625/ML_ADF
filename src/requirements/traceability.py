"""Build traceability matrices from ticket text and controlled artifacts."""

from .extractor import extract_requirements
from .models import Artifact, TraceabilityMatrix


def build_traceability_matrix(
    ticket_text: str,
    *,
    release_id: str,
    version: str | None = None,
    artifacts: list[Artifact] | None = None,
) -> TraceabilityMatrix:
    """Extract requirements and link exact artifact names mentioned in them."""
    known_artifacts = artifacts or []
    requirements = extract_requirements(ticket_text)
    unresolved_items: list[str] = []

    for requirement in requirements:
        requirement.bundle_components = [
            artifact.name
            for artifact in known_artifacts
            if artifact.name.lower() in requirement.statement.lower()
        ]
        if not requirement.bundle_components:
            requirement.ambiguities.append(
                "No controlled bundle artifact was matched; engineer review required"
            )
        if not requirement.mapped_tests:
            unresolved_items.append(f"{requirement.id} has no mapped test")

    if not requirements:
        unresolved_items.append("No explicit numbered requirements were extracted")

    return TraceabilityMatrix(
        release_id=release_id,
        version=version,
        requirements=requirements,
        unresolved_items=unresolved_items,
    )
