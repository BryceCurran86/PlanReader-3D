"""Replay-only driver for the frozen executable text-integrity validator.

The exact frozen validator blob is stored under a non-``test_`` filename so
pytest does not auto-collect its strict-xfail baseline profile. Direct function
calls below intentionally ignore those xfail marks, equivalent to production
replay with ``--runxfail``. This file is never merged.
"""
from __future__ import annotations

import pytest

from tests import pdf_text_integrity_authority_replay_contract_v2 as validator


ATTACKS = tuple(
    getattr(validator, f"test_attack{index:02d}_{suffix}")
    for index, suffix in (
        (1, "producer_owned_trusted_text_authority_exists"),
        (2, "missing_tounicode_requires_a_narrow_known_encoding_proof"),
        (3, "malformed_cmap_fails_closed"),
        (4, "control_or_unprintable_decoding_fails_closed"),
        (5, "visual_vs_encoded_mismatch_is_not_trusted"),
        (6, "type3_vector_glyph_text_is_quarantined"),
        (7, "later_opaque_occlusion_blocks_text_authority"),
        (8, "fill_before_text_is_not_misclassified_as_later_occlusion"),
        (9, "unresolved_clip_state_cannot_firm_text"),
        (10, "ocr_fallback_cannot_enter_native_text_authority"),
        (11, "low_confidence_caller_ocr_cannot_mint_trusted_text"),
        (12, "caller_ocr_contradiction_cannot_rewrite_native_result"),
        (13, "revision_source_and_snapshot_laundering_are_blocked"),
        (14, "same_string_from_different_source_bytes_has_distinct_receipt"),
        (15, "deterministic_replay_preserves_text_integrity_identity"),
        (16, "trusted_text_alone_does_not_unlock_opening_dimensions"),
    )
)


@pytest.mark.parametrize("attack", ATTACKS, ids=lambda fn: fn.__name__)
def test_frozen_text_integrity_attack_replay(attack) -> None:
    attack()
