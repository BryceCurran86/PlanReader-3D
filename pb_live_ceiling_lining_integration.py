"""Fail-closed live ceiling-lining claims from the source-owned authority chain.

This is the live-prediction boundary reviewed after the shadow and estimator-review
promotion seams were completed.  It does not project commercial rows and it never
turns ceiling lining into FIRM authority.

Inputs are the source PDF bytes plus normal page selection.  The module:
1. ingests the bytes through SourceVisibilityProducer;
2. accepts only F.07 RESOLVED floor-plan vector-frame viewports;
3. runs the fully source-owned ceiling shadow composition per exact viewport;
4. revalidates every resolved ceiling claim against its FIRM same-scope room area,
   producer-owned finish evidence, current source identity and physical scale;
5. emits a separate live PROVISIONAL claim;
6. refuses to add the same finish across multiple independent viewports because
   cross-viewport physical identity is not yet proven.

No benchmark ID, expected quantity, filename, project name or BOQ mapping is used.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math
import re
from pathlib import Path
from typing import Optional, Sequence

import fitz

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_hosted_opening_instance_adapter import authoritative_floor_plan_viewports
from pb_migration_contracts import (
    EvidenceResolutionStatus,
    QuantityEvidence,
    ViewportEvidence,
    ViewportResolutionStatus,
    stable_contract_id,
)
from pb_migration_provider_envelope import ProviderContext
from pb_page_scale_calibration_authority import measurement_authority_for_page_scale
from pb_source_ceiling_finish_evidence import SOURCE_CEILING_FINISH_METHOD
from pb_source_owned_ceiling_lining_pipeline import run_source_owned_ceiling_lining_shadow
from pb_source_visibility_authority import SourceVisibilityProducer


LIVE_CEILING_LINING_SCHEMA_VERSION = "1.0.0"
LIVE_CEILING_LINING_RESOLVED = "live_ceiling_lining_resolved"
LIVE_CEILING_LINING_UNAVAILABLE = "live_ceiling_lining_unavailable"
LIVE_CEILING_LINING_MULTI_VIEWPORT_IDENTITY_UNRESOLVED = (
    "live_ceiling_lining_multi_viewport_identity_unresolved"
)
LIVE_CEILING_LINING_TAG_FAMILY_CONFLICT = "live_ceiling_lining_tag_family_conflict"
LIVE_CEILING_CANONICAL_IDENTITY_CONFLICT = (
    "live_ceiling_canonical_identity_conflict"
)
LIVE_CEILING_QUANTITY_IDENTITY_CONFLICT = "live_ceiling_quantity_identity_conflict"
LIVE_CEILING_LINING_METRIC_AGGREGATE_NONFINITE = (
    "live_ceiling_lining_metric_aggregate_nonfinite"
)
LIVE_CEILING_LINING_SOURCE_VIEWPORT_FAILURE = (
    "live_ceiling_lining_source_viewport_failure"
)
LIVE_CEILING_LINING_SOURCE_SNAPSHOT_UNAVAILABLE = (
    "live_ceiling_lining_source_snapshot_unavailable"
)
LIVE_CEILING_LINING_SOURCE_CONTEXT_MISMATCH = (
    "live_ceiling_lining_source_context_mismatch"
)


@dataclass(frozen=True)
class LiveCanonicalCeilingSurfaceObject:
    canonical_ceiling_id: str
    document_id: str
    snapshot_id: str
    room_entity_id: str
    source_page: int
    viewport_id: str
    source_sha256: str
    revision_id: str
    polygon_pdf_pts: tuple[tuple[float, float], ...]
    area_m2: float
    finish_descriptor: str
    room_area_quantity_id: str
    ceiling_quantity_id: str
    source_room_index_id: str
    evidence_ids: tuple[str, ...]
    physical_scale_record_id: str
    measurement_authority: str = ""
    figured_dimension_ids: tuple[str, ...] = ()
    geometry_complete: bool = True
    metric_area_complete: bool = True
    metric_geometry_complete: bool = False
    coordinate_space: str = "source_page_points"
    schema_version: str = LIVE_CEILING_LINING_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "canonical_ceiling_id": self.canonical_ceiling_id,
            "document_id": self.document_id,
            "snapshot_id": self.snapshot_id,
            "room_entity_id": self.room_entity_id,
            "source_page": self.source_page,
            "viewport_id": self.viewport_id,
            "source_sha256": self.source_sha256,
            "revision_id": self.revision_id,
            "polygon_pdf_pts": [list(point) for point in self.polygon_pdf_pts],
            "area_m2": self.area_m2,
            "finish_descriptor": self.finish_descriptor,
            "room_area_quantity_id": self.room_area_quantity_id,
            "ceiling_quantity_id": self.ceiling_quantity_id,
            "source_room_index_id": self.source_room_index_id,
            "evidence_ids": list(self.evidence_ids),
            "physical_scale_record_id": self.physical_scale_record_id,
            "measurement_authority": self.measurement_authority,
            "figured_dimension_ids": list(self.figured_dimension_ids),
            "geometry_complete": self.geometry_complete,
            "metric_area_complete": self.metric_area_complete,
            "metric_geometry_complete": self.metric_geometry_complete,
            "coordinate_space": self.coordinate_space,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class LiveCeilingLiningClaim:
    claim_id: str
    tag: str
    finish_descriptor: str
    quantity_m2: float
    confidence: float
    source_page: int
    viewport_id: str
    source_sha256: str
    revision_id: str
    room_quantity_ids: tuple[str, ...]
    room_entity_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    physical_scale_record_id: str
    measurement_authority: str = ""
    figured_dimension_ids: tuple[str, ...] = ()
    status: str = AuthorityStatus.PROVISIONAL.value
    schema_version: str = LIVE_CEILING_LINING_SCHEMA_VERSION


@dataclass(frozen=True)
class LiveCeilingLiningResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    claims: tuple[LiveCeilingLiningClaim, ...]
    canonical_ceilings: tuple[LiveCanonicalCeilingSurfaceObject, ...] = ()
    quantity_evidence: tuple[QuantityEvidence, ...] = ()
    schema_version: str = LIVE_CEILING_LINING_SCHEMA_VERSION


def _clean(value: object) -> str:
    return str(value if value is not None else "").strip()


def _norm(value: object) -> str:
    return _clean(value).lower().replace("-", "_").replace(" ", "_")


def _source_positive_area_m2(value: object) -> Optional[float]:
    """Validate producer-owned native metric area without coercing source aliases."""
    if type(value) not in (int, float):
        return None
    try:
        area = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(area) or area <= 0.0:
        return None
    return area


def _exact_source_ceiling_quantity_id(value: object) -> bool:
    """Source quantity IDs are immutable receipts, not display strings."""
    return type(value) is str and bool(value) and value == value.strip()


def _source_room_polygon_pdf_pts(
    points: object,
) -> Optional[tuple[tuple[float, float], ...]]:
    """Require a finite, nondegenerate source room ring before canonicalizing.

    The room-area measurement is independently source-owned; this gate only
    prevents malformed physical geometry from being marked complete. Do not
    repair, snap, reorder, or infer missing original source vertices.
    """
    if type(points) not in (tuple, list) or len(points) < 3:
        return None
    polygon: list[tuple[float, float]] = []
    # Native source vertices are physical identities. Integers above 2**53
    # can round to a different float point (2**53 + 1 aliases 2**53).
    # Reject both integer and floating-point oversized coordinates before
    # conversion; never publish a silently altered room boundary.
    max_exact_native_coordinate = 1 << 53
    for point in points:
        if (
            type(point) not in (tuple, list)
            or len(point) != 2
            or type(point[0]) not in (int, float)
            or type(point[1]) not in (int, float)
        ):
            return None
        if (
            abs(point[0]) > max_exact_native_coordinate
            or abs(point[1]) > max_exact_native_coordinate
        ):
            return None
        try:
            x, y = float(point[0]), float(point[1])
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(x) or not math.isfinite(y):
            return None
        polygon.append((x, y))

    # Origin-relative triangle fan avoids avoidable cancellation for ordinary
    # translated PDF polygons. A collinear/zero-area ring is not a physical
    # room face; a nonfinite intermediate is not a valid source measurement.
    origin_x, origin_y = polygon[0]
    double_area_terms: list[float] = []
    for index in range(1, len(polygon) - 1):
        ax = polygon[index][0] - origin_x
        ay = polygon[index][1] - origin_y
        bx = polygon[index + 1][0] - origin_x
        by = polygon[index + 1][1] - origin_y
        term = ax * by - ay * bx
        if not math.isfinite(term):
            return None
        double_area_terms.append(term)
    try:
        double_area = math.fsum(double_area_terms)
    except (ValueError, OverflowError):
        return None
    if not math.isfinite(double_area) or double_area == 0.0:
        return None

    # Nonzero signed area does not prove a simple physical room boundary:
    # crossed edges can cancel only partially. Preserve the source vertices
    # verbatim; a repeated *closing* vertex is the sole allowed duplicate.
    ring = polygon[:-1] if polygon[0] == polygon[-1] else polygon
    count = len(ring)
    if count < 3:
        return None
    for index in range(count):
        before, vertex, after = (
            ring[index - 1], ring[index], ring[(index + 1) % count]
        )
        if vertex == after:
            return None
        # Adjacent collinear edges may continue in the same direction, but
        # reversing along the same physical segment is an overlapping ring.
        ax, ay = before[0] - vertex[0], before[1] - vertex[1]
        bx, by = after[0] - vertex[0], after[1] - vertex[1]
        turn = ax * by - ay * bx
        dot = ax * bx + ay * by
        if not math.isfinite(turn) or not math.isfinite(dot):
            return None
        if turn == 0.0 and dot > 0.0:
            return None

    def orientation(a, b, c):
        ax, ay = b[0] - a[0], b[1] - a[1]
        bx, by = c[0] - a[0], c[1] - a[1]
        return ax * by - ay * bx

    def on_segment(a, b, c):
        return (
            min(a[0], b[0]) <= c[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])
        )

    # Sort by horizontal interval to skip disjoint edges. Cap *actual*
    # overlapping-x pair visits: a malicious complex source ring must abstain
    # rather than consume unbounded quadratic work. No geometry is simplified.
    edges = sorted(
        (
            min(ring[i][0], ring[(i + 1) % count][0]),
            max(ring[i][0], ring[(i + 1) % count][0]),
            min(ring[i][1], ring[(i + 1) % count][1]),
            max(ring[i][1], ring[(i + 1) % count][1]),
            i,
            ring[i],
            ring[(i + 1) % count],
        )
        for i in range(count)
    )
    examined = 0
    for position, (xmin, xmax, ymin, ymax, i, a, b) in enumerate(edges):
        for next_position in range(position + 1, len(edges)):
            oxmin, _oxmax, oymin, oymax, j, c, d = edges[next_position]
            if oxmin > xmax:
                break
            examined += 1
            if examined > 500_000:
                return None
            if oymin > ymax or oymax < ymin:
                continue
            # Consecutive edges share one permitted endpoint. Their possible
            # overlapping backtrack was already rejected above.
            if abs(i - j) == 1 or {i, j} == {0, count - 1}:
                continue
            turns = (
                orientation(a, b, c), orientation(a, b, d),
                orientation(c, d, a), orientation(c, d, b),
            )
            if not all(math.isfinite(turn) for turn in turns):
                return None
            t1, t2, t3, t4 = turns
            if (
                (t1 == 0.0 and on_segment(a, b, c))
                or (t2 == 0.0 and on_segment(a, b, d))
                or (t3 == 0.0 and on_segment(c, d, a))
                or (t4 == 0.0 and on_segment(c, d, b))
                or (t1 != 0.0 and t2 != 0.0 and t3 != 0.0 and t4 != 0.0
                    and (t1 > 0.0) != (t2 > 0.0)
                    and (t3 > 0.0) != (t4 > 0.0))
            ):
                return None
    return tuple(polygon)


def _tag_for_descriptor(descriptor: str) -> str:
    """Return a generic material-family tag derived only from source finish text."""
    text = _norm(descriptor)
    families = (
        ("chipboard", ("chipboard", "chip_board")),
        ("gypsum", ("gypsum",)),
        ("plasterboard", ("plasterboard", "plaster_board")),
        ("fibre_cement", ("fibre_cement", "fiber_cement", "fibrecement", "fibercement")),
        ("acoustic", ("acoustic", "acoustical")),
        ("pvc", ("pvc", "polyvinyl")),
        ("timber", ("timber", "wood", "wooden")),
        ("board", ("board",)),
    )
    for family, needles in families:
        if any(needle in text for needle in needles):
            return f"ceiling_{family}"
    return "ceiling_lining"


def _selected_page_indices(page_count: int, pages: Optional[Sequence[int]]) -> tuple[int, ...]:
    """Preserve the complete explicitly requested original PDF page universe.

    Never coerce a foreign page token or silently discard an invalid sibling:
    the source producer must see the exact selected pages or fail before ingest.
    """
    if pages is None:
        return tuple(range(page_count))
    if isinstance(pages, (str, bytes, bytearray)) or not isinstance(pages, Sequence):
        raise ValueError("original ceiling page selection requires an integer sequence")
    indices = tuple(pages)
    if any(
        type(index) is not int or index < 0 or index >= page_count
        for index in indices
    ):
        raise ValueError("original ceiling page selection contains an invalid page index")
    return tuple(sorted(set(indices)))


def _claim_from_quantity(
    *,
    quantity,
    source_result,
    page_no: int,
    viewport_id: str,
) -> Optional[
    tuple[
        str,
        str,
        float,
        tuple[str, ...],
        tuple[str, ...],
        tuple[str, ...],
        str,
        str,
        tuple[str, ...],
    ]
]:
    if (
        quantity.family != "ceiling_lining"
        or type(quantity.unit) is not str
        or quantity.unit != "m2"
        or quantity.abstained
        or quantity.value is None
        or quantity.status != AuthorityStatus.PROVISIONAL.value
        or quantity.authority != MeasurementAuthorityType.MODEL_DERIVED.value
        or quantity.blocking_reasons
        or len(quantity.input_entity_ids) != 1
        # A source-owned ceiling quantity ID is an exact evidence receipt.
        # Do not accept padded or foreign-string aliases as a live identity.
        or not _exact_source_ceiling_quantity_id(quantity.quantity_id)
    ):
        return None

    metric_value = _source_positive_area_m2(quantity.value)
    if metric_value is None:
        return None

    meta = quantity.metadata if isinstance(quantity.metadata, dict) else {}
    if (
        meta.get("shadow_only") is not True
        or meta.get("commercial_projection_allowed") is not False
        # Viewport identity is a producer-owned source receipt, not display
        # text. Never strip or stringify a foreign viewport into this scope.
        or type(meta.get("viewport_id")) is not str
        or not meta["viewport_id"]
        or meta["viewport_id"] != viewport_id
        # Page identity is producer-owned. Never coerce a bool, float or
        # numeric-text alias into an authenticated original PDF page.
        or type(meta.get("page_no")) is not int
        or meta["page_no"] != page_no
    ):
        return None

    # Original finish text-integrity methods and evidence IDs are typed
    # producer receipts. Stringifying/trimming a foreign object, or iterating
    # a bare string as individual IDs, cannot authenticate ceiling material.
    finish_descriptor = meta.get("finish_descriptor")
    finish_methods = meta.get("finish_source_methods")
    finish_ids = meta.get("finish_evidence_ids")
    source_evidence_ids = quantity.evidence_ids
    if (
        type(finish_descriptor) is not str
        or not finish_descriptor
        or finish_descriptor != finish_descriptor.strip()
        or type(finish_methods) not in (tuple, list)
        or not finish_methods
        or type(finish_ids) not in (tuple, list)
        or not finish_ids
        or type(source_evidence_ids) not in (tuple, list)
        or not source_evidence_ids
    ):
        return None
    for receipts in (finish_methods, finish_ids, source_evidence_ids):
        if (
            any(type(item) is not str or not item or item != item.strip()
                for item in receipts)
            or len(set(receipts)) != len(receipts)
        ):
            return None
    if (
        SOURCE_CEILING_FINISH_METHOD not in finish_methods
        or not set(finish_ids).issubset(set(source_evidence_ids))
    ):
        return None

    # A producer-owned room-area receipt is an exact identity, not display
    # text. Coercion/whitespace repair could bind an unrelated FIRM area and
    # leave a provisional claim that the final canonical issuer rejects.
    upstream_id = meta.get("upstream_area_quantity_id")
    if (
        type(upstream_id) is not str
        or not upstream_id
        or upstream_id != upstream_id.strip()
    ):
        return None
    # Quantity identity is cryptographic source lineage, never last-writer-wins.
    # A modified record replay with the SAME upstream source quantity ID
    # revokes the entire ID instead of choosing the last candidate. Exact
    # byte-for-byte/equality replays are harmless and remain idempotent.
    area_by_id = {}
    conflicting_area_ids = set()
    for item in source_result.room_area_quantities:
        item_id = item.quantity_id
        if (
            type(item_id) is not str
            or not item_id
            or item_id != item_id.strip()
            or item_id in conflicting_area_ids
        ):
            continue
        previous = area_by_id.get(item_id)
        if previous is not None and previous != item:
            area_by_id.pop(item_id, None)
            conflicting_area_ids.add(item_id)
            continue
        area_by_id[item_id] = item
    area = area_by_id.get(upstream_id)
    scope = quantity.input_entity_ids[0]
    if (
        area is None
        or type(area.family) is not str
        or area.family != "room_area"
        or type(area.unit) is not str
        or area.unit != "m2"
        or area.abstained
        or area.value is None
        or area.status != AuthorityStatus.FIRM.value
        or area.authority
        not in {
            MeasurementAuthorityType.PDF_SCALED.value,
            MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        }
        or tuple(area.input_entity_ids) != (scope,)
        or _source_positive_area_m2(area.value) != metric_value
        or area.blocking_reasons
    ):
        return None

    scale_record_id = ""
    figured_dimension_ids: tuple[str, ...] = ()
    if area.authority == MeasurementAuthorityType.PDF_SCALED.value:
        bridge = source_result.scale_bridge
        calibration = bridge.calibration
        physical = bridge.physical_scale_evidence
        if (
            bridge.status is not EvidenceResolutionStatus.CORROBORATED
            or calibration is None
            or physical is None
            or not physical.record_id
            or measurement_authority_for_page_scale(calibration)
            != AuthorityStatus.FIRM.value
        ):
            return None
        scale_record_id = str(physical.record_id)
    else:
        area_meta = area.metadata if isinstance(area.metadata, dict) else {}
        raw_figured_ids = area_meta.get("figured_dimension_ids")
        # Source IDs are producer-owned tokens, not freeform human text.
        # Treating a bare string as an iterable would turn "dim-h" into
        # several single-character IDs and falsely satisfy a two-axis gate.
        # Original figured-axis IDs are exact source receipts. Trimming a
        # padded token or discarding a blank one would silently repair an
        # untrusted identity into apparently authenticated two-axis evidence.
        if (
            type(raw_figured_ids) not in (tuple, list)
            or any(
                type(value) is not str
                or not value
                or value != value.strip()
                for value in raw_figured_ids
            )
        ):
            return None
        figured_dimension_ids = tuple(sorted(set(raw_figured_ids)))
        # The ceiling must carry both independently source-owned axes of
        # the documented room-area proof. One dimension ID, or repetitions of
        # the same ID, cannot establish a metric plane and must not enter the
        # canonical ceiling pipeline as a source-authenticated area.
        if len(figured_dimension_ids) < 2:
            return None

    return (
        _tag_for_descriptor(finish_descriptor),
        finish_descriptor,
        metric_value,
        (quantity.quantity_id,),
        tuple(quantity.input_entity_ids),
        tuple(quantity.evidence_ids),
        scale_record_id,
        str(area.authority),
        figured_dimension_ids,
    )


def canonical_ceiling_from_shadow_quantity(
    *,
    quantity: QuantityEvidence,
    source_result,
    page_no: int,
    viewport_id: str,
) -> Optional[LiveCanonicalCeilingSurfaceObject]:
    """Project one already-validated shadow quantity onto canonical ceiling identity.

    This performs no extraction, measurement or commercial promotion.  It is
    intentionally reusable by the estimator-review collector so AG-09 can see
    the same canonical object without replaying the ceiling pipeline.
    """
    resolved = _claim_from_quantity(
        quantity=quantity,
        source_result=source_result,
        page_no=page_no,
        viewport_id=viewport_id,
    )
    if resolved is None:
        return None
    (
        _tag,
        descriptor,
        value,
        _quantity_ids,
        room_ids,
        evidence_ids,
        scale_record_id,
        measurement_authority,
        figured_dimension_ids,
    ) = resolved
    if len(room_ids) != 1:
        return None

    room_index = source_result.pipeline.room_area_bridge.room_index
    if room_index is None:
        return None
    room_id = room_ids[0]
    room = room_index.room(room_id)
    if room is None:
        return None
    source_polygon = _source_room_polygon_pdf_pts(room.polygon_pdf_pts)
    if source_polygon is None:
        return None

    quantity_meta = (
        quantity.metadata if isinstance(quantity.metadata, dict) else {}
    )
    upstream_area_id = quantity_meta.get("upstream_area_quantity_id")
    if (
        type(upstream_area_id) is not str
        or not upstream_area_id
        or upstream_area_id != upstream_area_id.strip()
    ):
        return None

    context = source_result.effective_context
    document_id = _clean(context.document_id)
    source_sha256 = _clean(context.source_sha256)
    revision_id = _clean(context.current_revision_id)
    snapshot_id = _clean(context.evidence_snapshot_id)
    if not all((document_id, source_sha256, revision_id, snapshot_id)):
        return None

    canonical_id = stable_contract_id(
        "live_canonical_ceiling_surface",
        {
            "source_sha256": source_sha256,
            "revision_id": revision_id,
            "page_no": int(page_no),
            "viewport_id": viewport_id,
            "room_entity_id": room_id,
        },
    )
    return LiveCanonicalCeilingSurfaceObject(
        canonical_ceiling_id=canonical_id,
        document_id=document_id,
        snapshot_id=snapshot_id,
        room_entity_id=room_id,
        source_page=int(page_no),
        viewport_id=viewport_id,
        source_sha256=source_sha256,
        revision_id=revision_id,
        polygon_pdf_pts=source_polygon,
        area_m2=float(value),
        finish_descriptor=descriptor,
        room_area_quantity_id=upstream_area_id,
        ceiling_quantity_id=quantity.quantity_id,
        source_room_index_id=room_index.index_id,
        evidence_ids=tuple(evidence_ids),
        physical_scale_record_id=scale_record_id,
        measurement_authority=measurement_authority,
        figured_dimension_ids=figured_dimension_ids,
    )


def _source_result_context_matches(*, result, expected: ProviderContext) -> bool:
    """Verify the source producer did not substitute a different page/run root.

    The trusted wall build may advance ONLY the source snapshot receipt. Every
    other document/revision/page/viewport/owner field must remain identical.
    """
    actual = getattr(result, "effective_context", None)
    return (
        type(actual) is ProviderContext
        and type(actual.evidence_snapshot_id) is str
        and bool(actual.evidence_snapshot_id)
        and actual == replace(
            expected, evidence_snapshot_id=actual.evidence_snapshot_id
        )
    )


def collect_live_ceiling_lining_claims(
    pdf_path: Path | str,
    *,
    pages: Optional[Sequence[int]] = None,
    topology_pages: Optional[Sequence[int]] = None,
    authoritative_room_area_quantities: Optional[Sequence[QuantityEvidence]] = None,
) -> LiveCeilingLiningResult:
    """Collect live provisional ceiling claims from authoritative source viewports."""

    path = Path(pdf_path)
    payload = path.read_bytes()
    source_sha = hashlib.sha256(payload).hexdigest()
    document_id = f"live-source:{source_sha[:32]}"

    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        selected = _selected_page_indices(len(doc), pages)
        topology_selected = (
            selected
            if topology_pages is None
            else _selected_page_indices(len(doc), topology_pages)
        )
        if any(index not in set(selected) for index in topology_selected):
            raise ValueError("topology_pages must be a subset of pages")
        page_ids = tuple(str(index + 1) for index in selected)
        source = SourceVisibilityProducer(
            producer_method="live-ceiling-lining",
            producer_version=LIVE_CEILING_LINING_SCHEMA_VERSION,
        )
        published = source.ingest_native_pdf_bytes(
            document_id=document_id,
            source_bytes=payload,
            source_locator="memory://live-source.pdf",
            page_ids=page_ids,
        )
        by_descriptor: dict[
            str,
            list[
                tuple[
                    int,
                    str,
                    str,
                    float,
                    tuple[str, ...],
                    tuple[str, ...],
                    tuple[str, ...],
                    str,
                    float,
                ]
            ],
        ] = {}
        canonical_ceilings_by_id: dict[
            str, LiveCanonicalCeilingSurfaceObject
        ] = {}
        canonical_conflicts: set[str] = set()
        # All source quantity IDs for one disputed physical canonical ceiling
        # must abstain together, even if their own IDs are distinct.
        canonical_quantity_ids_by_id: dict[str, set[str]] = {}
        validated_quantities: dict[str, QuantityEvidence] = {}
        # One source quantity ID can identify only one physical ceiling in one
        # original page/viewport. Equal replays are idempotent; changed or
        # cross-scope reuses revoke every occurrence, never first/last wins.
        seen_ceiling_quantity_ids: dict[
            str, tuple[QuantityEvidence, tuple[int, str]]
        ] = {}
        conflicting_ceiling_quantity_ids: set[str] = set()
        upstream_room_areas = tuple(authoritative_room_area_quantities or ())

        for page_index in topology_selected:
            page_no = page_index + 1
            page = doc[page_index]
            for segmented in authoritative_floor_plan_viewports(
                page, page_number=page_no
            ):
                if segmented.bounding_box is None:
                    continue
                # F.07 viewport IDs are original source identities, not
                # display strings. Never stringify, trim or silently skip an
                # authoritative sibling: that would publish an incomplete
                # selected viewport universe from earlier valid siblings.
                viewport_id = getattr(segmented, "view_id", None)
                if (
                    type(viewport_id) is not str
                    or not viewport_id
                    or viewport_id != viewport_id.strip()
                ):
                    return LiveCeilingLiningResult(
                        status=EvidenceResolutionStatus.ABSTAINED,
                        reason_codes=(
                            LIVE_CEILING_LINING_UNAVAILABLE,
                            LIVE_CEILING_LINING_SOURCE_VIEWPORT_FAILURE,
                        ),
                        claims=(),
                    )
                bbox = tuple(float(value) for value in segmented.bounding_box)
                viewport = ViewportEvidence(
                    viewport_id=viewport_id,
                    document_id=published.revision.document_id,
                    page_id=str(page_no),
                    bbox=bbox,
                    view_type="floor_plan",
                    status=ViewportResolutionStatus.RESOLVED,
                    evidence_ids=(),
                    confidence=float(segmented.confidence),
                )
                current = source.published_snapshot_for_revision(
                    published.revision.revision_id
                )
                if current is None:
                    # A missing revision snapshot is a failure of the complete
                    # selected original viewport universe, not a skippable view.
                    # A prior sibling cannot remain publishable on a partial
                    # source receipt. Do not infer or replace missing evidence.
                    return LiveCeilingLiningResult(
                        status=EvidenceResolutionStatus.ABSTAINED,
                        reason_codes=(
                            LIVE_CEILING_LINING_UNAVAILABLE,
                            LIVE_CEILING_LINING_SOURCE_SNAPSHOT_UNAVAILABLE,
                        ),
                        claims=(),
                    )
                context = ProviderContext(
                    run_id=f"live-ceiling:{current.snapshot.snapshot_id}:{viewport_id}",
                    workspace_id="live-extractor",
                    project_id="live-extractor",
                    document_id=current.revision.document_id,
                    source_sha256=current.revision.source_sha256,
                    revision_id=current.revision.revision_id,
                    current_revision_id=current.revision.revision_id,
                    selected_pages=(page_index,),
                    owned_viewport_ids=(viewport_id,),
                    evidence_snapshot_id=current.snapshot.snapshot_id,
                    owned_page_numbers=(page_no,),
                    viewport_page_ownership=((viewport_id, page_no),),
                )

                scoped_room_areas = tuple(
                    area
                    for area in upstream_room_areas
                    if (
                        isinstance(area.metadata, dict)
                        and _clean(area.metadata.get("source_sha256")).lower()
                        == current.revision.source_sha256.lower()
                        and _clean(area.metadata.get("revision_id"))
                        == current.revision.revision_id
                        and _clean(area.metadata.get("viewport_id")) == viewport_id
                        and _clean(area.metadata.get("page_no")) == str(page_no)
                    )
                )

                try:
                    result = run_source_owned_ceiling_lining_shadow(
                        source_visibility_producer=source,
                        context=context,
                        viewport=viewport,
                        page_no=page_no,
                        authoritative_area_quantities=(
                            scoped_room_areas if scoped_room_areas else None
                        ),
                    )
                except Exception:
                    # An unavailable original source viewport is negative
                    # evidence against the COMPLETE selected viewport universe.
                    # Never publish an earlier sibling's ceiling as though all
                    # physical views were inspected successfully. Do not leak
                    # exception details or mint a fallback area.
                    return LiveCeilingLiningResult(
                        status=EvidenceResolutionStatus.ABSTAINED,
                        reason_codes=(
                            LIVE_CEILING_LINING_UNAVAILABLE,
                            LIVE_CEILING_LINING_SOURCE_VIEWPORT_FAILURE,
                        ),
                        claims=(),
                    )

                if not _source_result_context_matches(
                    result=result, expected=context,
                ):
                    # A source-owned ceiling result may advance its snapshot
                    # during wall derivation, but must never switch the source
                    # root, revision, selected page or physical viewport.
                    # Reject the whole selected universe so a valid earlier
                    # sibling cannot survive a substituted later result.
                    return LiveCeilingLiningResult(
                        status=EvidenceResolutionStatus.ABSTAINED,
                        reason_codes=(
                            LIVE_CEILING_LINING_UNAVAILABLE,
                            LIVE_CEILING_LINING_SOURCE_CONTEXT_MISMATCH,
                        ),
                        claims=(),
                    )

                for quantity in result.ceiling_quantities:
                    quantity_id = quantity.quantity_id
                    if not _exact_source_ceiling_quantity_id(quantity_id):
                        # Reject invalid producer IDs before replay tracking;
                        # never trim/repair an original ceiling identity.
                        continue
                    source_scope = (page_no, viewport_id)
                    prior = seen_ceiling_quantity_ids.get(quantity_id)
                    if prior is not None:
                        if prior != (quantity, source_scope):
                            conflicting_ceiling_quantity_ids.add(quantity_id)
                        # Do not add the same source-owned quantity twice.
                        continue
                    seen_ceiling_quantity_ids[quantity_id] = (quantity, source_scope)
                    resolved = _claim_from_quantity(
                        quantity=quantity,
                        source_result=result,
                        page_no=page_no,
                        viewport_id=viewport_id,
                    )
                    if resolved is None:
                        continue
                    (
                        tag,
                        descriptor,
                        value,
                        quantity_ids,
                        room_ids,
                        evidence_ids,
                        scale_record_id,
                        measurement_authority,
                        figured_dimension_ids,
                    ) = resolved
                    # A source metric without its producer-owned physical room
                    # polygon is not a live ceiling claim. The real issuer may
                    # already reject the absent canonical object, but the
                    # earlier provisional claim must fail closed as well.
                    ceiling_object = canonical_ceiling_from_shadow_quantity(
                        quantity=quantity,
                        source_result=result,
                        page_no=page_no,
                        viewport_id=viewport_id,
                    )
                    if ceiling_object is None:
                        continue

                    validated_quantities[quantity.quantity_id] = quantity
                    by_descriptor.setdefault(descriptor, []).append(
                        (
                            page_no,
                            viewport_id,
                            tag,
                            value,
                            quantity_ids,
                            room_ids,
                            evidence_ids,
                            scale_record_id,
                            measurement_authority,
                            figured_dimension_ids,
                            float(quantity.confidence),
                        )
                    )

                    canonical_id = ceiling_object.canonical_ceiling_id
                    canonical_quantity_ids_by_id.setdefault(
                        canonical_id, set()
                    ).add(quantity.quantity_id)
                    prior = canonical_ceilings_by_id.get(canonical_id)
                    if prior is not None and prior != ceiling_object:
                        canonical_conflicts.add(canonical_id)
                    else:
                        canonical_ceilings_by_id[canonical_id] = ceiling_object

        canonical_conflict_quantity_ids = {
            quantity_id
            for canonical_id in canonical_conflicts
            for quantity_id in canonical_quantity_ids_by_id.get(canonical_id, ())
        }
        for canonical_id in canonical_conflicts:
            canonical_ceilings_by_id.pop(canonical_id, None)

        revoked_quantity_ids = (
            conflicting_ceiling_quantity_ids | canonical_conflict_quantity_ids
        )
        if revoked_quantity_ids:
            # A disputed source ID OR physical canonical ceiling revokes every
            # associated claim row, canonical object and issuer evidence.
            # A source claim cannot survive its canonical identity failure.
            for descriptor, rows in tuple(by_descriptor.items()):
                retained = [
                    row for row in rows
                    if not any(
                        quantity_id in revoked_quantity_ids
                        for quantity_id in row[4]
                    )
                ]
                if retained:
                    by_descriptor[descriptor] = retained
                else:
                    by_descriptor.pop(descriptor, None)
            canonical_ceilings_by_id = {
                canonical_id: ceiling
                for canonical_id, ceiling in canonical_ceilings_by_id.items()
                if ceiling.ceiling_quantity_id not in revoked_quantity_ids
            }
            for quantity_id in revoked_quantity_ids:
                validated_quantities.pop(quantity_id, None)

        claims: list[LiveCeilingLiningClaim] = []
        multi_viewport_blocked = False
        metric_aggregate_nonfinite = False
        for descriptor in sorted(by_descriptor):
            rows = by_descriptor[descriptor]
            viewport_keys = {(row[0], row[1]) for row in rows}
            if len(viewport_keys) != 1:
                # Do not sum potentially duplicated plans across viewports.
                multi_viewport_blocked = True
                continue

            page_no, viewport_id = next(iter(viewport_keys))
            tag_values = {row[2] for row in rows}
            scale_ids = {row[7] for row in rows}
            if len(tag_values) != 1 or len(scale_ids) != 1:
                continue

            # Every row is source-validated finite m², but their sum can
            # overflow to infinity. Keep the existing finite summation/IDs
            # byte-for-byte; never issue a nonphysical aggregate quantity.
            quantity_m2 = sum(row[3] for row in rows)
            if not math.isfinite(quantity_m2) or quantity_m2 <= 0.0:
                metric_aggregate_nonfinite = True
                continue
            room_quantity_ids = tuple(
                sorted({qid for row in rows for qid in row[4]})
            )
            room_entity_ids = tuple(
                sorted({rid for row in rows for rid in row[5]})
            )
            evidence_ids = tuple(
                sorted({eid for row in rows for eid in row[6]})
            )
            confidence = min(row[10] for row in rows)
            tag = next(iter(tag_values))
            scale_record_id = next(iter(scale_ids))
            measurement_authorities = {row[8] for row in rows}
            figured_dimension_ids = tuple(
                sorted({value for row in rows for value in row[9]})
            )
            if len(measurement_authorities) != 1:
                continue
            measurement_authority = next(iter(measurement_authorities))
            claim_id = stable_contract_id(
                "live_ceiling",
                {
                    "tag": tag,
                    "finish_descriptor": descriptor,
                    "quantity_m2": quantity_m2,
                    "source_sha256": source_sha,
                    "revision_id": published.revision.revision_id,
                    "page_no": page_no,
                    "viewport_id": viewport_id,
                    "room_quantity_ids": room_quantity_ids,
                    "room_entity_ids": room_entity_ids,
                    "evidence_ids": evidence_ids,
                    "physical_scale_record_id": scale_record_id,
                    "measurement_authority": measurement_authority,
                    "figured_dimension_ids": figured_dimension_ids,
                },
            )
            claims.append(
                LiveCeilingLiningClaim(
                    claim_id=claim_id,
                    tag=tag,
                    finish_descriptor=descriptor,
                    quantity_m2=quantity_m2,
                    confidence=confidence,
                    source_page=page_no,
                    viewport_id=viewport_id,
                    source_sha256=source_sha,
                    revision_id=published.revision.revision_id,
                    room_quantity_ids=room_quantity_ids,
                    room_entity_ids=room_entity_ids,
                    evidence_ids=evidence_ids,
                    physical_scale_record_id=scale_record_id,
                    measurement_authority=measurement_authority,
                    figured_dimension_ids=figured_dimension_ids,
                )
            )

        # A family tag is a publication identity. If distinct explicit
        # descriptors collapse to the same family tag, do not let confidence
        # or iteration order pick one. Cross-descriptor identity is unresolved.
        tag_to_descriptors: dict[str, set[str]] = {}
        for claim in claims:
            tag_to_descriptors.setdefault(claim.tag, set()).add(claim.finish_descriptor)
        conflicted_tags = {
            tag for tag, descriptors in tag_to_descriptors.items()
            if len(descriptors) > 1
        }
        tag_conflict_blocked = bool(conflicted_tags)
        if conflicted_tags:
            claims = [claim for claim in claims if claim.tag not in conflicted_tags]

        canonical_ceilings = tuple(
            sorted(
                canonical_ceilings_by_id.values(),
                key=lambda item: item.canonical_ceiling_id,
            )
        )
        claim_quantity_ids = {
            quantity_id
            for claim in claims
            for quantity_id in claim.room_quantity_ids
        }
        canonical_quantity_ids = {
            ceiling.ceiling_quantity_id for ceiling in canonical_ceilings
        }
        surviving_quantity_ids = claim_quantity_ids & canonical_quantity_ids
        surviving_quantities = tuple(
            validated_quantities[quantity_id]
            for quantity_id in sorted(surviving_quantity_ids)
            if quantity_id in validated_quantities
        )

        if claims:
            reasons = [LIVE_CEILING_LINING_RESOLVED]
            if multi_viewport_blocked:
                reasons.append(LIVE_CEILING_LINING_MULTI_VIEWPORT_IDENTITY_UNRESOLVED)
            if tag_conflict_blocked:
                reasons.append(LIVE_CEILING_LINING_TAG_FAMILY_CONFLICT)
            if canonical_conflicts:
                reasons.append(LIVE_CEILING_CANONICAL_IDENTITY_CONFLICT)
            if conflicting_ceiling_quantity_ids:
                reasons.append(LIVE_CEILING_QUANTITY_IDENTITY_CONFLICT)
            if metric_aggregate_nonfinite:
                reasons.append(LIVE_CEILING_LINING_METRIC_AGGREGATE_NONFINITE)
            return LiveCeilingLiningResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=tuple(reasons),
                claims=tuple(sorted(claims, key=lambda item: item.claim_id)),
                canonical_ceilings=canonical_ceilings,
                quantity_evidence=surviving_quantities,
            )

        reasons = [LIVE_CEILING_LINING_UNAVAILABLE]
        if multi_viewport_blocked:
            reasons.append(LIVE_CEILING_LINING_MULTI_VIEWPORT_IDENTITY_UNRESOLVED)
        if tag_conflict_blocked:
            reasons.append(LIVE_CEILING_LINING_TAG_FAMILY_CONFLICT)
        if canonical_conflicts:
            reasons.append(LIVE_CEILING_CANONICAL_IDENTITY_CONFLICT)
        if conflicting_ceiling_quantity_ids:
            reasons.append(LIVE_CEILING_QUANTITY_IDENTITY_CONFLICT)
        if metric_aggregate_nonfinite:
            reasons.append(LIVE_CEILING_LINING_METRIC_AGGREGATE_NONFINITE)
        return LiveCeilingLiningResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=tuple(reasons),
            claims=(),
            canonical_ceilings=canonical_ceilings,
            quantity_evidence=surviving_quantities,
        )
    finally:
        doc.close()


__all__ = [
    "LIVE_CEILING_CANONICAL_IDENTITY_CONFLICT",
    "LIVE_CEILING_QUANTITY_IDENTITY_CONFLICT",
    "LIVE_CEILING_LINING_METRIC_AGGREGATE_NONFINITE",
    "LIVE_CEILING_LINING_SOURCE_VIEWPORT_FAILURE",
    "LIVE_CEILING_LINING_SOURCE_SNAPSHOT_UNAVAILABLE",
    "LIVE_CEILING_LINING_SOURCE_CONTEXT_MISMATCH",
    "LIVE_CEILING_LINING_MULTI_VIEWPORT_IDENTITY_UNRESOLVED",
    "LIVE_CEILING_LINING_RESOLVED",
    "LIVE_CEILING_LINING_SCHEMA_VERSION",
    "LIVE_CEILING_LINING_TAG_FAMILY_CONFLICT",
    "LIVE_CEILING_LINING_UNAVAILABLE",
    "LiveCanonicalCeilingSurfaceObject",
    "LiveCeilingLiningClaim",
    "LiveCeilingLiningResult",
    "canonical_ceiling_from_shadow_quantity",
    "collect_live_ceiling_lining_claims",
]
