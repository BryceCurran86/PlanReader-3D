"""Re-prove every original opening's host, whole-wall frame and dimension axes.

Source F07 is SUPPORT ONLY. This tool never constructs a host/frame/dimension,
signs a customer quantity, edits a frozen evaluator or grants opening counts.
Every row comes from the existing live source producers, not input JSON.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import segment_source_page_viewports
from tools.diag_gptmax_producer_opening_scope_receipts import _observe
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention
from tools.diag_gptmax_same_root_f07_g17_original import classify_live_view


def _positive(value: object) -> bool:
    if type(value) not in (float, int):
        return False
    return math.isfinite(value) and value > 0


def _frame_valid(frame: dict | None, host: dict | None, identity: str) -> bool:
    if frame is None or host is None:
        return False
    if (frame.get("opening_identity_id") != identity
            or frame.get("host_binding_record_id") != host.get("record_id")
            or frame.get("host_wall_id") != host.get("host_wall_id")
            or frame.get("coordinate_unit") != "pdf_point"
            or not frame.get("record_id")
            or not frame.get("whole_wall_candidate_ids")
            or not frame.get("source_observation_ids")):
        raise ValueError("source frame identity/units/ancestry inconsistent")
    length = frame.get("whole_wall_length_pt")
    u0, u1 = frame.get("u0_pt"), frame.get("u1_pt")
    if not all(type(x) in (int, float) and math.isfinite(x) for x in (u0, u1, length)):
        raise ValueError("nonfinite whole-wall opening frame")
    if not (_positive(length) and _positive(u1 - u0)
            and u0 >= -1e-6 and u1 <= length + 1e-6
            and _positive(frame.get("wall_thickness_pt"))):
        raise ValueError("whole-wall opening extent not bounded")
    axis, normal, origin = (frame.get(k) for k in
                            ("axis_unit", "normal_unit", "origin_pt"))
    if not all(type(x) in (list, tuple) and len(x) == 2
               and all(type(v) in (float, int) and math.isfinite(v) for v in x)
               for x in (axis, normal, origin)):
        raise ValueError("incomplete source-owned host frame axes")
    if (abs(math.hypot(*axis) - 1) > 1e-5
            or abs(math.hypot(*normal) - 1) > 1e-5
            or abs(axis[0] * normal[0] + axis[1] * normal[1]) > 1e-5):
        raise ValueError("unproved orthogonal opening frame axes")
    return True


def assess_gpt1_opening_candidates(rows: list[dict], canonical: list[dict],
                                    f07: dict, *, source_root: dict) -> dict:
    """Fail-closed review queue, not a new measurement or signed authority."""
    by_canonical = {r["physical_opening_id"]: r for r in canonical}
    by_rows = {r["physical_opening_id"]: r for r in rows}
    if (len(by_canonical) != len(canonical) or len(by_rows) != len(rows)
            or set(by_rows) != set(by_canonical)):
        raise ValueError("duplicate or mismatched original source opening inventory")
    if not all(source_root.get(k) for k in
               ("document_id", "revision_id", "snapshot_id", "source_sha256")):
        raise ValueError("source owner scope required")
    supported = (f07.get("status") == "SOURCE_VIEW_CANDIDATE_SAME_ROOT_ONLY"
                 and bool(f07.get("selected_view_id"))
                 and bool(f07.get("selected_bbox_pt")))
    assessed = []
    for identity, row in sorted(by_rows.items()):
        c = by_canonical[identity]
        if (row.get("canonical_opening_id") != identity
                or c.get("canonical_opening_id") != identity
                or any(row.get(k) != source_root[k] or c.get(k) != source_root[k]
                       for k in source_root)
                or row.get("page_id") != c.get("page_id")
                or not row.get("physical_existence_record")
                or row["physical_existence_record"].get("record_id") != identity):
            raise ValueError("original physical existence source/root mismatch")
        host, frame = row["host_record"], row["frame_record"]
        if host is not None and (
                host.get("record_id") != c.get("host_binding_record_id")
                or host.get("host_wall_id") != c.get("host_wall_id")
                or host.get("opening_identity_id") != identity
                or not host.get("member_wall_candidate_ids")):
            raise ValueError("original structural host source mismatch")
        if host is None and (c.get("host_binding_record_id") or c.get("host_wall_id")):
            raise ValueError("canonical claims host without producer proof")
        frame_ok = _frame_valid(frame, host, identity)
        if frame_ok != bool(c.get("host_frame_record_id")):
            raise ValueError("canonical whole-wall frame identity changed")
        if frame_ok and frame["record_id"] != c["host_frame_record_id"]:
            raise ValueError("original frame receipt changed")
        label = row.get("original_label_dimension_result") or {}
        e = label.get("evidence")
        pair_ok = bool(
            label.get("status") == "corroborated" and e
            and e.get("opening_record_id") == identity
            and len(e.get("dimension_values_mm") or ()) == 2
            and all(_positive(v) for v in e["dimension_values_mm"])
            and _positive(e.get("area_m2"))
        )
        if pair_ok:
            a, b = e["dimension_values_mm"]
            if not math.isclose(a * b / 1_000_000, e["area_m2"], rel_tol=1e-9):
                raise ValueError("authenticated figured opening area disagrees with pair")
            if (c.get("figured_area_record_id")
                    and e.get("evidence_id") != c["figured_area_record_id"]):
                raise ValueError("canonical source dimension identity mismatch")
        axis_ok = (
            pair_ok and bool(e.get("axis_order_resolved"))
            and bool(c.get("width_record_id")) and bool(c.get("height_record_id"))
            and c["width_record_id"] != c["height_record_id"]
            and _positive(c.get("width_m")) and _positive(c.get("height_m"))
            and bool(c.get("geometry_complete"))
            and math.isclose(
                c["width_m"] * c["height_m"], e["area_m2"], rel_tol=1e-6)
        )
        typed = c.get("opening_kind") in ("door", "window")
        if not supported:
            gate = "source_owned_floor_plan_unavailable"
        elif host is None:
            gate = "structural_host_unavailable"
        elif not frame_ok:
            gate = "whole_wall_frame_unavailable"
        elif not typed:
            gate = "opening_filling_kind_unproven"
        elif not pair_ok:
            gate = "source_figured_dimension_pair_unproven"
        elif not axis_ok:
            gate = "width_height_axis_authority_unproven"
        else:
            gate = "independent_gpt1_measurement_validation_required"
        assessed.append({
            "physical_opening_id": identity,
            "source_sha256": c["source_sha256"],
            "snapshot_id": c["snapshot_id"],
            "source_decision_scope_id": row["attempted_host_selector"]["decision_scope_id"],
            "same_root_f07_view_id_support_only": f07.get("selected_view_id") if supported else None,
            "authenticated_host_record_id": None if host is None else host["record_id"],
            "source_host_member_wall_ids": [] if host is None else host["member_wall_candidate_ids"],
            "authenticated_frame_record_id": None if not frame_ok else frame["record_id"],
            "frame_reason_codes": list(row["frame_reason_codes"]),
            "host_reason_codes": list(row["host_reason_codes"]),
            "figured_pair_area_support": pair_ok,
            "axis_order_authenticated": axis_ok,
            "filling_kind_source_supported": typed,
            "prior_signed_quantity_id": row.get("quantity_id"),
            "first_remaining_gate": gate,
            "new_gpt1_candidate_handoff": bool(
                supported and host is not None and frame_ok and typed
                and axis_ok and not row.get("quantity_id")),
            # No output JSON is a signed quantity or a trust-grant token.
            "measurement_published": False,
            "customer_seal_granted": False,
            "opening_count_granted": False,
        })
    return {
        "status": "UNPUBLISHED_SOURCE_REPROVED_OPENING_GPT1_QUEUE",
        "original_physical_opening_count": len(assessed),
        "original_authenticated_hosts": sum(r["host_record"] is not None for r in rows),
        "original_complete_host_frames": sum(r["frame_record"] is not None for r in rows),
        "original_signed_area_quantities": sum(bool(r.get("quantity_id")) for r in rows),
        "first_gate_counts": dict(sorted(Counter(r["first_remaining_gate"] for r in assessed).items())),
        "source_floor_plan_support_only": supported,
        "gpt1_new_handoff_candidates": [r for r in assessed if r["new_gpt1_candidate_handoff"]],
        "opening_decisions": assessed,
        "signed_customer_publisher_activated": False,
        "global_opening_count_granted": False,
    }


def original_host_frame_dimension_report(pdf: bytes, *, page_id: str) -> dict:
    if type(pdf) is not bytes or not pdf:
        raise TypeError("original source PDF bytes required")
    if type(page_id) is not str or not page_id.isdecimal() or int(page_id) < 1 or str(int(page_id)) != page_id:
        raise ValueError("canonical page required")
    digest = sha256(pdf).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
    pub = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{digest[:32]}",
        source_bytes=pdf,
        source_locator="memory://gptmax-original-host-frame-dimension.pdf",
        page_ids=(int(page_id),))
    comp = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=pub.revision.revision_id,
        page_ids=(page_id,))
    voids = compose_live_physical_opening_voids(
        source_visibility_producer=source, wall_opening_composition=comp)
    published = source.published_snapshot_for_revision(pub.revision.revision_id)
    before = _retention(comp, voids, verify_customer_rows=True)
    existing = _observe(source, published, comp, voids)
    views = segment_source_page_viewports(
        source, revision_id=pub.revision.revision_id, page_id=page_id,
        physical_plan_view_shadow=True)
    view = classify_live_view(views, expected_page=int(page_id))
    if (source.published_snapshot_for_revision(pub.revision.revision_id) != published
            or sha256(source._producer._store.source_bytes_by_revision[pub.revision.revision_id]).hexdigest() != digest
            or _retention(comp, voids, verify_customer_rows=True) != before):
        raise RuntimeError("source snapshot or original sealed customer receipt mutated")
    root = {key: getattr(pub.revision, key) for key in
            ("document_id", "revision_id", "source_sha256")}
    root["snapshot_id"] = published.snapshot.snapshot_id
    queue = assess_gpt1_opening_candidates(
        existing, before["canonical"], view, source_root=root)
    return {
        **queue,
        "source_sha256": digest,
        "snapshot_id": root["snapshot_id"],
        "revision_id": root["revision_id"],
        "page_id": page_id,
        "source_snapshot_and_original_sealed_receipts_unchanged": True,
        "same_root_f07": view,
        "signed_source_lineage_handoff_granted": False,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--page-id", required=True)
    p.add_argument("--sha256", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    raw = args.pdf.read_bytes()
    if sha256(raw).hexdigest() != args.sha256:
        raise ValueError("immutable original PDF SHA mismatch")
    result = original_host_frame_dimension_report(raw, page_id=args.page_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print({"hosted": result["original_authenticated_hosts"],
           "framed": result["original_complete_host_frames"],
           "figured_area": result["original_signed_area_quantities"],
           "new_gpt1_handoffs": len(result["gpt1_new_handoff_candidates"]),
           "first_gate_counts": result["first_gate_counts"]})


if __name__ == "__main__":
    main()
