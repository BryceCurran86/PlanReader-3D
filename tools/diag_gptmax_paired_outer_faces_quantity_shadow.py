"""Original-source paired outer-face experiment, with exact retained receipts."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import (
    LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
)
from pb_live_physical_opening_void_composition import (
    compose_live_physical_opening_voids,
)
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
from pb_raster_opening_source_primitives import MAX_PRIMITIVES
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention


def paired_outer_faces_quantity_shadow_report(
    original_pdf: bytes, *, page_id: str
) -> dict:
    if type(original_pdf) is not bytes or not original_pdf:
        raise TypeError("original PDF bytes required")
    if (
        type(page_id) is not str
        or not page_id.isdecimal()
        or int(page_id) < 1
        or str(int(page_id)) != page_id
    ):
        raise ValueError("canonical original page address required")
    digest = sha256(original_pdf).hexdigest()

    def compose(enabled):
        source = SourceVisibilityProducer(
            producer_method="live-physical-net-wall",
            producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
            raster_paired_outer_faces_shadow=enabled,
        )
        pub = source.ingest_native_pdf_bytes(
            document_id=f"live-source:{digest[:32]}",
            source_bytes=original_pdf,
            source_locator="memory://paired-original-faces.pdf",
            page_ids=(int(page_id),),
        )
        composition = compose_live_wall_opening_authority(
            source_visibility_producer=source,
            revision_id=pub.revision.revision_id,
            page_ids=(page_id,),
        )
        voids = compose_live_physical_opening_voids(
            source_visibility_producer=source, wall_opening_composition=composition
        )
        pub = source.published_snapshot_for_revision(pub.revision.revision_id)
        return (
            source,
            pub,
            composition,
            voids,
            _retention(composition, voids, verify_customer_rows=True),
        )

    old_source, old_pub, old_comp, old_voids, before = compose(False)
    source, pub, composition, voids, after = compose(True)
    first_failure = "original_producer_snapshot_changed" if old_pub != pub else None
    differences = []
    if before["walls"] != after["walls"] and first_failure is None:
        first_failure = "original_w4_source_scope_changed"
    for family, key in (
        ("hosts", "opening_identity_id"),
        ("frames", "opening_identity_id"),
        ("canonical", "physical_opening_id"),
        ("quantities", "quantity_id"),
        ("customer_rows", "quantity_id"),
    ):
        previous = {r[key]: r for r in before[family]}
        current = {r[key]: r for r in after[family]}
        if len(previous) != len(before[family]) or len(current) != len(after[family]):
            raise RuntimeError("duplicate original receipt address:" + family)
        for identity, record in previous.items():
            if current.get(identity) != record:
                differences.append(
                    dict(
                        family=family,
                        identity=identity,
                        before=record,
                        after=current.get(identity),
                    )
                )
                if first_failure is None:
                    first_failure = (
                        "original_" + family + "_receipt_changed:" + identity
                    )
    canonical = {o.physical_opening_id: o for o in voids.canonical_openings}
    previous = {o.physical_opening_id for o in old_voids.canonical_openings}
    labels = OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    candidates = []
    for identity in sorted(canonical.keys() - previous):
        opening = canonical[identity]
        address = ObservationSelector(
            document_id=pub.revision.document_id,
            revision_id=pub.revision.revision_id,
            source_sha256=digest,
            snapshot_id=pub.snapshot.snapshot_id,
            observation_id=opening.representative_observation_id,
        )
        physical = composition.physical_opening_authority.prove_existence(address)
        host = composition.opening_host_binding_authority.resolve(
            composition.binding_selectors[identity]
        )
        host_trace = next(
            r for r in after["hosts"] if r["opening_identity_id"] == identity
        )
        fs = composition.host_frame_selectors.get(identity)
        frame = composition.opening_host_frame_authority.resolve(fs) if fs else None
        frame_trace = next(
            r for r in after["frames"] if r["opening_identity_id"] == identity
        )
        label = labels.publish_scope(address)
        quantity = next(
            (q for q in after["quantities"] if q["input_entity_ids"] == [identity]),
            None,
        )
        object_failure = (
            "host_wall_identity"
            if host.record is None
            else "host_frame"
            if frame is None or frame.evidence is None
            else "source_figured_measurement_or_kind"
            if quantity is None
            else "independent_publication_and_frozen_review"
        )
        first = "retention:" + first_failure if first_failure else object_failure
        candidates.append(
            dict(
                physical_opening_id=identity,
                canonical_opening=opening.to_dict(),
                physical_result=asdict(physical),
                host_result=asdict(host),
                frame_result=asdict(frame) if frame else None,
                original_host_producer_trace=host_trace,
                original_frame_producer_trace=frame_trace,
                figured_label_result=asdict(label),
                quantity=quantity,
                first_failing_authority_stage=first,
                first_object_authority_failure=object_failure,
            )
        )

    def source_audit(owner, published, comp):
        authority = owner.physical_opening_authority()
        seed = next(r for r in comp.opening_bindings if r.representative_observation_id)
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=digest,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=seed.representative_observation_id,
        )
        closure = authority.assess_raster_candidate_closure(selector)
        return dict(
            raster_candidate_closure=asdict(closure),
            raw_registered_gaps=[
                dict(
                    source_scope=dict(
                        zip(
                            (
                                "document_id",
                                "revision_id",
                                "source_sha256",
                                "snapshot_id",
                                "page_id",
                            ),
                            key,
                        )
                    ),
                    raw_candidate_id=gap_id,
                    source_observation_ids=sorted(support),
                    aperture_bbox_pt=aperture,
                    # Review-only first source-stage alternatives. These are
                    # not independent opening instances or count authority.
                    first_source_gate_alternatives=list(dict(
                        authority._raster_gap_first_gate_shadow_cache.get(key, ())
                    ).get(gap_id, ())),
                )
                for key, rows in sorted(
                    authority._raster_gap_candidate_audit_cache.items()
                )
                for gap_id, support, aperture in rows
            ],
            original_face_continuity_comparisons=[
                dict(
                    source_scope=dict(
                        zip(
                            (
                                "document_id",
                                "revision_id",
                                "source_sha256",
                                "snapshot_id",
                                "page_id",
                            ),
                            key,
                        )
                    ),
                    **r,
                )
                for key, rows in sorted(
                    authority._raster_outer_face_comparison_cache.items()
                )
                for r in rows
            ],
        )

    baseline_audit = source_audit(old_source, old_pub, old_comp)
    candidate_audit = source_audit(source, pub, composition)

    def retained(family, key, positive=False, disposition=False):
        current = {r[key]: r for r in after[family]}
        for previous in before[family]:
            if positive and not previous["record_id"]:
                continue
            now = current.get(previous[key])
            if now is None:
                return False
            if disposition:
                if (previous["status"], previous["reason_codes"]) != (
                    now["status"],
                    now["reason_codes"],
                ):
                    return False
            elif previous != now:
                return False
        return True

    if (
        source.published_snapshot_for_revision(pub.revision.revision_id) != pub
        or sha256(
            source._producer._store.source_bytes_by_revision[pub.revision.revision_id]
        ).hexdigest()
        != digest
        or _retention(old_comp, old_voids, verify_customer_rows=True) != before
    ):
        raise RuntimeError("original source or default receipts changed during read")
    return dict(
        status="UNPUBLISHED_SHADOW_REVIEW",
        source_sha256=digest,
        snapshot_id=pub.snapshot.snapshot_id,
        original_baseline_published_snapshot=asdict(old_pub),
        candidate_published_snapshot=asdict(pub),
        baseline_receipts=before,
        candidate_receipts=after,
        additional_physical_candidates=candidates,
        baseline_source_audit=baseline_audit,
        candidate_source_audit=candidate_audit,
        original_face_continuity_comparisons=candidate_audit[
            "original_face_continuity_comparisons"
        ],
        original_receipt_differences=differences,
        retention_observations=dict(
            original_published_snapshot_retained=old_pub == pub,
            original_ordinary_wall_scopes_retained=before["walls"] == after["walls"],
            original_authenticated_hosts_retained=retained(
                "hosts", "opening_identity_id", positive=True
            ),
            original_authenticated_frames_retained=retained(
                "frames", "opening_identity_id", positive=True
            ),
            original_host_dispositions_retained=retained(
                "hosts", "opening_identity_id", disposition=True
            ),
            original_frame_dispositions_retained=retained(
                "frames", "opening_identity_id", disposition=True
            ),
            original_quantities_retained=retained("quantities", "quantity_id"),
            original_customer_rows_retained=retained("customer_rows", "quantity_id"),
            original_audit_seal_retained=before["sealed_run"] == after["sealed_run"],
        ),
        first_original_receipt_retention_failure=first_failure,
        original_receipts_retained=(first_failure is None),
        count_granted=False,
        production_activation_granted=False,
        primitive_safety_cap=MAX_PRIMITIVES,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = paired_outer_faces_quantity_shadow_report(
        args.pdf.read_bytes(), page_id=args.page_id
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
