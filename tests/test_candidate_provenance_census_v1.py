"""Candidate drawing-path provenance census: descriptive, shadow-only, ref-only.

Synthetic drawings check the census's behaviour only.  They are not evidence
about real drawings, and no expected value here comes from a benchmark.
"""
from __future__ import annotations

import ast
import dataclasses
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import fitz
import pytest

from pb_candidate_provenance_census import (
    CENSUS_SCHEMA_VERSION,
    FINE_BANDS,
    LENGTH_BANDS,
    CandidateProvenanceCensus,
    aggregate_candidate_provenance_censuses,
    build_candidate_provenance_census,
    collect_candidate_provenance_census,
    fine_length_band,
    length_band,
    parse_visible_segment_ref,
)
from pb_item35_production_authority_shadow import collect_item35_authority_shadow
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PhysicalOpeningAuthority,
    PhysicalOpeningCandidateStructureResult,
)
from pb_provider_gold_isolation import (
    FORBIDDEN_MODULES,
    FORBIDDEN_NAME_FRAGMENTS,
    walk_local_import_graph,
)
from pb_semantic_conflict_diagnostic import collect_semantic_scope, diagnose_semantic_conflicts
from pb_source_observation_authority import ObservationSelector, SourceObservationAuthorityResult
from pb_source_visibility_authority import (
    NATIVE_PDF_VISIBLE_SEGMENT,
    RASTER_PDF_VISIBLE_SEGMENT,
    SourceVisibilityAuthority,
)
from scripts import candidate_provenance_census_report as report_script

REPO = Path(__file__).resolve().parents[1]
MODULE = "pb_candidate_provenance_census"
DOC = "census-test"
SHA = "a" * 64


# ---------------------------------------------------------------- fixtures
def _wall(spans, top, gap=10.0):
    lines = []
    for x0, x1 in spans:
        lines.append(((x0, top), (x1, top)))  # top face
        lines.append(((x0, top + gap), (x1, top + gap)))  # bottom face
    return lines


def _jambs(xs, top, gap=10.0):
    return [((x, top), (x, top + gap)) for x in xs]


# Two adjacent openings (three wall spans; the collinear faces also make a third,
# spanning candidate) + one isolated control opening.  Segment order = draw order.
ADJ_FACES = _wall([(20, 100), (140, 180), (220, 300)], 100.0)
ADJ_JAMBS = _jambs([100, 140, 180, 220], 100.0)
CTRL_FACES = _wall([(20, 100), (140, 220)], 300.0)
CTRL_JAMBS = _jambs([100, 140], 300.0)
ALL_SEGMENTS = ADJ_FACES + ADJ_JAMBS + CTRL_FACES + CTRL_JAMBS  # indices 0..15
TOP_FACES = [s for i, s in enumerate(ADJ_FACES) if i % 2 == 0] + [
    s for i, s in enumerate(CTRL_FACES) if i % 2 == 0
]
BOTTOM_FACES = [s for i, s in enumerate(ADJ_FACES) if i % 2 == 1] + [
    s for i, s in enumerate(CTRL_FACES) if i % 2 == 1
]


def _groupings():
    return {
        "separate": [[s] for s in ALL_SEGMENTS],  # 16 paths
        "one_path": [list(ALL_SEGMENTS)],  # 1 path
        "faces_vs_jambs": [ADJ_FACES + CTRL_FACES, ADJ_JAMBS + CTRL_JAMBS],  # 2 paths
        "top_bottom_jambs": [TOP_FACES, BOTTOM_FACES, ADJ_JAMBS + CTRL_JAMBS],  # 3 paths
    }


def _draw_groups(page, groups):
    for group in groups:
        shape = page.new_shape()
        for first, second in group:
            shape.draw_line(fitz.Point(*first), fitz.Point(*second))
        shape.finish(color=(0, 0, 0), width=1, closePath=False)  # do not draw a return line
        shape.commit()


def _write(path: Path, draw, *, width=700, height=650) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=width, height=height)
    page.insert_text(fitz.Point(40, 40), "GROUND FLOOR PLAN", color=(0, 0, 0))
    draw(page)
    doc.save(path)
    doc.close()
    return path


def _grouped_pdf(tmp_path, name, groups, **page):
    return _write(tmp_path / f"{name}.pdf", lambda p: _draw_groups(p, groups), **page)


def _scope(pdf, document_id=DOC, pages=None):
    source, result = collect_semantic_scope(pdf, document_id=document_id, pages=pages)
    reference = diagnose_semantic_conflicts(
        source_visibility_producer=source, semantic_result=result
    ).candidate_structure
    return source, result, reference


def _census(pdf, **kwargs):
    return collect_candidate_provenance_census(pdf, document_id=DOC, **kwargs).to_dict()


def _sel(record, observation_id):
    return ObservationSelector(
        document_id=record.document_id,
        revision_id=record.revision_id,
        source_sha256=record.source_sha256,
        snapshot_id=record.snapshot_id,
        observation_id=observation_id,
    )


@pytest.fixture()
def grouped(tmp_path):
    return {name: _grouped_pdf(tmp_path, name, groups) for name, groups in _groupings().items()}


# ------------------------------------------------------------ ref grammar
@pytest.mark.parametrize(
    "ref, klass, path, item, edge",
    [
        ("visible:segment:d0i0", "native_line", 0, 0, None),
        ("visible:segment:d24i0", "native_line", 24, 0, None),
        ("visible:segment:d4330i3", "native_line", 4330, 3, None),
        ("visible:segment:d10i0e3", "native_rect_edge", 10, 0, 3),
        ("visible:segment:d7i12e0", "native_rect_edge", 7, 12, 0),
    ],
)
def test_native_refs_parse_and_the_rect_edge_subclass_comes_from_ref_syntax(
    ref, klass, path, item, edge
):
    parsed = parse_visible_segment_ref(ref)
    assert (parsed.ref_class, parsed.path_index, parsed.item_index, parsed.edge_index) == (
        klass,
        path,
        item,
        edge,
    )
    assert parsed.reason is None


def test_raster_refs_are_recognised_and_carry_no_pdf_path():
    parsed = parse_visible_segment_ref(f"visible:raster_segment:{SHA}:1.0.0:17")
    assert parsed.ref_class == "raster"
    assert parsed.path_index is None and parsed.item_index is None


@pytest.mark.parametrize(
    "ref",
    [
        "",
        "segment:d1i2",  # the parent form, not a visible ref
        "visible:segment:d1",
        "visible:segment:d1i",
        "visible:segment:di2",
        "visible:segment:d01i2",  # leading zero: not canonical
        "visible:segment:d1i02",
        "visible:segment:d1i2e4",  # only edges 0..3 exist
        "visible:segment:d1i2e",
        "visible:segment:d1i2e01",
        "visible:segment:D1I2",
        "visible:segment:d1i2 ",
        "visible:segment:d1i2\n",
        " visible:segment:d1i2",
        "visible:segment:d1i2extra",
        "visible:segment:d٣i2",  # non-ASCII digit
        "visible:segment:d-1i2",
        "visible:rect:0",
        "visible:raster_segment:short:1.0.0:1",
        f"visible:raster_segment:{SHA.upper()}:1.0.0:1",
        f"visible:raster_segment:{SHA}:1.0.0:01",
        f"visible:raster_segment:{SHA}::1",
        "visible:visible:segment:d1i2",
    ],
)
def test_anything_off_grammar_is_unparseable_never_guessed(ref):
    parsed = parse_visible_segment_ref(ref)
    assert parsed.ref_class == "unparseable"
    assert parsed.reason in {"ref_prefix_unrecognized", "ref_grammar_mismatch"}
    assert parsed.path_index is None


def test_non_string_refs_are_unparseable():
    for value in (None, 7, b"visible:segment:d1i2", ("visible:segment:d1i2",)):
        parsed = parse_visible_segment_ref(value)
        assert parsed.ref_class == "unparseable" and parsed.reason == "ref_not_a_string"


def test_every_ref_the_real_extractor_mints_parses_and_kind_does_not_split_the_subclass(tmp_path):
    def draw(page):
        _draw_groups(page, [[((30, 30), (90, 30)), ((90, 30), (90, 60))], [((10, 200), (300, 210))]])
        page.draw_rect(fitz.Rect(150, 150, 230, 180))  # re item -> 4 rect edges, one path

    pdf = _write(tmp_path / "mixed.pdf", draw)
    source, result = collect_semantic_scope(pdf, document_id=DOC)
    published = source.published_snapshot_for_revision(result.record.revision_id)
    authority = source.authority()
    seen = Counter()
    kinds = set()
    for observation_id in result.record.visible_observation_ids:
        visible = authority.resolve_visible(_sel(result.record, observation_id))
        observation = visible.observation
        parsed = parse_visible_segment_ref(observation.source_primitive_ref)
        assert parsed.ref_class in {"native_line", "native_rect_edge"}, observation.source_primitive_ref
        seen[parsed.ref_class] += 1
        kinds.add(observation.observation_kind)
    assert published is not None
    assert seen["native_rect_edge"] == 4 and seen["native_line"] >= 3
    # Amendment: BOTH subclasses carry the same observation kind, so the kind cannot
    # tell them apart; only the verified ref syntax can.
    assert kinds == {NATIVE_PDF_VISIBLE_SEGMENT}


# ------------------------------------------------------------ length bands
@pytest.mark.parametrize(
    "value, band",
    [
        (0.0, "<0.5"),
        (0.4999999, "<0.5"),
        (0.5, "[0.5,1)"),
        (0.9999, "[0.5,1)"),
        (1.0, "[1,2)"),
        (1.999, "[1,2)"),
        (2.0, "[2,5)"),
        (4.999, "[2,5)"),
        (5.0, "[5,10)"),
        (9.999, "[5,10)"),
        (10.0, "[10,25)"),
        (24.999, "[10,25)"),
        (25.0, "[25,100)"),
        (99.999, "[25,100)"),
        (100.0, "[100,∞)"),
        (12345.0, "[100,∞)"),
        (None, "unknown"),
        (float("nan"), "unknown"),
        (float("inf"), "unknown"),
    ],
)
def test_length_bands_are_the_approved_fixed_reporting_bins(value, band):
    assert length_band(value) == band
    assert LENGTH_BANDS == (
        "<0.5", "[0.5,1)", "[1,2)", "[2,5)", "[5,10)", "[10,25)", "[25,100)",
        "[100,∞)", "unknown",
    )


def test_fine_bands_refine_the_tiny_range_and_are_consistent_with_the_bands():
    for value in (0.1, 0.5, 0.55, 0.65, 0.75, 0.85, 0.95, 1.0, 1.3, 1.6, 2.0, 50.0, None):
        fine = fine_length_band(value)
        assert fine in FINE_BANDS
        coarse = length_band(value)
        if coarse == "<0.5":
            assert fine == "<0.5"
        if coarse == "unknown":
            assert fine == "unknown"
    assert fine_length_band(0.7) == "[0.7,0.8)"


# ------------------------------------------------- path structure (designed fixtures)
# Draw order gives path indices: `separate` = 0..15 (one segment per path).
# Segment indices: 0..5 adjacent faces (A_top, A_bot, B_top, B_bot, C_top, C_bot),
# 6..9 adjacent jambs (x=100,140,180,220), 10..13 control faces, 14..15 control jambs.
# Candidates: c1 {0,1,2,3,6,7}  c2 {2,3,4,5,8,9}  c3 {0,1,4,5,6,9}  (participating: they
# share members) and the isolated control opening c4 {10..15}.
EXPECTED = {
    "separate": {
        "distinct": {"participating": {"6": 3}, "control": {"6": 1}},
        "class": {"participating": "three_plus_paths", "control": "three_plus_paths"},
        "per_path": {"participating": {"1": 18}, "control": {"1": 6}},
        "span": {"participating": {"7": 2, "9": 1}, "control": {"5": 1}},
        "order": {
            "participating": {"non_contiguous": 3},
            "control": {"contiguous_run": 1},
        },
    },
    "one_path": {
        "distinct": {"participating": {"1": 3}, "control": {"1": 1}},
        "class": {"participating": "single_path", "control": "single_path"},
        "per_path": {"participating": {"6": 3}, "control": {"6": 1}},
        "span": {"participating": {"0": 3}, "control": {"0": 1}},
        "order": {"participating": {"single_path": 3}, "control": {"single_path": 1}},
    },
    "faces_vs_jambs": {
        "distinct": {"participating": {"2": 3}, "control": {"2": 1}},
        "class": {"participating": "two_paths", "control": "two_paths"},
        "per_path": {"participating": {"2": 3, "4": 3}, "control": {"2": 1, "4": 1}},
        "span": {"participating": {"1": 3}, "control": {"1": 1}},
        "order": {
            "participating": {"contiguous_run": 3},
            "control": {"contiguous_run": 1},
        },
    },
    "top_bottom_jambs": {
        "distinct": {"participating": {"3": 3}, "control": {"3": 1}},
        "class": {"participating": "three_plus_paths", "control": "three_plus_paths"},
        "per_path": {"participating": {"2": 9}, "control": {"2": 3}},
        "span": {"participating": {"2": 3}, "control": {"2": 1}},
        "order": {
            "participating": {"contiguous_run": 3},
            "control": {"contiguous_run": 1},
        },
    },
}


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_path_structure_matches_the_designed_layout(grouped, name):
    census = _census(grouped[name])
    assert census["status"] == "ok"
    expected = EXPECTED[name]
    for group in ("participating", "control"):
        block = census["groups"][group]
        want = 3 if group == "participating" else 1
        assert block["candidates_total"] == want
        assert block["complete"] == want and block["provenance_incomplete"] == 0
        assert block["path_class"][expected["class"][group]] == want
        assert sum(block["path_class"].values()) == want
        assert block["distinct_paths_per_candidate"] == expected["distinct"][group]
        assert block["members_per_path"] == expected["per_path"][group]
        assert block["path_index_span"] == expected["span"][group]
        order = {k: v for k, v in block["draw_order"].items() if v}
        assert order == expected["order"][group]
        # every segment is its own (path,item) in these layouts
        assert block["distinct_items_per_candidate"] == {"6": want}
        assert block["member_incidences"] == {
            "total": 6 * want, "native_line": 6 * want, "native_rect_edge": 0, "raster": 0
        }


def test_all_consistency_checks_pass_against_the_structure_reference(grouped):
    for name, pdf in grouped.items():
        census = _census(pdf)
        checks = census["consistency"]["checks"]
        assert census["consistency"]["all_checks_passed"] is True, (name, checks)
        assert all(value is True for value in checks.values()), (name, checks)
        assert census["consistency"]["candidates_total"] == 4
        assert census["pages"] == {"enumerated": 1, "unavailable": 0, "unavailable_detail": []}


def test_reference_checks_are_reported_not_checked_when_no_reference_is_given(grouped):
    census = _census(grouped["separate"], with_reference=False)
    checks = census["consistency"]["checks"]
    for name in (
        "candidates_total_matches_structure_reference",
        "ambiguous_observations_match_structure_reference",
        "observations_in_multiple_candidates_match_structure_reference",
        "observations_in_candidates_match_structure_reference",
    ):
        assert checks[name] is None
    assert census["consistency"]["all_checks_passed"] is True  # the rest still pass


def test_a_wrong_reference_is_reported_as_a_failed_check(grouped):
    source, result, reference = _scope(grouped["separate"])
    wrong = dataclasses.replace(reference, candidates_total=reference.candidates_total + 1)
    census = build_candidate_provenance_census(
        source_visibility_producer=source, semantic_result=result, reference_structure=wrong
    ).to_dict()
    assert census["consistency"]["checks"]["candidates_total_matches_structure_reference"] is False
    assert census["consistency"]["all_checks_passed"] is False


def test_control_group_is_the_isolated_opening_and_participating_are_the_overlapping_ones(grouped):
    census = _census(grouped["separate"])
    # totals of the groups add up to all candidates; nothing is dropped
    assert census["groups"]["participating"]["candidates_total"] == 3
    assert census["groups"]["control"]["candidates_total"] == 1
    assert census["ambiguous_observations"]["observations_in_multiple_candidates"] == 8
    assert census["ambiguous_observations"]["assessed"] == 8
    assert census["ambiguous_observations"]["accessor_disposition_mismatch"] == 0


def test_an_independent_oracle_over_the_raw_refs_agrees_with_the_census(grouped):
    """Recompute paths from the raw refs with a separate regex and compare."""
    pattern = re.compile(r"visible:segment:d(\d+)i(\d+)")
    for name, pdf in grouped.items():
        source, result, _ = _scope(pdf)
        authority = source.authority()
        physical = PhysicalOpeningAuthority(authority)
        record = result.record

        def path_of(observation_id):
            ref = authority.resolve_visible(_sel(record, observation_id)).observation.source_primitive_ref
            return int(pattern.fullmatch(ref).group(1))  # single page: bare == qualified

        seed = sorted(record.visible_observation_ids)[0]
        candidates = physical.visible_candidate_structures(_sel(record, seed)).candidates
        distinct = Counter()
        spans = Counter()
        containing = {}
        for candidate in candidates:
            paths = {path_of(oid) for oid in candidate.source_observation_ids}
            distinct[len(paths)] += 1
            spans[max(paths) - min(paths)] += 1
            for oid in candidate.source_observation_ids:
                containing.setdefault(oid, []).append(candidate)
        path_size = Counter(path_of(oid) for oid in record.visible_observation_ids)
        own_size = Counter()
        union_size = Counter()
        for oid, group in containing.items():
            if len(group) < 2:
                continue  # not ambiguous
            own_size[path_size[path_of(oid)]] += 1
            union_size[len({path_of(m) for c in group for m in c.source_observation_ids})] += 1

        census = build_candidate_provenance_census(
            source_visibility_producer=source, semantic_result=result
        ).to_dict()
        got_distinct = Counter()
        got_span = Counter()
        for group in ("participating", "control"):
            for key, value in census["groups"][group]["distinct_paths_per_candidate"].items():
                got_distinct[int(key)] += value
            for key, value in census["groups"][group]["path_index_span"].items():
                got_span[int(key)] += value
        assert got_distinct == distinct, name
        assert got_span == spans, name
        obs = census["ambiguous_observations"]
        assert {int(k): v for k, v in obs["own_path_visible_segment_count"].items()} == own_size, name
        assert {
            int(k): v for k, v in obs["distinct_paths_in_union_of_its_candidates"].items()
        } == union_size, name


# Hand-derived observation-level expectations for the designed layouts (8 ambiguous
# observations: A,A',B,B',C,C' faces and the x=100 / x=220 jambs).  `own path size` is
# the number of visible segments on the observation's own path.
@pytest.mark.parametrize(
    "name, own_size, concentration",
    [
        ("separate", {"1": 8}, "none_single_path"),
        ("one_path", {"16": 8}, "all_single_path"),
        ("faces_vs_jambs", {"10": 6, "6": 2}, "none_single_path"),
        ("top_bottom_jambs", {"5": 6, "6": 2}, "none_single_path"),
    ],
)
def test_observation_level_path_concentration_matches_the_designed_layout(
    grouped, name, own_size, concentration
):
    obs = _census(grouped[name])["ambiguous_observations"]
    assert obs["assessed"] == obs["accessor_disposition_agree"] == 8
    assert obs["own_path_visible_segment_count"] == own_size
    assert obs["path_concentration"][concentration] == 8
    assert sum(obs["path_concentration"].values()) == obs["complete_native"] == 8
    assert sum(obs["own_length_band_by_path_concentration"].values()) == 8
    assert sum(obs["own_length_band"].values()) == 8


# --------------------------------------------- rect edges, items, native path identity
def _blocks(page, *, one_path):
    left = fitz.Rect(20, 100, 100, 110)
    right = fitz.Rect(140, 100, 220, 110)
    if one_path:
        shape = page.new_shape()
        shape.draw_rect(left)
        shape.draw_rect(right)
        shape.finish(color=(0, 0, 0), width=1, closePath=False)
        shape.commit()
    else:
        page.draw_rect(left, color=(0, 0, 0), width=1)
        page.draw_rect(right, color=(0, 0, 0), width=1)
    # a second adjacent block makes the shared faces ambiguous (page is enumerated)
    page.draw_rect(fitz.Rect(260, 100, 300, 110), color=(0, 0, 0), width=1)


# Layout (x): rect L 20..100, rect R 140..220, rect T 260..300, all y 100..110.  Every
# candidate is bounded by two rects: c1 = L+R, c2 = R+T, c3 = L+T (the collinear pair
# spanning R).  Each contributes 3 members per rect (top edge, bottom edge, the edge
# facing the gap), all `rect_edge` refs (`d<N>i0e<K>`), one (path,item) per rect.
@pytest.mark.parametrize(
    "one_path, distinct_paths, members_per_path",
    [
        (False, {"2": 3}, {"3": 6}),  # L, R, T are three paths
        (True, {"1": 1, "2": 2}, {"6": 1, "3": 4}),  # L and R share one path; T is another
    ],
)
def test_rect_edges_are_classified_from_ref_syntax_and_items_are_counted(
    tmp_path, one_path, distinct_paths, members_per_path
):
    pdf = _write(tmp_path / f"blocks_{one_path}.pdf", lambda p: _blocks(p, one_path=one_path))
    census = _census(pdf)
    block = census["groups"]["participating"]
    assert block["candidates_total"] == 3 and census["groups"]["control"]["candidates_total"] == 0
    assert block["member_incidences"] == {
        "total": 18, "native_line": 0, "native_rect_edge": 18, "raster": 0
    }
    assert block["distinct_paths_per_candidate"] == distinct_paths
    assert block["members_per_path"] == members_per_path
    # two rects per candidate -> two (page, path, item) keys, whatever the path grouping
    assert block["distinct_items_per_candidate"] == {"2": 3}
    inventory = census["inventory"]
    assert inventory["by_ref_class"]["native_rect_edge"] == 12  # 3 rects x 4 edges
    assert inventory["by_ref_class"]["native_line"] == 0
    assert inventory["native_paths"] == (2 if one_path else 3)
    assert inventory["native_paths_by_visible_segment_count"] == (
        {"4": 1, "8": 1} if one_path else {"4": 3}
    )
    assert census["consistency"]["all_checks_passed"] is True


def test_native_path_identity_is_page_qualified_never_the_bare_index(tmp_path):
    def draw(page):
        _draw_groups(page, [[s] for s in ADJ_FACES + ADJ_JAMBS])

    doc = fitz.open()
    for _ in range(2):  # two pages with identical layouts -> identical bare path indices
        page = doc.new_page(width=700, height=650)
        page.insert_text(fitz.Point(40, 40), "GROUND FLOOR PLAN", color=(0, 0, 0))
        draw(page)
    pdf = tmp_path / "two_pages.pdf"
    doc.save(pdf)
    doc.close()
    census = _census(pdf)
    assert census["pages"]["enumerated"] == 2
    inventory = census["inventory"]
    assert inventory["native_paths"] == 20  # 10 paths per page, not 10
    assert inventory["bare_path_indices_shared_by_several_pages"] == 10
    total = Counter()
    for group in ("participating", "control"):
        total.update(census["groups"][group]["distinct_paths_per_candidate"])
    # candidates of page 1 and page 2 never share a path, so each is P=6 (separate paths)
    assert total == {"6": 6}
    assert census["consistency"]["checks"]["native_path_identity_is_page_qualified"] is True
    assert set(census["by_page"]) == {"1", "2"}


# ------------------------------------------------------- bands and anomalies
def _with_thin_rect(page):
    _draw_groups(page, [[s] for s in ADJ_FACES + ADJ_JAMBS])
    page.draw_rect(fitz.Rect(500, 500, 600, 500.3), color=(0, 0, 0), width=1)  # 0.3 tall


def test_the_producer_never_lets_sub_half_native_segments_become_visible_records(tmp_path):
    """Observed: the extractor emits the 0.3-long edges of a thin rectangle, but the
    visibility authority rejects native geometry shorter than 0.5, so no such record
    reaches the census (and none is filtered by the census)."""
    census = _census(_write(tmp_path / "thin.pdf", _with_thin_rect))
    inventory = census["inventory"]
    assert inventory["by_ref_class"]["native_rect_edge"] == 2  # only the two 100-long edges
    assert inventory["visible_segments_on_enumerated_pages"] == 10 + 2
    assert not any(key.endswith("|<0.5") for key in inventory["length_band_by_ref_class"])
    assert sum(census["anomalies"]["counts"].values()) == 0
    assert "VISIBILITY_GEOMETRY_INVALID" in census["anomalies"]["note"]


def test_a_native_rect_edge_below_half_is_reported_as_an_anomaly_and_kept(monkeypatch, tmp_path):
    pdf = _write(tmp_path / "blocks.pdf", lambda p: _blocks(p, one_path=False))
    target = _some_candidate_member(pdf)
    source, result, reference = _scope(pdf)

    def tiny(observation_id, result_):
        if observation_id != target:
            return None
        return _replace_observation(result_, geometry=(10.0, 10.0, 10.0, 10.2))

    baseline = build_candidate_provenance_census(
        source_visibility_producer=source, semantic_result=result, reference_structure=reference
    ).to_dict()
    with monkeypatch.context() as patch:
        _forge_after_structures(patch, tiny)
        census = build_candidate_provenance_census(
            source_visibility_producer=source, semantic_result=result, reference_structure=reference
        ).to_dict()
    assert census["anomalies"]["counts"]["native_rect_edge_below_0_5"] == 1
    assert census["anomalies"]["counts"]["native_line_below_0_5"] == 0
    example = census["anomalies"]["examples"]["native_rect_edge_below_0_5"][0]
    assert example["observation_id"] == target
    assert re.fullmatch(r"visible:segment:d\d+i\d+e[0-3]", example["source_primitive_ref"])
    for group in ("participating", "control"):
        assert (
            census["groups"][group]["candidates_total"]
            == baseline["groups"][group]["candidates_total"]
        )


def test_length_band_sums_match_member_totals(grouped):
    census = _census(grouped["separate"])
    for block in census["groups"].values():
        length = block["length"]
        assert sum(length["band_incidences"].values()) == block["member_incidences"]["total"]
        assert sum(length["fine_band_incidences"].values()) == block["member_incidences"]["total"]
        assert set(length["band_incidences"]) == set(LENGTH_BANDS)
    assert census["consistency"]["checks"]["length_band_sums_match_member_incidences"] is True


def _forge_after_structures(monkeypatch, forge):
    """Forge visible records only AFTER candidate discovery, so discovery is unaffected."""
    state = {"armed": False}
    original_structures = PhysicalOpeningAuthority.visible_candidate_structures
    original_resolve = SourceVisibilityAuthority.resolve_visible

    def structures(self, selector):
        out = original_structures(self, selector)
        state["armed"] = True
        return out

    def resolve(self, selector):
        result = original_resolve(self, selector)
        if state["armed"]:
            forged = forge(selector.observation_id, result)
            if forged is not None:
                return forged
        return result

    monkeypatch.setattr(PhysicalOpeningAuthority, "visible_candidate_structures", structures)
    monkeypatch.setattr(SourceVisibilityAuthority, "resolve_visible", resolve)


def _replace_observation(result, **changes):
    return dataclasses.replace(
        result, observation=dataclasses.replace(result.observation, **changes)
    )


def _some_candidate_member(pdf):
    source, result, _ = _scope(pdf)
    physical = PhysicalOpeningAuthority(source.authority())
    record = result.record
    seed = sorted(record.visible_observation_ids)[0]
    candidates = physical.visible_candidate_structures(_sel(record, seed)).candidates
    return candidates[0].source_observation_ids[0]


def _some_ambiguous_member(pdf):
    """A member observation that belongs to two or more candidates."""
    source, result, _ = _scope(pdf)
    physical = PhysicalOpeningAuthority(source.authority())
    record = result.record
    seed = sorted(record.visible_observation_ids)[0]
    counts = Counter()
    for candidate in physical.visible_candidate_structures(_sel(record, seed)).candidates:
        counts.update(candidate.source_observation_ids)
    return sorted(oid for oid, n in counts.items() if n > 1)[0]


def test_a_native_line_below_half_is_reported_as_an_anomaly_and_kept(monkeypatch, grouped):
    pdf = grouped["separate"]
    target = _some_ambiguous_member(pdf)
    source, result, reference = _scope(pdf)

    def tiny(observation_id, result_):
        if observation_id != target:
            return None
        return _replace_observation(result_, geometry=(10.0, 10.0, 10.2, 10.0))

    baseline = build_candidate_provenance_census(
        source_visibility_producer=source, semantic_result=result, reference_structure=reference
    ).to_dict()
    with monkeypatch.context() as patch:
        _forge_after_structures(patch, tiny)
        census = build_candidate_provenance_census(
            source_visibility_producer=source, semantic_result=result, reference_structure=reference
        ).to_dict()
    assert census["anomalies"]["counts"]["native_line_below_0_5"] == 1
    # nothing is filtered: every candidate is still counted and still complete
    for group in ("participating", "control"):
        assert (
            census["groups"][group]["candidates_total"]
            == baseline["groups"][group]["candidates_total"]
        )
        assert census["groups"][group]["provenance_incomplete"] == 0
    assert census["groups"]["participating"]["length"]["band_incidences"]["<0.5"] >= 1


# ----------------------------------------------------------------- fail closed
@pytest.mark.parametrize(
    "case, forge_kwargs, reason",
    [
        ("garbage_ref", {"source_primitive_ref": "visible:segment:d01i0"}, "ref_grammar_mismatch"),
        ("foreign_ref", {"source_primitive_ref": "rect:3"}, "ref_prefix_unrecognized"),
        (
            "raster_ref_on_native_kind",
            {"source_primitive_ref": f"visible:raster_segment:{SHA}:1.0.0:3"},
            "ref_kind_mismatch",
        ),
        (
            "native_ref_on_raster_kind",
            {"observation_kind": RASTER_PDF_VISIBLE_SEGMENT},
            "ref_kind_mismatch",
        ),
        ("other_document", {"document_id": "someone-else"}, "observation_lineage_mismatch"),
        ("other_revision", {"revision_id": "someone-else"}, "observation_lineage_mismatch"),
        ("other_source_sha", {"source_sha256": "f" * 64}, "observation_lineage_mismatch"),
        ("other_snapshot", {"snapshot_id": "someone-else"}, "observation_lineage_mismatch"),
        ("viewport_scoped", {"viewport_id": "vp-1"}, "observation_viewport_scoped"),
    ],
)
def test_unresolvable_or_unparseable_provenance_makes_the_candidate_incomplete(
    monkeypatch, grouped, case, forge_kwargs, reason
):
    pdf = grouped["separate"]
    target = _some_candidate_member(pdf)
    source, result, reference = _scope(pdf)

    def forge(observation_id, result_):
        return _replace_observation(result_, **forge_kwargs) if observation_id == target else None

    with monkeypatch.context() as patch:
        _forge_after_structures(patch, forge)
        census = build_candidate_provenance_census(
            source_visibility_producer=source, semantic_result=result, reference_structure=reference
        ).to_dict()
    incomplete = sum(g["provenance_incomplete"] for g in census["groups"].values())
    assert incomplete >= 1
    reasons = Counter()
    for group in census["groups"].values():
        reasons.update(group["incomplete_reasons"])
    assert reasons[reason] >= 1, (case, dict(reasons))
    for group in census["groups"].values():
        assert group["complete"] + group["provenance_incomplete"] == group["candidates_total"]
        assert sum(group["path_class"].values()) == group["complete"]
    checks = census["consistency"]["checks"]
    assert checks["no_failed_provenance_resolutions"] is False
    assert census["consistency"]["all_checks_passed"] is False
    # the totals still match the reference: the candidate is counted, not dropped
    assert checks["candidates_total_matches_structure_reference"] is True


def test_a_member_that_is_not_corroborated_is_incomplete_not_dropped(monkeypatch, grouped):
    pdf = grouped["separate"]
    target = _some_candidate_member(pdf)
    source, result, reference = _scope(pdf)

    def forge(observation_id, result_):
        if observation_id != target:
            return None
        return SourceObservationAuthorityResult(
            status=EvidenceResolutionStatus.CONFLICT,
            proposition=None,
            physical_opening_existence="physical_opening_existence_unresolved",
            reason_codes=("forced_conflict",),
        )

    with monkeypatch.context() as patch:
        _forge_after_structures(patch, forge)
        census = build_candidate_provenance_census(
            source_visibility_producer=source, semantic_result=result, reference_structure=reference
        ).to_dict()
    reasons = Counter()
    for group in census["groups"].values():
        reasons.update(group["incomplete_reasons"])
    assert reasons["observation_not_corroborated"] >= 1
    assert census["inventory"]["visible_ids_unresolved"] == 1
    assert census["consistency"]["checks"]["candidates_total_matches_structure_reference"] is True


def test_a_raster_member_is_recognised_as_pathless_not_as_unknown(monkeypatch, grouped):
    pdf = grouped["separate"]
    target = _some_ambiguous_member(pdf)
    source, result, reference = _scope(pdf)

    def forge(observation_id, result_):
        if observation_id != target:
            return None
        return _replace_observation(
            result_,
            source_primitive_ref=f"visible:raster_segment:{SHA}:1.0.0:5",
            observation_kind=RASTER_PDF_VISIBLE_SEGMENT,
        )

    with monkeypatch.context() as patch:
        _forge_after_structures(patch, forge)
        census = build_candidate_provenance_census(
            source_visibility_producer=source, semantic_result=result, reference_structure=reference
        ).to_dict()
    raster = sum(g["path_class"]["raster_involved"] for g in census["groups"].values())
    assert raster >= 1
    assert sum(g["provenance_incomplete"] for g in census["groups"].values()) == 0
    for group in census["groups"].values():
        assert sum(group["path_class"].values()) == group["complete"]
    assert census["inventory"]["by_ref_class"]["raster"] == 1
    assert census["ambiguous_observations"]["raster_involved"] >= 1


def test_unavailable_pages_are_explicit(monkeypatch, grouped):
    source, result, reference = _scope(grouped["separate"])

    def abstain(self, selector):
        return PhysicalOpeningCandidateStructureResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            page_id=None,
            candidates=(),
            reason_codes=("forced_unavailable",),
        )

    with monkeypatch.context() as patch:
        patch.setattr(PhysicalOpeningAuthority, "visible_candidate_structures", abstain)
        census = build_candidate_provenance_census(
            source_visibility_producer=source, semantic_result=result, reference_structure=reference
        ).to_dict()
    assert census["pages"]["enumerated"] == 0 and census["pages"]["unavailable"] == 1
    assert census["pages"]["unavailable_detail"][0]["reason_codes"] == ["forced_unavailable"]
    assert census["groups"]["participating"]["candidates_total"] == 0
    assert census["consistency"]["checks"]["no_unavailable_pages"] is False
    assert census["consistency"]["checks"]["candidates_total_matches_structure_reference"] is False
    assert census["consistency"]["all_checks_passed"] is False


def test_an_accessor_that_disagrees_with_the_disposition_is_reported(monkeypatch, grouped):
    source, result, reference = _scope(grouped["separate"])
    record = result.record
    clean = PhysicalOpeningAuthority(source.authority())
    seed = sorted(record.visible_observation_ids)[0]
    counts = Counter()
    for candidate in clean.visible_candidate_structures(_sel(record, seed)).candidates:
        counts.update(candidate.source_observation_ids)
    shared = sorted(oid for oid, n in counts.items() if n > 1)[0]
    original = PhysicalOpeningAuthority.visible_candidate_structures

    def dropped(self, selector):
        out = original(self, selector)
        kept = tuple(c for c in out.candidates if shared not in c.source_observation_ids)
        return dataclasses.replace(out, candidates=kept)

    with monkeypatch.context() as patch:
        patch.setattr(PhysicalOpeningAuthority, "visible_candidate_structures", dropped)
        census = build_candidate_provenance_census(
            source_visibility_producer=source, semantic_result=result, reference_structure=reference
        ).to_dict()
    assert census["ambiguous_observations"]["accessor_disposition_mismatch"] > 0
    assert census["consistency"]["checks"]["candidate_and_member_ids_agree_with_accessor"] is False
    assert census["consistency"]["all_checks_passed"] is False


def test_absent_semantic_record_is_reported_not_treated_as_clean(grouped):
    source, result, _ = _scope(grouped["separate"])
    absent = dataclasses.replace(result, record=None)
    census = build_candidate_provenance_census(
        source_visibility_producer=source, semantic_result=absent
    ).to_dict()
    assert census["status"] == "semantic_record_absent"
    assert census["consistency"]["all_checks_passed"] is None
    assert census["groups"]["participating"]["candidates_total"] == 0


def test_input_types_are_validated(grouped):
    source, result, reference = _scope(grouped["separate"])
    with pytest.raises(TypeError):
        build_candidate_provenance_census(source_visibility_producer=object(), semantic_result=result)
    with pytest.raises(TypeError):
        build_candidate_provenance_census(source_visibility_producer=source, semantic_result=object())
    with pytest.raises(TypeError):
        build_candidate_provenance_census(
            source_visibility_producer=source, semantic_result=result, reference_structure=object()
        )
    other_source, _other_result, _ = _scope(grouped["one_path"])
    with pytest.raises(ValueError, match="does not belong"):
        build_candidate_provenance_census(
            source_visibility_producer=other_source, semantic_result=result
        )


# ------------------------------------------- examples: deterministic, raw refs kept
def test_examples_are_deterministic_by_stable_id_and_keep_the_raw_refs(grouped):
    source, result, reference = _scope(grouped["separate"])
    authority = source.authority()
    census = build_candidate_provenance_census(
        source_visibility_producer=source, semantic_result=result, reference_structure=reference
    ).to_dict()
    for group, block in census["examples"]["candidates"].items():
        assert block["dominant_cells"]
        for cell, entries in block["by_cell"].items():
            assert 1 <= len(entries) <= 3
            ids = [entry["candidate_id"] for entry in entries]
            assert ids == sorted(ids)
            for entry in entries:
                assert f"{entry['path_class']}|" in cell
                for member in entry["members"]:
                    visible = authority.resolve_visible(_sel(result.record, member["observation_id"]))
                    # raw source_primitive_ref, verbatim
                    assert member["source_primitive_ref"] == visible.observation.source_primitive_ref
                    assert member["ref_class"] in {"native_line", "native_rect_edge"}
    obs = census["examples"]["ambiguous_observations"]
    assert obs["dominant_cells"]
    for entries in obs["by_cell"].values():
        assert [e["observation"]["observation_id"] for e in entries] == sorted(
            e["observation"]["observation_id"] for e in entries
        )


def test_dominant_cells_keep_ties(grouped):
    census = _census(grouped["separate"])
    cells = census["groups"]["participating"]["length"]["path_class_by_shortest_member_band"]
    top = max(cells.values())
    dominant = census["examples"]["candidates"]["participating"]["dominant_cells"]
    assert all(cells[name] >= min(cells[d] for d in dominant) for name in dominant)
    assert {name for name, value in cells.items() if value == top} <= set(dominant)


# --------------------------------------------------------------- determinism
def test_census_is_deterministic_with_a_recomputable_stable_id(grouped):
    source, result, reference = _scope(grouped["separate"])
    first = build_candidate_provenance_census(
        source_visibility_producer=source, semantic_result=result, reference_structure=reference
    )
    second = build_candidate_provenance_census(
        source_visibility_producer=source, semantic_result=result, reference_structure=reference
    )
    assert first == second and first.record_id == second.record_id
    assert first.to_dict()["schema_version"] == CENSUS_SCHEMA_VERSION
    assert first.to_dict()["commercial_authority_granted"] is False
    json.dumps(first.to_dict(), sort_keys=True)
    # The id is over the CONTENT: re-serialising the same content is the same census.
    assert CandidateProvenanceCensus(
        record_id=first.record_id, payload_json=json.dumps(json.loads(first.payload_json))
    ).to_dict() == first.to_dict()
    tampered = json.loads(first.payload_json)
    tampered["groups"]["control"]["candidates_total"] += 1
    with pytest.raises(ValueError, match="record_id does not match"):
        CandidateProvenanceCensus(record_id=first.record_id, payload_json=json.dumps(tampered))
    with pytest.raises(ValueError):
        CandidateProvenanceCensus(
            record_id=first.record_id, payload_json=first.payload_json, commercial_authority_granted=True
        )


def test_binding_names_the_exact_source_and_snapshot(grouped):
    source, result, reference = _scope(grouped["separate"])
    census = build_candidate_provenance_census(
        source_visibility_producer=source, semantic_result=result, reference_structure=reference
    ).to_dict()
    record = result.record
    binding = census["binding"]
    assert binding["semantic_record_id"] == record.record_id
    assert binding["source_sha256"] == record.source_sha256
    assert binding["snapshot_id"] == record.snapshot_id
    assert binding["revision_id"] == record.revision_id
    assert binding["document_id"] == record.document_id


# ------------------------------------------------------------ metamorphic checks
def _structure_only(census):
    """Path structure, independent of coordinates, lengths and draw-order numbering."""
    out = {}
    for group, block in census["groups"].items():
        out[group] = {
            key: block[key]
            for key in (
                "candidates_total",
                "path_class",
                "distinct_paths_per_candidate",
                "distinct_items_per_candidate",
                "members_per_path",
                "max_members_from_one_path",
            )
        }
    out["obs"] = {
        key: census["ambiguous_observations"][key]
        for key in ("assessed", "path_concentration", "own_path_visible_segment_count")
    }
    return out


def _transformed(groups, fn):
    return [[(fn(a), fn(b)) for a, b in group] for group in groups]


@pytest.mark.parametrize("transform", ["translate", "scale", "transpose"])
@pytest.mark.parametrize("name", ["separate", "faces_vs_jambs"])
def test_path_structure_is_invariant_under_exact_similarity_transforms(tmp_path, grouped, name, transform):
    fn = {
        "translate": lambda p: (p[0] + 30.0, p[1] + 40.0),
        "scale": lambda p: (p[0] * 2.0, p[1] * 2.0),
        "transpose": lambda p: (p[1], p[0]),
    }[transform]
    page = {"scale": {"width": 1400, "height": 1300}, "transpose": {"width": 650, "height": 700}}.get(
        transform, {}
    )
    moved = _grouped_pdf(tmp_path, f"{name}_{transform}", _transformed(_groupings()[name], fn), **page)
    assert _structure_only(_census(moved)) == _structure_only(_census(grouped[name]))
    if transform != "scale":  # lengths are preserved by translation and transposition
        assert (
            _census(moved)["groups"]["participating"]["length"]["band_incidences"]
            == _census(grouped[name])["groups"]["participating"]["length"]["band_incidences"]
        )


def test_path_structure_is_invariant_to_drawing_order(tmp_path, grouped):
    reordered = [list(reversed(group)) for group in reversed(_groupings()["separate"])]
    pdf = _grouped_pdf(tmp_path, "reordered", reordered)
    assert _structure_only(_census(pdf)) == _structure_only(_census(grouped["separate"]))
    pdf2 = _grouped_pdf(tmp_path, "reordered2", [list(reversed(g)) for g in _groupings()["one_path"]])
    assert _structure_only(_census(pdf2)) == _structure_only(_census(grouped["one_path"]))


def test_splitting_a_wall_segment_inside_its_path_keeps_the_path_structure(tmp_path, grouped):
    split_faces = []
    for first, second in ADJ_FACES:
        if first == (20, 100) and second == (100, 100):
            split_faces += [((20, 100), (60, 100)), ((60, 100), (100, 100))]
        else:
            split_faces.append((first, second))
    groups = [[s] for s in split_faces + ADJ_JAMBS + CTRL_FACES + CTRL_JAMBS]
    pdf = _grouped_pdf(tmp_path, "split", groups)
    split = _census(pdf)
    base = _census(grouped["separate"])
    assert split["groups"]["participating"]["path_class"] == base["groups"]["participating"]["path_class"]
    assert split["groups"]["participating"]["distinct_paths_per_candidate"] == {"6": 3}
    assert split["consistency"]["all_checks_passed"] is True


def test_unrelated_content_and_page_expansion_leave_existing_groups_unchanged(tmp_path, grouped):
    extra = [[((500, 500), (600, 540))], [((500, 560), (640, 580))], [((10, 400), (10, 440))]]
    more = _census(_grouped_pdf(tmp_path, "extra", _groupings()["separate"] + extra))
    base = _census(grouped["separate"])
    assert more["groups"] == base["groups"]
    assert more["by_page"] == base["by_page"]
    assert (
        more["inventory"]["visible_segments_on_enumerated_pages"]
        == base["inventory"]["visible_segments_on_enumerated_pages"] + 3
    )
    wide = _census(_grouped_pdf(tmp_path, "wide", _groupings()["separate"], width=2000, height=1500))
    assert wide["groups"] == base["groups"]


def test_page_scope_and_document_scope_agree_for_a_single_page(grouped):
    document = _census(grouped["separate"])
    page = _census(grouped["separate"], pages=[0])
    assert document["groups"] == page["groups"]
    assert document["by_page"] == page["by_page"]


# ---------------------------------------------------------- shadow-only / no effect
def test_the_census_changes_no_decision_and_no_shared_state(grouped):
    source, result, reference = _scope(grouped["separate"])
    record = result.record
    authority = source.authority()

    def decisions():
        fresh = PhysicalOpeningAuthority(authority)
        out = []
        for observation_id in sorted(record.visible_observation_ids):
            selector = _sel(record, observation_id)
            disposition = fresh.classify_disposition(selector)
            existence = fresh.prove_existence(selector)
            closure = fresh.assess_visible_candidate_closure(selector)
            out.append(
                (
                    disposition,
                    (existence.status, existence.reason_codes, existence.existence_record),
                    closure,
                )
            )
        return out

    published_before = source.published_snapshot_for_revision(record.revision_id)
    before = decisions()
    build_candidate_provenance_census(
        source_visibility_producer=source, semantic_result=result, reference_structure=reference
    )
    assert decisions() == before
    assert source.published_snapshot_for_revision(record.revision_id) == published_before
    assert result.record == record


def test_the_shadow_and_semantic_record_are_identical_with_and_without_the_census(grouped):
    pdf = grouped["separate"]
    before = collect_item35_authority_shadow(pdf, document_id=DOC)
    census = collect_candidate_provenance_census(pdf, document_id=DOC)
    after = collect_item35_authority_shadow(pdf, document_id=DOC)
    assert before == after
    assert census.to_dict()["binding"]["semantic_record_id"] == before["semantic_record_id"]


# ------------------------------------------------------------------ aggregation
def test_aggregation_sums_and_is_order_invariant(grouped):
    censuses = [collect_candidate_provenance_census(grouped[n], document_id=DOC) for n in ("separate", "one_path")]
    forward = aggregate_candidate_provenance_censuses(censuses)
    backward = aggregate_candidate_provenance_censuses(list(reversed(censuses)))
    assert forward == backward
    assert forward["scope_count"] == 2 and forward["scopes_without_semantic_record"] == 0
    assert forward["groups"]["participating"]["candidates_total"] == 6
    assert forward["groups"]["control"]["candidates_total"] == 2
    assert forward["groups"]["participating"]["distinct_paths_per_candidate"] == {"1": 3, "6": 3}
    assert forward["consistency"]["all_checks_passed"] is True
    assert "length_quantiles" not in forward["groups"]["participating"]["length"]
    assert forward["commercial_authority_granted"] is False


def test_aggregation_ands_the_checks_and_counts_absent_scopes(monkeypatch, grouped):
    good = collect_candidate_provenance_census(grouped["separate"], document_id=DOC)
    source, result, reference = _scope(grouped["one_path"])
    wrong = dataclasses.replace(reference, candidates_total=999)
    bad = build_candidate_provenance_census(
        source_visibility_producer=source, semantic_result=result, reference_structure=wrong
    )
    absent = build_candidate_provenance_census(
        source_visibility_producer=source, semantic_result=dataclasses.replace(result, record=None)
    )
    summary = aggregate_candidate_provenance_censuses([good, bad, absent])
    assert summary["scope_count"] == 3 and summary["scopes_without_semantic_record"] == 1
    assert summary["consistency"]["checks"]["candidates_total_matches_structure_reference"] is False
    assert summary["consistency"]["all_checks_passed"] is False
    empty = aggregate_candidate_provenance_censuses([])
    assert empty["scope_count"] == 0 and empty["consistency"]["all_checks_passed"] is None
    with pytest.raises(TypeError):
        aggregate_candidate_provenance_censuses([1])  # type: ignore[list-item]


# ------------------------------------------------- isolation / authority rules
def _pb_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return {name for name in found if name.startswith(("pb_", "scripts"))}


def test_module_only_uses_public_authority_seams():
    assert _pb_imports(REPO / f"{MODULE}.py") == {
        "pb_migration_contracts",
        "pb_physical_opening_authority",
        "pb_semantic_conflict_diagnostic",
        "pb_semantic_opening_enumeration_authority",
        "pb_source_observation_authority",
        "pb_source_visibility_authority",
    }
    assert _pb_imports(REPO / "scripts" / "candidate_provenance_census_report.py") == {MODULE}
    tree = ast.parse((REPO / f"{MODULE}.py").read_text(encoding="utf-8"))
    used = {"physical": set(), "visibility": set()}
    private = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id in used:
                used[node.value.id].add(node.attr)
            if node.attr.startswith("_") and not (
                isinstance(node.value, ast.Name) and node.value.id == "self"
            ):
                private.append(node.attr)
    assert used["physical"] == {"visible_candidate_structures", "classify_disposition"}
    assert used["visibility"] == {"resolve_visible"}
    assert private == []


def test_module_and_script_are_gold_free():
    visited, findings = walk_local_import_graph(MODULE)
    assert findings == () and not set(visited) & FORBIDDEN_MODULES
    for path in (REPO / f"{MODULE}.py", REPO / "scripts" / "candidate_provenance_census_report.py"):
        text = path.read_text(encoding="utf-8").lower()
        for fragment in FORBIDDEN_NAME_FRAGMENTS:
            assert fragment not in text, (path.name, fragment)
        assert "benchmarks/" not in text


def test_no_production_module_imports_the_census():
    offenders = []
    for path in sorted(REPO.rglob("*.py")):
        relative = path.relative_to(REPO)
        if relative.parts[0] in {"tests", "scripts", ".git"} or path.name == f"{MODULE}.py":
            continue
        if MODULE in path.read_text(encoding="utf-8", errors="ignore"):
            offenders.append(str(relative))
    assert offenders == []


def test_importing_the_live_extractor_does_not_load_the_census():
    code = (
        "import sys\n"
        "import pb_planreader_pdf_extractor, pb_item35_production_authority_shadow\n"
        f"sys.exit(1 if {MODULE!r} in sys.modules else 0)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO,
        env={**os.environ, "PYTHONPATH": str(REPO)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr[-2000:]


def test_the_census_never_rejects_filters_or_thresholds():
    """Descriptive only: no candidate/observation is dropped by a comparison against a
    length constant, and no 'reject'/'filter'/'threshold' decision exists in the module."""
    source = (REPO / f"{MODULE}.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            assert not re.search(r"reject|filter_|threshold|drop_", node.name), node.name


# ---------------------------------------------------------------- the script
def test_script_report_is_deterministic_and_carries_the_census(tmp_path, grouped):
    first = report_script.build_report([grouped["separate"]])
    second = report_script.build_report([grouped["separate"]])
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    (entry,) = first["entries"]
    assert entry["status"] == "ok" and entry["census"]["binding"]["source_sha256"]
    assert first["coverage"] == {
        "entries_total": 1,
        "entries_with_semantic_record": 1,
        "entries_without_semantic_record": 0,
        "entries_error": 0,
        "entries_source_unavailable": 0,
    }
    assert first["summary"]["groups"]["participating"]["candidates_total"] == 3
    assert entry["census"]["consistency"]["all_checks_passed"] is True


def test_script_document_id_is_content_derived_and_errors_are_reported(tmp_path, grouped):
    payload = grouped["separate"].read_bytes()
    assert report_script.document_id_for(payload).startswith("item35_funnel:")
    copy = tmp_path / "renamed.pdf"
    copy.write_bytes(payload)
    a = report_script.build_report([grouped["separate"]])
    b = report_script.build_report([copy])
    assert a["entries"][0]["census"]["binding"]["document_id"] == b["entries"][0]["census"]["binding"]["document_id"]
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"not a pdf")
    missing = tmp_path / "missing.pdf"
    report = report_script.build_report([bad, missing])
    statuses = sorted(entry["status"] for entry in report["entries"])
    assert statuses == ["error", "source_unavailable"]
    assert report["coverage"]["entries_error"] == 1 and report["coverage"]["entries_source_unavailable"] == 1


def test_script_cli(tmp_path, grouped, capsys):
    out = tmp_path / "out" / "report.json"
    assert report_script.main([str(grouped["separate"]), "--output", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["summary"]["scope_count"] == 1
    assert report_script.main([str(grouped["separate"]), "--pages", "0", "--no-reference"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["entries"][0]["census"]["consistency"]["checks"][
        "candidates_total_matches_structure_reference"
    ] is None
    assert report_script.main([str(tmp_path / "empty_dir_that_does_not_exist_xyz")]) == 1
