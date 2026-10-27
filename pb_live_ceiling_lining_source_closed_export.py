"""Source-closed export for cross-view canonical ceiling-lining quantities.

Consumes only typed canonical ceilings and FIRM ceiling_lining QuantityEvidence
already published by the live integration. This module does not extract, bind,
measure, infer a finish, read benchmark truth, or create a new quantity.
"""
from __future__ import annotations

import math
from types import MappingProxyType
from typing import Mapping

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_live_floor_area_quantity_publication import _valid_original_source_sha
from pb_migration_contracts import QuantityEvidence
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import (
    SealedSourceClosedRun,
    SourceClosedRunConflictError,
    seal_source_closed_run,
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _original_ceiling_simple_bbox(
    points: list[tuple[float, float]] | tuple[tuple[float, float], ...],
    *,
    quantity_id: str,
) -> tuple[float, float, float, float]:
    """Negative geometry veto only; no ceil finish or source area derived."""
    def finite_source_coordinate(value: object) -> bool:
        if type(value) not in (int, float):
            return False
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError, OverflowError):
            return False

    if type(points) not in (tuple, list) or len(points) < 3 or any(
        type(p) not in (tuple, list) or len(p) != 2 or
        any(not finite_source_coordinate(v) for v in p)
        for p in points
    ):
        raise SourceClosedRunConflictError(
            f"canonical ceiling polygon is invalid: {quantity_id}"
        )
    ring = tuple((float(p[0]), float(p[1])) for p in points)
    # Genuine PDF polygons may close on the first vertex; other repeated
    # interior vertices, crossed source paths and zero-area rings cannot
    # authorize an actual ceiling surface.
    if len(ring) > 1 and ring[-1] == ring[0]:
        ring = ring[:-1]
    if len(ring) < 3 or len(set(ring)) != len(ring):
        raise SourceClosedRunConflictError(
            f"canonical ceiling polygon is not a simple physical zone: {quantity_id}"
        )
    from shapely.errors import GEOSException
    from shapely.geometry import Polygon
    try:
        polygon = Polygon(ring)
        valid = (
            polygon.is_valid and polygon.exterior.is_simple
            and math.isfinite(polygon.area) and polygon.area > 0.0
        )
    except (GEOSException, ValueError, OverflowError) as exc:
        raise SourceClosedRunConflictError(
            f"canonical ceiling polygon GEOS geometry invalid: {quantity_id}"
        ) from exc
    if not valid:
        raise SourceClosedRunConflictError(
            f"canonical ceiling polygon is not a simple physical zone: {quantity_id}"
        )
    return polygon.bounds



def _require_exact_ceiling_finish_semantic(
    *,
    semantic_key: object,
    canonical_ceiling_id: str,
    finish_code: object,
    semantic_finish: object,
) -> None:
    """Veto a rekeyed original ceiling finish; do not infer materials."""
    if (
        type(semantic_key) is not str
        or type(finish_code) is not str or not finish_code
        or finish_code != finish_code.strip()
        or type(semantic_finish) is not str or not semantic_finish
        or semantic_finish != semantic_finish.strip()
        or semantic_key !=
        f"ceiling_lining:{canonical_ceiling_id}:{finish_code}:{semantic_finish}"
    ):
        raise SourceClosedRunConflictError(
            "ceiling quantity semantic key conflicts with exact source finish"
        )


def _require_one_ceiling_per_original_area(
    owners: dict[tuple[str, str, str], str],
    *,
    source_root: tuple[str, str],
    upstream_area_id: object,
    canonical_ceiling_id: str,
) -> None:
    """One original whole-room area cannot source two physical ceilings."""
    if (
        type(upstream_area_id) is not str or not upstream_area_id
        or upstream_area_id != upstream_area_id.strip()
        or type(canonical_ceiling_id) is not str or not canonical_ceiling_id
        or canonical_ceiling_id != canonical_ceiling_id.strip()
    ):
        raise SourceClosedRunConflictError(
            "ceiling original upstream room-area issuer is invalid"
        )
    # PDF producer IDs are document/revision-local. Two independent
    # originals can reuse an area receipt without sharing physical ownership.
    original_key = (*source_root, upstream_area_id)
    previous = owners.get(original_key)
    if previous is not None and previous != canonical_ceiling_id:
        raise SourceClosedRunConflictError(
            "one original room-area source reissued as competing ceiling surfaces"
        )
    owners[original_key] = canonical_ceiling_id


def build_live_ceiling_lining_source_traces(
    claim: LivePhysicalNetWallClaim,
    *,
    workspace_id: int,
    project_id: str,
) -> Mapping[str, CommercialTakeoffSourceTrace]:
    if type(claim) is not LivePhysicalNetWallClaim:
        raise TypeError("claim must be LivePhysicalNetWallClaim")
    if type(workspace_id) is not int or workspace_id <= 0:
        raise SourceClosedRunConflictError("ceiling workspace_id requires exact positive integer")

    rooms_by_canonical_id = {}
    rooms_by_physical_id = {}
    for room in claim.canonical_rooms:
        canonical_id = _clean(room.canonical_room_id)
        physical_id = _clean(room.physical_room_id)
        if not canonical_id or not physical_id:
            continue
        if canonical_id in rooms_by_canonical_id:
            raise SourceClosedRunConflictError(
                f"duplicate canonical room identity: {canonical_id}"
            )
        if physical_id in rooms_by_physical_id:
            raise SourceClosedRunConflictError(
                f"duplicate physical room identity: {physical_id}"
            )
        rooms_by_canonical_id[canonical_id] = room
        rooms_by_physical_id[physical_id] = room

    ceilings = {}
    for ceiling in claim.canonical_ceilings:
        canonical_id = _clean(ceiling.canonical_ceiling_id)
        if not canonical_id:
            continue
        if canonical_id in ceilings:
            raise SourceClosedRunConflictError(
                f"duplicate canonical ceiling identity: {canonical_id}"
            )
        ceilings[canonical_id] = ceiling

    traces: dict[str, CommercialTakeoffSourceTrace] = {}
    seen_source_ids: set[str] = set()
    # Exact original quantity IDs are the earliest family gate. Preserve
    # existing duplicate/invalid-source failures before any new RCP mark
    # rivalry, including an ABSTAINED clone preceding a positive record.
    for original in claim.ceiling_lining_quantity_evidence:
        if not isinstance(original, QuantityEvidence):
            raise TypeError(
                "ceiling_lining_quantity_evidence must contain QuantityEvidence"
            )
        if original.family != "ceiling_lining":
            raise SourceClosedRunConflictError(
                f"non-ceiling quantity reached ceiling exporter: {original.quantity_id}"
            )
        original_id = original.quantity_id
        if (
            type(original_id) is not str or not original_id
            or original_id != original_id.strip()
            or original_id in seen_source_ids
        ):
            raise SourceClosedRunConflictError(
                f"duplicate or invalid original ceiling-lining quantity id: {original_id}"
            )
        seen_source_ids.add(original_id)
    # A numeric original with unresolved producer blockers cannot become a
    # source-closed ceiling simply because the direct seal caller bypasses the
    # customer projection's separate inventory veto. Keep this AFTER the
    # complete original family/ID census so duplicate source IDs retain their
    # established first-failure classification. True ABSTAINED rivals remain
    # in the original material-mark census below.
    for original in claim.ceiling_lining_quantity_evidence:
        if (
            not original.abstained
            and original.value is not None
            and original.blocking_reasons
        ):
            raise SourceClosedRunConflictError(
                "numeric ceiling-lining source quantity retains unresolved blockers: "
                f"{original.quantity_id}"
            )
    source_area_ceiling_owners: dict[tuple[str, str, str], str] = {}
    original_mark_ceiling_owners: dict[tuple[str, str, str], str] = {}
    original_occurrence_ceiling_owners: dict[tuple[str, str, str], str] = {}
    # Preserve source-owned rivals rejected by geometry/measurement authority.
    # The FIRM-only loop below cannot independently see such claimants.
    abstained_original_marks: set[tuple[str, str, str, str]] = set()
    unresolved_root_original_marks: set[tuple[str, str]] = set()
    for prior in claim.ceiling_lining_quantity_evidence:
        if not isinstance(prior, QuantityEvidence):
            continue  # Existing complete inventory validation below raises.
        if not (prior.abstained or prior.value is None):
            continue
        prior_meta = prior.metadata if isinstance(prior.metadata, Mapping) else {}
        digest = prior_meta.get("source_sha256")
        revision = prior_meta.get("revision_id")
        root_proved = (
            _valid_original_source_sha(digest)
            and type(revision) is str
            and bool(revision)
            and revision == revision.strip()
        )
        for key in (
            "finish_occurrence_record_id",
            "finish_occurrence_evidence_id",
        ):
            original_id = prior_meta.get(key)
            if (type(original_id) is str and original_id
                    and original_id == original_id.strip()):
                if root_proved:
                    abstained_original_marks.add((
                        digest.lower(), revision, key, original_id,
                    ))
                else:
                    # Missing source ownership cannot prove that a known
                    # competing original mark belongs to another document.
                    unresolved_root_original_marks.add((key, original_id))
    for quantity in claim.ceiling_lining_quantity_evidence:
        # Complete original source identity was prevalidated above.
        if quantity.abstained or quantity.value is None:
            continue
        if len(quantity.input_entity_ids) != 1:
            raise SourceClosedRunConflictError(
                f"ceiling quantity must own one canonical ceiling identity: "
                f"{quantity.quantity_id}"
            )
        if (
            _clean(quantity.status) != AuthorityStatus.FIRM.value
            or _clean(quantity.authority)
            != MeasurementAuthorityType.DOCUMENTED_DIMENSION.value
        ):
            raise SourceClosedRunConflictError(
                f"ceiling quantity is not firm documented authority: "
                f"{quantity.quantity_id}"
            )

        metadata = (
            quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
        )
        # Native figured dimensions are source-owned IDs. Trimming/deduping
        # a forged imported pair can fabricate two admissible measuring axes.
        original_figured_ids = metadata.get("figured_dimension_ids")
        if (
            type(original_figured_ids) not in (tuple, list)
            or len(original_figured_ids) != 2
            or any(type(value) is not str or not value or value != value.strip()
                   for value in original_figured_ids)
            or len(set(original_figured_ids)) != 2
        ):
            raise SourceClosedRunConflictError(
                f"documented ceiling quantity lacks exact figured dimension pair: {quantity.quantity_id}"
            )
        figured_ids = tuple(sorted(original_figured_ids))

        canonical_ceiling_id = _clean(quantity.input_entity_ids[0])
        _require_exact_ceiling_finish_semantic(
            semantic_key=quantity.semantic_key,
            canonical_ceiling_id=canonical_ceiling_id,
            finish_code=metadata.get("finish_code"),
            semantic_finish=metadata.get("semantic_finish"),
        )
        ceiling = ceilings.get(canonical_ceiling_id)
        if ceiling is None:
            raise SourceClosedRunConflictError(
                f"ceiling quantity references unknown canonical ceiling: "
                f"{canonical_ceiling_id}"
            )
        if (
            _clean(metadata.get("canonical_ceiling_id")) != canonical_ceiling_id
            or _clean(metadata.get("physical_ceiling_surface_id"))
            != canonical_ceiling_id
            or _clean(ceiling.ceiling_quantity_id) != _clean(quantity.quantity_id)
        ):
            raise SourceClosedRunConflictError(
                f"ceiling quantity canonical identity mismatch: "
                f"{quantity.quantity_id}"
            )

        canonical_room_id = _clean(metadata.get("canonical_room_id"))
        physical_room_id = _clean(metadata.get("physical_room_id"))
        room = rooms_by_canonical_id.get(canonical_room_id)
        if (
            room is None
            or rooms_by_physical_id.get(physical_room_id) is not room
            or _clean(ceiling.room_entity_id) != canonical_room_id
        ):
            raise SourceClosedRunConflictError(
                f"ceiling quantity references unknown room identity: "
                f"{quantity.quantity_id}"
            )

        # A source room-face is a producer-owned physical geometry receipt.
        # Normalizing both sides allowed two missing, padded or type-coerced
        # receipts to agree and inherit the original room's ceiling m².
        # Preserve the exact original source identity before any FIRM seal.
        original_face_id = metadata.get("source_room_face_record_id")
        producer_face_id = room.source_room_face_record_id
        if (
            type(producer_face_id) is not str
            or not producer_face_id
            or producer_face_id != producer_face_id.strip()
            or type(original_face_id) is not str
            or original_face_id != producer_face_id
        ):
            raise SourceClosedRunConflictError(
                f"ceiling quantity original room-face receipt mismatch: "
                f"{quantity.quantity_id}"
            )

        if type(quantity.value) not in (int, float) or type(ceiling.area_m2) not in (int, float):
            raise SourceClosedRunConflictError(
                f"ceiling quantity is not typed metric: {quantity.quantity_id}"
            )
        try:
            value = float(quantity.value)
            ceiling_value = float(ceiling.area_m2)
        except (TypeError, ValueError, OverflowError) as exc:
            raise SourceClosedRunConflictError(
                f"ceiling quantity is not metric: {quantity.quantity_id}"
            ) from exc
        if (
            not math.isfinite(value)
            or value <= 0.0
            or not math.isfinite(ceiling_value)
            or abs(value - ceiling_value) > 1e-9
        ):
            raise SourceClosedRunConflictError(
                f"ceiling quantity disagrees with canonical ceiling area: "
                f"{quantity.quantity_id}"
            )

        if (
            _clean(metadata.get("document_id")) != _clean(ceiling.document_id)
            or _clean(metadata.get("source_sha256")).lower()
            != _clean(ceiling.source_sha256).lower()
            or _clean(metadata.get("revision_id")) != _clean(ceiling.revision_id)
            or _clean(metadata.get("snapshot_id")) != _clean(ceiling.snapshot_id)
            or _clean(metadata.get("page_no")) != str(ceiling.source_page)
            or _clean(metadata.get("viewport_id")) != _clean(ceiling.viewport_id)
            or _clean(metadata.get("upstream_room_area_quantity_id"))
            != _clean(ceiling.room_area_quantity_id)
            or _clean(metadata.get("source_room_index_id"))
            != _clean(ceiling.source_room_index_id)
            or _clean(metadata.get("semantic_finish"))
            != _clean(ceiling.finish_descriptor)
            or _clean(ceiling.measurement_authority)
            != MeasurementAuthorityType.DOCUMENTED_DIMENSION.value
            or tuple(sorted(ceiling.figured_dimension_ids)) != figured_ids
        ):
            raise SourceClosedRunConflictError(
                f"ceiling quantity canonical lineage mismatch: "
                f"{quantity.quantity_id}"
            )

        # Do not accept an invented, padded or missing original root simply
        # because a caller has made the metadata and canonical object agree.
        # This is a negative check, not original-PDF authentication.
        if (
            not _valid_original_source_sha(ceiling.source_sha256)
            or not _valid_original_source_sha(metadata.get("source_sha256"))
            or type(ceiling.revision_id) is not str
            or not ceiling.revision_id
            or ceiling.revision_id != ceiling.revision_id.strip()
            or type(metadata.get("revision_id")) is not str
            or metadata["revision_id"] != ceiling.revision_id
        ):
            raise SourceClosedRunConflictError(
                f"ceiling original source root is malformed: {quantity.quantity_id}"
            )

        # RCP support IDs are independent original semantic-source receipts.
        # Stringifying or stripping an imported value here would allow a
        # reconstructed FIRM row to borrow an unproved page, viewport or
        # snapshot before the actual seal/customer source trace is built.
        for support_field in (
            "support_snapshot_id", "support_page_id", "support_viewport_id",
        ):
            receipt = metadata.get(support_field)
            if (
                type(receipt) is not str
                or not receipt
                or receipt != receipt.strip()
            ):
                raise SourceClosedRunConflictError(
                    "ceiling quantity lacks exact semantic support lineage: "
                    f"{quantity.quantity_id} ({support_field})"
                )

        if _clean(metadata.get("row_role")) != "ceiling_area":
            raise SourceClosedRunConflictError(
                f"ceiling quantity row role mismatch: {quantity.quantity_id}"
            )

        # Reject malformed original producer receipts without trimming
        # source IDs or silently deduplicating a disputed observation.
        for receipts in (ceiling.evidence_ids, quantity.evidence_ids):
            if (
                type(receipts) not in (tuple, list) or not receipts
                or any(type(v) is not str or not v or v != v.strip() for v in receipts)
                or len(set(receipts)) != len(receipts)
            ):
                raise SourceClosedRunConflictError(
                    f"canonical ceiling trace receipts are invalid: {quantity.quantity_id}"
                )
        evidence_ids = tuple(ceiling.evidence_ids)
        if not set(quantity.evidence_ids).issubset(set(evidence_ids)):
            raise SourceClosedRunConflictError(
                f"canonical ceiling trace does not cover quantity evidence: {quantity.quantity_id}"
            )

        # An original finish observation is independent of the producer's
        # occurrence record and dictionary definition. Each must remain an
        # exact issuer-owned ID; never turn a boolean, integer or padded
        # string into a valid material source receipt.
        original_fields = (
            "finish_occurrence_record_id",
            "finish_occurrence_evidence_id",
            "finish_definition_record_id",
            "finish_code",
            "semantic_finish",
        )
        if any(
            type(metadata.get(key)) is not str
            or not metadata[key]
            or metadata[key] != metadata[key].strip()
            for key in original_fields
        ):
            raise SourceClosedRunConflictError(
                f"ceiling material original issuer receipt malformed: {quantity.quantity_id}"
            )
        mark_id = metadata["finish_occurrence_evidence_id"]
        occurrence_id = metadata["finish_occurrence_record_id"]
        if mark_id not in quantity.evidence_ids or mark_id not in evidence_ids:
            raise SourceClosedRunConflictError(
                f"ceiling material occurrence source receipt mismatch: {quantity.quantity_id}"
            )
        # An unmeasurable rival does not relinquish the original RCP mark.
        # Compare source roots to distinguish unrelated PDF/revision-local IDs.
        root = (ceiling.source_sha256.lower(), ceiling.revision_id)
        if any(
            ((*root, field, original_id) in abstained_original_marks
             or (field, original_id) in unresolved_root_original_marks)
            for field, original_id in (
                ("finish_occurrence_record_id", occurrence_id),
                ("finish_occurrence_evidence_id", mark_id),
            )
        ):
            raise SourceClosedRunConflictError(
                "original RCP material mark contested by abstained source "
                "quantity: " + quantity.quantity_id
            )

        points = ceiling.polygon_pdf_pts
        if type(points) not in (tuple, list) or len(points) < 3:
            raise SourceClosedRunConflictError(
                f"canonical ceiling polygon is invalid: {quantity.quantity_id}"
            )
        checked = []
        for point in points:
            if (type(point) not in (tuple, list) or len(point) != 2
                    or any(type(v) not in (int, float) for v in point)):
                raise SourceClosedRunConflictError(
                    f"canonical ceiling polygon is invalid: {quantity.quantity_id}"
                )
            try:
                x, y = float(point[0]), float(point[1])
            except (TypeError, ValueError, OverflowError) as exc:
                raise SourceClosedRunConflictError(
                    f"canonical ceiling polygon is invalid: {quantity.quantity_id}"
                ) from exc
            if not math.isfinite(x) or not math.isfinite(y):
                raise SourceClosedRunConflictError(
                    f"canonical ceiling polygon is invalid: {quantity.quantity_id}"
                )
            checked.append((x, y))
        xs, ys = [p[0] for p in checked], [p[1] for p in checked]
        doubled_area = math.fsum(
            checked[i][0] * checked[(i + 1) % len(checked)][1]
            - checked[(i + 1) % len(checked)][0] * checked[i][1]
            for i in range(len(checked))
        )
        if (max(xs) <= min(xs) or max(ys) <= min(ys)
                or not math.isfinite(doubled_area) or abs(doubled_area) <= 2e-9):
            raise SourceClosedRunConflictError(
                f"canonical ceiling polygon is invalid: {quantity.quantity_id}"
            )
        source_bbox = _original_ceiling_simple_bbox(
            checked, quantity_id=quantity.quantity_id
        )

        trace = CommercialTakeoffSourceTrace(
            workspace_id=workspace_id,
            project_id=project_id,
            document_id=ceiling.document_id,
            source_sha256=ceiling.source_sha256,
            source_page=str(ceiling.source_page),
            viewport_id=ceiling.viewport_id,
            revision_id=ceiling.revision_id,
            current_revision_id=ceiling.revision_id,
            evidence_ids=evidence_ids,
            canonical_entity_ids=tuple(
                dict.fromkeys(
                    (
                        canonical_ceiling_id,
                        canonical_room_id,
                        physical_room_id,
                    )
                )
            ),
            source_bbox=source_bbox,
            metadata={
                "family": "ceiling_lining",
                "canonical_ceiling_id": canonical_ceiling_id,
                "physical_ceiling_surface_id": canonical_ceiling_id,
                "canonical_room_id": canonical_room_id,
                "physical_room_id": physical_room_id,
                "source_room_face_record_id": room.source_room_face_record_id,
                "source_room_index_id": ceiling.source_room_index_id,
                "room_area_quantity_id": ceiling.room_area_quantity_id,
                "support_page_id": metadata.get("support_page_id"),
                "support_viewport_id": metadata.get("support_viewport_id"),
                "support_snapshot_id": metadata.get("support_snapshot_id"),
                "finish_code": metadata.get("finish_code"),
                "semantic_finish": metadata.get("semantic_finish"),
                "measurement_authority": ceiling.measurement_authority,
                "figured_dimension_ids": tuple(ceiling.figured_dimension_ids),
            },
        )
        if quantity.quantity_id in traces:
            raise SourceClosedRunConflictError(
                f"duplicate ceiling quantity id: {quantity.quantity_id}"
            )
        _require_one_ceiling_per_original_area(
            source_area_ceiling_owners,
            source_root=root,
            upstream_area_id=metadata.get("upstream_room_area_quantity_id"),
            canonical_ceiling_id=canonical_ceiling_id,
        )
        # Two distinct physical ceilings cannot claim one original RCP mark
        # even if the producer rekeys the occurrence or quantity identifiers.
        # Check AFTER established source area and canonical gates so their
        # first-failure classifications remain stable.
        for original_id, owners in (
            (mark_id, original_mark_ceiling_owners),
            (occurrence_id, original_occurrence_ceiling_owners),
        ):
            original_key = (*root, original_id)
            earlier = owners.get(original_key)
            if earlier is not None and earlier != canonical_ceiling_id:
                raise SourceClosedRunConflictError(
                    f"original RCP material mark has competing ceilings: {original_id}"
                )
            owners[original_key] = canonical_ceiling_id
        traces[quantity.quantity_id] = trace

    return MappingProxyType(traces)


def seal_live_ceiling_lining_run(
    claim: LivePhysicalNetWallClaim,
    *,
    workspace_id: int,
    project_id: str,
) -> SealedSourceClosedRun:
    quantities = tuple(
        quantity
        for quantity in claim.ceiling_lining_quantity_evidence
        if not quantity.abstained and quantity.value is not None
    )
    traces = build_live_ceiling_lining_source_traces(
        claim,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    return seal_source_closed_run(
        quantities,
        project_id=project_id,
        traces_by_quantity_id=traces,
    )


__all__ = [
    "build_live_ceiling_lining_source_traces",
    "seal_live_ceiling_lining_run",
]
