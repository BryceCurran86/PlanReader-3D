"""Original-source Lot16 frame-pair wire (skips when PDF absent)."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from tools.diag_cursor_lot16_frame_unproven_pair_shadow import (
    LOT16_SHA,
    lot16_frame_unproven_pair_shadow_report,
)

_CANDIDATES = (
    Path(r"C:\Users\bryce\PlanReader-3D\documents\sources")
    / "1. Construction Plans - Lot 16 Power (REV E).pdf",
    Path("documents/sources") / "1. Construction Plans - Lot 16 Power (REV E).pdf",
)


def _lot16_pdf() -> bytes | None:
    for path in _CANDIDATES:
        if path.is_file():
            raw = path.read_bytes()
            if sha256(raw).hexdigest() == LOT16_SHA:
                return raw
    return None


@pytest.mark.slow
def test_lot16_baseline_frame_pair_attach_retains_signed_eight():
    pdf = _lot16_pdf()
    if pdf is None:
        pytest.skip("original Lot16 PDF unavailable")
    report = lot16_frame_unproven_pair_shadow_report(pdf, source_fragment_roles=False)
    assert report["signed_eight_quantity_ids_retained"] is True
    assert report["frame_granted"] is False
    assert report["benchmark_score_granted"] is False
    assert report["first_gate_counts"]["whole_wall_frame_unavailable"] >= 1
    assert report["frame_unproven_pair_attach"]["frame_blocked_openings_with_ledger"] >= 1
