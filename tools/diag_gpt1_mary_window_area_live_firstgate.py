"""Read-only original-plan check of the ACTUAL live window-area consumer.

Native Wxx words alone never certify opening kind, physical wall host, frame,
signed customer quantities, or a frozen benchmark score.  This instrument
reads the production claim; it does not create or amend QuantityEvidence.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import inspect
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import (
    LivePhysicalNetWallClaim, collect_live_physical_net_wall_claim,
)
from pb_live_physical_opening_void_composition import LiveCanonicalOpeningObject
from pb_migration_contracts import QuantityEvidence

TARGETS = ("W01", "W02", "W05", "W06")
PLAN_PAGE_INDEX = 6
ELEVATION_PAGE_INDEX = 28


@dataclass(frozen=True)
class WindowAreaGate:
    type_mark: str
    first_missing_gate: str
    plan_native_occurrences: int
    elevation_native_occurrences: int
    physical_opening_id: str | None = None
    canonical_kind: str | None = None
    host_binding_record_id: str | None = None
    area_basis: str | None = None
    quantity_id: str | None = None


def _native_mark_count(page, mark: str) -> int:
    # Text is diagnostic ONLY; no claim of trusted glyph/clip/plan-mark owner.
    return sum(
        word[4].strip(".,:;()").upper() == mark
        for word in page.get_text("words")
    )


def diagnose_actual_window_area_gates(
    original_pdf_bytes: bytes,
    expected_sha256: str,
    claim: LivePhysicalNetWallClaim,
) -> dict:
    """Report first *observed* consumer-side failure; never mint a quantity."""
    if type(claim) is not LivePhysicalNetWallClaim:
        raise TypeError("actual LivePhysicalNetWallClaim required")
    if type(original_pdf_bytes) is not bytes or not original_pdf_bytes:
        raise ValueError("original source bytes required")
    digest = sha256(original_pdf_bytes).hexdigest()
    if type(expected_sha256) is not str or digest != expected_sha256.lower():
        raise ValueError("original source sha256 mismatch")
    import fitz

    with fitz.open(stream=original_pdf_bytes, filetype="pdf") as pdf:
        if len(pdf) <= ELEVATION_PAGE_INDEX:
            raise ValueError("original source plan/elevation pages missing")
        plan = pdf[PLAN_PAGE_INDEX]
        elevation = pdf[ELEVATION_PAGE_INDEX]
        plan_counts = {k: _native_mark_count(plan, k) for k in TARGETS}
        elevation_counts = {k: _native_mark_count(elevation, k) for k in TARGETS}

    openings = tuple(claim.canonical_openings)
    if any(type(o) is not LiveCanonicalOpeningObject for o in openings):
        raise TypeError("untrusted canonical opening in original claim")
    quantities = tuple(claim.opening_quantity_evidence)
    if any(type(q) is not QuantityEvidence for q in quantities):
        raise TypeError("untrusted quantity in original claim")
    if len({o.physical_opening_id for o in openings}) != len(openings):
        raise ValueError("duplicate canonical physical opening identity")
    if len({q.quantity_id for q in quantities}) != len(quantities):
        raise ValueError("duplicate issued opening quantity identity")
    by_mark = {}
    for opening in openings:
        mark = str(opening.type_mark or "").strip().upper()
        if mark in TARGETS:
            by_mark.setdefault(mark, []).append(opening)

    report = []
    for mark in TARGETS:
        members = by_mark.get(mark, [])
        label_count = plan_counts[mark]
        if label_count != 1 or elevation_counts[mark] < 1:
            report.append(WindowAreaGate(
                mark, "original_native_mark_unavailable_or_ambiguous",
                label_count, elevation_counts[mark]))
            continue
        if len(members) != 1:
            report.append(WindowAreaGate(
                mark, "physical_type_mark_binding_unavailable"
                if not members else "physical_type_mark_binding_conflict",
                label_count, elevation_counts[mark]))
            continue
        opening = members[0]
        physical_id = opening.physical_opening_id
        reason = None
        if (
            opening.source_sha256 != digest
            or str(opening.page_id) != str(PLAN_PAGE_INDEX + 1)
            or not opening.viewport_id
            or opening.canonical_opening_id != physical_id
        ):
            reason = "canonical_source_page_or_physical_identity_unbound"
        elif opening.opening_kind != "window":
            reason = "independent_window_kind_unavailable"
        elif not opening.host_wall_id or not (
            opening.host_binding_record_id or opening.host_frame_record_id
        ):
            reason = "structural_host_binding_unavailable"
        elif (
            opening.area_basis != "authenticated_elevation_frame"
            or not opening.figured_area_record_id
        ):
            reason = "authenticated_elevation_frame_area_unavailable"
        matches = [
            q for q in quantities
            if q.input_entity_ids == (physical_id,)
            and q.semantic_key == f"window_area:{physical_id}"
            and q.metadata.get("area_basis") == "authenticated_elevation_frame"
            and q.metadata.get("source_sha256") == digest
            and not q.abstained
        ]
        if reason is None and len(matches) != 1:
            reason = (
                "live_issued_quantity_unavailable"
                if not matches else "live_issued_quantity_conflict"
            )
        if reason is None and (
            matches[0].metadata.get("measurement_record_id")
            != opening.figured_area_record_id
            or matches[0].metadata.get("snapshot_id") != opening.snapshot_id
        ):
            reason = "issued_area_measurement_lineage_mismatch"
        report.append(WindowAreaGate(
            mark, reason or "LIVE_QUANTITY_OBSERVED_NOT_CUSTOMER_SEALED",
            label_count, elevation_counts[mark], physical_id,
            opening.opening_kind, opening.host_binding_record_id,
            opening.area_basis,
            matches[0].quantity_id if reason is None else None,
        ))

    from dataclasses import asdict
    return {
        "status": "SOURCE_ONLY_LIVE_ISSUER_FIRST_GATE_DIAGNOSTIC",
        "source_sha256": digest,
        "physical_opening_inventory": len(openings),
        "real_issuer_quantity_inventory": len(quantities),
        "not_source_authority": True,
        "measurement_published_by_this_tool": False,
        "customer_seal_granted": False,
        "benchmark_score_granted": False,
        "windows": [asdict(item) for item in report],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--native-source-text", action="store_true")
    args = parser.parse_args()
    params = inspect.signature(collect_live_physical_net_wall_claim).parameters
    # Match the actual source-handoff page universe, not a convenient
    # hand-selected p7/p29 subset that could omit contradictory schedule or
    # physical source evidence. Do not silently make p7 a topology authority.
    from tools.run_source_closed_project_handoff import _source_page_scopes
    topology_pages, support_pages, page_count = _source_page_scopes(args.pdf)
    if PLAN_PAGE_INDEX not in topology_pages:
        raise SystemExit(
            "original p7 not producer-authenticated as a topology page"
        )
    kwargs = {
        "pages": tuple(range(page_count)),
        "topology_pages": topology_pages,
        "room_area_support_pages": support_pages or None,
    }
    if args.native_source_text:
        if "source_native_finish_text_shadow" not in params:
            raise SystemExit(
                "native source text not wired to live collector; no fallback"
            )
        kwargs["source_native_finish_text_shadow"] = True
    pdf_bytes = args.pdf.read_bytes()
    if sha256(pdf_bytes).hexdigest() != args.expected_sha256.lower():
        raise SystemExit("original source SHA mismatch")
    claim = collect_live_physical_net_wall_claim(args.pdf, **kwargs)
    report = diagnose_actual_window_area_gates(
        pdf_bytes, args.expected_sha256, claim,
    )
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
