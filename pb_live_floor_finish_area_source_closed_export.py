"""Source-closed export for authenticated canonical floor-finish quantities.

Consumes only FIRM floor_finish_area QuantityEvidence already produced by
CrossViewFloorFinishProducer and retained on the same canonical floor. This
module does not infer finishes, dimensions, room identity, or benchmark mappings.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from types import MappingProxyType

from pb_geometry_takeoff_model import AuthorityStatus
from pb_live_floor_area_quantity_publication import _valid_original_source_sha
from pb_live_floor_area_source_closed_export import _same_original_floor_room_ring
from pb_live_canonical_floor_surface import LiveCanonicalFloorSurfaceObject
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_migration_contracts import QuantityEvidence
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import (
    SealedSourceClosedRun,
    SourceClosedRunConflictError,
    seal_source_closed_run,
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _original_floor_polygon_is_simple(
    points: tuple[tuple[float, float], ...],
) -> bool:
    """A source floor area cannot be sealed from a self-crossing ring.

    This is a *negative* geometry check on an already source-owned floor,
    not a replacement physical room issuer, scale or measurement authority.
    GEOS failures and unavailable validation abstain rather than publish.
    """
    if not isinstance(points, (tuple, list)) or len(points) < 3:
        return False
    try:
        if any(
            not isinstance(point, (tuple, list))
            or len(point) != 2
            or any(
                type(value) not in (int, float)
                or not math.isfinite(float(value))
                for value in point
            )
            for point in points
        ):
            return False
        from shapely.geometry import Polygon

        # An exact repeated closing coordinate is the only duplicate
        # allowed in a physical perimeter. Duplicate *interior* vertices
        # imply a collapsed/backtracked source edge, not a closed face.
        ring = tuple(tuple(point) for point in points)
        if ring[0] == ring[-1]:
            ring = ring[:-1]
        if len(ring) < 3 or len(set(ring)) != len(ring):
            return False
        shape = Polygon(ring)
        return bool(
            shape.is_valid
            and shape.exterior.is_simple
            and math.isfinite(shape.area)
            and shape.area > 0.0
        )
    except Exception:
        return False



def _require_exact_floor_finish_semantic(
    semantic_key: object,
    *,
    canonical_floor_id: str,
    finish_code: object,
    semantic_finish: object,
) -> None:
    """Original finish code, material and physical floor form one source key."""
    if (
        type(semantic_key) is not str
        or type(finish_code) is not str or not finish_code
        or finish_code != finish_code.strip()
        or type(semantic_finish) is not str or not semantic_finish
        or semantic_finish != semantic_finish.strip()
        or semantic_key !=
        f"floor_finish_area:{canonical_floor_id}:{finish_code}:{semantic_finish}"
    ):
        raise SourceClosedRunConflictError(
            "floor finish semantic identity disagrees with original source code"
        )


def build_live_floor_finish_area_source_traces(
    claim: LivePhysicalNetWallClaim,
    *,
    workspace_id: int,
    project_id: str,
) -> Mapping[str, CommercialTakeoffSourceTrace]:
    """Build exact source traces for already-authenticated floor finishes."""
    if type(claim) is not LivePhysicalNetWallClaim:
        raise TypeError("claim must be LivePhysicalNetWallClaim")
    if type(workspace_id) is not int or workspace_id <= 0:
        raise SourceClosedRunConflictError(
            "floor finish source workspace_id must be an original positive integer"
        )

    floors_by_id: dict[str, LiveCanonicalFloorSurfaceObject] = {}
    for floor in claim.canonical_floors:
        if type(floor) is not LiveCanonicalFloorSurfaceObject:
            raise TypeError(
                "canonical_floors must contain LiveCanonicalFloorSurfaceObject"
            )
        floor_id = _clean(floor.canonical_floor_id)
        if not floor_id:
            continue
        if floor_id in floors_by_id:
            raise SourceClosedRunConflictError(
                f"duplicate canonical floor identity: {floor_id}"
            )
        floors_by_id[floor_id] = floor

    traces: dict[str, CommercialTakeoffSourceTrace] = {}
    # Defensive replay boundary: producer-owned source occurrence and physical
    # floor identity are one-to-one. Different QuantityEvidence IDs cannot
    # mint independent customer rows from the same upstream physical fact.
    quantity_owner_by_floor: dict[str, str] = {}
    quantity_owner_by_physical_floor: dict[str, tuple[str, str]] = {}
    floor_owner_by_occurrence: dict[tuple[str, str, str], str] = {}
    floor_owner_by_original_observation: dict[tuple[str, str, str], str] = {}
    # Original quantity identity is a producer-owned family invariant, not
    # only a FIRM-survivor invariant. Filtering blocked evidence before this
    # check would conceal a disputed source identity from commercial sealing.
    seen_original_quantity_ids: set[str] = set()
    # Whole-family producer ID uniqueness wins FIRST, even if a later
    # material-owner rivalry is also present. Preserve the established
    # duplicate/invalid-source first-failure contracts for blocked siblings.
    for original in claim.floor_finish_quantity_evidence:
        if not isinstance(original, QuantityEvidence):
            raise TypeError(
                "floor_finish_quantity_evidence must contain QuantityEvidence"
            )
        if original.family != "floor_finish_area":
            raise SourceClosedRunConflictError(
                f"non-floor-finish quantity reached exporter: {original.quantity_id}"
            )
        original_id = original.quantity_id
        if (type(original_id) is not str or not original_id
                or original_id != original_id.strip()):
            raise SourceClosedRunConflictError(
                "invalid original floor-finish quantity id"
            )
        if original_id in seen_original_quantity_ids:
            raise SourceClosedRunConflictError(
                f"duplicate original floor-finish quantity id: {original_id}"
            )
        seen_original_quantity_ids.add(original_id)
    # The customer boundary already rejects a non-abstained numeric source
    # that retains producer blockers. Apply the same veto at the independent
    # source-seal boundary: a caller must not bypass customer projection and
    # seal a contradictory original FIRM (or other numeric) receipt directly.
    # Keep this AFTER the complete original family/ID census so duplicate
    # original identities retain their established first-failure precedence.
    for original in claim.floor_finish_quantity_evidence:
        if (
            not original.abstained
            and original.value is not None
            and original.blocking_reasons
        ):
            raise SourceClosedRunConflictError(
                "numeric floor-finish source quantity retains unresolved blockers: "
                f"{original.quantity_id}"
            )

    # Keep an explicit negative-claimant census BEFORE the FIRM-only path.
    # Original material records can remain attached to an ABSTAINED quantity
    # even when its physical floor cannot yet be published. A positive floor
    # must not silently reuse that same source mark or observation.
    abstained_original_claims: set[tuple[str, str, str, str]] = set()
    unresolved_root_original_claims: set[tuple[str, str]] = set()
    for original in claim.floor_finish_quantity_evidence:
        if not (original.abstained or original.value is None):
            continue
        original_metadata = (
            original.metadata if isinstance(original.metadata, Mapping) else {}
        )
        digest = original_metadata.get("source_sha256")
        revision = original_metadata.get("revision_id")
        root_proved = (
            _valid_original_source_sha(digest)
            and type(revision) is str
            and bool(revision)
            and revision == revision.strip()
        )
        for field in (
            "finish_occurrence_record_id",
            "finish_occurrence_evidence_id",
        ):
            source_identity = original_metadata.get(field)
            if (
                type(source_identity) is not str
                or not source_identity
                or source_identity != source_identity.strip()
            ):
                continue
            if root_proved:
                abstained_original_claims.add((
                    digest.lower(), revision, field, source_identity,
                ))
            else:
                # A missing/malformed SHA or revision does NOT make an
                # original mark disappear. Without a provable independent
                # source root, an identical source ID contests the FIRM row.
                unresolved_root_original_claims.add((field, source_identity))
    for quantity in claim.floor_finish_quantity_evidence:
        # Every original family/source ID has already been validated above.
        if quantity.abstained or quantity.value is None:
            continue
        if quantity.unit != "m2" or quantity.status != AuthorityStatus.FIRM.value:
            raise SourceClosedRunConflictError(
                "floor-finish quantity must be FIRM m2: "
                f"{quantity.quantity_id}"
            )
        if len(quantity.input_entity_ids) != 1:
            raise SourceClosedRunConflictError(
                "floor-finish quantity must own exactly one canonical floor: "
                f"{quantity.quantity_id}"
            )

        floor_id = _clean(quantity.input_entity_ids[0])
        floor = floors_by_id.get(floor_id)
        if floor is None:
            raise SourceClosedRunConflictError(
                f"floor-finish quantity references unknown canonical floor: {floor_id}"
            )
        if _clean(quantity.authority) != _clean(floor.metric_area_authority):
            raise SourceClosedRunConflictError(
                "floor-finish metric authority disagrees with canonical floor: "
                f"{quantity.quantity_id}"
            )
        if not floor.physical_floor_surface_identity_resolved:
            raise SourceClosedRunConflictError(
                f"physical floor identity is unresolved: {floor_id}"
            )
        if not _clean(floor.physical_floor_surface_id):
            raise SourceClosedRunConflictError(
                f"physical floor identity is missing: {floor_id}"
            )
        # A source-backed floor finish must consume one original documented
        # metric-area quantity, not only a copied numeric floor field.
        area_receipt_id = floor.metric_area_quantity_id
        if (
            type(area_receipt_id) is not str
            or not area_receipt_id
            or area_receipt_id != area_receipt_id.strip()
        ):
            raise SourceClosedRunConflictError(
                f"floor-finish source metric area receipt is missing: {floor_id}"
            )

        if (
            type(quantity.value) not in (int, float)
            or type(floor.metric_area_m2) not in (int, float)
            or type(quantity.confidence) not in (int, float)
        ):
            raise SourceClosedRunConflictError(
                f"floor-finish source metric is untyped: {quantity.quantity_id}"
            )
        try:
            confidence = float(quantity.confidence)
        except (TypeError, ValueError, OverflowError) as exc:
            raise SourceClosedRunConflictError(
                f"floor-finish source metric is untyped: {quantity.quantity_id}"
            ) from exc
        try:
            qvalue = float(quantity.value)
            floor_value = float(floor.metric_area_m2)
        except (TypeError, ValueError, OverflowError) as exc:
            raise SourceClosedRunConflictError(
                f"floor-finish quantity is not metric: {quantity.quantity_id}"
            ) from exc
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise SourceClosedRunConflictError(
                f"floor-finish source metric is untyped: {quantity.quantity_id}"
            )
        if (
            not math.isfinite(qvalue)
            or qvalue <= 0.0
            or not math.isfinite(floor_value)
            or abs(qvalue - floor_value) > 1e-9
        ):
            raise SourceClosedRunConflictError(
                "floor-finish quantity value disagrees with canonical floor: "
                f"{quantity.quantity_id}"
            )

        metadata = (
            quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
        )
        if _clean(metadata.get("canonical_floor_id")) != floor_id:
            raise SourceClosedRunConflictError(
                "floor-finish canonical identity metadata mismatch: "
                f"{quantity.quantity_id}"
            )
        if _clean(metadata.get("physical_floor_surface_id")) != _clean(
            floor.physical_floor_surface_id
        ):
            raise SourceClosedRunConflictError(
                "floor-finish physical identity metadata mismatch: "
                f"{quantity.quantity_id}"
            )
        if _clean(metadata.get("source_sha256")).lower() != _clean(
            floor.source_sha256
        ).lower():
            raise SourceClosedRunConflictError(
                f"floor-finish source SHA mismatch: {quantity.quantity_id}"
            )
        # Matching invented source strings are still not original hashes.
        # Reuse the same syntactic source-SHA guard as canonical floor area;
        # the original SourceVisibilityProducer must separately verify bytes.
        if (
            not _valid_original_source_sha(floor.source_sha256)
            or not _valid_original_source_sha(metadata.get("source_sha256"))
        ):
            raise SourceClosedRunConflictError(
                f"floor-finish source SHA is malformed: {quantity.quantity_id}"
            )
        # Source-local mark IDs can be reused across documents/revisions.
        # A missing or coerced revision never proves a distinct original.
        if (
            type(floor.revision_id) is not str
            or not floor.revision_id
            or floor.revision_id != floor.revision_id.strip()
            or type(metadata.get("revision_id")) is not str
            or metadata["revision_id"] != floor.revision_id
        ):
            raise SourceClosedRunConflictError(
                f"floor-finish revision mismatch: {quantity.quantity_id}"
            )

        # The physical room-face receipt is an original producer address,
        # not an optional label. Two matching missing or coerced identifiers
        # cannot authenticate a FIRM floor-finish area at the final seal.
        # Do not strip/pad or stringify either source owner into agreement.
        original_face = metadata.get("source_room_face_record_id")
        canonical_face = floor.source_room_face_record_id
        if (
            type(original_face) is not str
            or not original_face
            or original_face != original_face.strip()
            or type(canonical_face) is not str
            or not canonical_face
            or canonical_face != canonical_face.strip()
            or original_face != canonical_face
        ):
            raise SourceClosedRunConflictError(
                "floor-finish source room face mismatch: "
                f"{quantity.quantity_id}"
            )
        original_source_page = metadata.get("page_no")
        canonical_source_page = floor.page_id
        if (
            type(original_source_page) is not str
            or type(canonical_source_page) is not str
            or not original_source_page
            or not canonical_source_page
            or original_source_page != original_source_page.strip()
            or canonical_source_page != canonical_source_page.strip()
            or original_source_page != canonical_source_page
        ):
            raise SourceClosedRunConflictError(
                "floor-finish source page mismatch: "
                f"{quantity.quantity_id}"
            )

        # A semantic role is not a material finish *occurrence* without
        # its exact authenticated source dictionary code and finish family.
        if any(
            type(metadata.get(key)) is not str
            or not metadata[key]
            or metadata[key] != metadata[key].strip()
            for key in ("finish_code", "semantic_finish")
        ):
            raise SourceClosedRunConflictError(
                f"floor-finish source material identity is malformed: {quantity.quantity_id}"
            )
        # All original issuer and support addresses have one exact typed form.
        # Silently stringifying True, numbers or padded values invents source
        # lineage that the original PDF producer never issued.
        source_issuer_fields = (
            "finish_occurrence_record_id",
            "finish_definition_record_id",
            "finish_occurrence_evidence_id",
            "support_snapshot_id",
            "support_page_id",
            "support_viewport_id",
        )
        if any(
            type(metadata.get(name)) is not str
            or (
                metadata[name]
                and metadata[name] != metadata[name].strip()
            )
            for name in source_issuer_fields
        ):
            raise SourceClosedRunConflictError(
                "floor-finish source issuer identity is malformed: "
                f"{quantity.quantity_id}"
            )
        occurrence_id = _clean(metadata.get("finish_occurrence_record_id"))
        definition_id = _clean(metadata.get("finish_definition_record_id"))
        # An issuer's source observation ID is a typed PDF-address identity,
        # not a label converted to a string by _clean().
        raw_observation_id = metadata.get("finish_occurrence_evidence_id")
        if (
            type(raw_observation_id) is not str
            or (
                raw_observation_id
                and raw_observation_id != raw_observation_id.strip()
            )
        ):
            raise SourceClosedRunConflictError(
                "floor-finish original observation source ID malformed: "
                f"{quantity.quantity_id}"
            )
        occurrence_evidence_id = raw_observation_id
        # Occurrence record and source receipt are different producer IDs.
        # Require the exact source occurrence witness actually retained in
        # both QuantityEvidence and its canonical floor; a metadata-only
        # occurrence assertion cannot authorize a customer finish quantity.
        if (
            not occurrence_evidence_id
            or occurrence_evidence_id not in quantity.evidence_ids
            or occurrence_evidence_id not in floor.evidence_ids
        ):
            raise SourceClosedRunConflictError(
                "floor-finish occurrence evidence receipt mismatch: "
                f"{quantity.quantity_id}"
            )
        if not occurrence_id or not definition_id:
            raise SourceClosedRunConflictError(
                "floor-finish source occurrence/definition receipt is missing: "
                f"{quantity.quantity_id}"
            )
        # This source ID must be unique across the complete original source
        # inventory, including rejected source-owner rivals. Source/revision
        # scope avoids falsely colliding unrelated original documents that
        # reuse a local observation identifier.
        source_root = (
            floor.source_sha256.lower(), floor.revision_id,
        )
        if any(
            ((*source_root, field, receipt) in abstained_original_claims
             or (field, receipt) in unresolved_root_original_claims)
            for field, receipt in (
                ("finish_occurrence_record_id", occurrence_id),
                ("finish_occurrence_evidence_id", occurrence_evidence_id),
            )
        ):
            raise SourceClosedRunConflictError(
                "floor-finish original material source owner contested by "
                "an abstained quantity: " + quantity.quantity_id
            )
        # An original producer receipt is local to its exact SHA+revision.
        # Do not collide two independently verified source roots merely
        # because their PDF-local mark numbers are equal.
        occurrence_owner_key = (*source_root, occurrence_id)
        prior_floor = floor_owner_by_occurrence.get(occurrence_owner_key)
        if prior_floor is not None and prior_floor != floor_id:
            raise SourceClosedRunConflictError(
                "floor-finish source occurrence has competing physical floors: "
                f"{occurrence_id}"
            )
        # Resolve the most specific failed authority first: a repeated
        # canonical floor is a direct conflict before considering competing
        # canonical aliases of the same physical surface.
        prior_quantity = quantity_owner_by_floor.get(floor_id)
        if prior_quantity is not None and prior_quantity != quantity.quantity_id:
            raise SourceClosedRunConflictError(
                "canonical floor has competing finish area quantities: "
                f"{floor_id}"
            )
        physical_floor_id = _clean(floor.physical_floor_surface_id)
        prior_physical_owner = quantity_owner_by_physical_floor.get(
            physical_floor_id
        )
        if (
            prior_physical_owner is not None
            and prior_physical_owner != (floor_id, quantity.quantity_id)
        ):
            raise SourceClosedRunConflictError(
                "physical floor has competing finish area quantities: "
                f"{physical_floor_id}"
            )
        # Check the exact FT code at the customer seal only AFTER the more
        # specific competing canonical/physical floor owner checks above.
        # Preserving first-failure ordering avoids changing old conflict gates.
        _require_exact_floor_finish_semantic(
            quantity.semantic_key,
            canonical_floor_id=floor_id,
            finish_code=metadata.get("finish_code"),
            semantic_finish=metadata.get("semantic_finish"),
        )
        observation_owner_key = (*source_root, occurrence_evidence_id)
        prior_observation_floor = floor_owner_by_original_observation.get(
            observation_owner_key
        )
        if (
            prior_observation_floor is not None
            and prior_observation_floor != floor_id
        ):
            raise SourceClosedRunConflictError(
                "floor-finish original observation has competing physical floors: "
                f"{occurrence_evidence_id}"
            )
        floor_owner_by_original_observation[observation_owner_key] = floor_id
        floor_owner_by_occurrence[occurrence_owner_key] = floor_id
        quantity_owner_by_floor[floor_id] = quantity.quantity_id
        quantity_owner_by_physical_floor[physical_floor_id] = (
            floor_id, quantity.quantity_id
        )

        semantic_finish = _clean(metadata.get("semantic_finish")).lower()
        if (
            not _clean(metadata.get("support_snapshot_id"))
            or not _clean(metadata.get("support_page_id"))
            or not _clean(metadata.get("support_viewport_id"))
            or not semantic_finish
            or _clean(floor.finish_descriptor).lower() != semantic_finish
        ):
            raise SourceClosedRunConflictError(
                "floor-finish semantic mismatch with canonical floor: "
                f"{quantity.quantity_id}"
            )

        viewport_id = _clean(metadata.get("viewport_id"))
        if not viewport_id:
            raise SourceClosedRunConflictError(
                f"floor-finish quantity lacks owned viewport: {quantity.quantity_id}"
            )
        if _clean(floor.viewport_id) and _clean(floor.viewport_id) != viewport_id:
            raise SourceClosedRunConflictError(
                f"floor-finish viewport mismatch: {quantity.quantity_id}"
            )

        # A source trace may not conceal duplicated or blank evidence IDs
        # through set normalization before commercial sealing.
        for receipts in (floor.evidence_ids, quantity.evidence_ids):
            if (
                not isinstance(receipts, (tuple, list))
                or not receipts
                or any(type(value) is not str or not value or value != value.strip()
                       for value in receipts)
                or len(set(receipts)) != len(receipts)
            ):
                raise SourceClosedRunConflictError(
                    "floor-finish source evidence receipts are incomplete or duplicated: "
                    f"{quantity.quantity_id}"
                )
        floor_evidence = set(floor.evidence_ids)
        if not set(quantity.evidence_ids).issubset(floor_evidence):
            raise SourceClosedRunConflictError(
                "floor-finish source trace does not cover quantity evidence: "
                f"{quantity.quantity_id}"
            )

        points = tuple(floor.polygon_pdf_pts or ())
        if not floor.geometry_complete or len(points) < 3:
            raise SourceClosedRunConflictError(
                "floor-finish source polygon is invalid or incomplete: "
                f"{quantity.quantity_id}"
            )
        source_bbox = None
        if points:
            try:
                if any(
                    not isinstance(point, (tuple, list)) or len(point) != 2
                    or any(type(v) not in (int, float) for v in point)
                    for point in points
                ):
                    raise ValueError("untyped source point coordinates")
                xs = tuple(float(point[0]) for point in points)
                ys = tuple(float(point[1]) for point in points)
            except (TypeError, ValueError, IndexError, OverflowError) as exc:
                raise SourceClosedRunConflictError(
                    f"floor source polygon is invalid: {quantity.quantity_id}"
                ) from exc
            if xs and ys:
                if (
                    len(points) < 3
                    or not all(math.isfinite(value) for value in (*xs, *ys))
                    or max(xs) <= min(xs)
                    or max(ys) <= min(ys)
                ):
                    raise SourceClosedRunConflictError(
                        "floor-finish source polygon is invalid: "
                        f"{quantity.quantity_id}"
                    )
                # Bounding boxes do not prove a physical floor face. A
                # diagonal collinear or self-cancelling source room may have
                # a positive box and old FIRM m2, but cannot seal a finish.
                try:
                    twice_area = math.fsum(
                        xs[i] * ys[(i + 1) % len(xs)]
                        - xs[(i + 1) % len(xs)] * ys[i]
                        for i in range(len(xs))
                    )
                except (ValueError, OverflowError) as exc:
                    raise SourceClosedRunConflictError(
                        f"floor-finish source polygon is invalid: {quantity.quantity_id}"
                    ) from exc
                if not math.isfinite(twice_area) or abs(twice_area) <= 2e-9:
                    raise SourceClosedRunConflictError(
                        f"floor-finish source polygon is degenerate: {quantity.quantity_id}"
                    )
                # A bow-tie or source stroke backtrack can have strictly
                # positive shoelace area. It is not a physical floor ring.
                if not _original_floor_polygon_is_simple(points):
                    raise SourceClosedRunConflictError(
                        f"floor-finish source polygon self-intersects or is invalid: {quantity.quantity_id}"
                    )
                source_bbox = (min(xs), min(ys), max(xs), max(ys))

        # The canonical floor is projected from one original room face.
        # A foreign simple room polygon cannot lend source ownership to a
        # previously FIRM floor-finish area. Roomless legacy runs stay intact.
        if claim.canonical_rooms:
            owners = tuple(
                room for room in claim.canonical_rooms
                if getattr(room, "canonical_room_id", None) == floor.room_entity_id
            )
            if len(owners) != 1:
                raise SourceClosedRunConflictError(
                    "floor-finish original canonical room owner missing or contested: "
                    f"{quantity.quantity_id}"
                )
            room = owners[0]
            room_source = (
                room.canonical_room_id, room.document_id, room.revision_id,
                room.source_sha256, room.snapshot_id, room.page_id,
                room.source_room_face_record_id, room.viewport_id,
            )
            floor_source = (
                floor.room_entity_id, floor.document_id, floor.revision_id,
                floor.source_sha256, floor.snapshot_id, floor.page_id,
                floor.source_room_face_record_id, floor.viewport_id,
            )
            if (
                any(
                    type(value) is not str or not value or value != value.strip()
                    for value in (*room_source, *floor_source)
                )
                or room_source[:3] != floor_source[:3]
                or room.source_sha256.lower() != floor.source_sha256.lower()
                or room_source[4:] != floor_source[4:]
                or not _same_original_floor_room_ring(
                    points, room.polygon_pdf_pts, quantity_id=quantity.quantity_id,
                )
            ):
                raise SourceClosedRunConflictError(
                    "floor-finish original canonical room geometry/source mismatch: "
                    f"{quantity.quantity_id}"
                )

        trace = CommercialTakeoffSourceTrace(
            workspace_id=workspace_id,
            project_id=project_id,
            document_id=floor.document_id,
            source_sha256=floor.source_sha256,
            source_page=str(floor.page_id),
            viewport_id=viewport_id,
            revision_id=floor.revision_id,
            current_revision_id=floor.revision_id,
            evidence_ids=tuple(sorted(floor_evidence)),
            canonical_entity_ids=tuple(
                dict.fromkeys(
                    value
                    for value in (
                        floor_id,
                        _clean(floor.physical_floor_surface_id),
                        _clean(floor.room_entity_id),
                    )
                    if value
                )
            ),
            source_bbox=source_bbox,
            metadata={
                "family": "floor_finish_area",
                "canonical_floor_id": floor_id,
                "physical_floor_surface_id": floor.physical_floor_surface_id,
                "room_entity_id": floor.room_entity_id,
                "source_room_face_record_id": floor.source_room_face_record_id,
                "finish_code": metadata.get("finish_code"),
                "semantic_finish": semantic_finish,
                "support_snapshot_id": metadata.get("support_snapshot_id"),
                "support_page_id": metadata.get("support_page_id"),
                "support_viewport_id": metadata.get("support_viewport_id"),
                "support_source_partition_id": metadata.get(
                    "support_source_partition_id"
                ),
                "support_block_no": metadata.get("support_block_no"),
                "finish_binding_mode": metadata.get("finish_binding_mode"),
                "finish_definition_record_id": metadata.get(
                    "finish_definition_record_id"
                ),
                "finish_occurrence_record_id": metadata.get(
                    "finish_occurrence_record_id"
                ),
                "source_dimension_page_id": metadata.get(
                    "source_dimension_page_id"
                ),
            },
        )
        if quantity.quantity_id in traces:
            raise SourceClosedRunConflictError(
                f"duplicate floor-finish quantity id: {quantity.quantity_id}"
            )
        traces[quantity.quantity_id] = trace

    return MappingProxyType(traces)


def seal_live_floor_finish_area_run(
    claim: LivePhysicalNetWallClaim,
    *,
    workspace_id: int,
    project_id: str,
) -> SealedSourceClosedRun:
    """Seal already-FIRM canonical floor-finish area quantities."""
    quantities = tuple(
        quantity
        for quantity in claim.floor_finish_quantity_evidence
        if isinstance(quantity, QuantityEvidence)
        and not quantity.abstained
        and quantity.value is not None
    )
    traces = build_live_floor_finish_area_source_traces(
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
    "build_live_floor_finish_area_source_traces",
    "seal_live_floor_finish_area_run",
]
