"""Source-closed export for canonical ceiling-area quantities.

Consumes only FIRM canonical ceiling QuantityEvidence already published by
publish_live_ceiling_area_quantities. This module does not discover ceilings,
measure geometry, promote customer rows, or read benchmark truth.
"""
from __future__ import annotations

import math
from types import MappingProxyType
from typing import Mapping

from pb_live_ceiling_area_quantity_publication import (
    publish_live_ceiling_area_quantities,
)
from pb_live_ceiling_lining_integration import LiveCeilingLiningResult
from pb_live_ceiling_lining_source_closed_export import _original_ceiling_simple_bbox
from pb_migration_contracts import QuantityEvidence
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import (
    SealedSourceClosedRun,
    SourceClosedRunConflictError,
    seal_source_closed_run,
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def build_live_ceiling_area_source_traces(
    result: LiveCeilingLiningResult,
    *,
    workspace_id: int,
    project_id: str,
) -> Mapping[str, CommercialTakeoffSourceTrace]:
    """Build exact canonical-ceiling source traces for final ceiling quantities."""
    if type(result) is not LiveCeilingLiningResult:
        raise TypeError("result must be LiveCeilingLiningResult")
    if type(workspace_id) is not int or workspace_id <= 0:
        raise SourceClosedRunConflictError(
            "canonical ceiling source workspace_id must be an original positive integer"
        )

    # The canonical ceiling publisher deliberately accepts *identical* raw
    # source replay as provisional/idempotent. The final signed commercial
    # boundary has a stronger contract: one producer source receipt ID cannot
    # appear twice, even as ABSTAIN or an equality-identical replay. Inspect
    # the entire original typed family before any published FIRM filtering.
    seen_original_source_ids: set[str] = set()
    for original in result.quantity_evidence:
        if not isinstance(original, QuantityEvidence):
            raise TypeError("quantity_evidence must contain QuantityEvidence")
        if original.family != "ceiling_lining":
            raise SourceClosedRunConflictError(
                "non-ceiling original quantity reached ceiling-area source seal"
            )
        original_id = original.quantity_id
        if (
            type(original_id) is not str
            or not original_id
            or original_id != original_id.strip()
            or original_id in seen_original_source_ids
        ):
            raise SourceClosedRunConflictError(
                f"duplicate or invalid original ceiling source quantity id: {original_id}"
            )
        seen_original_source_ids.add(original_id)

    # The provisional canonical publisher can filter contradictory original
    # numeric FIRM claims before the source-closed trace is constructed. Audit
    # the COMPLETE typed original inventory after duplicate/family validation:
    # a blocked positive original may not vanish from a direct sealed run.
    # Genuine abstained/provisional sources remain nonpublishing as before.
    for original in result.quantity_evidence:
        if (
            not original.abstained
            and original.value is not None
            and _clean(original.status).casefold() == "firm"
            and original.blocking_reasons
        ):
            raise SourceClosedRunConflictError(
                "legacy numeric firm ceiling source retains unresolved blockers: "
                f"{original.quantity_id}"
            )

    ceilings = {}
    for ceiling in result.canonical_ceilings:
        canonical_id = _clean(ceiling.canonical_ceiling_id)
        if not canonical_id:
            continue
        if canonical_id in ceilings:
            raise SourceClosedRunConflictError(
                f"duplicate canonical ceiling identity: {canonical_id}"
            )
        ceilings[canonical_id] = ceiling

    traces: dict[str, CommercialTakeoffSourceTrace] = {}
    # Two distinct canonical rooms must not reissue the very same physical
    # original ceiling face as independent FIRM quantities.  Source-area IDs
    # and room labels alone cannot establish two physical ceiling surfaces.
    # This is a negative-only seal check, not an area/finish measurement.
    claimed_original_faces: dict[tuple[object, ...], str] = {}
    for quantity in publish_live_ceiling_area_quantities(result):
        if not isinstance(quantity, QuantityEvidence):
            raise TypeError("ceiling quantities must contain QuantityEvidence")
        if quantity.family != "ceiling_lining":
            raise SourceClosedRunConflictError(
                f"non-ceiling quantity reached ceiling exporter: {quantity.quantity_id}"
            )
        if quantity.abstained or quantity.value is None:
            continue
        if len(quantity.input_entity_ids) != 1:
            raise SourceClosedRunConflictError(
                f"ceiling quantity must own one canonical ceiling: {quantity.quantity_id}"
            )

        canonical_id = _clean(quantity.input_entity_ids[0])
        ceiling = ceilings.get(canonical_id)
        if ceiling is None:
            raise SourceClosedRunConflictError(
                f"ceiling quantity references unknown canonical ceiling: {canonical_id}"
            )
        try:
            qvalue = float(quantity.value)
            ceiling_value = float(ceiling.area_m2)
        except (TypeError, ValueError, OverflowError) as exc:
            raise SourceClosedRunConflictError(
                f"ceiling quantity is not metric: {quantity.quantity_id}"
            ) from exc
        if (
            not math.isfinite(qvalue)
            or qvalue <= 0.0
            or not math.isfinite(ceiling_value)
            or abs(qvalue - ceiling_value) > 1e-9
        ):
            raise SourceClosedRunConflictError(
                f"ceiling quantity value disagrees with canonical ceiling: {quantity.quantity_id}"
            )

        metadata = quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
        if _clean(metadata.get("canonical_ceiling_id")) != canonical_id:
            raise SourceClosedRunConflictError(
                f"ceiling quantity canonical identity mismatch: {quantity.quantity_id}"
            )
        if (
            _clean(metadata.get("source_sha256")).lower()
            != _clean(ceiling.source_sha256).lower()
        ):
            raise SourceClosedRunConflictError(
                f"ceiling quantity source SHA mismatch: {quantity.quantity_id}"
            )
        if _clean(metadata.get("revision_id")) != _clean(ceiling.revision_id):
            raise SourceClosedRunConflictError(
                f"ceiling quantity revision mismatch: {quantity.quantity_id}"
            )
        if _clean(metadata.get("viewport_id")) != _clean(ceiling.viewport_id):
            raise SourceClosedRunConflictError(
                f"ceiling quantity viewport mismatch: {quantity.quantity_id}"
            )
        if _clean(metadata.get("page_no")) != str(ceiling.source_page):
            raise SourceClosedRunConflictError(
                f"ceiling quantity page mismatch: {quantity.quantity_id}"
            )

        # Preserve original native ceiling receipts; source normalization may
        # not silently repair a padded, untyped or duplicated source identity.
        for original_receipts in (ceiling.evidence_ids, quantity.evidence_ids):
            if (
                type(original_receipts) not in (tuple, list)
                or not original_receipts
                or any(type(v) is not str or not v or v != v.strip()
                       for v in original_receipts)
                or len(set(original_receipts)) != len(original_receipts)
            ):
                raise SourceClosedRunConflictError(
                    f"ceiling source evidence receipts are invalid: {quantity.quantity_id}"
                )
        evidence_ids = tuple(ceiling.evidence_ids)
        if not set(quantity.evidence_ids).issubset(set(evidence_ids)):
            raise SourceClosedRunConflictError(
                f"ceiling source trace does not cover quantity evidence: {quantity.quantity_id}"
            )

        points = tuple(ceiling.polygon_pdf_pts or ())
        # A canonical "geometry_complete" flag alone cannot authenticate
        # an absent physical ceiling source face at the final signed seal.
        if len(points) < 3:
            raise SourceClosedRunConflictError(
                f"ceiling source polygon is invalid or incomplete: {quantity.quantity_id}"
            )
        source_bbox = None
        if points:
            try:
                if any(
                    not isinstance(point, (tuple, list)) or len(point) != 2
                    or any(type(v) not in (int, float) for v in point)
                    for point in points
                ):
                    raise ValueError("untyped ceiling PDF geometry")
                xs = tuple(float(point[0]) for point in points)
                ys = tuple(float(point[1]) for point in points)
                if (
                    not all(math.isfinite(v) for v in (*xs, *ys))
                    or max(xs) <= min(xs) or max(ys) <= min(ys)
                ):
                    raise ValueError("degenerate ceiling PDF geometry")
            except (TypeError, ValueError, IndexError, OverflowError) as exc:
                raise SourceClosedRunConflictError(
                    f"ceiling source polygon is invalid: {quantity.quantity_id}"
                ) from exc
            # A positive bounding rectangle may enclose a collinear or
            # self-cancelling ring. PDF points are source geometry only;
            # neither the rectangle nor a prior metric value can authorize
            # a physically zero-area ceiling face.
            if len(points) < 3:
                raise SourceClosedRunConflictError(
                    f"ceiling source polygon is invalid: {quantity.quantity_id}"
                )
            try:
                signed_twice_area = math.fsum(
                    xs[i] * ys[(i + 1) % len(points)]
                    - xs[(i + 1) % len(points)] * ys[i]
                    for i in range(len(points))
                )
            except (TypeError, ValueError, OverflowError) as exc:
                raise SourceClosedRunConflictError(
                    f"ceiling source polygon is invalid: {quantity.quantity_id}"
                ) from exc
            if not math.isfinite(signed_twice_area) or abs(signed_twice_area) <= 2e-9:
                raise SourceClosedRunConflictError(
                    f"ceiling source polygon is invalid or degenerate: {quantity.quantity_id}"
                )
            # The legacy canonical ceiling seal must enforce the same source
            # physical-zone simplicity gate as the cross-view ceiling seal.
            # A nonzero shoelace area and bbox can still belong to a crossed
            # or backtracked ring; neither grants FIRM commercial authority.
            # Reuse the existing negative-only validator, never infer area.
            try:
                source_bbox = _original_ceiling_simple_bbox(
                    points, quantity_id=quantity.quantity_id,
                )
            except SourceClosedRunConflictError as exc:
                raise SourceClosedRunConflictError(
                    f"ceiling source polygon is invalid or degenerate: {quantity.quantity_id}"
                ) from exc

        # The simple-ring validator above authenticates shape validity but
        # does not compare it with independently named FIRM ceilings.  Compare
        # undirected source edges so a rotated starting vertex, reversed
        # winding, or explicit closing point cannot evade physical identity.
        # Different source pages/viewports/revisions remain independent.
        ring = tuple(zip(xs, ys))
        if ring[0] == ring[-1]:
            ring = ring[:-1]
        original_edges = tuple(sorted(
            (a, b) if a <= b else (b, a)
            for a, b in zip(ring, ring[1:] + ring[:1])
        ))
        physical_face_key = (
            ceiling.source_sha256.lower(),
            ceiling.revision_id,
            ceiling.source_page,
            ceiling.viewport_id,
            original_edges,
        )
        previous_owner = claimed_original_faces.get(physical_face_key)
        if previous_owner is not None and previous_owner != canonical_id:
            raise SourceClosedRunConflictError(
                "distinct canonical ceilings claim the same original source face: "
                f"{previous_owner}, {canonical_id}"
            )
        claimed_original_faces[physical_face_key] = canonical_id

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
            canonical_entity_ids=(canonical_id,),
            source_bbox=source_bbox,
            metadata={
                "family": "ceiling_lining",
                "canonical_ceiling_id": canonical_id,
                "room_entity_id": ceiling.room_entity_id,
                "room_area_quantity_id": ceiling.room_area_quantity_id,
                "shadow_ceiling_quantity_id": ceiling.ceiling_quantity_id,
                "source_room_index_id": ceiling.source_room_index_id,
                "measurement_authority": ceiling.measurement_authority,
                "figured_dimension_ids": tuple(ceiling.figured_dimension_ids),
                "physical_scale_record_id": ceiling.physical_scale_record_id,
                "finish_descriptor": ceiling.finish_descriptor,
            },
        )
        if quantity.quantity_id in traces:
            raise SourceClosedRunConflictError(
                f"duplicate ceiling quantity id: {quantity.quantity_id}"
            )
        traces[quantity.quantity_id] = trace

    return MappingProxyType(traces)


def seal_live_ceiling_area_run(
    result: LiveCeilingLiningResult,
    *,
    workspace_id: int,
    project_id: str,
) -> SealedSourceClosedRun:
    """Seal final canonical ceiling-area quantities on canonical identity."""
    # Audit original source IDs before consuming canonical FIRM projections.
    # A provisional producer replay may not reach a signed ceiling/customer row.
    traces = build_live_ceiling_area_source_traces(
        result,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    quantities = tuple(
        quantity
        for quantity in publish_live_ceiling_area_quantities(result)
        if not quantity.abstained and quantity.value is not None
    )
    return seal_source_closed_run(
        quantities,
        project_id=project_id,
        traces_by_quantity_id=traces,
    )


__all__ = [
    "build_live_ceiling_area_source_traces",
    "seal_live_ceiling_area_run",
]
