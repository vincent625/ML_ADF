"""Data models for the requirements traceability workflow."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Artifact:
    """A controlled source artifact referenced by a release requirement."""

    name: str
    source: str
    checksum: str | None = None
    owner: str | None = None
    release_targets: tuple[str, ...] = ()


@dataclass
class Requirement:
    """An atomic, reviewable release requirement."""

    id: str
    statement: str
    source: str
    bundle_components: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    mapped_tests: list[str] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)
    approval_status: str = "pending"


@dataclass
class TraceabilityMatrix:
    """The reviewable output of requirements extraction."""

    release_id: str
    version: str | None
    requirements: list[Requirement]
    unresolved_items: list[str] = field(default_factory=list)
    approval_status: str = "pending"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return asdict(self)
