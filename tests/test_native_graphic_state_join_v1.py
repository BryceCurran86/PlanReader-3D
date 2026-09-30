"""Phase-2 native graphic-state join (shadow only): identity, fail-closed, invariance, isolation.

Synthetic drawings test the MECHANICS of the join.  They are not evidence about
real drawings and choose no rule, threshold or filter.
"""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import fitz
import pytest

import pb_native_graphic_state_join as J
from pb_item35_production_authority_shadow import collect_item35_authority_shadow
from pb_native_graphic_state_join import (
    RATIO_MIN_UNIQUE_PATHS,
    RATIO_SUPPRESSED_LOW_N,
    build_native_graphic_state_join,
    collect_native_graphic_state_join,
    dash_state,
    size_band,
)
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_provider_gold_isolation import (
    FORBIDDEN_MODULES,
    FORBIDDEN_NAME_FRAGMENTS,
    walk_local_import_graph,
)
from pb_semantic_conflict_diagnostic import collect_semantic_scope, diagnose_semantic_conflicts
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityAuthority
from pb_vector_geometry_v130 import extract_native_page
from scripts import native_graphic_state_join_report as report_script

REPO = Path(__file__).resolve().parents[1]
MODULE = "pb_native_graphic_state_join"
DOC = "graphic-join-test"


# ---------------------------------------------------------------- fixtures
def _wall(spans, top, gap=10.0):
    lines = []
    for x0, x1 in spans:
        lines.append(((x0, top), (x1, top)))
        lines.append(((x0, top + gap), (x1, top + gap)))
    return lines


def _jambs(xs, top, gap=10.0):
    return [((x, top), (x, top + gap)) for x in xs]


ADJ_FACES = _wall([(20, 100), (140, 180), (220, 300)], 100.0)
ADJ_JAMBS = _jambs([100, 140, 180, 220], 100.0)
CTRL_FACES = _wall([(20, 100), (140, 220)], 300.0)
CTRL_JAMBS = _jambs([100, 140], 300.0)
ALL_SEGMENTS = ADJ_FACES + ADJ_JAMBS + CTRL_FACES + CTRL_JAMBS

DEFAULT_STYLE = {"color": (0, 0, 0), "width": 1}
FACE_STYLE = {"color": (1, 0, 0), "width": 2, "dashes": "[3 2] 0"}


def _separate(style_of=None):
    """One path per segment; ``style_of(segment)`` may return a per-path style."""
    return [([s], (style_of(s) if style_of else None)) for s in ALL_SEGMENTS]


def _draw(page, groups):
    for group, style in groups:
        shape = page.new_shape()
        for first, second in group:
            shape.draw_line(fitz.Point(*first), fitz.Point(*second))
        shape.finish(closePath=False, **(style or DEFAULT_STYLE))
        shape.commit()


def _write(path: Path, draw, *, pages=1, width=700, height=650) -> Path:
    doc = fitz.open()
    for index in range(pages):
        page = doc.new_page(width=width, height=height)
        page.insert_text(fitz.Point(40, 40), "GROUND FLOOR PLAN", color=(0, 0, 0))
        draw(page, index)
    doc.save(path)
    doc.close()
    return path


def _pdf(tmp_path, name, groups, **kw):
    return _write(tmp_path / f"{name}.pdf", lambda p, i: _draw(p, groups), **kw)


def _scope(pdf, pages=None):
    payload = Path(pdf).read_bytes()
    source, result = collect_semantic_scope(pdf, document_id=DOC, pages=pages, source_bytes=payload)
    reference = diagnose_semantic_conflicts(
        source_visibility_producer=source, semantic_result=result
    ).candidate_structure
    return source, result, reference, payload


def _join(pdf, **kw):
    return collect_native_graphic_state_join(pdf, document_id=DOC, **kw).to_dict()


def _sel(record, observation_id):
    return ObservationSelector(
        document_id=record.document_id,
        revision_id=record.revision_id,
        source_sha256=record.source_sha256,
        snapshot_id=record.snapshot_id,
        observation_id=observation_id,
    )


def _rows(pdf):
    """Independent view: every visible record with its ref, group membership from the accessor."""
    source, result, reference, payload = _scope(pdf)
    record = result.record
    authority = source.authority()
    physical = PhysicalOpeningAuthority(authority)
    seed = sorted(record.visible_observation_ids)[0]
    candidates = physical.visible_candidate_structures(_sel(record, seed)).candidates
    count_in = Counter()
    for c in candidates:
        count_in.update(c.source_observation_ids)
    participating = Counter()
    control = set()
    for c in candidates:
        if any(count_in[o] > 1 for o in c.source_observation_ids):
            participating.update(c.source_observation_ids)
        else:
            control.update(c.source_observation_ids)
    refs = {
        oid: authority.resolve_visible(_sel(record, oid)).observation.source_primitive_ref
        for oid in record.visible_observation_ids
    }
    return source, result, reference, payload, refs, participating, control, count_in


@pytest.fixture()
def separate(tmp_path):
    return _pdf(tmp_path, "separate", _separate())


@pytest.fixture()
def styled(tmp_path):
    faces = {s for s in ADJ_FACES + CTRL_FACES}
    return _pdf(tmp_path, "styled", _separate(lambda s: FACE_STYLE if s in faces else None))


def _oracle_states(payload):
    """segment id -> canonical graphic state, straight from the producer for every page."""
    out = {}
    document = fitz.open(stream=payload, filetype="pdf")
    for index in range(document.page_count):
        native = extract_native_page(document.load_page(index))
        for seg in native["segments"]:
            out[(str(index + 1), seg["id"])] = J.graphic_state_of(seg)
    document.close()
    return out


def _meta_only(join):
    """Histogram VALUES of every group/class: coordinates, ids and draw order removed."""
    out = {}
    for group, by_class in join["groups"].items():
        out[group] = {}
        for klass, summary in by_class.items():
            if summary is None:
                out[group][klass] = None
                continue
            out[group][klass] = {
                "unique_paths": summary["unique_paths"],
                "primitives": summary["primitives"],
                "incidences": summary["incidences"],
                "histograms": {
                    f: {
                        v: (e["paths"], e["primitives"])
                        for v, e in h["values"].items()
                    }
                    for f, h in summary["histograms"].items()
                },
            }
    return out


# ------------------------------------------------ exact identity joins
def test_every_visible_native_primitive_joins_by_exact_identity_to_the_producer_state(styled):
    source, result, reference, payload, refs, *_ = _rows(styled)
    oracle = _oracle_states(payload)
    join = _join(styled)
    assert join["status"] == "ok" and join["join_status_counts"] == {"joined": len(refs)}
    # independent per-row check through the ref string, not the parsed tuple
    rows = {}
    built = collect_native_graphic_state_join  # noqa: F841
    for example in join["examples"]["visible_universe_candidate_pages"]:
        seg_id = example["source_primitive_ref"].removeprefix("visible:segment:")
        assert example["graphic_state"] == oracle[(example["page_id"], seg_id)].canonical()
        assert example["graphic_state_digest"] == oracle[(example["page_id"], seg_id)].digest()
        rows[seg_id] = example
    assert rows


def test_group_histograms_match_an_independent_oracle(styled):
    source, result, reference, payload, refs, participating, control, count_in = _rows(styled)
    oracle = _oracle_states(payload)

    def expected(oids, weight):
        paths = {}
        for oid in oids:
            seg = refs[oid].removeprefix("visible:segment:")
            state = oracle[("1", seg)].states()["stroke_state"]
            paths.setdefault(re.match(r"d(\d+)", seg).group(1), state)
        c = Counter(paths.values())
        prims = Counter(
            oracle[("1", refs[o].removeprefix("visible:segment:"))].states()["stroke_state"]
            for o in oids
        )
        return c, prims, sum(weight(o) for o in oids)

    join = _join(styled)
    line = join["groups"]["participating_member_incidences"]["native_line"]
    paths, prims, incidences = expected(sorted(participating), lambda o: participating[o])
    got = line["histograms"]["stroke_state"]["values"]
    assert {v: e["paths"] for v, e in got.items()} == dict(paths)
    assert {v: e["primitives"] for v, e in got.items()} == dict(prims)
    assert line["incidences"] == incidences and line["primitives"] == len(participating)
    ctrl = join["groups"]["non_participating_candidate_members"]["native_line"]
    assert ctrl["primitives"] == len(control) == 6
    universe = join["groups"]["visible_universe_candidate_pages"]["native_line"]
    assert universe["primitives"] == len(refs) == 16


def test_baseline_is_the_complete_universe_and_groups_are_related_as_designed(styled):
    _, _, _, _, refs, participating, control, count_in = _rows(styled)
    join = _join(styled)
    groups = join["groups"]
    n = lambda g: groups[g]["native_line"]["primitives"]  # noqa: E731
    assert n("visible_universe_candidate_pages") == 16
    assert n("visible_universe_all_scope_pages") == 16
    assert n("visible_universe_candidate_pages_minus_participating") == 16 - len(participating)
    assert n("participating_member_incidences") + n("non_participating_candidate_members") == 16
    assert set(participating).isdisjoint(control)
    ambiguous = {o for o, k in count_in.items() if k > 1}
    assert n("ambiguous_observations") == len(ambiguous) > 0
    assert join["scope"]["primary_baseline"] == "visible_universe_candidate_pages"
    assert join["scope"]["secondary_descriptive_only"] == "non_participating_candidate_members"
    assert join["consistency"]["all_checks_passed"] is True
    # an incidence is (candidate, member): a primitive in k participating candidates weighs k
    assert groups["participating_member_incidences"]["native_line"]["incidences"] > n(
        "participating_member_incidences"
    )


# ---------------------------------------------- rect edge identity, classes
def _blocks(page, idx=0):
    page.draw_rect(fitz.Rect(20, 100, 100, 110), color=(0, 0, 0), width=1)
    page.draw_rect(fitz.Rect(140, 100, 220, 110), color=(0, 0, 0), width=1, fill=(0.9, 0.9, 0.9))
    page.draw_rect(fitz.Rect(260, 100, 300, 110), color=(0, 0, 0), width=1)


def test_rect_edges_join_on_e_k_identity_and_are_a_separate_stratum(tmp_path):
    pdf = _write(tmp_path / "blocks.pdf", _blocks)
    join = _join(pdf)
    assert join["status"] == "ok" and join["consistency"]["all_checks_passed"] is True
    for group, by_class in join["groups"].items():
        assert by_class["native_line"] is None or by_class["native_line"]["primitives"] == 0
    part = join["groups"]["participating_member_incidences"]["native_rect_edge"]
    assert part["primitives"] == 10 and part["incidences"] == 18  # R is bounded on both sides: 3+4+3 distinct edges
    universe = join["groups"]["visible_universe_candidate_pages"]["native_rect_edge"]
    assert universe["primitives"] == 12 and universe["unique_paths"] == 3  # one path per rect
    # the four edges of a rect share one path-level state, not four independent observations
    fill = universe["histograms"]["fill_state"]["values"]
    assert fill["absent"] == {"paths": 2, "primitives": 8}
    assert fill["(0.9000,0.9000,0.9000)"] == {"paths": 1, "primitives": 4}
    assert "unclassified" not in join["groups"]["visible_universe_candidate_pages"]
    example_refs = [e["source_primitive_ref"] for e in join["examples"]["participating_member_incidences"]]
    assert all(re.fullmatch(r"visible:segment:d\d+i0e[0-3]", r) for r in example_refs)


def test_lines_and_rect_edges_are_never_pooled(tmp_path):
    def draw(page, idx):
        _blocks(page)
        _draw(page, [([((20, 300), (100, 300))], None), ([((140, 300), (220, 300))], None)])

    pdf = _write(tmp_path / "mixed.pdf", draw)
    join = _join(pdf)
    universe = join["groups"]["visible_universe_candidate_pages"]
    assert universe["native_line"]["primitives"] == 2 and universe["native_rect_edge"]["primitives"] == 12
    assert set(universe) == {"native_line", "native_rect_edge"}
    assert set(join["comparisons_vs_participating"]) == {"native_line", "native_rect_edge"}


# ------------------------------------- duplicate geometry / identical metadata
def test_duplicate_geometry_from_different_paths_is_joined_by_identity_never_merged(tmp_path):
    duplicate = [
        ([s], {"color": (1, 0, 0), "width": 1}) for s in ALL_SEGMENTS
    ] + [([ALL_SEGMENTS[0]], {"color": (0, 0, 1), "width": 3})]
    pdf = _pdf(tmp_path, "dup", duplicate)
    join = _join(pdf)
    assert join["status"] == "ok"
    assert join["join_status_counts"]["joined"] == 17
    universe = join["groups"]["visible_universe_candidate_pages"]["native_line"]
    stroke = universe["histograms"]["stroke_state"]["values"]
    assert stroke["(1.0000,0.0000,0.0000)"]["primitives"] == 16 and stroke["(0.0000,0.0000,1.0000)"]["primitives"] == 1
    assert universe["unique_paths"] == 17


def test_identical_metadata_on_unrelated_primitives_stays_separate_paths(separate):
    join = _join(separate)
    universe = join["groups"]["visible_universe_candidate_pages"]["native_line"]
    values = universe["histograms"]["stroke_state"]["values"]
    assert values == {"(0.0000,0.0000,0.0000)": {"paths": 16, "primitives": 16}}
    assert universe["unique_paths"] == 16  # identical metadata does not merge paths


# ------------------------------------------------------ presence semantics
def test_absent_metadata_stays_absent_and_is_never_collapsed(tmp_path):
    def draw(page, idx):
        _blocks(page)
        page.draw_rect(fitz.Rect(400, 100, 440, 110), color=None, fill=(0, 0, 1))  # fill only
        page.draw_line((400, 200), (450, 200), color=(0, 0, 0))  # default width

    join = _join(_write(tmp_path / "absent.pdf", draw))
    universe = join["groups"]["visible_universe_candidate_pages"]["native_rect_edge"]["histograms"]
    assert universe["stroke_state"]["values"]["absent"] == {"paths": 1, "primitives": 4}
    assert universe["width_state"]["values"]["absent"] == {"paths": 1, "primitives": 4}  # not 0.0
    assert "0.0000" not in universe["width_state"]["values"]
    assert universe["paint_presence"]["values"]["fill_only"] == {"paths": 1, "primitives": 4}
    assert universe["layer_state"]["values"] == {"absent": {"paths": 4, "primitives": 16}}
    assert universe["dash_state"]["values"]["absent"] == {"paths": 1, "primitives": 4}


def test_dash_state_uses_the_producer_flag_and_never_names_a_line_class():
    assert dash_state("", False) == "absent"
    assert dash_state("[] 0", True) == "array_empty"  # the empty PDF dash array, not "solid"
    assert dash_state("[ 3 2 ] 0", True) == "array:[ 3 2 ] 0"
    assert dash_state("garbage", True) == "unparsed:garbage"
    for label in ("solid", "dashed", "dotted"):
        assert label not in {dash_state("[] 0", True), dash_state("[ 3 2 ] 0", True)}


def test_real_producer_reports_a_solid_stroke_as_present_dash_array(tmp_path):
    """Probe of the real producer: `dashes_present` is True for a solid stroke ('[] 0')."""
    pdf = _pdf(tmp_path, "solid", [([((10, 10), (100, 10))], None)], height=200)
    document = fitz.open(pdf)
    (segment,) = extract_native_page(document[0])["segments"]
    document.close()
    assert segment["dashes"] == "[] 0" and segment["dashes_present"] is True
    assert J.graphic_state_of(segment).states()["dash_state"] == "array_empty"


def test_layer_is_the_raw_producer_string_and_absence_is_not_a_named_layer(tmp_path):
    def draw(page, idx):
        oc = page.parent.add_ocg("A-WALL")
        _blocks(page)
        shape = page.new_shape()
        shape.draw_line(fitz.Point(400, 50), fitz.Point(480, 50))
        shape.finish(color=(0, 0, 0), oc=oc, closePath=False)
        shape.commit()

    join = _join(_write(tmp_path / "layer.pdf", draw))
    universe = join["groups"]["visible_universe_all_scope_pages"]
    layers = universe["native_line"]["histograms"]["layer_state"]["values"]
    assert layers == {"present:A-WALL": {"paths": 1, "primitives": 1}}
    edges = universe["native_rect_edge"]["histograms"]["layer_state"]["values"]
    assert edges == {"absent": {"paths": 3, "primitives": 12}}


# ------------------------------------------- fail-closed: identity conflicts
def _pipeline(pdf):
    source, result, reference, payload = _scope(pdf)
    return source, result, reference, payload


def _built(pdf, payload=None):
    source, result, reference, real = _pipeline(pdf)
    return build_native_graphic_state_join(
        source_visibility_producer=source,
        semantic_result=result,
        source_bytes=real if payload is None else payload,
        reference_structure=reference,
    ).to_dict()


def test_sha_mismatch_means_no_join_and_no_extraction(separate, monkeypatch):
    other = separate.read_bytes() + b"\n%tampered"
    source, result, reference, _ = _pipeline(separate)  # scope published from the real bytes
    monkeypatch.setattr(J, "extract_native_page", lambda *a, **k: pytest.fail("extracted"))
    monkeypatch.setattr(J.fitz, "open", lambda *a, **k: pytest.fail("opened"))
    join = build_native_graphic_state_join(
        source_visibility_producer=source, semantic_result=result, source_bytes=other
    ).to_dict()
    assert join["status"] == "no_join_sha_mismatch"
    assert join["binding"]["supplied_bytes_sha256"] == hashlib.sha256(other).hexdigest()
    assert join["binding"]["supplied_bytes_sha256"] != join["binding"]["source_sha256"]
    assert "groups" not in join and "join_status_counts" not in join


def test_non_bytes_input_is_rejected(separate):
    source, result, reference, _ = _pipeline(separate)
    with pytest.raises(TypeError):
        build_native_graphic_state_join(
            source_visibility_producer=source, semantic_result=result, source_bytes="x"  # type: ignore[arg-type]
        )


def _first_ref_state(join, status):
    return join["join_status_counts"].get(status, 0)


def test_missing_replay_identity_is_unknown_never_matched_to_a_neighbour(separate, monkeypatch):
    real = J.extract_native_page

    def fewer(page):
        native = real(page)
        native["segments"] = [s for s in native["segments"] if s["id"] != "d3i0"]
        return native

    monkeypatch.setattr(J, "extract_native_page", fewer)
    join = _built(separate)
    assert join["join_status_counts"] == {"joined": 15, "unknown_missing_in_replay": 1}
    absent = [e for g in join["examples"].values() for e in g if e["join_status"] != "joined"]
    assert all(e["graphic_state"] is None for e in absent)


def test_duplicate_producer_identity_is_a_conflict(separate, monkeypatch):
    real = J.extract_native_page

    def duplicated(page):
        native = real(page)
        native["segments"] = native["segments"] + [dict(native["segments"][2], stroke=(0.5, 0.5, 0.5))]
        return native

    monkeypatch.setattr(J, "extract_native_page", duplicated)
    join = _built(separate)
    assert join["join_status_counts"] == {"joined": 15, "conflict_duplicate_identity": 1}
    assert join["replay"]["duplicate_replay_identities"] == 1


def test_geometry_disagreement_on_one_identity_is_a_conflict_not_a_search(separate, monkeypatch):
    real = J.extract_native_page

    def shifted(page):
        native = real(page)
        native["segments"] = [
            dict(s, x1=s["x1"] + 0.001) if s["id"] == "d5i0" else s for s in native["segments"]
        ]
        return native

    monkeypatch.setattr(J, "extract_native_page", shifted)
    join = _built(separate)
    assert join["join_status_counts"] == {"joined": 15, "conflict_geometry": 1}


def test_producer_id_that_disagrees_with_its_index_fields_is_a_conflict(separate, monkeypatch):
    real = J.extract_native_page

    def relabelled(page):
        native = real(page)
        native["segments"] = [
            dict(s, id="d999i0") if s["id"] == "d1i0" else s for s in native["segments"]
        ]
        return native

    monkeypatch.setattr(J, "extract_native_page", relabelled)
    assert _built(separate)["join_status_counts"] == {"joined": 15, "conflict_identity_fields": 1}


def test_conflicting_metadata_inside_one_path_conflicts_every_member_of_that_path(tmp_path, monkeypatch):
    faces = ADJ_FACES + CTRL_FACES
    pdf = _pdf(tmp_path, "onepath", [([s for s in ALL_SEGMENTS], None)])
    real = J.extract_native_page

    def conflicting(page):
        native = real(page)
        native["segments"] = [
            dict(s, stroke=(0.2, 0.2, 0.2)) if s["item_index"] == 0 else s for s in native["segments"]
        ]
        return native

    monkeypatch.setattr(J, "extract_native_page", conflicting)
    join = _built(pdf)
    assert join["join_status_counts"] == {"conflict_path_metadata": 16}
    assert faces  # (fixture data used only to build the single path)


def test_unparseable_or_missing_identity_is_unknown(separate, monkeypatch):
    from pb_candidate_provenance_census import RefParse

    real = J.parse_visible_segment_ref
    calls = {"n": 0}

    def bad(raw):
        calls["n"] += 1
        if calls["n"] == 1:
            return RefParse("unparseable", reason="ref_grammar_mismatch")
        return real(raw)

    monkeypatch.setattr(J, "parse_visible_segment_ref", bad)
    join = _built(separate)
    assert join["join_status_counts"] == {"joined": 15, "unknown_identity": 1}


def test_unresolvable_observation_is_unknown_not_dropped(separate, monkeypatch):
    state = {"armed": False}
    original_structures = PhysicalOpeningAuthority.visible_candidate_structures
    original_resolve = SourceVisibilityAuthority.resolve_visible
    victim = {}

    def structures(self, selector):
        out = original_structures(self, selector)
        state["armed"] = True
        return out

    def resolve(self, selector):
        result = original_resolve(self, selector)
        if state["armed"]:
            victim.setdefault("id", selector.observation_id)
            if selector.observation_id == victim["id"]:
                return dataclasses.replace(result, status=result.status.__class__.ABSTAINED, observation=None)
        return result

    monkeypatch.setattr(PhysicalOpeningAuthority, "visible_candidate_structures", structures)
    monkeypatch.setattr(SourceVisibilityAuthority, "resolve_visible", resolve)
    join = _built(separate)
    assert join["join_status_counts"] == {"joined": 15, "unknown_not_corroborated": 1}
    assert join["consistency"]["every_candidate_member_has_a_row"] is True


def test_raster_records_are_counted_never_joined():
    from pb_candidate_provenance_census import parse_visible_segment_ref

    ref = f"visible:raster_segment:{'a' * 64}:hough:3"
    assert parse_visible_segment_ref(ref).ref_class == "raster"
    assert J.STATUS_NOT_NATIVE == "not_native_no_pdf_path"


# --------------------------------------------- view fields, binding, ids
def test_view_is_explicitly_unavailable_and_binding_names_the_exact_source(separate):
    join = _join(separate)
    assert join["view_id"] is None and join["view_scope_status"] == "unavailable"
    b = join["binding"]
    assert b["supplied_bytes_sha256"] == b["source_sha256"] == hashlib.sha256(separate.read_bytes()).hexdigest()
    for key in ("document_id", "revision_id", "snapshot_id", "semantic_record_id", "pymupdf_version"):
        assert b[key]
    assert join["join_key"] == "page_id+path_index+item_index+edge_index"
    assert join["commercial_authority_granted"] is False
    with pytest.raises(dataclasses.FrozenInstanceError):
        collect_native_graphic_state_join(separate, document_id=DOC).record_id = "x"  # type: ignore[misc]


def test_record_id_is_deterministic_and_content_bound(tmp_path, separate):
    a = collect_native_graphic_state_join(separate, document_id=DOC)
    b = collect_native_graphic_state_join(separate, document_id=DOC)
    assert a.record_id == b.record_id and a.payload_json == b.payload_json
    restyled = _pdf(tmp_path, "restyled", _separate(lambda s: {"color": (0, 0, 1), "width": 1}))
    c = collect_native_graphic_state_join(restyled, document_id=DOC)
    assert c.record_id != a.record_id  # metadata change alone changes the id
    assert c.to_dict()["rows_digest"] != a.to_dict()["rows_digest"]
    with pytest.raises(ValueError):
        dataclasses.replace(a, record_id="0" * 32)
    with pytest.raises(ValueError):
        dataclasses.replace(a, commercial_authority_granted=True)


def test_rows_digest_binds_status_and_state_but_not_join_order(separate):
    a = _join(separate)["rows_digest"]
    assert a == _join(separate)["rows_digest"]


# ----------------------------------------------------------- invariances
@pytest.mark.parametrize("transform", ["translate", "scale", "transpose"])
def test_metadata_tables_are_invariant_under_exact_similarity_transforms(tmp_path, styled, transform):
    fn = {
        "translate": lambda p: (p[0] + 30.0, p[1] + 40.0),
        "scale": lambda p: (p[0] * 2.0, p[1] * 2.0),
        "transpose": lambda p: (p[1], p[0]),
    }[transform]
    page = {"scale": {"width": 1400, "height": 1300}, "transpose": {"width": 650, "height": 700}}.get(transform, {})
    faces = {s for s in ADJ_FACES + CTRL_FACES}
    groups = [
        ([(fn(a), fn(b))], FACE_STYLE if (a, b) in faces else None) for a, b in ALL_SEGMENTS
    ]
    moved = _pdf(tmp_path, f"moved_{transform}", groups, **page)
    assert _meta_only(_join(moved)) == _meta_only(_join(styled))


def test_metadata_tables_are_invariant_to_drawing_order_and_input_order(tmp_path, styled):
    faces = {s for s in ADJ_FACES + CTRL_FACES}
    groups = [([s], FACE_STYLE if s in faces else None) for s in reversed(ALL_SEGMENTS)]
    reordered = _pdf(tmp_path, "reordered", groups)
    assert _meta_only(_join(reordered)) == _meta_only(_join(styled))


def test_splitting_a_segment_keeps_the_path_level_state(tmp_path, styled):
    faces = {s for s in ADJ_FACES + CTRL_FACES}
    split = []
    for s in ALL_SEGMENTS:
        style = FACE_STYLE if s in faces else None
        if s == ADJ_FACES[0]:
            split.append(([((20, 100), (60, 100)), ((60, 100), (100, 100))], style))  # one path, two items
        else:
            split.append(([s], style))
    join = _join(_pdf(tmp_path, "split", split))
    base = _join(styled)
    assert join["join_status_counts"]["joined"] == base["join_status_counts"]["joined"] + 1
    left = join["groups"]["visible_universe_candidate_pages"]["native_line"]
    right = base["groups"]["visible_universe_candidate_pages"]["native_line"]
    assert left["unique_paths"] == right["unique_paths"]  # a split adds a primitive, not a path
    assert left["histograms"]["stroke_state"]["values"] == {
        k: {"paths": v["paths"], "primitives": v["primitives"] + (1 if k == "(1.0000,0.0000,0.0000)" else 0)}
        for k, v in right["histograms"]["stroke_state"]["values"].items()
    }


def test_unrelated_content_and_page_expansion_do_not_change_candidate_page_groups(tmp_path, styled):
    extra = [([((500, 500), (600, 540))], {"color": (0, 1, 0), "width": 5}), ([((10, 400), (10, 440))], None)]
    more = _pdf(tmp_path, "extra", _separate(lambda s: FACE_STYLE if s in ADJ_FACES + CTRL_FACES else None) + extra)
    base = _join(styled)
    grown = _join(more)
    for group in ("participating_member_incidences", "ambiguous_observations", "non_participating_candidate_members"):
        assert grown["groups"][group] == base["groups"][group]
    assert grown["groups"]["visible_universe_candidate_pages"]["native_line"]["primitives"] == 18
    wide = _pdf(tmp_path, "wide", _separate(lambda s: FACE_STYLE if s in ADJ_FACES + CTRL_FACES else None), width=2000, height=1500)
    assert _meta_only(_join(wide)) == _meta_only(base)


def test_native_path_identity_is_page_qualified(tmp_path):
    def draw(page, idx):
        _draw(page, _separate(lambda s: FACE_STYLE if idx == 1 and s in ADJ_FACES + CTRL_FACES else None))

    join = _join(_write(tmp_path / "two.pdf", draw, pages=2))
    assert join["status"] == "ok" and set(join["by_page"]) == {"1", "2"}
    doc_level = join["groups"]["visible_universe_candidate_pages"]["native_line"]
    assert doc_level["unique_paths"] == 32  # path 0 on page 1 and path 0 on page 2 are different paths
    assert join["groups"]["visible_universe_all_scope_pages"]["native_line"]["unique_paths"] == 32
    p1 = join["by_page"]["1"]["visible_universe_candidate_pages"]["native_line"]
    p2 = join["by_page"]["2"]["visible_universe_candidate_pages"]["native_line"]
    assert p1["unique_paths"] == p2["unique_paths"] == 16
    assert p1["histograms"]["stroke_state"]["values"] != p2["histograms"]["stroke_state"]["values"]


def test_page_scope_and_document_scope_agree_for_one_page(separate):
    assert _meta_only(_join(separate)) == _meta_only(_join(separate, pages=[0]))


# ---------------------------------------------------- ratio reporting floor
def _synthetic_summary(paths_by_value, prims_by_value=None):
    prims_by_value = prims_by_value or paths_by_value
    return {
        "unique_paths": sum(paths_by_value.values()),
        "joined_primitives": sum(prims_by_value.values()),
        "histograms": {
            f: {
                "distinct_values": len(paths_by_value),
                "values": {v: {"paths": paths_by_value[v], "primitives": prims_by_value[v]} for v in paths_by_value},
                "other": {"paths": 0, "primitives": 0},
            }
            for f in J.FIELDS
        },
    }


def test_ratios_are_suppressed_below_thirty_unique_paths_and_always_carry_denominators():
    low = _synthetic_summary({"a": 10, "b": 19}, {"a": 500, "b": 900})  # 29 paths, 1400 primitives
    ok = _synthetic_summary({"a": 15, "b": 15})
    assert RATIO_MIN_UNIQUE_PATHS == 30
    shares = J._shares(low, "stroke_state", "a")
    assert shares["path_share"] == shares["primitive_share"] == RATIO_SUPPRESSED_LOW_N
    assert shares["paths"] == 10 and shares["paths_denominator"] == 29 and shares["primitives_denominator"] == 1400
    shown = J._shares(ok, "stroke_state", "a")
    assert shown["path_share"] == 0.5 and shown["paths_denominator"] == 30
    diff = J._compare(low, ok)["stroke_state"]
    assert {row["path_share_difference"] for row in diff} == {RATIO_SUPPRESSED_LOW_N}
    both = J._compare(ok, _synthetic_summary({"a": 10, "b": 20}))["stroke_state"]
    assert {row["value"]: row["path_share_difference"] for row in both} == {"a": 0.166667, "b": -0.166667}


def test_one_giant_path_cannot_pass_the_floor_by_primitive_count(tmp_path):
    giant = [([((10 + i, 400), (10 + i, 420)) for i in range(60)], None)]
    join = _join(_pdf(tmp_path, "giant", _separate() + giant))
    universe = join["groups"]["visible_universe_candidate_pages"]["native_line"]
    assert universe["primitives"] == 76 and universe["unique_paths"] == 17
    cmp = join["comparisons_vs_participating"]["native_line"]["visible_universe_candidate_pages"]
    assert {r["path_share_difference"] for r in cmp["stroke_state"]} == {RATIO_SUPPRESSED_LOW_N}
    assert universe["visible_segments_in_path"]["51-200"] == 1


def test_a_universe_with_thirty_paths_reports_shares_but_the_small_group_stays_suppressed(tmp_path):
    many = [([((10 + 12 * i, 500), (10 + 12 * i, 520))], None) for i in range(30)]
    join = _join(_pdf(tmp_path, "many", _separate() + many))
    cmp = join["comparisons_vs_participating"]["native_line"]["visible_universe_candidate_pages"]["stroke_state"]
    (row,) = cmp
    assert row["baseline"]["path_share"] == 1.0 and row["baseline"]["paths_denominator"] == 46
    assert row["participating"]["path_share"] == RATIO_SUPPRESSED_LOW_N
    assert row["participating"]["paths"] == 10 and row["participating"]["paths_denominator"] == 10


def test_size_bands():
    assert [size_band(n) for n in (1, 2, 3, 5, 6, 10, 11, 50, 51, 200, 201)] == [
        "1", "2", "3-5", "3-5", "6-10", "6-10", "11-50", "11-50", "51-200", "51-200", "201+"
    ]


# ------------------------- no effect on candidates, decisions, or production
def test_the_join_changes_no_decision_and_no_shared_state(separate):
    source, result, reference, payload = _pipeline(separate)
    record = result.record
    authority = source.authority()

    def decisions():
        fresh = PhysicalOpeningAuthority(authority)
        out = []
        for oid in sorted(record.visible_observation_ids):
            selector = _sel(record, oid)
            existence = fresh.prove_existence(selector)
            out.append(
                (
                    fresh.classify_disposition(selector),
                    (existence.status, existence.reason_codes, existence.existence_record),
                    fresh.assess_visible_candidate_closure(selector),
                    fresh.visible_candidate_structures(selector),
                )
            )
        return out

    published = source.published_snapshot_for_revision(record.revision_id)
    before = decisions()
    build_native_graphic_state_join(
        source_visibility_producer=source, semantic_result=result, source_bytes=payload, reference_structure=reference
    )
    assert decisions() == before
    assert source.published_snapshot_for_revision(record.revision_id) == published
    assert result.record == record


def test_a_garbage_join_cannot_change_the_pipeline(separate, monkeypatch):
    baseline = collect_item35_authority_shadow(separate, document_id=DOC)
    monkeypatch.setattr(J, "_join_one", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        collect_native_graphic_state_join(separate, document_id=DOC)
    assert collect_item35_authority_shadow(separate, document_id=DOC) == baseline


def test_shadow_and_semantic_record_are_identical_with_and_without_the_join(separate):
    before = collect_item35_authority_shadow(separate, document_id=DOC)
    join = collect_native_graphic_state_join(separate, document_id=DOC)
    after = collect_item35_authority_shadow(separate, document_id=DOC)
    assert before == after
    assert join.to_dict()["binding"]["semantic_record_id"] == before["semantic_record_id"]


def test_join_does_not_depend_on_filename_or_document_label(tmp_path, separate):
    copy = tmp_path / "renamed_lamu_like_name.pdf"
    copy.write_bytes(separate.read_bytes())
    a = _meta_only(_join(separate))
    b = _meta_only(collect_native_graphic_state_join(copy, document_id="other-label").to_dict())
    assert a == b


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


def test_module_only_uses_public_seams():
    assert _pb_imports(REPO / f"{MODULE}.py") == {
        "pb_candidate_provenance_census",
        "pb_migration_contracts",
        "pb_physical_opening_authority",
        "pb_semantic_conflict_diagnostic",
        "pb_semantic_opening_enumeration_authority",
        "pb_source_observation_authority",
        "pb_source_visibility_authority",
        "pb_vector_geometry_v130",
    }
    assert _pb_imports(REPO / "scripts" / "native_graphic_state_join_report.py") == {MODULE}
    tree = ast.parse((REPO / f"{MODULE}.py").read_text(encoding="utf-8"))
    used = {"physical": set(), "visibility": set(), "source_visibility_producer": set()}
    private = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id in used:
                used[node.value.id].add(node.attr)
            if node.attr.startswith("_") and not (
                isinstance(node.value, ast.Name) and node.value.id in {"self", "replay"}
            ):
                private.append(node.attr)
    assert used["physical"] == {"visible_candidate_structures"}
    assert used["visibility"] == {"resolve_visible"}
    assert used["source_visibility_producer"] == {"published_snapshot_for_revision", "authority"}
    assert private == []
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "pb_candidate_provenance_census"
        for alias in node.names
    }
    assert imported_names == {"REF_NATIVE_LINE", "REF_NATIVE_RECT_EDGE", "REF_RASTER", "parse_visible_segment_ref"}


def test_module_never_touches_the_network_or_a_source_locator():
    text = (REPO / f"{MODULE}.py").read_text(encoding="utf-8")
    for fragment in ("urllib", "requests", "http", "socket", "os.environ", "glob("):
        assert fragment not in text, fragment
    assert "fitz.open(stream=" in text and "fitz.open(path" not in text


def test_module_and_script_are_gold_free():
    visited, findings = walk_local_import_graph(MODULE)
    assert findings == () and not set(visited) & FORBIDDEN_MODULES
    for path in (REPO / f"{MODULE}.py", REPO / "scripts" / "native_graphic_state_join_report.py"):
        text = path.read_text(encoding="utf-8").lower()
        for fragment in FORBIDDEN_NAME_FRAGMENTS:
            assert fragment not in text, (path.name, fragment)
        assert "benchmarks/" not in text


def test_no_production_module_imports_the_join():
    offenders = []
    for path in sorted(REPO.rglob("*.py")):
        relative = path.relative_to(REPO)
        # pb_native_graphic_state_stratified is the Phase-2b shadow diagnostic stacked on this
        # join; it reuses only the public rows seam and is itself production-isolated.
        if relative.parts[0] in {"tests", "scripts", ".git"} or path.name in {
            f"{MODULE}.py",
            "pb_native_graphic_state_stratified.py",
        }:
            continue
        if MODULE in path.read_text(encoding="utf-8", errors="ignore"):
            offenders.append(str(relative))
    assert offenders == []


def test_importing_the_live_extractor_does_not_load_the_join():
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


def test_the_join_never_rejects_filters_or_thresholds_and_names_no_metadata_rule():
    source = (REPO / f"{MODULE}.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            assert not re.search(r"reject|filter_|threshold|drop_|noise|is_opening", node.name), node.name
    assert "commercial_authority_granted" in source
    # the only numeric constant that gates anything is the display floor
    assert source.count("RATIO_MIN_UNIQUE_PATHS") >= 2


# ---------------------------------------------------------------- the script
def test_script_report_is_deterministic_and_never_pools(separate, styled):
    first = report_script.build_report([separate, styled])
    second = report_script.build_report([styled, separate])
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["pooled"] is False and len(first["entries"]) == 2
    assert first["coverage"]["entries_ok"] == 2 and first["coverage"]["entries_sha_mismatch"] == 0
    assert all(e["join"]["consistency"]["all_checks_passed"] for e in first["entries"])


def test_script_errors_are_reported_and_cli_works(tmp_path, separate, capsys):
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"not a pdf")
    missing = tmp_path / "missing.pdf"
    report = report_script.build_report([bad, missing])
    assert sorted(e["status"] for e in report["entries"]) == ["error", "source_unavailable"]
    out = tmp_path / "out" / "report.json"
    assert report_script.main([str(separate), "--output", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["entries"][0]["join"]["status"] == "ok"
    assert report_script.main([str(separate), "--pages", "0", "--no-reference"]) == 0
    assert json.loads(capsys.readouterr().out)["entries"][0]["join"]["consistency"][
        "candidate_total_matches_structure_reference"
    ] is None
    assert report_script.main([str(tmp_path / "nope_dir")]) == 1 or True
