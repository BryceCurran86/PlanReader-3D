"""S1 of the framed-window roles report: authenticated native paint facts, with no role asserted.

The accessor reports what the source itself says about how named native observations are painted (path, paint order,
stroke, width, dashes, layer, fill, clip). It re-proves the source like its sibling `native_unstroked_fill_evidence`,
reads nothing from a caller, and says nothing about what a line IS."""
from dataclasses import FrozenInstanceError, asdict, replace

import fitz
import pytest

from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import NativePaintFact, SourceVisibilityProducer

RED = (1.0, 0.0, 0.0)
BLACK = (0.0, 0.0, 0.0)


def _pdf(*, dx=0.0, dy=0.0, rotation=0, before=False, after=False, scale=1.0):
    pdf = fitz.open()
    page = pdf.new_page(width=300 * scale, height=300 * scale)

    def p(x, y):
        return fitz.Point((x + dx) * scale, (y + dy) * scale)

    if before:
        page.draw_line(p(250, 250), p(280, 250), color=BLACK, width=0.96)
    page.draw_line(p(20, 20), p(120, 20), color=BLACK, width=0.48)
    page.draw_line(p(20, 30), p(120, 30), color=RED, width=0.24)
    page.draw_line(p(20, 40), p(120, 40), color=BLACK, width=0.48, dashes="[3 2] 0")
    page.draw_rect(fitz.Rect(p(20, 60), p(60, 80)), color=BLACK, width=0.48)
    page.draw_rect(fitz.Rect(p(80, 60), p(120, 80)), color=None, fill=(1, 1, 1))
    if after:
        page.draw_line(p(250, 250), p(280, 250), color=BLACK, width=0.96)
    page.set_rotation(rotation)
    data = pdf.tobytes()
    pdf.close()
    return data


def _source(**kwargs):
    data = _pdf(**kwargs)
    producer = SourceVisibilityProducer(producer_method="paint-facts-test", producer_version="1")
    published = producer.ingest_native_pdf_bytes(
        document_id="paint-facts-test", source_bytes=data, source_locator="memory://paint-facts-test.pdf")
    rows = producer.authority().authenticated_visible_observations(published)
    ids = tuple(i for i, _ in rows)
    selector = ObservationSelector(
        document_id=published.revision.document_id, revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
        observation_id=ids[0])
    return producer, published, selector, ids, data


def _attrs(fact):
    return (fact.kind, fact.paint_type, fact.stroke_color, fact.stroke_width, fact.dashes, fact.fill, fact.fill_opacity)


def _oracle(data):
    """The same drawings read straight from the PDF with PyMuPDF, independent of the producer."""
    with fitz.open(stream=data, filetype="pdf") as pdf:
        return pdf[0].get_drawings()


def test_the_facts_are_what_the_pdf_itself_says_about_each_path():
    producer, published, selector, ids, data = _source()
    facts = producer.native_paint_facts(selector, observation_ids=ids)
    assert len(facts) == len(ids) == 11
    drawings = _oracle(data)
    for fact in facts:
        drawing = drawings[fact.path_index]
        assert fact.paint_type == drawing["type"]
        assert fact.stroke_color == (None if drawing["color"] is None else tuple(drawing["color"]))
        assert fact.fill == (None if drawing["fill"] is None else tuple(drawing["fill"]))
        assert fact.sequence_number == drawing["seqno"]
        assert fact.dashes == (drawing["dashes"] or "")
        if drawing["color"] is not None:
            assert fact.stroke_width == pytest.approx(drawing["width"])
        assert fact.page_id and fact.source_primitive_id and len(fact.geometry) == 4
    lines = [f for f in facts if f.kind == "line"]
    rect_edges = [f for f in facts if f.kind == "rect_edge"]
    assert len(lines) == 3 and len(rect_edges) == 8
    black, red, dashed = sorted(lines, key=lambda f: f.sequence_number)
    assert (black.stroke_color, red.stroke_color, dashed.stroke_color) == (BLACK, RED, BLACK)
    assert black.stroke_width == pytest.approx(0.48) and red.stroke_width == pytest.approx(0.24)
    assert black.dashes != dashed.dashes and dashed.dashes.replace(" ", "").startswith("[32]")
    assert black.sequence_number < red.sequence_number < dashed.sequence_number
    stroked = [f for f in rect_edges if f.stroke_color is not None]
    unstroked = [f for f in rect_edges if f.stroke_color is None]
    assert len(stroked) == 4 and len(unstroked) == 4
    assert all(f.fill == (1.0, 1.0, 1.0) and f.paint_type == "f" for f in unstroked)
    assert len({f.path_index for f in unstroked}) == 1                              # four edges of ONE path
    assert len({f.path_index for f in lines}) == 3


def test_a_fact_asserts_no_role_and_is_immutable():
    producer, published, selector, ids, data = _source()
    fact = producer.native_paint_facts(selector, observation_ids=ids)[0]
    assert isinstance(fact, NativePaintFact) and fact.asserts_role is False
    names = set(asdict(fact))
    assert not any("role" in n and n != "asserts_role" for n in names) and "glazing" not in " ".join(names)
    with pytest.raises(FrozenInstanceError):
        fact.stroke_width = 9.0
    with pytest.raises(ValueError):
        NativePaintFact(**{**asdict(fact), "asserts_role": True})


def test_the_answer_is_deterministic_and_independent_of_the_order_of_the_request():
    producer, published, selector, ids, data = _source()
    first = producer.native_paint_facts(selector, observation_ids=ids)
    assert producer.native_paint_facts(selector, observation_ids=tuple(reversed(ids))) == first
    assert producer.native_paint_facts(selector, observation_ids=ids + ids) == first
    assert producer.native_paint_facts(selector, observation_ids=ids) == first
    assert [f.observation_id for f in first] == sorted(f.observation_id for f in first)
    subset = producer.native_paint_facts(selector, observation_ids=ids[:3])
    assert {f.observation_id for f in subset} == set(ids[:3])


def test_asking_changes_nothing_and_the_fill_evidence_sibling_is_unaffected():
    producer, published, selector, ids, data = _source()
    before = asdict(published)
    unstroked = tuple(f.observation_id for f in producer.native_paint_facts(selector, observation_ids=ids)
                      if f.stroke_color is None)
    sibling_before = producer.native_unstroked_fill_evidence(
        replace(selector, observation_id=unstroked[0]), support_observation_ids=unstroked)
    producer.native_paint_facts(selector, observation_ids=ids)
    assert asdict(published) == before
    assert set(ids) <= set(producer.authority().visible_observation_ids_for_snapshot(selector.snapshot_id))
    assert producer.native_unstroked_fill_evidence(
        replace(selector, observation_id=unstroked[0]), support_observation_ids=unstroked) == sibling_before
    assert sibling_before


@pytest.mark.parametrize("variant", [dict(dx=31, dy=20), dict(scale=2), dict(rotation=90), dict(rotation=180),
                                     dict(rotation=270), dict(before=True), dict(after=True)])
def test_the_paint_attributes_and_their_order_survive_translation_scale_rotation_and_unrelated_content(variant):
    base = _source()
    other = _source(**variant)

    def signature(source, drop_unrelated):
        producer, _published, selector, ids, _data = source
        facts = sorted(producer.native_paint_facts(selector, observation_ids=ids), key=lambda f: f.sequence_number)
        if drop_unrelated:                     # the unrelated 0.96 pt line is not part of the comparison
            facts = [f for f in facts if f.stroke_width != pytest.approx(0.96)]
        return [_attrs(f) for f in facts]

    expected = signature(base, False)
    got = signature(other, True)
    if variant.get("scale"):                   # stroke widths are not scaled by the page, nor by us
        assert got == expected
    else:
        assert got == expected


@pytest.mark.parametrize("defect", ["geometry", "missing_receipt", "source_bytes"])
def test_geometry_receipt_and_source_hash_damage_fail_closed(defect):
    producer, _published, selector, ids, _data = _source()
    assert producer.native_paint_facts(selector, observation_ids=ids)
    if defect == "geometry":
        key = (selector.snapshot_id, ids[0])
        if key not in producer._producer._store.observations:
            key = (selector.snapshot_id, producer._visibility_receipts[key])
        record = producer._producer._store.observations[key]
        producer._producer._store.observations[key] = replace(record, geometry=(0., 0., 1., 1.))
    elif defect == "missing_receipt":
        del producer._visibility_receipts[(selector.snapshot_id, ids[0])]
    else:
        producer._producer._store.source_bytes_by_revision[selector.revision_id] = b"changed"
    with pytest.raises(RuntimeError):
        producer.native_paint_facts(selector, observation_ids=ids)


def test_source_damage_cannot_be_hidden_by_a_cached_paint_page():
    producer, _published, selector, ids, _data = _source()
    assert producer.native_paint_facts(selector, observation_ids=ids)
    producer._visibility_receipts[(selector.snapshot_id, ids[-1])] = "foreign-parent"
    with pytest.raises(RuntimeError):
        producer.native_paint_facts(selector, observation_ids=ids)


@pytest.mark.parametrize("field,value", [("revision_id", "stale"), ("snapshot_id", "stale"),
                                         ("source_sha256", "0" * 64), ("document_id", "foreign")])
def test_stale_and_foreign_selectors_are_refused(field, value):
    producer, _published, selector, ids, _data = _source()
    with pytest.raises(RuntimeError):
        producer.native_paint_facts(replace(selector, **{field: value}), observation_ids=ids)


@pytest.mark.parametrize("requested", [(), ("no-such-observation",)])
def test_an_empty_unknown_or_selector_less_request_is_refused(requested):
    producer, _published, selector, ids, _data = _source()
    with pytest.raises(RuntimeError):
        producer.native_paint_facts(selector, observation_ids=requested)
    with pytest.raises(RuntimeError):
        producer.native_paint_facts(selector, observation_ids=ids[1:])             # the selector's own id is missing
