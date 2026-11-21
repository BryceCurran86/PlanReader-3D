"""Review-only: source-native internal door apertures <-> canonical opening representatives.

One physical internal door aperture can be represented by several canonical
opening records (G17 combines every face and jamb pairing it finds). Nothing
today says which records belong to which source-native door symbol, so a door
mark can never reach kind, host or metric authority. This module answers ONE
question from existing evidence only: which canonical records lie inside the
aperture box of each source-native swing or cavity-slider symbol, and which
existing gate stops that aperture first.

It never ranks, chooses, merges or deletes a representative, never writes a
kind, host, frame, area or quantity, and never treats a symbol as a physical
opening. Every authority flag is False by construction. It adds no geometry
rule: aperture boxes come from the existing internal swing barrier and
cavity-slider detectors, and the containment rule is the one the merged window
and sliding-aperture reviews use.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pb_live_physical_opening_void_composition import LiveCanonicalOpeningObject
from pb_migration_contracts import stable_contract_id
from pb_source_internal_door_completeness_shadow import (
    inspect_source_internal_door_completeness,
)
from pb_source_internal_swing_room_barrier import (
    detect_source_internal_swing_room_barriers,
)
from pb_source_native_cavity_slider_jamb_shadow import (
    match_source_native_cavity_sliders,
)

INTERNAL_DOOR_APERTURE_REVIEW_SCHEMA_VERSION = "1.0.0"
INTERNAL_DOOR_APERTURE_REVIEW_STATUS = "INTERNAL_DOOR_APERTURE_REVIEW_ONLY"
INTERNAL_DOOR_APERTURE_REVIEW_ABSTAINED = "ABSTAINED"

# Same absolute containment margin as pb_original_window_canonical_representative_review
# (kept local so a change there cannot silently change this review; a test guards parity).
CONTAINMENT_TOLERANCE_PT = 1.25

SYMBOL_HINGED_SWING = "hinged_swing"
SYMBOL_CAVITY_SLIDER = "cavity_slider"

STATE_NO_APERTURE_BOX = "NO_APERTURE_BOX_HOST_UNPROVEN"
STATE_NO_REPRESENTATIVE = "NO_CANONICAL_REPRESENTATIVE"
STATE_SINGLE = "SINGLE_CANONICAL_REPRESENTATIVE_REVIEW_ONLY"
STATE_MULTIPLE = "MULTIPLE_CANONICAL_REPRESENTATIVES_RETAINED"
STATE_SHARED = "SHARED_CANONICAL_REPRESENTATIVE_CONFLICT"

# Gate names reuse pb_original_opening_area_gate_diagnostics.REASON_CODES where one exists.
GATE_NO_APERTURE_BOX = "aperture_host_unproven"
GATE_NO_REPRESENTATIVE = "no_canonical_representative"
GATE_SHARED = "shared_representative_conflict"
GATE_KIND_CONFLICT = "kind_conflict_with_source_symbol"
GATE_KIND = "opening_kind_unresolved"
GATE_HOST_WALL = "opening_host_wall_missing"
GATE_HOST_RECEIPT = "opening_host_binding_or_frame_missing"
GATE_AREA = "positive_measured_area_missing"
GATE_BASIS = "opening_measurement_basis_missing"
GATE_ISSUER = "all_observable_gates_present_existing_issuer_decides"

REASON_MIXED_SCOPE = "canonical_openings_mixed_source_scope"

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class InternalDoorApertureEntry:
    entry_id: str
    symbol_kind: str
    mark_status: str
    aperture_bounds_pdf_pts: tuple[float, float, float, float] | None
    native_path_ids: tuple[int, ...]
    printed_width_mm: int | None
    representative_ids: tuple[str, ...]
    shared_representative_ids: tuple[str, ...]
    state: str
    kinds_on_representatives: tuple[str, ...]
    representatives_with_door_kind: int
    representatives_with_host_wall: int
    representatives_with_host_receipt: int
    representatives_with_positive_area: int
    representatives_with_area_basis: int
    first_open_gate: str
    physical_opening_authenticated: bool = False
    kind_authorized: bool = False
    host_authorized: bool = False
    measurement_authorized: bool = False
    customer_quantity_authorized: bool = False
    frozen_benchmark_scored: bool = False

    def __post_init__(self) -> None:
        for name in (
            "physical_opening_authenticated", "kind_authorized", "host_authorized",
            "measurement_authorized", "customer_quantity_authorized", "frozen_benchmark_scored",
        ):
            if getattr(self, name) is not False:
                raise ValueError("internal_door_aperture_entry_cannot_carry_authority")

    def to_dict(self) -> dict[str, object]:
        return {
            "entry_id": self.entry_id,
            "symbol_kind": self.symbol_kind,
            "mark_status": self.mark_status,
            "aperture_bounds_pdf_pts": (
                list(self.aperture_bounds_pdf_pts) if self.aperture_bounds_pdf_pts else None
            ),
            "native_path_ids": list(self.native_path_ids),
            "printed_width_mm": self.printed_width_mm,
            "representative_ids": list(self.representative_ids),
            "shared_representative_ids": list(self.shared_representative_ids),
            "state": self.state,
            "kinds_on_representatives": list(self.kinds_on_representatives),
            "representatives_with_door_kind": self.representatives_with_door_kind,
            "representatives_with_host_wall": self.representatives_with_host_wall,
            "representatives_with_host_receipt": self.representatives_with_host_receipt,
            "representatives_with_positive_area": self.representatives_with_positive_area,
            "representatives_with_area_basis": self.representatives_with_area_basis,
            "first_open_gate": self.first_open_gate,
            "physical_opening_authenticated": False,
            "kind_authorized": False,
            "host_authorized": False,
            "measurement_authorized": False,
            "customer_quantity_authorized": False,
            "frozen_benchmark_scored": False,
        }


@dataclass(frozen=True)
class InternalDoorApertureReview:
    status: str
    reason_codes: tuple[str, ...]
    source_sha256: str
    page_index: int
    entries: tuple[InternalDoorApertureEntry, ...] = ()
    in_scope_record_count: int = 0
    out_of_scope_record_count: int = 0
    records_bound_to_an_aperture: int = 0
    records_shared_by_apertures: int = 0
    schema_version: str = INTERNAL_DOOR_APERTURE_REVIEW_SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "source_sha256": self.source_sha256,
            "page_index": self.page_index,
            "entries": [entry.to_dict() for entry in self.entries],
            "in_scope_record_count": self.in_scope_record_count,
            "out_of_scope_record_count": self.out_of_scope_record_count,
            "records_bound_to_an_aperture": self.records_bound_to_an_aperture,
            "records_shared_by_apertures": self.records_shared_by_apertures,
            "physical_opening_authenticated": False,
            "kind_authorized": False,
            "host_authorized": False,
            "measurement_authorized": False,
            "customer_quantity_authorized": False,
            "frozen_benchmark_scored": False,
            "schema_version": self.schema_version,
        }

    def to_public_summary(self) -> dict[str, object]:
        """Counts only: no ids, coordinates, words or paths."""
        by_state = Counter(entry.state for entry in self.entries)
        by_gate = Counter(entry.first_open_gate for entry in self.entries)
        by_symbol = Counter(entry.symbol_kind for entry in self.entries)
        return {
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "aperture_count": len(self.entries),
            "symbol_counts": dict(sorted(by_symbol.items())),
            "state_counts": dict(sorted(by_state.items())),
            "first_open_gate_counts": dict(sorted(by_gate.items())),
            "representatives_per_aperture": [
                len(entry.representative_ids) for entry in self.entries
            ],
            "in_scope_record_count": self.in_scope_record_count,
            "out_of_scope_record_count": self.out_of_scope_record_count,
            "records_bound_to_an_aperture": self.records_bound_to_an_aperture,
            "records_shared_by_apertures": self.records_shared_by_apertures,
            "physical_opening_authenticated": False,
            "kind_authorized": False,
            "host_authorized": False,
            "measurement_authorized": False,
            "customer_quantity_authorized": False,
            "frozen_benchmark_scored": False,
        }


def _finite_number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _clean_bounds(value: object) -> tuple[float, float, float, float] | None:
    try:
        bounds = tuple(float(v) for v in value)  # type: ignore[union-attr]
    except (TypeError, ValueError, OverflowError):
        return None
    if len(bounds) != 4 or not all(math.isfinite(v) for v in bounds):
        return None
    if bounds[2] < bounds[0] or bounds[3] < bounds[1]:
        return None
    return bounds


def _record_inside(
    source_geometries: object,
    bounds: tuple[float, float, float, float],
    tolerance: float = CONTAINMENT_TOLERANCE_PT,
) -> bool:
    """True when EVERY valid geometry of the record lies inside the box (and at least one is valid).

    A record that spills out of the aperture is not that aperture's representative. For the
    single-segment records the producer emits this is the same predicate as the merged window review.
    """
    if not isinstance(source_geometries, tuple):
        return False
    valid = 0
    for geometry in source_geometries:
        if (
            type(geometry) is not tuple or len(geometry) != 4
            or not all(_finite_number(v) for v in geometry)
        ):
            continue
        x0, y0, x1, y1 = geometry
        valid += 1
        if not (
            bounds[0] - tolerance <= min(x0, x1) <= max(x0, x1) <= bounds[2] + tolerance
            and bounds[1] - tolerance <= min(y0, y1) <= max(y0, y1) <= bounds[3] + tolerance
        ):
            return False
    return valid > 0


def _positive_area(value: object) -> bool:
    return _finite_number(value) and value > 0.0  # type: ignore[operator]


def _first_open_gate(
    *,
    has_box: bool,
    exclusive: Sequence[LiveCanonicalOpeningObject],
    shared_count: int,
) -> str:
    if not has_box:
        return GATE_NO_APERTURE_BOX
    if not exclusive:
        return GATE_SHARED if shared_count else GATE_NO_REPRESENTATIVE
    kinds = {str(o.opening_kind or "").strip().lower() for o in exclusive}
    if "window" in kinds:
        return GATE_KIND_CONFLICT
    if "door" not in kinds:
        return GATE_KIND
    if not any(str(o.host_wall_id or "").strip() for o in exclusive):
        return GATE_HOST_WALL
    if not any(
        str(o.host_binding_record_id or "").strip() or str(o.host_frame_record_id or "").strip()
        for o in exclusive
    ):
        return GATE_HOST_RECEIPT
    if not any(_positive_area(o.area_m2) for o in exclusive):
        return GATE_AREA
    if not any(str(o.area_basis or "").strip() for o in exclusive):
        return GATE_BASIS
    return GATE_ISSUER


def review_internal_door_apertures(
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Sequence[Any] | Mapping[str, Any]],
    canonical_openings: Iterable[LiveCanonicalOpeningObject],
    *,
    page_index: int,
    expected_source_sha256: str,
) -> InternalDoorApertureReview:
    """Bind each source-native internal door aperture to the canonical records inside it.

    ``drawings`` and ``source_words`` are the original page's native rows (never mutated).
    ``canonical_openings`` are the producer's existing records; those of another SHA or page are
    excluded and counted, a set that mixes document, revision or snapshot abstains.
    """
    if type(expected_source_sha256) is not str or _HEX64.fullmatch(expected_source_sha256) is None:
        raise ValueError("full_original_source_sha256_required")
    if type(page_index) is not int or page_index < 0:
        raise ValueError("page_index_must_be_a_non_negative_int")
    page_id = str(page_index + 1)

    records = tuple(canonical_openings)
    seen: set[str] = set()
    for record in records:
        if (
            type(record) is not LiveCanonicalOpeningObject
            or type(record.canonical_opening_id) is not str
            or not record.canonical_opening_id
            or record.canonical_opening_id in seen
        ):
            raise ValueError("duplicate_or_untrusted_canonical_opening")
        seen.add(record.canonical_opening_id)
    in_scope = tuple(
        r for r in records
        if r.source_sha256 == expected_source_sha256 and r.page_id == page_id
    )
    out_of_scope = len(records) - len(in_scope)
    scopes = {(r.document_id, r.revision_id, r.snapshot_id) for r in in_scope}
    if len(scopes) > 1:
        return InternalDoorApertureReview(
            INTERNAL_DOOR_APERTURE_REVIEW_ABSTAINED, (REASON_MIXED_SCOPE,),
            expected_source_sha256, page_index,
            in_scope_record_count=len(in_scope), out_of_scope_record_count=out_of_scope,
        )

    inspection = inspect_source_internal_door_completeness(
        drawings, source_words, page_index=page_index,
    )
    barriers = detect_source_internal_swing_room_barriers(
        drawings, source_words, page_index=page_index,
    )
    sliders = match_source_native_cavity_sliders(
        drawings, source_words, page_index=page_index,
    )
    barrier_by_arc: dict[int, list[Any]] = {}
    for barrier in barriers:
        barrier_by_arc.setdefault(barrier.swing_arc_path_id, []).append(barrier)
    slider_by_word: dict[int, list[Any]] = {}
    for slider in sliders:
        slider_by_word.setdefault(slider.cs_word_index, []).append(slider)

    # Aperture boxes. A symbol with no unique detector receipt has no box and is reported, not dropped.
    draft: list[dict[str, Any]] = []
    for mark in inspection.marks:
        box: tuple[float, float, float, float] | None = None
        if mark.kind == "native_swing_arc_leaf":
            symbol = SYMBOL_HINGED_SWING
            matches = barrier_by_arc.get(mark.native_path_ids[0], []) if mark.native_path_ids else []
            if len(matches) == 1:
                box = _clean_bounds(matches[0].bounds_pdf_pts)
        else:
            symbol = SYMBOL_CAVITY_SLIDER
            matches = slider_by_word.get(mark.source_word_index, []) if mark.source_word_index is not None else []
            if len(matches) == 1:
                a0, a1 = matches[0].clear_interval_pdf_pts
                b0, b1 = matches[0].band_pdf_pts
                box = _clean_bounds(
                    (a0, b0, a1, b1) if matches[0].horizontal else (b0, a0, b1, a1)
                )
        draft.append({"mark": mark, "symbol": symbol, "box": box})

    membership: dict[str, list[int]] = {}
    for record in in_scope:
        hits = [
            index for index, item in enumerate(draft)
            if item["box"] is not None and _record_inside(record.source_geometries, item["box"])
        ]
        if hits:
            membership[record.canonical_opening_id] = hits
    by_id = {r.canonical_opening_id: r for r in in_scope}
    shared_ids = {rid for rid, hits in membership.items() if len(hits) > 1}

    entries: list[InternalDoorApertureEntry] = []
    for index, item in enumerate(draft):
        mark = item["mark"]
        exclusive = sorted(
            (by_id[rid] for rid, hits in membership.items() if hits == [index]),
            key=lambda r: r.canonical_opening_id,
        )
        shared = sorted(rid for rid in shared_ids if index in membership[rid])
        has_box = item["box"] is not None
        if not has_box:
            state = STATE_NO_APERTURE_BOX
        elif shared:
            state = STATE_SHARED
        elif not exclusive:
            state = STATE_NO_REPRESENTATIVE
        elif len(exclusive) == 1:
            state = STATE_SINGLE
        else:
            state = STATE_MULTIPLE
        kinds = tuple(sorted({
            k for k in (str(o.opening_kind or "").strip().lower() for o in exclusive)
            if k in ("door", "window")
        }))
        native_ids = tuple(int(v) for v in mark.native_path_ids)
        entries.append(InternalDoorApertureEntry(
            entry_id=stable_contract_id(
                "internal_door_aperture",
                {
                    "source_sha256": expected_source_sha256, "page_index": page_index,
                    "symbol_kind": item["symbol"], "native_path_ids": list(native_ids),
                    "source_word_index": mark.source_word_index,
                },
                digest_chars=32,
            ),
            symbol_kind=item["symbol"],
            mark_status=str(mark.status),
            aperture_bounds_pdf_pts=item["box"],
            native_path_ids=native_ids,
            printed_width_mm=mark.label_width_mm,
            representative_ids=tuple(o.canonical_opening_id for o in exclusive),
            shared_representative_ids=tuple(shared),
            state=state,
            kinds_on_representatives=kinds,
            representatives_with_door_kind=sum(
                str(o.opening_kind or "").strip().lower() == "door" for o in exclusive
            ),
            representatives_with_host_wall=sum(bool(str(o.host_wall_id or "").strip()) for o in exclusive),
            representatives_with_host_receipt=sum(
                bool(str(o.host_binding_record_id or "").strip() or str(o.host_frame_record_id or "").strip())
                for o in exclusive
            ),
            representatives_with_positive_area=sum(_positive_area(o.area_m2) for o in exclusive),
            representatives_with_area_basis=sum(bool(str(o.area_basis or "").strip()) for o in exclusive),
            first_open_gate=_first_open_gate(
                has_box=has_box, exclusive=exclusive, shared_count=len(shared),
            ),
        ))
    entries.sort(key=lambda e: (
        e.symbol_kind,
        e.aperture_bounds_pdf_pts if e.aperture_bounds_pdf_pts is not None else (math.inf,) * 4,
        e.native_path_ids,
    ))
    return InternalDoorApertureReview(
        INTERNAL_DOOR_APERTURE_REVIEW_STATUS,
        (),
        expected_source_sha256,
        page_index,
        entries=tuple(entries),
        in_scope_record_count=len(in_scope),
        out_of_scope_record_count=out_of_scope,
        records_bound_to_an_aperture=len(membership) - len(shared_ids),
        records_shared_by_apertures=len(shared_ids),
    )


__all__ = [
    "CONTAINMENT_TOLERANCE_PT",
    "InternalDoorApertureEntry",
    "InternalDoorApertureReview",
    "review_internal_door_apertures",
]
