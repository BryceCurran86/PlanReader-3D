"""Read-only census: which gate stops a source door swing from becoming a doorway chord, and which wall strip owns the door's ink.

Counts, gates and signed offsets only. No words, coordinates, room names, quantities or benchmark values are printed, so the output
is safe to quote publicly for a private source (the source is identified by a 16 character hash prefix only).

For each requested page it builds the dark-painted layered ring (shadow) with a spy on ``propose_source_owned_doorway_chords`` that
captures the exact arguments of the proposal, then asks ``diagnose_source_owned_doorway_chord_gates`` for one receipt per source
swing witness: the first failing gate (G0 axis, G1 four supports, G2 no parent raw gap, G3 competing parent raw gaps, G4 duplicate
door interval, or a proposed chord), the support counts, and for every same-axis raw gap on the door's wall line the signed miss at
each end of the door interval (positive = the gap STOPS SHORT of that end). It adds which strip collector minted a strip from each
witness's native paths and how far that strip reaches into the doorway; that attribution runs the collectors on the FULL rows, so it
shows what door symbol ink would mint even where the builder already keeps it out of the strips. The builder keeps it out only with
its ``door_jamb_returns`` switch (``--door-jamb-returns`` here; off, as by default, reports the builder as it normally runs).

This module changes no production behaviour and grants no authority. Every figure is a topology diagnostic; nothing here is a wall,
an opening, a closure, a quantity or a score.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import fitz

import pb_layered_wall_doorway_room_ring_shadow as layered
import pb_source_segmented_door_swing_shadow as swing

_NO_ABSOLUTE_COORDINATES = (
    "counts, gates and signed offsets only; no coordinates, words or names; source identified by a hash prefix"
)


def capture_proposer_call(
    rows: Sequence[Mapping[str, Any]],
    *,
    page_index: int,
    wall_end_stroke_closures: bool = False,
    source_heavy_stroke_wall_bands: bool = False,
    door_jamb_returns: bool = False,
) -> tuple[Any, tuple[Any, tuple[Mapping[str, Any], ...], tuple[Any, ...]] | None]:
    """Build the dark-painted layered ring and capture ``(drawings, witnesses, gaps)`` as the chord proposer received them.

    ``None`` for the capture when the builder never reached the proposal (a page over the structural cap, or with no wall ink).
    The proposer is restored whatever happens."""
    captured: list[tuple[Any, tuple[Mapping[str, Any], ...], tuple[Any, ...]]] = []
    real = swing.propose_source_owned_doorway_chords

    def spy(drawings, swing_witnesses, original_wall_gaps):
        captured.append((drawings, tuple(swing_witnesses), tuple(original_wall_gaps)))
        return real(drawings, swing_witnesses, original_wall_gaps)

    swing.propose_source_owned_doorway_chords = spy
    try:
        result = layered.build_layered_wall_doorway_room_rings(
            rows,
            source_sha256="0" * 64,
            page_index=page_index,
            dark_painted_wall_source=True,
            wall_end_stroke_closures=wall_end_stroke_closures,
            source_heavy_stroke_wall_bands=source_heavy_stroke_wall_bands,
            door_jamb_returns=door_jamb_returns,
        )
    finally:
        swing.propose_source_owned_doorway_chords = real
    return result, (captured[0] if captured else None)


def strips_by_collector(drawings: Sequence[Mapping[str, Any]]) -> dict[str, list[Any]]:
    """Every line-based and filled strip collector run on the FULL rows, in a fixed order."""
    return {
        "filled_wall": list(layered._collect_strips(drawings)[0]),
        "dark_painted_fill": list(layered._collect_dark_painted_source_wall_strips(drawings)),
        "stroke_pair": list(layered._collect_stroke_pair_strips(drawings)),
        "merged_collinear_face": list(layered._collect_merged_collinear_dark_face_strips(drawings)),
        "heavy_stroke": list(layered._collect_source_heavy_stroke_strips(drawings)),
    }


def strip_attribution(
    strips: Mapping[str, Sequence[Any]], witness: Mapping[str, Any], receipt: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """The strips that contain any native path of ``witness``: collector, thickness, and how far each reaches into the doorway.

    ``reach_into_door_interval`` is how much of the strip's extent ALONG THE DOOR'S AXIS lies inside the door interval, whatever the
    strip's own orientation: a thin strip standing across the doorway at its hinge end reaches in by half its thickness.
    ``covers_the_wall_line`` says whether the strip's extent across the axis includes the door's wall line, that is, whether it can
    cut the raw wall gap there at all."""
    owned = set(witness["native_source_path_indices"])
    interval = receipt["door_interval_pdf_pts"]
    perp = receipt["wall_line_perp_pdf_pts"]
    horizontal = receipt["axis"] == "horizontal"
    out: list[dict[str, Any]] = []
    for collector, collected in strips.items():
        for strip in collected:
            shared = owned.intersection(strip.native_path_indices())
            if not shared:
                continue
            band = strip.band()
            reach: float | None = None
            covers: bool | None = None
            if interval is not None and perp is not None:
                along = (strip.x0, strip.x1) if horizontal else (strip.y0, strip.y1)
                across = (strip.y0, strip.y1) if horizontal else (strip.x0, strip.x1)
                reach = round(max(0.0, min(along[1], interval[1]) - max(along[0], interval[0])), 3)
                covers = across[0] - .18 <= perp <= across[1] + .18
            out.append({
                "collector": collector,
                "owned_paths_in_strip": len(shared),
                "strip_path_count": len(strip.native_path_indices()),
                "thickness_pdf_pts": round(band[1] - band[0], 3),
                "strip_runs_along_the_door_axis": bool(strip.horizontal == horizontal),
                "reach_into_door_interval_pdf_pts": reach,
                "covers_the_wall_line": covers,
            })
    return out


def _witness_record(receipt: Mapping[str, Any], witness: Mapping[str, Any], attribution: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = receipt["gap_candidates"]
    return {
        "witness_index": receipt["witness_index"],
        "leaf_native_path_index": witness["leaf_native_path_index"],
        "axis": receipt["axis"],
        "first_failing_gate": receipt["first_failing_gate"] or "chord_proposed",
        "chord_proposed": receipt["chord_proposed"],
        "agrees_with_proposer": receipt["agrees_with_proposer"],
        "support_counts": receipt["support_counts"],
        "missing_required_supports": None if receipt["missing_required_supports"] is None else list(receipt["missing_required_supports"]),
        "same_axis_gap_count": receipt["same_axis_gap_count"],
        "parent_gap_count": receipt["parent_gap_count"],
        "parents_share_one_geometry": receipt["parents_share_one_geometry"],
        "duplicate_of_witness_index": receipt["duplicate_of_witness_index"],
        "gap_candidates": None if candidates is None else [
            {
                "lo_end_miss_pdf_pts": c["lo_end_miss_pdf_pts"],
                "hi_end_miss_pdf_pts": c["hi_end_miss_pdf_pts"],
                "contains_interval": c["contains_interval"],
                "an_end_coincides": c["an_end_coincides"],
                "is_parent": c["is_parent"],
            } for c in candidates
        ],
        "strips_owning_witness_paths": attribution,
    }


def page_report(
    rows: Sequence[Mapping[str, Any]],
    *,
    page_index: int,
    wall_end_stroke_closures: bool = False,
    source_heavy_stroke_wall_bands: bool = False,
    door_jamb_returns: bool = False,
    detail: bool = True,
) -> dict[str, Any]:
    """One page's counts-only chord-gate report (see the module docstring)."""
    result, captured = capture_proposer_call(
        rows, page_index=page_index, wall_end_stroke_closures=wall_end_stroke_closures,
        source_heavy_stroke_wall_bands=source_heavy_stroke_wall_bands, door_jamb_returns=door_jamb_returns,
    )
    report: dict[str, Any] = {
        "page_index": page_index,
        "rows": len(rows),
        "builder_status": result.status.value,
        "builder_reason_codes": list(result.reason_codes),
        "builder_keeps_door_owned_strokes_out_of_the_strips": door_jamb_returns,
        "proposal_called": captured is not None,
        "witness_count": 0,
        "chord_count": 0,
        "raw_gap_count": 0,
        "gate_histogram": {},
        "witnesses_with_strips_from_their_own_paths": 0,
        "witnesses": [],
    }
    if captured is None:
        return report
    drawings, witnesses, gaps = captured
    receipts = swing.diagnose_source_owned_doorway_chord_gates(drawings, witnesses, gaps)
    strips = strips_by_collector(drawings) if witnesses else {}
    records = []
    for receipt, witness in zip(receipts, witnesses):
        records.append(_witness_record(receipt, witness, strip_attribution(strips, witness, receipt)))
    report.update({
        "witness_count": len(receipts),
        "chord_count": sum(1 for r in receipts if r["chord_proposed"]),
        "raw_gap_count": len(gaps),
        "gate_histogram": dict(sorted(Counter(r["first_failing_gate"] or "chord_proposed" for r in receipts).items())),
        "witnesses_with_strips_from_their_own_paths": sum(1 for r in records if r["strips_owning_witness_paths"]),
        "all_receipts_agree_with_the_proposer": all(r["agrees_with_proposer"] for r in receipts),
    })
    if detail:
        report["witnesses"] = records
    return report


def build_report(
    pdf: Path, page_indices: Sequence[int] | None, *, opt_ins: bool = False, door_jamb_returns: bool = False, detail: bool = True,
) -> dict[str, Any]:
    payload = pdf.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    document = fitz.open(stream=payload, filetype="pdf")
    try:
        indices = list(range(len(document))) if page_indices is None else list(page_indices)
        for index in indices:
            if not 0 <= index < len(document):
                raise ValueError(f"page index {index} is outside the {len(document)} page document")
        pages = []
        for index in indices:
            rows = document[index].get_drawings()
            pages.append(page_report(
                rows, page_index=index, wall_end_stroke_closures=opt_ins, source_heavy_stroke_wall_bands=opt_ins,
                door_jamb_returns=door_jamb_returns, detail=detail,
            ))
    finally:
        document.close()
    totals: Counter[str] = Counter()
    for page in pages:
        totals.update(page["gate_histogram"])
    return {
        "note": _NO_ABSOLUTE_COORDINATES,
        "source_sha256_prefix": sha[:16],
        "opt_in_flags": bool(opt_ins),
        "door_jamb_returns": bool(door_jamb_returns),
        "pages": pages,
        "totals": {
            "pages": len(pages),
            "pages_with_a_proposal": sum(1 for p in pages if p["proposal_called"]),
            "witnesses": sum(p["witness_count"] for p in pages),
            "chords": sum(p["chord_count"] for p in pages),
            "gate_histogram": dict(sorted(totals.items())),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--page-index", type=int, action="append", help="0-based original page; repeat for several pages")
    parser.add_argument("--all-pages", action="store_true", help="every page of the document (slow on large vector sheets)")
    parser.add_argument("--opt-ins", action="store_true",
                        help="also run the builder with wall_end_stroke_closures and source_heavy_stroke_wall_bands")
    parser.add_argument("--door-jamb-returns", action="store_true",
                        help="run the builder with its door_jamb_returns switch (door strokes out of the wall strips, jamb returns in)")
    parser.add_argument("--summary-only", action="store_true", help="drop the per-witness records")
    parser.add_argument("--json-out", type=Path, help="write the report here instead of printing it (keep it outside the repository)")
    args = parser.parse_args(argv)
    if bool(args.page_index) == bool(args.all_pages):
        parser.error("give --page-index (repeatable) or --all-pages, not both and not neither")
    report = build_report(
        args.pdf, None if args.all_pages else args.page_index, opt_ins=args.opt_ins, door_jamb_returns=args.door_jamb_returns,
        detail=not args.summary_only,
    )
    text = json.dumps(report, indent=1, sort_keys=True)
    if args.json_out is not None:
        args.json_out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
