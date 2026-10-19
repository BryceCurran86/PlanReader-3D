"""Independent GPT3 review-vs-issuer bridge for MAX original opening AREA.

A MAX review flag is NOT a QuantityEvidence, source seal, customer approval,
complete whole-wall frame, or benchmark match. Only the *live production*
opening-area issuer may identify actual gross-area quantities.

This module is read-only and does not ingest PDF source, score frozen truth,
select physical walls, or publish/rekey quantities.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import math

from pb_live_physical_opening_void_composition import (
    LiveCanonicalOpeningObject,
    LivePhysicalOpeningVoidComposition,
)
from pb_live_opening_area_quantity_publication import (
    LIVE_OPENING_FIGURED_AREA_QUANTITY_AUTHORITY,
    publish_live_opening_area_quantities,
)
from pb_migration_contracts import QuantityEvidence
from tools.diag_gptmax_lot16_host_frame_gpt1_handoff import (
    verify_archived_signed_predecessors,
)


class SourceIssuerConvergenceConflict(ValueError):
    """Stop on an inconsistent/forged review or original production ledger."""


def _index(rows: object, field: str, *, role: str) -> dict[str, object]:
    if type(rows) not in (list, tuple):
        raise SourceIssuerConvergenceConflict(f"{role}: typed source inventory unavailable")
    by_id: dict[str, object] = {}
    for row in rows:
        if isinstance(row, Mapping):
            identity = row.get(field)
        else:
            identity = getattr(row, field, None)
        if (type(identity) is not str or not identity
                or identity != identity.strip() or identity in by_id):
            raise SourceIssuerConvergenceConflict(
                f"{role}: missing, padded, or duplicate original identity"
            )
        by_id[identity] = row
    return by_id


def audit_max_area_review_against_live_issuer(
    max_report: Mapping[str, object],
    live_composition: LivePhysicalOpeningVoidComposition,
    *,
    archived_signed_run: dict | None = None,
    archived_customer_rows: list | None = None,
    current_source_retention: dict | None = None,
) -> dict[str, object]:
    """Audit true source-issued area versus MAX review queue; grant NO release.

    Optional archives must be the genuine signed producer archive and current
    source-producer retention. Archived full signed/customer bodies are compared
    using the existing independent source-closed verification contract.
    """
    if (type(live_composition) is not LivePhysicalOpeningVoidComposition
            or not isinstance(max_report, Mapping)):
        raise TypeError("original live opening composition and review report required")
    if max_report.get("status") != "UNPUBLISHED_SOURCE_REPROVED_OPENING_GPT1_QUEUE":
        raise SourceIssuerConvergenceConflict("MAX source review status not authenticated")
    for key in (
        "signed_customer_publisher_activated", "global_opening_count_granted",
        "signed_source_lineage_handoff_granted",
    ):
        if max_report.get(key, False) is not False:
            raise SourceIssuerConvergenceConflict(f"MAX review cannot grant {key}")

    members = _index(
        live_composition.canonical_openings, "physical_opening_id",
        role="live physical producer")
    decisions = _index(
        max_report.get("opening_decisions"), "physical_opening_id",
        role="MAX source-first gate")
    if (set(members) != set(decisions)
            or max_report.get("original_physical_opening_count") != len(members)
            or not members):
        raise SourceIssuerConvergenceConflict("complete original physical opening universe differs")
    canonical = _index(
        live_composition.canonical_openings, "canonical_opening_id",
        role="live canonical producer")
    if set(canonical) != set(members):
        raise SourceIssuerConvergenceConflict("canonical/physical opening identity conflict")

    new_reviews = _index(
        max_report.get("gpt1_new_area_review_candidates"),
        "physical_opening_id", role="MAX new area review")
    flagged = {
        pid for pid, decision in decisions.items()
        if decision.get("new_gpt1_area_candidate_handoff") is True
    }
    if set(new_reviews) != flagged or any(
        new_reviews[pid] != decisions[pid] for pid in flagged
    ):
        raise SourceIssuerConvergenceConflict("review queue membership or decision body mismatch")

    archive_required = (
        archived_signed_run is not None or archived_customer_rows is not None
        or current_source_retention is not None
    )
    if archive_required and (
        type(archived_signed_run) is not dict
        or type(archived_customer_rows) is not list
        or type(current_source_retention) is not dict
    ):
        raise SourceIssuerConvergenceConflict("signed and customer archive/retention must be supplied together")
    if archive_required:
        verify_archived_signed_predecessors(
            archived_signed_run, archived_customer_rows,
            current_source_retention
        )
    # Independently run the ACTUAL live publisher. A report-provided area,
    # quantity ID or review status can never be a substitute.
    published = publish_live_opening_area_quantities(live_composition)
    by_quantity = _index(published, "quantity_id", role="live source area publisher")
    publisher_by_physical = _index(
        published, "semantic_key", role="live source semantic key"
    )
    del publisher_by_physical  # quantity must still be linked by physical ID below
    owners: dict[str, QuantityEvidence] = {}
    for quantity in published:
        if (
            type(quantity) is not QuantityEvidence
            or quantity.family != "opening_area"
            or quantity.status != "corroborated"
            or quantity.abstained
            or len(quantity.input_entity_ids) != 1
        ):
            raise SourceIssuerConvergenceConflict("untrusted live producer area quantity body")
        owner = quantity.input_entity_ids[0]
        if owner in owners or owner not in members:
            raise SourceIssuerConvergenceConflict("reused/unknown source physical area owner")
        owners[owner] = quantity

    if archive_required:
        retained = _index(current_source_retention.get("quantities"), "quantity_id",
                          role="actual source issued quantity bodies")
        if set(retained) != set(by_quantity) or any(
            retained[qid] != q.to_dict() for qid, q in by_quantity.items()
        ):
            raise SourceIssuerConvergenceConflict("actual live issuer and sealed source retention differ")
        by_customer = _index(
            current_source_retention.get("customer_rows"), "quantity_id",
            role="source-verified customer projection")
        if set(by_customer) != set(by_quantity):
            raise SourceIssuerConvergenceConflict("source/customer quantity bijection broken")
        for qid, quantity in by_quantity.items():
            row = by_customer[qid]
            embedded = row.get("commercial_projection_provenance", {}).get("quantity")
            if embedded != quantity.to_dict():
                raise SourceIssuerConvergenceConflict("original customer embeds different QuantityEvidence body")

    historical_by_owner: dict[str, str] = {}
    if archive_required:
        for row in archived_signed_run["quantities"]:
            refs = row.get("object_identity_refs")
            qid = row.get("quantity_id")
            if (type(refs) is not list or len(refs) != 1
                    or type(qid) is not str or refs[0] in historical_by_owner):
                raise SourceIssuerConvergenceConflict("historical physical opening source identity duplicated")
            historical_by_owner[refs[0]] = qid
        if len(historical_by_owner) != 8:
            raise SourceIssuerConvergenceConflict("expected original eight source-signed Lot16 openings")
        if any(
            decisions[owner].get("prior_signed_quantity_id") != qid
            for owner, qid in historical_by_owner.items()
            if owner in decisions
        ):
            raise SourceIssuerConvergenceConflict("historical signed opening remapped as new review")

    findings = []
    for pid in sorted(decisions):
        decision = decisions[pid]
        member = members[pid]
        if (type(member) is not LiveCanonicalOpeningObject
                or member.canonical_opening_id != pid
                or decision.get("source_sha256") != member.source_sha256
                or decision.get("snapshot_id") != member.snapshot_id
                or member.revision_id != live_composition.revision_id
                or any(decision.get(key) is not False for key in (
                    "measurement_published", "customer_seal_granted",
                    "opening_count_granted"
                ))):
            raise SourceIssuerConvergenceConflict("review source root/physical lineage conflict")
        if not decision.get("new_gpt1_area_candidate_handoff"):
            continue
        if (decision.get("prior_signed_quantity_id") is not None
                or pid in historical_by_owner
                or decision.get("opening_area_first_remaining_gate")
                != "independent_gpt1_opening_area_measurement_validation_required"
                or not decision.get("figured_pair_area_support")
                or not decision.get("figured_area_receipt_bound")
                or not decision.get("filling_kind_source_supported")
                or decision.get("authenticated_host_record_id")
                != member.host_binding_record_id
                or decision.get("authenticated_frame_record_id")
                != member.host_frame_record_id
                or member.opening_kind not in ("door", "window")
                or member.area_basis != "figured_opening_label"
                or type(member.area_m2) not in (float, int)
                or not math.isfinite(member.area_m2)
                or member.area_m2 <= 0
                or not member.host_wall_id
                or not member.figured_area_record_id
                or member.figured_area_record_id not in member.evidence_ids
                or member.host_binding_record_id not in member.evidence_ids
                or (member.host_frame_record_id is not None
                    and member.host_frame_record_id not in member.evidence_ids)):
            raise SourceIssuerConvergenceConflict("MAX area review unowned by exact live producer")
        issuer = owners.get(pid)
        status = "REVIEW_ONLY_SOURCE_ISSUER_UNAVAILABLE"
        if issuer is not None:
            if (issuer.authority != LIVE_OPENING_FIGURED_AREA_QUANTITY_AUTHORITY
                    or issuer.value != member.area_m2
                    or issuer.metadata.get("measurement_record_id")
                    != member.figured_area_record_id
                    or issuer.metadata.get("host_binding_record_id")
                    != member.host_binding_record_id
                    or issuer.metadata.get("host_frame_record_id")
                    != member.host_frame_record_id):
                raise SourceIssuerConvergenceConflict("source area review versus production issuer value/ancestry conflict")
            # A source issuer claiming an actual NEW quantity cannot still be
            # labelled unsigned in its original-producer report: the two
            # producer receipts disagree, so DON'T offer it for release.
            status = "ISSUER_PRESENT_BUT_MAX_REPORT_UNSIGNED_CONFLICT"
        findings.append({
            "physical_opening_id": pid,
            "status": status,
            "host_only_figured_gross_area": member.host_frame_record_id is None,
            "new_firm_or_customer_quantity_granted": False,
            "frozen_v2_score_granted": False,
        })
    return {
        "status": "UNPUBLISHED_GPT3_SOURCE_ISSUER_RECONCILIATION",
        "complete_physical_source_inventory": len(members),
        "real_producer_issued_opening_area_count": len(published),
        "historical_full_signed_and_customer_bodies_verified": archive_required,
        "review_candidates": findings,
        "source_verified_new_quantity_count": 0,
        "customer_release_authorized": False,
        "benchmark_score_authorized": False,
    }
