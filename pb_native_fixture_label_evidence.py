"""Conservative native-PDF fixture-label evidence helpers.

This module recovers standalone drawing labels from PyMuPDF's structured text
representation without treating page-wide keyword presence as an instance
count.  It is deliberately narrow: a span contributes only when the span's
entire normalized text is a supported fixture identity.

The helper does not read benchmark data, infer missing fixtures, or convert
prose/specification notes into counts.  Bounding boxes are used only to avoid
counting duplicate renderings of the same native text object twice.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any


_CHALKBOARD_LABEL_RE = re.compile(
    r"(?:chalk\s*board|chalkboard|black\s*board|blackboard)",
    re.IGNORECASE,
)


def _normalized_standalone_label(value: Any) -> str | None:
    """Return conservative label text only when the whole span is a fixture identity."""
    if not isinstance(value, str):
        return None
    normalized = value.strip().strip(":-.").strip()
    if not normalized or _CHALKBOARD_LABEL_RE.fullmatch(normalized) is None:
        return None
    return re.sub(r"\s+", " ", normalized.casefold())


def _bbox_key(value: Any) -> tuple[float, float, float, float] | None:
    """Return a stable four-coordinate bbox key, or None when unusable."""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    if len(value) < 4:
        return None
    try:
        return tuple(round(float(value[index]), 4) for index in range(4))
    except (TypeError, ValueError):
        return None


def count_standalone_chalkboard_spans(text_dict: Mapping[str, Any] | None) -> int:
    """Count independently positioned standalone chalkboard labels.

    ``text_dict`` is the structure returned by ``page.get_text("dict")``.
    Only exact standalone label spans count.  Prose, dimensioned notes,
    malformed structures, and unsupported text fail closed.

    Duplicate rendering of the same label at the same bbox counts once.  When
    bbox evidence is absent, repeated identical span text is conservatively
    treated as one unresolved label rather than multiplied.
    """
    if not isinstance(text_dict, Mapping):
        return 0
    blocks = text_dict.get("blocks")
    if not isinstance(blocks, Sequence) or isinstance(blocks, (str, bytes)):
        return 0

    witnessed: set[tuple[str, tuple[float, float, float, float] | None]] = set()
    try:
        for block in blocks:
            if not isinstance(block, Mapping):
                continue
            lines = block.get("lines")
            if not isinstance(lines, Sequence) or isinstance(lines, (str, bytes)):
                continue
            for line in lines:
                if not isinstance(line, Mapping):
                    continue
                spans = line.get("spans")
                if not isinstance(spans, Sequence) or isinstance(spans, (str, bytes)):
                    continue
                for span in spans:
                    if not isinstance(span, Mapping):
                        continue
                    label = _normalized_standalone_label(span.get("text"))
                    if label is None:
                        continue
                    witnessed.add((label, _bbox_key(span.get("bbox"))))
    except (TypeError, ValueError):
        return 0

    return len(witnessed)
