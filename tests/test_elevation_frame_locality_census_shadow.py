"""Locality census: pure core, the real producer on the authority's own synthetic elevations, and hygiene."""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from dataclasses import fields, replace
from pathlib import Path

import pytest

import pb_elevation_frame_locality_census_shadow as C
import pb_opening_elevation_frame_area_authority as authority_module
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer
from test_opening_elevation_frame_area_authority import _elevation_pdf

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "pb_elevation_frame_locality_census_shadow.py"
CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED
LAYOUT = C.layout_numbers(8.0, 16.0, 4.4)


def word(oid, text, x, y, w=20.0, h=8.0):
    return C.TrustedWordRef(oid, text, (x, y, x + w, y + h))


def dim_row(oid, text, value, x0, y0, x1, y1, unit="mm"):
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    return (oid, text, value, unit, (cx - 10.0, cy - 4.0, cx + 10.0, cy + 4.0), ((x0, y0), (x1, y1)))


def scene(x_line_y=80.0, y_line_x=110.0):
    """A frame 150 x 120 at (150,120); its width dimension line at x_line_y, its height dimension line at y_line_x."""
    words = [word("tag", "W1", 215.0, 180.0), word("w", "3000", 215.0, x_line_y - 4.0), word("h", "2400", y_line_x - 10.0, 176.0)]
    rows = [dim_row("dx", "3000", 3000.0, 150.0, x_line_y, 300.0, x_line_y), dim_row("dy", "2400", 2400.0, y_line_x, 120.0, y_line_x, 240.0)]
    return words, rows


# --- pure core -------------------------------------------------------------------------------------------


def test_layout_numbers_follow_the_authoritys_formula():
    layout = C.layout_numbers(10.0, 20.0, 5.5)
    assert layout.geometry_tolerance_pt == max(5.5 * 2.0, 10.0 * 0.75, 1.0)
    assert layout.locality_limit_pt == max(20.0 * 2.5, layout.geometry_tolerance_pt)
    assert layout.word_tolerance_pt == max(10.0 * 0.20, 0.75)
    assert C.layout_numbers(0.1, 0.1, 0.1).geometry_tolerance_pt == 1.0


def test_a_local_frame_has_both_dimension_lines_within_the_limit():
    words, rows = scene()
    dims, tags, pairs = C.measure_locality(trusted_words=words, dimension_rows=rows, layout=LAYOUT)
    assert [d.axis for d in dims] == ["x", "y"] and all(d.value_word_trusted for d in dims)
    assert len(tags) == 1 and tags[0].key == "W1" and tags[0].kind == "window"
    (pair,) = pairs
    assert pair.frame_bbox == (150.0, 120.0, 300.0, 240.0)
    assert pair.x_line_to_frame_edge_pt == 40.0 and pair.y_line_to_frame_edge_pt == 40.0
    assert not pair.x_line_exceeds_locality_limit and not pair.y_line_exceeds_locality_limit
    assert pair.physical_aspect == pytest.approx(1.25) and pair.geometric_aspect == pytest.approx(1.25)
    assert pair.aspect_relative_deviation == pytest.approx(0.0)


def test_a_remote_dimension_line_is_reported_with_its_distance_and_the_limit_not_decided():
    words, rows = scene(x_line_y=-200.0)
    _, _, pairs = C.measure_locality(trusted_words=words, dimension_rows=rows, layout=LAYOUT)
    (pair,) = pairs
    assert pair.x_line_to_frame_edge_pt == 320.0 and pair.x_line_exceeds_locality_limit
    assert not pair.y_line_exceeds_locality_limit


def test_every_bracketing_pair_is_kept_and_other_tags_inside_the_frame_are_named():
    words, rows = scene()
    words.append(word("door", "D1", 258.0, 180.0))
    rows.append(dim_row("dx2", "3000", 3000.0, 140.0, 60.0, 310.0, 60.0))
    words.append(word("w2", "3000", 215.0, 56.0))
    _, tags, pairs = C.measure_locality(trusted_words=words, dimension_rows=rows, layout=LAYOUT)
    w1 = next(t for t in tags if t.key == "W1")
    assert len(w1.x_dimensions_bracketing) == 2
    mine = [p for p in pairs if p.tag_observation_id == "tag"]
    assert len(mine) == 2 and all(p.other_tag_keys_inside_frame == ("D1",) for p in mine)


def test_dimension_values_need_a_unique_trusted_word_and_a_usable_unit():
    words, rows = scene()
    words.append(word("dup", "3000", 215.0, 76.0))                      # a second word with the same text at the same place
    dims, _, _ = C.measure_locality(trusted_words=words, dimension_rows=rows, layout=LAYOUT)
    assert {d.observation_id: d.value_word_trusted for d in dims} == {"dx": False, "dy": True}
    rows[1] = dim_row("dy", "2400", 2400.0, 110.0, 120.0, 110.0, 240.0, unit="ft")
    dims, _, _ = C.measure_locality(trusted_words=scene()[0], dimension_rows=rows, layout=LAYOUT)
    assert next(d for d in dims if d.observation_id == "dy").millimetres is None


def test_oblique_dimension_lines_are_not_measured_and_input_order_does_not_matter():
    words, rows = scene()
    rows.append(dim_row("diag", "999", 999.0, 0.0, 0.0, 50.0, 40.0))
    a = C.measure_locality(trusted_words=words, dimension_rows=rows, layout=LAYOUT)
    b = C.measure_locality(trusted_words=list(reversed(words)), dimension_rows=list(reversed(rows)), layout=LAYOUT)
    assert a == b and all(d.observation_id != "diag" for d in a[0])


def test_translation_does_not_change_the_measured_distances():
    words, rows = scene()
    moved_words = [C.TrustedWordRef(w.observation_id, w.text, (w.bbox[0] + 500.0, w.bbox[1] - 77.0, w.bbox[2] + 500.0, w.bbox[3] - 77.0)) for w in words]
    moved_rows = [(o, t, v, u, (b[0] + 500.0, b[1] - 77.0, b[2] + 500.0, b[3] - 77.0),
                   ((e[0][0] + 500.0, e[0][1] - 77.0), (e[1][0] + 500.0, e[1][1] - 77.0))) for o, t, v, u, b, e in rows]
    _, _, base = C.measure_locality(trusted_words=words, dimension_rows=rows, layout=LAYOUT)
    _, _, moved = C.measure_locality(trusted_words=moved_words, dimension_rows=moved_rows, layout=LAYOUT)
    assert [(p.x_line_to_frame_edge_pt, p.y_line_to_frame_edge_pt) for p in base] == [
        (p.x_line_to_frame_edge_pt, p.y_line_to_frame_edge_pt) for p in moved]


def test_every_grant_is_false_and_enforced():
    census = C.ElevationFrameLocalityCensusShadow._empty("x")
    for flag in C._GRANT_FLAGS:
        assert getattr(census, flag) is False
        with pytest.raises(ValueError, match="cannot grant"):
            replace(census, **{flag: True})
    with pytest.raises(ValueError):
        replace(census, status=EvidenceResolutionStatus.CORROBORATED)
    assert not ({"frame_bbox_record", "area_m2", "axis_x_mm", "axis_y_mm", "record"} & {f.name for f in fields(C.ElevationLocalityCensus)})


def test_the_mirrored_unit_range_matches_the_authoritys_own_constants():
    assert C._MIN_FRAME_DIMENSION_MM == authority_module._MIN_FRAME_DIMENSION_MM
    assert C._MAX_FRAME_DIMENSION_MM == authority_module._MAX_FRAME_DIMENSION_MM
    for text in ("W 1 ", "1000", "x"):
        assert C._claim_norm(text) == authority_module._claim_norm(text)


# --- through the real producer and the authority's own synthetic elevation ----------------------------------


def _source(payload):
    source = SourceVisibilityProducer(producer_method="locality-census-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(document_id="locality-census", source_bytes=payload,
                                               source_locator="memory://locality-census.pdf")
    return source, published


def _run(payload, **kw):
    source, published = _source(payload)
    return source, published, C.ElevationFrameLocalityCensusShadow(source, enabled=True).census(
        revision_id=published.revision.revision_id, page_id=1, **kw)


def test_disabled_by_default_and_strictly_boolean():
    source, published = _source(_elevation_pdf())
    off = C.ElevationFrameLocalityCensusShadow(source).census(revision_id=published.revision.revision_id, page_id=1)
    assert off.status is ABST and off.reason_codes == (C.CENSUS_DISABLED,) and off.ownership is None
    for bad in (1, None, "true"):
        with pytest.raises(ValueError):
            C.ElevationFrameLocalityCensusShadow(source, enabled=bad)
    with pytest.raises(TypeError):
        C.ElevationFrameLocalityCensusShadow(object(), enabled=True)


def test_the_authoritys_resolvable_frame_measures_local_and_the_far_chain_measures_remote():
    _, _, near = _run(_elevation_pdf(), include_authority_verdicts=True)
    assert near.status is CAND and near.reason_codes == (C.CENSUS_PRODUCED,)
    pair = next(p for p in near.pairs if next(t for t in near.tags if t.observation_id == p.tag_observation_id).key == "W1")
    assert not pair.x_line_exceeds_locality_limit and not pair.y_line_exceeds_locality_limit
    assert [(v.key, v.status) for v in near.authority_verdicts] == [("W1", "corroborated")]
    _, _, far = _run(_elevation_pdf(far_width_dimension=True), include_authority_verdicts=True)
    far_pair = next(p for p in far.pairs if next(t for t in far.tags if t.observation_id == p.tag_observation_id).key == "W1")
    assert far_pair.x_line_exceeds_locality_limit
    assert far_pair.x_line_to_frame_edge_pt > near.layout.locality_limit_pt
    assert [(v.key, v.status) for v in far.authority_verdicts] == [("W1", "abstained")]       # the authority's own answer


def test_the_composite_assembly_reports_the_other_tag_inside_the_frame():
    _, _, census = _run(_elevation_pdf(composite=True))
    assert any("D1" in p.other_tag_keys_inside_frame for p in census.pairs)


def test_replay_is_deterministic_and_changes_no_producer_state():
    source, published = _source(_elevation_pdf())
    shadow = C.ElevationFrameLocalityCensusShadow(source, enabled=True)

    def shape(obj):
        return {k: len(v) for k, v in sorted(vars(obj).items()) if isinstance(v, (dict, set, list, tuple))}

    before = shape(source)
    first = shadow.census(revision_id=published.revision.revision_id, page_id=1)
    second = shadow.census(revision_id=published.revision.revision_id, page_id=1)
    assert first == second and first.record_id == second.record_id
    assert shape(source) == before


def test_foreign_or_stale_inputs_abstain():
    source, published = _source(_elevation_pdf())
    shadow = C.ElevationFrameLocalityCensusShadow(source, enabled=True)
    assert shadow.census(revision_id="nope", page_id=1).reason_codes == (C.SOURCE_UNPROVEN,)
    assert shadow.census(revision_id=published.revision.revision_id, page_id=9).reason_codes == (C.SOURCE_UNPROVEN,)
    with pytest.raises(ValueError):
        shadow.census(revision_id=published.revision.revision_id, page_id="1")


# --- hygiene --------------------------------------------------------------------------------------------------


def _imports(path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def test_nothing_imports_the_census_and_it_imports_no_consumer():
    importers = [p.relative_to(REPO).as_posix() for root in ("", "tools", "scripts") for p in sorted((REPO / root).glob("*.py"))
                 if p != SOURCE and re.search(r"^\s*(?:from|import)\s+pb_elevation_frame_locality_census_shadow\b",
                                              p.read_text(encoding="utf-8", errors="replace"), re.M)]
    assert importers == []
    forbidden = ("pb_schedule_opening_instance_binding_authority", "pb_opening_host_binding_authority",
                 "pb_live_", "pb_generic_opening_count_authority", "pb_wall_room_topology_canonical_adapter",
                 "pb_physical_opening_authority")
    assert [m for m in _imports(SOURCE) if m.startswith(forbidden)] == []
    text = SOURCE.read_text(encoding="utf-8")
    assert "OpeningElevationFrameAreaRecord(" not in text and ".rect" not in text
    for needle in ("frozen_holdout", "reference_takeoff", "benchmarks", "Maryborough", "documents/sources", "expected_"):
        assert needle not in text
    assert not re.search(r"\b[0-9a-f]{64}\b", text) and not re.search(r"""["'][WD]0?\d{1,2}["']""", text)


def test_importing_the_census_loads_no_consumer_module():
    code = ("import sys; sys.path[:0] = [%r]; import pb_elevation_frame_locality_census_shadow; "
            "print(sorted(m for m in sys.modules if m.startswith(('pb_schedule_opening_instance_binding_authority',"
            "'pb_opening_host_binding_authority','pb_live_','pb_generic_opening_count_authority'))))") % str(REPO)
    done = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().splitlines()[-1] == "[]"
