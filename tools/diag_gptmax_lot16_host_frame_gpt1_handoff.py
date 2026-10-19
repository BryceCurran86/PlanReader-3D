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


def _signed_quantity_body_sha256(issuer_quantities: list[dict]) -> dict[str, str]:
    """Audit COMPLETE producer-issued quantity bodies; never create quantities.

    Kept strictly outside live quantity/measurement authority. An unchanged ID
    with altered value, evidence, status, physical scope or metadata MUST change
    its fingerprint before the historical archive release check can pass.
    """
    if type(issuer_quantities) not in (list, tuple):
        raise TypeError("original issued quantities must be a sequence")
    hashes: dict[str, str] = {}
    for row in issuer_quantities:
        if type(row) is not dict:
            raise ValueError("original signed source quantity body unavailable")
        quantity_id = row.get("quantity_id")
        if (type(quantity_id) is not str or not quantity_id
                or quantity_id != quantity_id.strip()
                or quantity_id in hashes):
            raise ValueError("duplicate or invalid original signed quantity ID")
        # Stable JSON over the actual body, not only an ID/value/count subset.
        # Reject non-finite values and unrepresentable metadata.
        body = json.dumps(row, sort_keys=True, ensure_ascii=False,
                          allow_nan=False, separators=(",", ":"))
        hashes[quantity_id] = sha256(body.encode("utf-8")).hexdigest()
    return dict(sorted(hashes.items()))


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


def _source_owned_axes_agree_with_figured_pair(canonical: dict, evidence: dict) -> bool:
    """Independent original axis receipts must agree with printed dimensions.

    A PDF callout such as 1215 SGW gives a *pair* without proving which
    printed number is the width. The separate live canonical producer may
    resolve both width and height from frame/schedule/physical witnesses.
    Do not veto those independently source-owned axes solely because the
    callout's order is unresolved; equally, never permit a matching area
    product with unrelated or swapped dimensions to pass this review gate.
    This is diagnostic compatibility only, NEVER a measurement issuer.
    """
    width_id = canonical.get("width_record_id")
    height_id = canonical.get("height_record_id")
    if (type(width_id) is not str or not width_id or width_id != width_id.strip()
            or type(height_id) is not str or not height_id
            or height_id != height_id.strip() or width_id == height_id
            or canonical.get("geometry_complete") is not True):
        return False
    # Canonical record IDs are claims until present in the original producer's
    # own evidence collection. Match the downstream _measurement_axes gate.
    receipts = canonical.get("evidence_ids")
    if (type(receipts) not in (tuple, list)
            or width_id not in receipts or height_id not in receipts):
        return False
    width = canonical.get("width_m")
    height = canonical.get("height_m")
    if not _positive(width) or not _positive(height):
        return False
    raw_pair = evidence.get("dimension_values_mm")
    if (type(raw_pair) not in (tuple, list) or len(raw_pair) != 2
            or any(not _positive(v) for v in raw_pair)):
        return False
    dimensions = sorted(float(v) / 1000 for v in raw_pair)
    axes = sorted((float(width), float(height)))
    if not all(math.isclose(a, b, rel_tol=1e-8, abs_tol=1e-9)
               for a, b in zip(dimensions, axes)):
        return False
    # If the original label authority *also* claims width/height order, it
    # must not contradict the independently issued canonical axis records.
    figured_width, figured_height = evidence.get("width_mm"), evidence.get("height_mm")
    if (figured_width is None) != (figured_height is None):
        return False
    if figured_width is not None:
        if (not _positive(figured_width) or not _positive(figured_height)
                or not math.isclose(float(figured_width) / 1000, width,
                                    rel_tol=1e-8, abs_tol=1e-9)
                or not math.isclose(float(figured_height) / 1000, height,
                                    rel_tol=1e-8, abs_tol=1e-9)):
            return False
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
        # The printed pair is order-invariant; the canonical producer's
        # distinct source-owned width and height records are independently
        # ordered. Require both actual axis values to match the printed pair,
        # not merely their product, without using the label to invent order.
        axis_ok = (
            pair_ok
            and _source_owned_axes_agree_with_figured_pair(c, e)
            and math.isclose(
                c["width_m"] * c["height_m"], e["area_m2"], rel_tol=1e-8)
        )
        typed = c.get("opening_kind") in ("door", "window")
        # A source-issued area from an unordered two-number label does NOT
        # imply width/height order. Review opening AREA independently from
        # 3D axis geometry; neither review flag signs a quantity.
        figured_receipt_bound = bool(
            pair_ok and type(c.get("figured_area_record_id")) is str
            and c["figured_area_record_id"]
            and c["figured_area_record_id"] == e.get("evidence_id")
            and type(c.get("evidence_ids")) in (tuple, list)
            and c["figured_area_record_id"] in c["evidence_ids"]
        )
        if not supported:
            area_gate = "source_owned_floor_plan_unavailable"
        elif host is None:
            area_gate = "structural_host_unavailable"
        elif not frame_ok:
            area_gate = "whole_wall_frame_unavailable"
        elif not typed:
            area_gate = "opening_filling_kind_unproven"
        elif not pair_ok:
            area_gate = "source_figured_dimension_pair_unproven"
        elif not figured_receipt_bound:
            area_gate = "original_figured_area_receipt_unbound"
        elif row.get("quantity_id"):
            area_gate = "original_signed_area_already_retained"
        else:
            area_gate = "independent_gpt1_opening_area_measurement_validation_required"
        area_review_ready = (
            area_gate == "independent_gpt1_opening_area_measurement_validation_required"
        )
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
            "figured_area_receipt_bound": figured_receipt_bound,
            "opening_area_first_remaining_gate": area_gate,
            "new_gpt1_area_candidate_handoff": area_review_ready,
            "axis_order_authenticated": axis_ok,
            "original_figured_label_order_source_resolved": (
                e.get("axis_order_resolved") is True if pair_ok else False
            ),
            "independent_source_axis_record_ids": (
                [c["width_record_id"], c["height_record_id"]]
                if axis_ok else []
            ),
            "independent_axes_agree_with_original_pair": axis_ok,
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
        "area_first_gate_counts": dict(sorted(
            Counter(r["opening_area_first_remaining_gate"] for r in assessed).items())),
        "gpt1_new_area_review_candidates": [
            r for r in assessed if r["new_gpt1_area_candidate_handoff"]
        ],
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
        # SHA-only diagnostic: no private source/customer body exposed.
        # Full archived eight-body comparison lives in the owner-source CI.
        "original_source_issued_quantity_body_sha256": (
            _signed_quantity_body_sha256(before["quantities"])
        ),
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
