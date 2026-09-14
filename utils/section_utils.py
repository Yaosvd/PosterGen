"""Deterministic section parsing helpers."""

import re
from typing import Any, Dict, List


HEADING_RE = re.compile(
    r"^(#{1,6})\s+(.+?)\s*$",
    re.MULTILINE,
)

NUMBERED_HEADING_RE = re.compile(
    r"^(?:\d+(?:\.\d+)*)\s+"
)


def normalize_heading(title: str) -> str:
    """Normalize a markdown section heading."""
    title = title.strip().strip("#").strip()
    return re.sub(r"\s+", " ", title)


def classify_section_type(title: str) -> str:
    """Map a paper heading to a coarse academic section type."""
    value = normalize_heading(title).lower()
    value = NUMBERED_HEADING_RE.sub("", value)

    if any(
        keyword in value
        for keyword in (
            "abstract",
            "introduction",
            "background",
            "related work",
            "motivation",
            "preliminary",
            "preliminaries",
        )
    ):
        return "foundation"

    if any(
        keyword in value
        for keyword in (
            "method",
            "approach",
            "framework",
            "architecture",
            "algorithm",
            "proposed",
            "model",
        )
    ):
        return "method"

    if any(
        keyword in value
        for keyword in (
            "experiment",
            "evaluation",
            "result",
            "ablation",
            "analysis",
            "benchmark",
        )
    ):
        return "evaluation"

    if any(
        keyword in value
        for keyword in (
            "conclusion",
            "discussion",
            "limitation",
            "future work",
        )
    ):
        return "conclusion"

    if any(
        keyword in value
        for keyword in (
            "appendix",
            "supplement",
        )
    ):
        return "appendix"

    return "other"


def split_markdown_sections(
    markdown: str,
) -> List[Dict[str, Any]]:
    """
    Split Marker-generated markdown by headings.

    This operation is deterministic and does not ask an LLM to infer
    scientific content.
    """
    matches = list(HEADING_RE.finditer(markdown))

    if not matches:
        return [
            {
                "section_id": "section_1",
                "section_name": "Paper",
                "section_type": "other",
                "level": 1,
                "content": markdown.strip(),
                "start_char": 0,
                "end_char": len(markdown),
            }
        ]

    sections: List[Dict[str, Any]] = []

    # Preserve title/authors/abstract-like text before the first heading.
    prefix = markdown[: matches[0].start()].strip()

    if prefix:
        sections.append(
            {
                "section_id": "section_0",
                "section_name": "Front Matter",
                "section_type": "foundation",
                "level": 0,
                "content": prefix,
                "start_char": 0,
                "end_char": matches[0].start(),
            }
        )

    for idx, match in enumerate(matches):
        content_start = match.end()
        content_end = (
            matches[idx + 1].start()
            if idx + 1 < len(matches)
            else len(markdown)
        )

        title = normalize_heading(match.group(2))
        content = markdown[content_start:content_end].strip()

        if not content:
            continue

        sections.append(
            {
                "section_id": f"section_{len(sections) + 1}",
                "section_name": title,
                "section_type": classify_section_type(title),
                "level": len(match.group(1)),
                "content": content,
                "start_char": match.start(),
                "end_char": content_end,
            }
        )

    return sections


def chunk_large_section(
    section: Dict[str, Any],
    max_chars: int = 12000,
) -> List[Dict[str, Any]]:
    """Split unusually long sections without changing their content."""
    content = section["content"]

    if len(content) <= max_chars:
        result = dict(section)
        result["chunk_index"] = 0
        return [result]

    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", content)
        if paragraph.strip()
    ]

    chunks: List[Dict[str, Any]] = []
    current: List[str] = []
    current_len = 0

    for paragraph in paragraphs:
        paragraph_len = len(paragraph) + 2

        if current and current_len + paragraph_len > max_chars:
            chunk = dict(section)
            chunk["content"] = "\n\n".join(current)
            chunk["chunk_index"] = len(chunks)
            chunks.append(chunk)

            current = []
            current_len = 0

        # A single giant paragraph is kept intact rather than silently
        # truncating its scientific content.
        current.append(paragraph)
        current_len += paragraph_len

    if current:
        chunk = dict(section)
        chunk["content"] = "\n\n".join(current)
        chunk["chunk_index"] = len(chunks)
        chunks.append(chunk)

    return chunks


def build_section_chunks(
    markdown: str,
    max_chars: int = 12000,
) -> List[Dict[str, Any]]:
    """Create section-aware chunks for downstream evidence extraction."""
    chunks: List[Dict[str, Any]] = []

    for section in split_markdown_sections(markdown):
        chunks.extend(
            chunk_large_section(
                section,
                max_chars=max_chars,
            )
        )

    return chunks
