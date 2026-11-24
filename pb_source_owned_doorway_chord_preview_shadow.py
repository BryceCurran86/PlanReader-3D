"""Shadow channel: source-owned doorway chords beside the canonical preview (default-off, never applied to the preview).

Why this exists. The canonical preview's ring builder (``pb_next_wall_ring_preview``) is a separate module. It has no merged collinear
dark-face collector and no segmented-swing producer, so it cannot see the walls of most source doors, and its result type has no
chord fields (P2c architecture note, sections 1.2 and 1.5). The layered module's dark-painted builder already recovers the reviewed
doorway chords on the same rows. This module runs that builder on the rows the preview scoped and reports its swing witnesses and
chords as counts plus topology-only receipts.

Nothing here reaches the preview's rings, closures, strips or overlay. It is read-only evidence: never a wall, an opening, a closure,
a quantity or a score, and it only runs when the caller asks for it. A page whose native vectors are not architectural (a tiled raster
underlay) never reaches the builder. An upstream chord that claims any authority makes the block abstain instead of being echoed.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from pb_layered_wall_doorway_room_ring_shadow import (
    build_layered_wall_doorway_room_rings as _build_layered_rings,
)
from pb_migration_contracts import stable_contract_id

SCHEMA_VERSION = "1.0.0"
PRODUCER = "pb_layered_wall_doorway_room_ring_shadow.build_layered_wall_doorway_room_rings(dark_painted_wall_source=True)"
INPUT_ROWS = "source rows after the outlined-lettering scope (the rows the preview's own source selector receives)"
REASON_NATIVE_VECTORS_NOT_ARCHITECTURAL = "native_vector_rows_not_architectural_on_raster_underlay_page"
REASON_UPSTREAM_CHORD_CLAIMS_AUTHORITY = "upstream_doorway_chord_claims_authority"

_RECEIPT_PREFIX = "source_owned_doorway_chord_shadow"
_AUTHORITY_FLAGS = ("source_physical_door_host_authenticated", "metric_area_issued", "commercial_publishable")
_PATH_FIELDS = (
    "source_swing_native_path_indices",
    "source_wall_end_left_path_indices",
    "source_wall_end_right_path_indices",
    "source_jamb_left_path_indices",
    "source_jamb_right_path_indices",
    "source_threshold_path_indices",
)


def _boxes(viewport_pdf_pts: Sequence[Sequence[float]] | None) -> list[tuple[float, float, float, float]] | None:
    if viewport_pdf_pts is None:
        return None
    boxes = []
    for box in viewport_pdf_pts:
        values = tuple(float(v) for v in box)
        if len(values) != 4 or not all(math.isfinite(v) for v in values):
            raise ValueError("viewport_pdf_pts must be a sequence of finite (x0, y0, x1, y1) boxes")
        boxes.append((min(values[0], values[2]), min(values[1], values[3]), max(values[0], values[2]), max(values[1], values[3])))
    return boxes


def _door_rect(horizontal: bool, band: tuple[float, float], interval: tuple[float, float]) -> tuple[float, float, float, float]:
    return (interval[0], band[0], interval[1], band[1]) if horizontal else (band[0], interval[0], band[1], interval[1])


def _inside_any(rect: tuple[float, float, float, float], boxes: list[tuple[float, float, float, float]]) -> bool:
    x0, y0, x1, y1 = rect
    return any(bx0 <= x0 and x1 <= bx1 and by0 <= y0 and y1 <= by1 for bx0, by0, bx1, by1 in boxes)


def _receipt(
    chord: Mapping[str, Any], *, source_sha256: str, page_index: int, boxes: list[tuple[float, float, float, float]] | None,
) -> dict[str, Any]:
    horizontal = bool(chord["horizontal"])
    band = (float(chord["wall_band_pdf_pts"][0]), float(chord["wall_band_pdf_pts"][1]))
    interval = (float(chord["door_interval_pdf_pts"][0]), float(chord["door_interval_pdf_pts"][1]))
    swing = sorted(int(i) for i in chord["source_swing_native_path_indices"])
    receipt: dict[str, Any] = {
        "receipt_id": stable_contract_id(
            _RECEIPT_PREFIX,
            {
                "source_sha256": source_sha256,
                "page_index": page_index,
                "horizontal": horizontal,
                "band": [round(v, 3) for v in band],
                "interval": [round(v, 3) for v in interval],
                "swing": swing,
            },
            digest_chars=24,
        ),
        "horizontal": horizontal,
        "wall_band_pdf_pts": [band[0], band[1]],
        "door_interval_pdf_pts": [interval[0], interval[1]],
    }
    for name in _PATH_FIELDS:
        receipt[name] = sorted(int(i) for i in chord[name])
    receipt.update({
        "inside_requested_viewport": None if boxes is None else _inside_any(_door_rect(horizontal, band, interval), boxes),
        "candidate_topology_doorway_closure": True,
        "source_physical_door_host_authenticated": False,
        "metric_area_issued": False,
        "commercial_publishable": False,
        "applied_to_preview_topology": False,
    })
    return receipt


def _block(
    *, source_sha256: str, page_index: int, boxes: list[tuple[float, float, float, float]] | None, builder_called: bool,
    builder_status: str, reason_codes: Sequence[str], witness_count: int, chords: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "producer": PRODUCER,
        "input_rows": INPUT_ROWS,
        "source_sha256": source_sha256,
        "page_index": page_index,
        "viewport_pdf_pts": None if boxes is None else [list(box) for box in boxes],
        "builder_called": builder_called,
        "builder_status": builder_status,
        "builder_reason_codes": list(reason_codes),
        "swing_witness_count": witness_count,
        "chord_count": len(chords),
        "witnesses_without_chord_count": max(0, witness_count - len(chords)),
        "chords": chords,
        "applied_to_preview_topology": False,
        "preview_rings_and_closures_unchanged": True,
        "quantity_authorized": False,
        "commercial_publishable": False,
    }


def source_owned_doorway_chord_shadow(
    rows: Sequence[Mapping[str, Any]],
    *,
    source_sha256: str,
    page_index: int,
    viewport_pdf_pts: Sequence[Sequence[float]] | None = None,
    native_vector_rows_architectural: bool = True,
) -> dict[str, Any]:
    """Counts and topology-only receipts of the source-owned doorway chords the layered dark-painted builder recovers on ``rows``.

    ``rows`` are the page's native drawing rows after the preview's outlined-lettering scope; they are never mutated. The block is
    deterministic, JSON-plain and says in plain flags that it was not applied to the preview, is no quantity and is not publishable.
    ``viewport_pdf_pts`` (boxes in the native frame, as the preview records them) only labels each chord ``inside_requested_viewport``;
    it never filters the builder's rows. With ``native_vector_rows_architectural=False`` (a tiled raster underlay page) the builder is
    not called and the block abstains with a reason.
    """
    if type(native_vector_rows_architectural) is not bool:
        raise ValueError("native_vector_rows_architectural must be an explicit boolean")
    if type(source_sha256) is not str or len(source_sha256) != 64 or any(c not in "0123456789abcdef" for c in source_sha256):
        raise ValueError("source_sha256 must be a 64-char lowercase hex digest")
    if type(page_index) is not int or page_index < 0:
        raise ValueError("page_index must be a non-negative int")
    boxes = _boxes(viewport_pdf_pts)
    if not native_vector_rows_architectural:
        return _block(
            source_sha256=source_sha256, page_index=page_index, boxes=boxes, builder_called=False, builder_status="abstained",
            reason_codes=(REASON_NATIVE_VECTORS_NOT_ARCHITECTURAL,), witness_count=0, chords=[],
        )
    result = _build_layered_rings(rows, source_sha256=source_sha256, page_index=page_index, dark_painted_wall_source=True)
    upstream = list(result.source_owned_doorway_chords)
    if any(chord.get(flag) is not False for chord in upstream for flag in _AUTHORITY_FLAGS):
        return _block(
            source_sha256=source_sha256, page_index=page_index, boxes=boxes, builder_called=True, builder_status="abstained",
            reason_codes=(REASON_UPSTREAM_CHORD_CLAIMS_AUTHORITY,), witness_count=len(result.source_segmented_swing_witnesses), chords=[],
        )
    receipts = [_receipt(chord, source_sha256=source_sha256, page_index=page_index, boxes=boxes) for chord in upstream]
    receipts.sort(key=lambda r: (r["door_interval_pdf_pts"], r["wall_band_pdf_pts"], r["source_swing_native_path_indices"], r["horizontal"]))
    return _block(
        source_sha256=source_sha256, page_index=page_index, boxes=boxes, builder_called=True, builder_status=result.status.value,
        reason_codes=result.reason_codes, witness_count=len(result.source_segmented_swing_witnesses), chords=receipts,
    )
