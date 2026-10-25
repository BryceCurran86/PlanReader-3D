"""Independent GPT3 review-vs-issuer bridge for MAX original opening AREA.

A MAX review flag is NOT a QuantityEvidence, source seal, customer approval,
complete whole-wall frame, or benchmark match. Only the *live production*
opening-area issuer may identify actual gross-area quantities.

This module is read-only and does not ingest PDF source, score frozen truth,
select physical walls, or publish/rekey quantities.
"""
from __future__ import annotations

from collections.abc import Mapping
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


ORIGINAL_LOT16_ARCHIVED_EIGHT_FINGERPRINT = (
    "ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb"
)
ORIGINAL_LOT16_SOURCE_SHA256 = (
    "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
)
ORIGINAL_LOT16_PROJECT_ID = "au_qld_lot16_power"


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
        # Do not accept an arbitrary self-consistent eight-row predecessor
        # as "the original Lot16 eight". The actual original archived signed
        # run is immutable and must match the independent 2026-10-15 seal.
        if (archived_signed_run.get("fingerprint")
                != ORIGINAL_LOT16_ARCHIVED_EIGHT_FINGERPRINT
                or archived_signed_run.get("project_id")
                != ORIGINAL_LOT16_PROJECT_ID
                or len(archived_signed_run.get("quantities") or ()) != 8
                or any(
                    row.get("source_sha256") != ORIGINAL_LOT16_SOURCE_SHA256
                    or row.get("project_id") != ORIGINAL_LOT16_PROJECT_ID
                    for row in archived_signed_run["quantities"]
                )):
            raise SourceIssuerConvergenceConflict(
                "archived signed predecessor is not the immutable original Lot16 eight"
            )
        if any(
            member.source_sha256 != ORIGINAL_LOT16_SOURCE_SHA256
            for member in live_composition.canonical_openings
        ):
            raise SourceIssuerConvergenceConflict(
                "current source opening inventory differs from original Lot16 PDF"
            )
        verify_archived_signed_predecessors(
            archived_signed_run, archived_customer_rows,
            current_source_retention
        )
    # Independently run the ACTUAL live publisher. A report-provided area,
    # quantity ID or review status can never be a substitute.
    published = publish_live_opening_area_quantities(live_composition)
    by_quantity = _index(published, "quantity_id", role="live source area publisher")
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
        # Actual complete customer lineage verification, not merely embedded
        # quantity comparisons or a claimed "verified" status in a report.
        from pb_customer_output_verification import verify_sealed_customer_output
        from pb_source_closed_run_export import sealed_source_closed_run_from_dict

        checked_run = sealed_source_closed_run_from_dict(
            current_source_retention["sealed_run"]
        )
        checked_customers = verify_sealed_customer_output(
            checked_run, current_source_retention["customer_rows"]
        )
        if set(checked_customers.verified_quantity_ids) != set(by_quantity):
            raise SourceIssuerConvergenceConflict(
                "real issuer and sealed customer quantities differ"
            )
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

    # Only a truly producer-issued, independently customer-verified row that
    # is NOT part of the immutable predecessor set is a *new source quantity*.
    # The MAX observer must retain the exact quantity ID for EVERY issuer row.
    # Review-only candidates can never be counted as newly signed quantities.
    new_sealed_issuer_areas: list[dict[str, object]] = []
    for pid, quantity in sorted(owners.items()):
        observed_id = decisions[pid].get("prior_signed_quantity_id")
        if observed_id != quantity.quantity_id:
            raise SourceIssuerConvergenceConflict(
                "MAX source issuer receipt differs from production QuantityEvidence"
            )
        if archive_required and pid not in historical_by_owner:
            new_sealed_issuer_areas.append({
                "physical_opening_id": pid,
                "quantity_id": quantity.quantity_id,
                "value_m2": quantity.value,
                "opening_kind": quantity.metadata.get("opening_kind"),
                "area_basis": quantity.metadata.get("area_basis"),
                "source_sha256": quantity.metadata.get("source_sha256"),
                "host_binding_record_id": quantity.metadata.get(
                    "host_binding_record_id"
                ),
                "customer_output_verified": True,
                "frozen_v2_score_granted": False,
            })
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
        # No archive => do not infer a new quantity by subtracting eight
        # from an unrelated current inventory. Verified source quantities
        # still require independent official V2 identity reconciliation.
        "source_verified_new_quantity_count": (
            len(new_sealed_issuer_areas) if archive_required else None
        ),
        "new_source_issued_customer_verified_areas": new_sealed_issuer_areas,
        "customer_release_authorized": False,
        "benchmark_score_authorized": False,
    }
