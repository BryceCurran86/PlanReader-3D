"""Archived ORIGINAL producer source receipts: six G17 openings, 12 flanks.

This test does not use scorer gold or any PDF-private bytes. It replays the
immutable source-observation lineage saved by an earlier original run. A pass
proves ONLY source-band geometry, never a W4 structural wall, opening host,
area, instance count, or benchmark match. A fresh producer replay remains
mandatory for promotion.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from pb_gpt2_raster_opening_parent_source_shadow import (
    AuthenticatedRasterOpeningParentLine, RasterOpeningParentSourceHandoff,
)
from pb_gpt2_raster_source_flank_band_shadow import (
    reconstruct_raster_source_flank_bands_shadow,
)

_ARCHIVE = (
    Path(__file__).resolve().parents[1]
    / "docs/engineering/gptmax_lot16_host_source_queue_20261016.json"
)
_EXPECTED_ORIGINAL_SHA = (
    "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
)


def _source_case_handoff(case: dict, digest: str):
    rows = []
    for original in case["source_g17_observations"]:
        parents = original.get("source_lineage_parent_ids")
        if not isinstance(parents, list) or len(parents) != 1:
            raise AssertionError("source has no unique original raster parent")
        ancestor = original.get("authenticated_source_parents")
        if (not isinstance(ancestor, list) or len(ancestor) != 1
                or ancestor[0]["observation_id"] != parents[0]
                or ancestor[0]["observation_kind"] != "raster_opening_primitive_segment"
                or ancestor[0]["geometry_pdf_pts"] != original["geometry_pdf_pts"]):
            raise AssertionError("original source parent identity/geometry conflict")
        rows.append(AuthenticatedRasterOpeningParentLine(
            parent_observation_id=parents[0],
            visible_observation_id=original["observation_id"],
            observation_kind=original["observation_kind"],
            original_source_primitive_ref=original["source_primitive_ref"],
            page_id=case.get("source_w4_ancestry_audit", {}).get("page_id", "3"),
            geometry_pdf_points=tuple(original["geometry_pdf_pts"]),
        ))
    ids = [row.parent_observation_id for row in rows]
    if len(set(ids)) != len(ids):
        raise AssertionError("duplicate original source parent across a G17 opening")
    return RasterOpeningParentSourceHandoff(
        "SOURCE_ONLY_CANDIDATE", digest, tuple(sorted(ids)),
        tuple(rows), (), ("original_source_parent_proven_in_archive",),
    )


def test_six_original_producer_unhosted_openings_recover_both_source_flanks():
    archive = json.loads(_ARCHIVE.read_text(encoding="utf-8"))
    assert archive["source_sha256"] == _EXPECTED_ORIGINAL_SHA
    assert archive["baseline_summary"]["canonical_opening_records"] == 21
    assert archive["baseline_summary"]["canonical_opening_area_records"] == 8
    assert archive["baseline_summary"]["authenticated_hosts"] == 15
    assert archive["authority_grants"]["new_host"] is False
    cases = [
        case for case in archive["case_evidence"]
        if case.get("host_binding", {}).get("status") == "abstained"
    ]
    assert len(cases) == 6
    for case in cases:
        original = _source_case_handoff(case, archive["source_sha256"])
        result = reconstruct_raster_source_flank_bands_shadow(original)
        assert result.status == "SOURCE_BAND_GEOMETRY_CANDIDATE", case["physical_opening_id"]
        assert len(result.candidates) == 2, case["physical_opening_id"]
        assert sorted(len(c.original_source_visible_ids) for c in result.candidates) == [3, 3]
        assert len(result.unresolved_source_parent_ids) == 2  # thin ink runs
        assert not result.physical_wall_granted
        assert not result.opening_host_granted
        assert not result.opening_count_granted
        assert not result.firm_quantity_granted
        assert all(not row.structural_wall_granted and not row.whole_wall_frame_granted
                   for row in result.candidates)


def test_original_source_line_order_and_segment_endpoint_reversal_invariance():
    archive = json.loads(_ARCHIVE.read_text(encoding="utf-8"))
    cases = [
        case for case in archive["case_evidence"]
        if case.get("host_binding", {}).get("status") == "abstained"
    ]
    for case in cases:
        original = _source_case_handoff(case, archive["source_sha256"])
        before = reconstruct_raster_source_flank_bands_shadow(original)
        reversed_rows = tuple(
            replace(row, geometry_pdf_points=(*row.geometry_pdf_points[2:],
                                                *row.geometry_pdf_points[:2]))
            for row in reversed(original.lines)
        )
        after = reconstruct_raster_source_flank_bands_shadow(
            replace(original, lines=reversed_rows)
        )
        assert before == after, case["physical_opening_id"]
