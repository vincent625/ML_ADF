"""Conservative extraction of requirements from release-ticket Markdown."""

import re

from .models import Requirement

_REQUIREMENT_HEADING = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:requirement|req(?:uirement)?)[\s:#-]*(\d+(?:\.\d+)*)\s*[:.)-]?\s*(.*?)\s*$",
    re.IGNORECASE,
)
_NUMBERED_ITEM = re.compile(r"^\s*(\d+(?:\.\d+)*)(?:[.)]|\s)\s*(.+?)\s*$")
_BULLET = re.compile(r"^\s*[-*]\s+(.+?)\s*$")


def extract_requirements(ticket_text: str) -> list[Requirement]:
    """Extract explicitly numbered or headed requirements from Markdown.

    The extractor deliberately avoids treating every paragraph as a
    requirement. This keeps the output auditable and sends unstructured
    material to human review instead of inventing acceptance criteria.
    """
    requirements: list[Requirement] = []
    current_source: str | None = None

    for line_number, line in enumerate(ticket_text.splitlines(), start=1):
        match = _REQUIREMENT_HEADING.match(line) or _NUMBERED_ITEM.match(line)
        if match:
            requirement_number, statement = match.groups()
            statement = _clean_statement(statement)
            if statement:
                requirements.append(
                    Requirement(
                        id=f"REQ-{len(requirements) + 1:03d}",
                        statement=statement,
                        source=f"ticket:{requirement_number} (line {line_number})",
                    )
                )
                current_source = requirements[-1].id
            continue

        bullet = _BULLET.match(line)
        if bullet and current_source and _looks_like_detail(bullet.group(1)):
            requirements[-1].ambiguities.append(
                f"Unstructured detail requires review (line {line_number}): "
                f"{_clean_statement(bullet.group(1))}"
            )

    return requirements


def _clean_statement(statement: str) -> str:
    """Normalize Markdown links and trailing whitespace without losing meaning."""
    statement = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", statement)
    return re.sub(r"\s+", " ", statement).strip()


def _looks_like_detail(statement: str) -> bool:
    """Identify bullets that should be reviewed as details, not requirements."""
    return bool(statement.strip()) and not statement.lower().startswith(("note:", "example:"))
