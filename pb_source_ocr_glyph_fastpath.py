"""Source OCR glyph fastpath for architectural plans with outlined vector lettering.

When an architectural PDF has CAD-outlined fonts or rasterized labels, native
``page.get_text("words")`` returns only title blocks or margin disclaimers.
This module extracts candidate printed words using the existing RapidOCRBackend
and normalizes them into the standard ``page.get_text("words")`` format:
``(x0, y0, x1, y1, text, block_no, line_no, word_no)``.

It never creates physical walls or authorizes takeoff quantities.
"""

from __future__ import annotations

import io
import math
import re
from typing import Any

from PIL import Image

from pb_portable_raster_ocr_authority import RapidOCRBackend

_ARCH_KEYWORD = re.compile(
    r"^(?:bed|bedroom|living|bath|bathroom|ens|ensuite|kitchen|meals|dining|family|lounge|"
    r"garage|entry|porch|patio|alfresco|balcony|terrace|wip|wir|robe|l'dry|laundry|wc|pwd|study|"
    r"w[- ]?\d+[a-z]*|sd[- ]?\d+|d[- ]?\d+|asw|aw|sgd|stacker)$",
    re.IGNORECASE,
)


def get_source_words_with_glyph_fastpath(
    page: Any,
    *,
    page_index: int = -1,
    dpi: int = 150,
) -> tuple[tuple[float, float, float, float, str, int, int, int], ...]:
    """Return native source words or RapidOCR-extracted glyph lines when native text lacks plan callouts.

    If the page already contains native architectural keywords (e.g. 3Laurel),
    native words are returned directly with zero OCR overhead.
    If native words lack room/window callouts and RapidOCR is available, OCR words
    are extracted and appended.
    """
    try:
        raw_words = page.get_text("words")
        native_words: list[tuple[float, float, float, float, str, int, int, int]] = [
            (
                float(w[0]),
                float(w[1]),
                float(w[2]),
                float(w[3]),
                str(w[4]),
                int(w[5]),
                int(w[6]),
                int(w[7]),
            )
            for w in raw_words
            if len(w) >= 8 and all(map(math.isfinite, (w[0], w[1], w[2], w[3])))
        ]
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, OSError):
        native_words = []

    has_arch_words = any(
        _ARCH_KEYWORD.match(w[4].strip()) for w in native_words
    )
    if has_arch_words:
        return tuple(native_words)

    backend = RapidOCRBackend()
    if not backend.is_available():
        return tuple(native_words)

    try:
        pix = page.get_pixmap(dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        lines = backend.extract_lines(img, dpi=dpi)
    except (AttributeError, RuntimeError, OSError, ValueError, TypeError):
        return tuple(native_words)

    ocr_words: list[tuple[float, float, float, float, str, int, int, int]] = []
    base_idx = len(native_words)

    for line_idx, line in enumerate(lines):
        text = str(line.text or "").strip()
        if not text:
            continue
        bb = line.bbox_pt
        if not (len(bb) == 4 and all(map(math.isfinite, bb)) and bb[2] > bb[0] and bb[3] > bb[1]):
            continue
        # Emit full line text
        ocr_words.append((bb[0], bb[1], bb[2], bb[3], text, 0, line_idx, base_idx + len(ocr_words)))

        # Also emit individual tokens if line is multi-word
        tokens = text.split()
        if len(tokens) > 1:
            total_chars = max(1, sum(len(t) for t in tokens))
            span_x = bb[2] - bb[0]
            cur_x = bb[0]
            for tok_idx, tok in enumerate(tokens):
                tok_len = len(tok)
                frac = tok_len / total_chars
                tok_x1 = cur_x + frac * span_x
                ocr_words.append((
                    cur_x, bb[1], tok_x1, bb[3], tok, 0, line_idx, base_idx + len(ocr_words)
                ))
                cur_x = tok_x1

    return tuple(native_words + ocr_words)
