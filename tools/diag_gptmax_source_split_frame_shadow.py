"""Run a narrowly opt-in original W4 split-host frame shadow, no customer activation."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_opening_host_frame_authority import OpeningHostFrameProducer
from pb_opening_kind_authority import resolve_opening_kind
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention


def original_split_frame_shadow(pdf: bytes, *, page_id: str, expected_sha256: str) -> dict:
    if type(pdf) is not bytes or not pdf:
        raise TypeError("real original PDF required")
    if sha256(pdf).hexdigest() != expected_sha256:
        raise ValueError("original source SHA mismatch")
    if (type(page_id) is not str or not page_id.isdecimal()
            or int(page_id) <= 0 or str(int(page_id)) != page_id):
        raise ValueError("canonical page number required")
    src = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
    pub = src.ingest_native_pdf_bytes(
        document_id=f"live-source:{expected_sha256[:32]}",
        source_bytes=pdf, source_locator="memory://gptmax-split-original.pdf",
        page_ids=(int(page_id),))
    comp = compose_live_wall_opening_authority(
        source_visibility_producer=src,
        revision_id=pub.revision.revision_id,
        page_ids=(page_id,))
    voids = compose_live_physical_opening_voids(
        source_visibility_producer=src, wall_opening_composition=comp)
    baseline = _retention(comp, voids, verify_customer_rows=True)
    published = src.published_snapshot_for_revision(pub.revision.revision_id)
    original = {r.opening_identity_id:r for r in comp.host_frames}
    shadow = OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=comp.physical_opening_authority,
        host_binding_authority=comp.opening_host_binding_authority,
        physical_wall_candidate_authority=comp.physical_wall_candidate_authority,
        raster_split_frame_shadow=True)
    rows = []
    for trace in sorted(comp.opening_bindings,key=lambda x:x.opening_identity_id):
        identity=trace.opening_identity_id
        selector=ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=expected_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=trace.representative_observation_id)
        frame=shadow.publish(
            opening_selector=selector,
            host_binding_selector=comp.binding_selectors[identity])
        old=original[identity]
        if old.record_id:
            if (frame.status is not EvidenceResolutionStatus.CORROBORATED
                    or frame.evidence is None
                    or frame.evidence.record_id != old.record_id):
                raise ValueError("a pre-existing original authentic frame changed in shadow")
        rows.append({
            "physical_opening_id":identity,
            "original_host_reason_codes":list(trace.reason_codes),
            "original_frame_status":old.status.value,
            "original_frame_record_id":old.record_id,
            "original_frame_reason_codes":list(old.reason_codes),
            "shadow_frame_status":frame.status.value,
            "shadow_frame_record_id":None if frame.evidence is None else frame.evidence.record_id,
            "shadow_frame_reason_codes":list(frame.reason_codes),
            "is_additional_complete_shadow_frame":bool(frame.evidence is not None and old.record_id is None),
            "new_customer_quantity_granted":False,
        })
    reversed_rows=[]
    for trace in reversed(comp.opening_bindings):
        selector=ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=expected_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=trace.representative_observation_id)
        frame=shadow.publish(opening_selector=selector,
                             host_binding_selector=comp.binding_selectors[trace.opening_identity_id])
        reversed_rows.append((trace.opening_identity_id,
                              None if frame.evidence is None else asdict(frame.evidence),
                              frame.status.value,tuple(frame.reason_codes)))
    for row in rows:
        expected=next(x for x in reversed_rows if x[0]==row["physical_opening_id"])
        if (row["shadow_frame_record_id"] != (None if expected[1] is None else expected[1]["record_id"])
                or row["shadow_frame_status"] != expected[2]
                or tuple(row["shadow_frame_reason_codes"]) != expected[3]):
            raise ValueError("source shadow changes under input ordering")
    if (src.published_snapshot_for_revision(pub.revision.revision_id)!=published
            or sha256(src._producer._store.source_bytes_by_revision[pub.revision.revision_id]).hexdigest()!=expected_sha256
            or _retention(comp, voids, verify_customer_rows=True)!=baseline):
        raise RuntimeError("shadow mutated original source or sealed receipts")
    return {
        "status":"UNPUBLISHED_ORIGINAL_SPLIT_FRAME_SHADOW",
        "source_sha256":expected_sha256,
        "snapshot_id":published.snapshot.snapshot_id,
        "page_id":page_id,
        "baseline_physical_count":len(baseline["canonical"]),
        "baseline_authenticated_host_count":sum(bool(x["host_wall_id"]) for x in baseline["hosts"]),
        "baseline_complete_frame_count":sum(bool(x["record_id"]) for x in baseline["frames"]),
        "baseline_signed_opening_area_count":len(baseline["quantities"]),
        "shadow_complete_frame_count":sum(bool(x["shadow_frame_record_id"]) for x in rows),
        "source_snapshot_signed_customer_retained":True,
        "opening_rows":rows,
        "new_frame_hypothesis_ids":[x["physical_opening_id"] for x in rows if x["is_additional_complete_shadow_frame"]],
        "gpt1_shadow_frame_source_bundles":_gpt1_shadow_frame_source_bundles(
            src=src,comp=comp,published=published,expected_sha256=expected_sha256,
            rows=rows,reversed_rows=reversed_rows),
        "customer_seal_activation_granted":False,
        "gpt1_metric_axis_handoff_granted":False,
        "global_opening_count_granted":False,
    }


def _gpt1_shadow_frame_source_bundles(*, src, comp, published, expected_sha256, rows, reversed_rows):
    """Complete unpublished source bundles for additional shadow frames.

    Shadow frames are reported separately from FIRM quantities. Typed-kind
    and metric-axis blockers stay on the bundle; they do not mint width,
    kind, or customer rows here.
    """
    width_authority = src.opening_dimension_authority()
    skip_prefix = "opening_host_frame_aligned_motif_fragments_skipped:"
    bundles = []
    for row in rows:
        if not row["is_additional_complete_shadow_frame"]:
            continue
        evidence = next(item[1] for item in reversed_rows if item[0] == row["physical_opening_id"])
        trace = next(
            item for item in comp.opening_bindings
            if item.opening_identity_id == row["physical_opening_id"]
        )
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=expected_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=trace.representative_observation_id,
        )
        existence = comp.physical_opening_authority.prove_existence(selector).existence_record
        kind = resolve_opening_kind(
            structural_pattern=None if existence is None else existence.structural_pattern,
        )
        width = width_authority.resolve_width(selector)
        bundles.append({
            "physical_opening_id": row["physical_opening_id"],
            "firm_quantity_granted": False,
            "customer_seal_activation_granted": False,
            "gpt1_metric_axis_handoff_granted": False,
            "host_binding_record_id": None if evidence is None else evidence["host_binding_record_id"],
            "host_wall_id": None if evidence is None else evidence["host_wall_id"],
            "member_wall_ids": [] if evidence is None else list(evidence["whole_wall_candidate_ids"]),
            "shadow_frame_record_id": row["shadow_frame_record_id"],
            "whole_wall_frame_id": None if evidence is None else evidence["whole_wall_frame_id"],
            "source_observation_ids": [] if evidence is None else list(evidence["source_observation_ids"]),
            "origin_pt": None if evidence is None else list(evidence["origin_pt"]),
            "u0_pt": None if evidence is None else evidence["u0_pt"],
            "u1_pt": None if evidence is None else evidence["u1_pt"],
            "wall_thickness_pt": None if evidence is None else evidence["wall_thickness_pt"],
            "skipped_motif_wall_ids": [
                code.split(":", 1)[1]
                for code in row["shadow_frame_reason_codes"]
                if code.startswith(skip_prefix)
            ],
            "skip_receipts_are_decision_provenance_not_frame_identity": True,
            "typed_kind_status": kind.status.value,
            "typed_kind": kind.opening_kind,
            "typed_kind_reasons": list(kind.reason_codes),
            "typed_kind_structural_pattern": None if existence is None else existence.structural_pattern,
            "metric_axis_width_status": width.status.value,
            "metric_axis_width_mm": width.value_mm,
            "metric_axis_width_reasons": [code for code in width.reason_codes if code],
            "original_host_reason_codes": list(row["original_host_reason_codes"]),
            "shadow_frame_reason_codes": list(row["shadow_frame_reason_codes"]),
        })
    return bundles


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf",required=True,type=Path)
    p.add_argument("--sha256",required=True)
    p.add_argument("--page-id",required=True)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    r=original_split_frame_shadow(a.pdf.read_bytes(),page_id=a.page_id,expected_sha256=a.sha256)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,sort_keys=True,indent=2)+"\n")
    print({k:r[k] for k in ("status","baseline_complete_frame_count",
                             "shadow_complete_frame_count","new_frame_hypothesis_ids")})


if __name__=="__main__":
    main()
