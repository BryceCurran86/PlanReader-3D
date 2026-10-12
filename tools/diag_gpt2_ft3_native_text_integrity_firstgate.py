"""Read-only first failure of native FT2/FT3 schedule text source integrity.

A PyMuPDF native source word or block can identify the place to inspect, but
only the producer-owned text-integrity and material-semantic authorities can
authenticate a definition. This routine never makes that decision.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Sequence


def _token(value: object) -> str:
    return " ".join(str(value or "").upper().split())


def native_finish_schedule_text_first_gates(
    words: Sequence[Any], *, page_id: str = "11"
) -> dict[str, object]:
    """Keep all native title/code blocks and reasons; never choose a winner."""
    grouped: dict[tuple[str, str, int], list[Any]] = {}
    for word in words:
        if (
            getattr(word, "page_id", None) != page_id
            or type(getattr(word, "block_no", None)) is not int
            or word.block_no < 0
            or type(getattr(word, "line_no", None)) is not int
            or word.line_no < 0
            or type(getattr(word, "word_no", None)) is not int
            or word.word_no < 0
            or type(getattr(word, "source_partition_id", None)) is not str
            or not word.source_partition_id
            or type(getattr(word, "observation_id", None)) is not str
            or not word.observation_id
            or type(getattr(word, "text", None)) is not str
        ):
            continue
        grouped.setdefault(
            (word.page_id, word.source_partition_id, word.block_no), []
        ).append(word)

    titles = []
    codes: dict[str, list[dict[str, object]]] = {"FT2": [], "FT3": []}
    for (page, partition, block), raw in sorted(grouped.items()):
        block_words = sorted(
            raw, key=lambda w: (w.line_no, w.word_no, w.observation_id)
        )
        all_tokens = [_token(word.text) for word in block_words]
        whole = " ".join(all_tokens)
        is_title = "INTERNAL FINISHES SCHEDULE" in whole
        present = [code for code in codes if code in all_tokens]
        if not is_title and not present:
            continue
        source_reasons = Counter(
            str(reason) for word in block_words if word.trusted is not True
            for reason in (getattr(word, "reason_codes", ()) or ())
            if isinstance(reason, str) and reason
        )
        trusted_count = sum(word.trusted is True for word in block_words)
        row = {
            "native_page_id": page,
            "original_source_partition_id": partition,
            "original_native_block_no": block,
            "original_native_word_count": len(block_words),
            "source_integrity_trusted_word_count": trusted_count,
            "source_integrity_untrusted_word_count":
                len(block_words) - trusted_count,
            "untrusted_source_first_reasons": dict(sorted(source_reasons.items())),
            "original_word_observation_ids": [
                word.observation_id for word in block_words
            ],
            "native_source_text_preview_diagnostic_only": whole[:350],
            "source_text_block_definition_authenticated_by_this_report": False,
            "source_floor_finish_occurrence_published": False,
        }
        if is_title:
            titles.append(dict(row))
        for code in present:
            codes[code].append(dict(row))

    code_results = {}
    for code, blocks in codes.items():
        gate = (
            "original_native_material_code_block_missing" if not blocks
            else "multiple_original_native_material_code_blocks" if len(blocks) > 1
            else "original_native_material_row_text_integrity_unproven"
            if blocks[0]["source_integrity_untrusted_word_count"]
            else "native_words_trusted_but_material_definition_unverified"
        )
        code_results[code] = {
            "first_unclosed_gate": gate,
            "native_row_blocks_diagnostic_only": blocks,
            "new_material_definition_authenticated": False,
            "new_material_occurrence_published": False,
        }
    return {
        "source_page_id": page_id,
        "native_internal_finish_schedule_title_blocks_diagnostic_only": titles,
        "native_material_code_first_gates_diagnostic_only": code_results,
        "native_schedule_definition_authenticated_by_this_report": False,
        "new_material_occurrences_published": False,
        "diagnostic_only": True,
    }
