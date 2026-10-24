"""GPT1 shadow: compare original producer review readiness with the REAL area issuer.

This consumes already constructed original typed canonical objects. It never
calls a customer seal, never creates a new canonical object or returns an
issued QuantityEvidence. The live publisher retains the only signing seam.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pb_live_opening_area_quantity_publication import (
    LIVE_OPENING_FIGURED_AREA_QUANTITY_AUTHORITY,
    _opening_quantity,
)
from pb_live_physical_opening_void_composition import (
    LiveCanonicalOpeningObject,
    LivePhysicalOpeningVoidComposition,
)


def reconcile_gpt1_area_review_with_issuer(
    composition: LivePhysicalOpeningVoidComposition,
    source_queue: Mapping[str, Any],
) -> dict[str, Any]:
    """Check source-review candidates against exact existing quantity preflight.

    The original typed producer object, not a reconstructed caller JSON
    row or an invented area, must enter the real production issuer.
    """
    if type(composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError("original typed physical opening composition required")
    if (
        not isinstance(source_queue, Mapping)
        or source_queue.get("status") != "UNPUBLISHED_SOURCE_REPROVED_OPENING_GPT1_QUEUE"
        or source_queue.get("signed_customer_publisher_activated") is not False
        or source_queue.get("global_opening_count_granted") is not False
    ):
        raise ValueError("unpublished original source review queue required")

    decisions = source_queue.get("opening_decisions")
    if not isinstance(decisions, list) or not decisions:
        raise ValueError("complete original opening review inventory required")
    by_id: dict[str, LiveCanonicalOpeningObject] = {}
    for obj in composition.canonical_openings:
        if type(obj) is not LiveCanonicalOpeningObject:
            raise TypeError("original canonical opening type required")
        oid = obj.physical_opening_id
        if (
            type(oid) is not str or not oid
            or oid != obj.canonical_opening_id
            or oid in by_id
            or obj.revision_id != composition.revision_id
        ):
            raise ValueError("original canonical physical identity/revision mismatch")
        by_id[oid] = obj

    seen: set[str] = set()
    issuer_agrees: list[str] = []
    publisher_ready_but_source_abstained: list[str] = []
    first_failed_issuer_gate: dict[str, str] = {}
    original_root: tuple[str, str, str] | None = None
    for row in decisions:
        if not isinstance(row, Mapping):
            raise TypeError("review decision must be typed source mapping")
        oid = row.get("physical_opening_id")
        if type(oid) is not str or oid in seen or oid not in by_id:
            raise ValueError("original source review inventory mismatch")
        seen.add(oid)
        obj = by_id[oid]
        root = (obj.document_id, obj.source_sha256, obj.snapshot_id)
        if original_root is None:
            original_root = root
        if (
            root != original_root
            or row.get("original_canonical_document_id") != obj.document_id
            or row.get("original_canonical_revision_id") != obj.revision_id
            or row.get("source_sha256") != obj.source_sha256
            or row.get("snapshot_id") != obj.snapshot_id
            or row.get("original_canonical_opening_kind") != obj.opening_kind
            or row.get("original_canonical_page_id") != obj.page_id
            or row.get("original_canonical_viewport_id") != obj.viewport_id
            or row.get("measurement_published") is not False
            or row.get("customer_seal_granted") is not False
            or row.get("opening_count_granted") is not False
        ):
            raise ValueError("foreign source/signed review decision")
        review_ready = row.get("new_gpt1_area_candidate_handoff")
        if type(review_ready) is not bool:
            raise ValueError("typed area ready flag required")
        original_signed = bool(row.get("prior_signed_quantity_id"))
        issued = _opening_quantity(obj)
        if review_ready:
            # A numeric area accepted by the real publisher does not prove
            # original physical door/window semantics, structural host, or
            # figured-label ownership.  Require the separately established
            # source gate results before reporting an issuer-ready candidate.
            required_source_gates = (
                "figured_pair_area_support",
                "figured_area_receipt_bound",
                "original_figured_label_source_scope_bound",
                "original_host_binding_receipt_bound",
                "original_physical_source_observation_receipts_bound",
                "original_opening_kind_source_authority_reproved",
                "filling_kind_source_supported",
                "canonical_figured_area_publication_basis_bound",
                "canonical_figured_area_value_bound",
            )
            if any(row.get(gate) is not True for gate in required_source_gates):
                raise ValueError("source review claim lacks independently re-proved opening area authority")
            # The source review and the typed real publisher must own the
            # SAME host and (when present) whole-wall frame record.  A
            # boolean source gate alone cannot prove which producer receipt
            # the issuer's canonical opening actually retained.  Gross
            # figured area is legitimately frame-optional, but never allowed
            # to borrow an unreviewed/foreign canonical frame.
            source_host_id = row.get("authenticated_host_record_id")
            source_frame_id = row.get("authenticated_frame_record_id")
            if (
                type(source_host_id) is not str
                or not source_host_id
                or source_host_id != source_host_id.strip()
                or source_host_id != obj.host_binding_record_id
                or (
                    source_frame_id is None
                    and obj.host_frame_record_id not in (None, "")
                )
                or (
                    source_frame_id is not None
                    and (
                        type(source_frame_id) is not str
                        or not source_frame_id
                        or source_frame_id != source_frame_id.strip()
                        or source_frame_id != obj.host_frame_record_id
                        or row.get("original_host_frame_receipt_bound") is not True
                    )
                )
            ):
                raise ValueError(
                    "original host/frame source receipt mismatches typed canonical issuer"
                )
            # The original source review grants FIGURED label ownership only.
            # The real issuer supports additional, separately-authenticated
            # elevation/schedule/geometry bases. A later canonical substitution
            # must not borrow a figured-only original approval merely because
            # its numeric value and receipt ID still match this review row.
            if obj.area_basis != "figured_opening_label" or (
                issued is not None
                and issued.authority != LIVE_OPENING_FIGURED_AREA_QUANTITY_AUTHORITY
            ):
                raise ValueError(
                    "original figured-label area basis mismatches typed canonical issuer"
                )
            if original_signed or row.get("opening_area_first_remaining_gate") != (
                "independent_gpt1_opening_area_measurement_validation_required"
            ):
                raise ValueError("original signed or blocked member claimed new review")
            if (
                issued is None
                or issued.input_entity_ids != (oid,)
                or issued.metadata["snapshot_id"] != obj.snapshot_id
                or issued.metadata["area_basis"] != obj.area_basis
                or issued.evidence_ids != tuple(sorted(obj.evidence_ids))
                or issued.semantic_key != f"{obj.opening_kind}_area:{oid}"
                or issued.metadata["measurement_record_id"] != row.get(
                    "source_figured_area_record_id"
                )
                or issued.value != row.get("source_figured_area_m2")
            ):
                raise RuntimeError(
                    "source-review candidate rejected by actual opening area issuer"
                )
            issuer_agrees.append(oid)
        elif issued is not None and not original_signed:
            # An issuer-compatible object may still lack independent
            # source-review ancestry. Report only, never activate it.
            publisher_ready_but_source_abstained.append(oid)
            first_failed_issuer_gate[oid] = str(
                row.get("opening_area_first_remaining_gate") or ""
            )

    if (
        seen != set(by_id)
        or source_queue.get("original_physical_opening_count") != len(by_id)
        or tuple(sorted(issuer_agrees)) != tuple(sorted(
            row["physical_opening_id"]
            for row in source_queue.get("gpt1_new_area_review_candidates", ())
        ))
    ):
        raise ValueError("original complete area-review/issuer universe mismatch")

    return {
        "status": "UNPUBLISHED_GPT1_ACTUAL_AREA_ISSUER_PREFLIGHT",
        "original_physical_opening_count": len(by_id),
        "source_review_issuer_compatible_ids": sorted(issuer_agrees),
        "issuer_compatible_but_source_abstained_ids": sorted(
            publisher_ready_but_source_abstained
        ),
        "source_abstention_first_gate_by_physical": dict(
            sorted(first_failed_issuer_gate.items())
        ),
        "measurement_published": False,
        "customer_seal_granted": False,
        "opening_count_granted": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
