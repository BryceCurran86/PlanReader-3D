"""Opening label lines are built from the opening's own page only, without re-authenticating other pages.

``_trusted_native_lines`` runs once per opening and used to resolve every text word of every page, then
discard the words whose receipt was on another page. The receipt-page filter must select exactly the words
that survived that discard, so the lines (and everything built on them) are unchanged.
"""
from __future__ import annotations

from dataclasses import replace

import fitz
import pytest

import pb_opening_label_semantic_authority as semantic
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_label_semantic_authority import OpeningLabelSemanticProducer
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

FRAME = (
    ((20.0, 100.0), (100.0, 100.0)),
    ((140.0, 100.0), (220.0, 100.0)),
    ((20.0, 110.0), (100.0, 110.0)),
    ((140.0, 110.0), (220.0, 110.0)),
    ((100.0, 100.0), (100.0, 110.0)),
    ((140.0, 100.0), (140.0, 110.0)),
)


def _pdf(*, other_page_words: tuple[str, ...] = ("DOOR", "WINDOW", "SCHEDULE", "NOTES")) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=400.0, height=300.0)
        for first, second in FRAME:
            page.draw_line(fitz.Point(*first), fitz.Point(*second), width=1.0)
        page.insert_text(fitz.Point(105.0, 125.0), "1218 SGW", fontsize=7.0)
        page.insert_text(fitz.Point(20.0, 180.0), "LEGEND", fontsize=8.0)
        page.insert_text(fitz.Point(20.0, 195.0), "SGW     SLIDING GLASS WINDOW", fontsize=7.0)
        other = doc.new_page(width=400.0, height=300.0)
        for index, word in enumerate(other_page_words):
            other.insert_text(fitz.Point(30.0, 40.0 + 14.0 * index), word, fontsize=8.0)
        other.insert_text(fitz.Point(105.0, 125.0), "DOOR", fontsize=7.0)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


@pytest.fixture()
def fixture():
    source = SourceVisibilityProducer(producer_method="page-text-filter-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="page-text-filter",
        source_bytes=_pdf(),
        source_locator="fixture:page-text-filter",
    )
    physical = source.physical_opening_authority()
    found = {}
    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = physical.prove_existence(selector)
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            found[result.existence_record.record_id] = (selector, result.existence_record)
    assert len(found) == 1
    selector, opening = next(iter(found.values()))
    return source, published, selector, opening


def _reference_lines(source, opening):
    """The previous implementation: resolve every word of every page, then discard other pages."""
    published = source.published_snapshot_for_revision(opening.revision_id)
    if published is None or published.snapshot.snapshot_id != opening.snapshot_id:
        return ()
    integrity = source.text_integrity_authority()
    grouped = {}
    for observation_id in published.text_observation_ids:
        resolved = integrity.resolve_text(ObservationSelector(
            document_id=opening.document_id,
            revision_id=opening.revision_id,
            source_sha256=opening.source_sha256,
            snapshot_id=opening.snapshot_id,
            observation_id=observation_id,
        ))
        receipt = getattr(resolved, "receipt", None)
        if (
            resolved.status is not EvidenceResolutionStatus.CORROBORATED
            or resolved.trusted_text is None
            or receipt is None
            or str(receipt.page_id) != str(opening.page_id)
        ):
            continue
        block_no = int(receipt.block_no) if receipt.block_no is not None else None
        line_no = int(receipt.line_no) if receipt.line_no is not None else None
        if block_no is not None and line_no is not None:
            key = ("native", block_no, line_no)
            order = int(receipt.word_no or 0)
        else:
            key = ("obs", observation_id)
            order = 0
        grouped.setdefault(key, []).append((
            order, observation_id, resolved.trusted_text,
            tuple(float(v) for v in receipt.geometry), block_no, line_no,
        ))
    out = []
    for rows in grouped.values():
        ordered = sorted(rows, key=lambda item: (item[0], item[1]))
        bbox = semantic._bbox_union([row[3] for row in ordered])
        if bbox is None:
            continue
        out.append((
            ordered[0][4], ordered[0][5],
            semantic._TrustedTextLine(
                observation_ids=tuple(row[1] for row in ordered),
                text=" ".join(row[2] for row in ordered).strip(),
                bbox=bbox,
            ),
        ))
    return tuple(out)


def _counting_resolve(source, monkeypatch):
    integrity = source.text_integrity_authority()
    calls = []
    original = type(integrity).resolve_text

    def spy(self, selector):
        calls.append(selector.observation_id)
        return original(self, selector)

    monkeypatch.setattr(type(integrity), "resolve_text", spy)
    return calls


def test_lines_equal_the_previous_implementation(fixture):
    source, _published, _selector, opening = fixture
    expected = _reference_lines(source, opening)
    assert expected, "the fixture must produce real lines"
    texts = [line.text for _b, _l, line in expected]
    assert any("SGW" in text for text in texts) and any("LEGEND" in text for text in texts)
    assert not any("DOOR" in text for text in texts), "other-page words must never become lines"
    assert semantic._trusted_native_lines(source, opening) == expected


def test_only_the_openings_own_page_is_resolved(fixture, monkeypatch):
    source, published, _selector, opening = fixture
    store = source._producer._store
    page_of = {
        observation_id: str(store.observations[(published.snapshot.snapshot_id, observation_id)].page_id)
        for observation_id in published.text_observation_ids
    }
    assert {"1", "2"} <= set(page_of.values()), "the fixture needs text on both pages"
    calls = _counting_resolve(source, monkeypatch)
    semantic._trusted_native_lines(source, opening)
    assert calls and {page_of[i] for i in calls} == {"1"}
    assert set(calls) == {i for i, page in page_of.items() if page == "1"}
    previous_calls = len(published.text_observation_ids)
    assert len(calls) < previous_calls


def test_filter_selects_receipt_page_in_order(fixture):
    source, published, _selector, _opening = fixture
    integrity = source.text_integrity_authority()
    snapshot_id = published.snapshot.snapshot_id
    ids = published.text_observation_ids
    page_one = integrity.observation_ids_with_receipt_page(snapshot_id, ids, "1")
    page_two = integrity.observation_ids_with_receipt_page(snapshot_id, ids, 2)
    assert page_one and page_two and not set(page_one) & set(page_two)
    assert set(page_one) | set(page_two) == set(ids)
    assert page_one == tuple(i for i in ids if i in set(page_one))
    assert integrity.observation_ids_with_receipt_page(snapshot_id, ids, "3") == ()
    assert integrity.observation_ids_with_receipt_page("other-snapshot", ids, "1") == ()
    assert integrity.observation_ids_with_receipt_page(
        snapshot_id, ("not-a-text-word", *page_one), "1"
    ) == page_one
    assert integrity.observation_ids_with_receipt_page(snapshot_id, (), "1") == ()


@pytest.mark.parametrize("tamper", [
    "other_page_receipt_moved_to_page_one",
    "page_one_receipt_removed",
    "page_one_word_geometry_changed",
    "page_one_receipt_untrusted",
    "other_page_word_geometry_changed",
])
def test_equal_to_the_previous_implementation_under_tampering(fixture, tamper):
    source, published, _selector, opening = fixture
    store = source._producer._store
    snapshot_id = published.snapshot.snapshot_id
    receipts = source.text_integrity_authority()._receipts
    by_page = {}
    for observation_id in published.text_observation_ids:
        receipt = receipts[(snapshot_id, observation_id)]
        by_page.setdefault(str(receipt.page_id), []).append(observation_id)
    one, two = by_page["1"][0], by_page["2"][0]
    undo = []

    def swap(mapping, key, value):
        undo.append((mapping, key, mapping.get(key)))
        mapping[key] = value

    if tamper == "other_page_receipt_moved_to_page_one":
        swap(receipts, (snapshot_id, two), replace(receipts[(snapshot_id, two)], page_id="1"))
    elif tamper == "page_one_receipt_removed":
        undo.append((receipts, (snapshot_id, one), receipts.pop((snapshot_id, one))))
    elif tamper == "page_one_word_geometry_changed":
        record = store.observations[(snapshot_id, one)]
        swap(store.observations, (snapshot_id, one), replace(record, geometry=(0.0, 0.0, 1.0, 1.0)))
    elif tamper == "page_one_receipt_untrusted":
        swap(receipts, (snapshot_id, one), replace(receipts[(snapshot_id, one)], trusted=False))
    else:
        record = store.observations[(snapshot_id, two)]
        swap(store.observations, (snapshot_id, two), replace(record, geometry=(0.0, 0.0, 1.0, 1.0)))
    try:
        assert semantic._trusted_native_lines(source, opening) == _reference_lines(source, opening)
    finally:
        for mapping, key, previous in reversed(undo):
            if previous is None:
                mapping.pop(key, None)
            else:
                mapping[key] = previous


def test_a_conflicting_word_on_another_page_cannot_change_the_published_label(fixture, monkeypatch):
    source, _published, selector, _opening = fixture
    producer = OpeningLabelSemanticProducer.from_source_visibility_producer(source)
    result = producer.publish_scope(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None and result.evidence.semantic_kind == "window"
    monkeypatch.setattr(semantic, "_trusted_native_lines", _reference_lines)
    reference = OpeningLabelSemanticProducer.from_source_visibility_producer(source).publish_scope(selector)
    assert reference == result
