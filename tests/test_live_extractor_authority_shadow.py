"""Shadow authority parity for live extractor openings."""
from __future__ import annotations

from pb_live_extractor_authority_shadow import collect_opening_authority_shadow
from pb_planreader_pdf_extractor import ExtractedPrediction


def test_blocked_conflict_opening_recorded_as_shadow_blocked() -> None:
    shadow = collect_opening_authority_shadow(
        [
            ExtractedPrediction(
                tag="D1",
                trade_type="doors",
                description="blocked conflict",
                quantity=None,
                unit="NO",
                confidence=0.0,
                source_page=1,
                dimensions=None,
                metadata={
                    "publication_blocked": True,
                    "reconciliation_status": "conflict_manual_review",
                },
            )
        ]
    )
    assert shadow["blocked_count"] == 1
    assert shadow["publishable_count"] == 0
    assert shadow["openings"][0]["shadow_authority"] == "BLOCKED"


def test_publishable_opening_stays_provisional_in_shadow() -> None:
    shadow = collect_opening_authority_shadow(
        [
            ExtractedPrediction(
                tag="W1",
                trade_type="windows",
                description="live only",
                quantity=4.0,
                unit="NO",
                confidence=0.8,
                source_page=1,
                dimensions=[1200.0, 900.0],
            )
        ]
    )
    assert shadow["publishable_count"] == 1
    assert shadow["openings"][0]["shadow_authority"] == "PROVISIONAL_LIVE_ONLY"
