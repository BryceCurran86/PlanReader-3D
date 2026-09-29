"""Page-local visibility indexing must preserve wall-source semantics."""
from __future__ import annotations

from types import SimpleNamespace

import fitz

import pb_physical_wall_candidate_authority as module
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_visibility_authority import (
    SourceVisibilityAuthority,
    SourceVisibilityProducer,
)


def _source(page_count=6):
    doc = fitz.open()
    try:
        for index in range(page_count):
            page = doc.new_page(width=500, height=500)
            y = 70.0 + index * 13.0
            shape = page.new_shape()
            for a, b in (
                ((50, y), (180, y)),
                ((50, y + 18), (180, y + 18)),
                ((180, y), (180, y + 18)),
                ((220, y), (360, y)),
                ((220, y + 18), (360, y + 18)),
                ((220, y), (220, y + 18)),
            ):
                shape.draw_line(a, b)
            shape.finish(width=1)
            shape.commit()
        payload = doc.tobytes(garbage=4, deflate=True)
    finally:
        doc.close()

    source = SourceVisibilityProducer(
        producer_method="wall-visible-page-index-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="wall-visible-page-index-test",
        source_bytes=payload,
        source_locator="memory://wall-visible-page-index-test.pdf",
    )
    return source, published, payload


def test_indexed_page_reconstruction_equals_legacy_fallback():
    source, published, payload = _source()
    indexed = module._visible_observations_by_page(
        source_producer=source,
        published=published,
    )

    for page in range(1, 7):
        page_id = str(page)
        legacy = module._source_page_segments(
            source_producer=source,
            published=published,
            source_bytes=payload,
            page_id=page_id,
            decision_scope_id=f"wall-source:page-{page_id}",
        )
        current = module._source_page_segments(
            source_producer=source,
            published=published,
            source_bytes=payload,
            page_id=page_id,
            decision_scope_id=f"wall-source:page-{page_id}",
            resolved_visible_observations=indexed.get(page_id, ()),
        )
        assert current == legacy


def test_visibility_index_authenticates_each_snapshot_observation_once(monkeypatch):
    source, published, _payload = _source(page_count=8)
    original = SourceVisibilityAuthority.resolve_visible
    calls = 0

    def counted(self, selector):
        nonlocal calls
        calls += 1
        return original(self, selector)

    monkeypatch.setattr(SourceVisibilityAuthority, "resolve_visible", counted)

    indexed = module._visible_observations_by_page(
        source_producer=source,
        published=published,
    )

    assert calls == len(published.visible_observation_ids)
    assert sum(len(rows) for rows in indexed.values()) == len(
        published.visible_observation_ids
    )


def test_indexed_opening_override_does_not_rescan_page_ownership(monkeypatch):
    source, published, _payload = _source(page_count=3)
    indexed = module._visible_observations_by_page(
        source_producer=source,
        published=published,
    )

    resolve_calls = 0
    original_resolve = SourceVisibilityAuthority.resolve_visible

    def counted_resolve(self, selector):
        nonlocal resolve_calls
        resolve_calls += 1
        return original_resolve(self, selector)

    def blocked_opening(self, selector):
        return SimpleNamespace(
            status=EvidenceResolutionStatus.ABSTAINED,
            proposition=None,
            existence_record=None,
            reason_codes=("test_blocked",),
        )

    monkeypatch.setattr(SourceVisibilityAuthority, "resolve_visible", counted_resolve)
    monkeypatch.setattr(PhysicalOpeningAuthority, "prove_existence", blocked_opening)

    result = module._producer_opening_relation_overrides(
        source_producer=source,
        published=published,
        page_id="2",
        records=(),
        resolved_visible_observations=indexed["2"],
    )

    assert result == {}
    assert resolve_calls == 0


def test_opening_override_indexed_and_fallback_agree_on_empty_records():
    source, published, _payload = _source(page_count=2)
    indexed = module._visible_observations_by_page(
        source_producer=source,
        published=published,
    )
    legacy = module._producer_opening_relation_overrides(
        source_producer=source,
        published=published,
        page_id="1",
        records=(),
    )
    current = module._producer_opening_relation_overrides(
        source_producer=source,
        published=published,
        page_id="1",
        records=(),
        resolved_visible_observations=indexed["1"],
    )
    assert current == legacy



def test_shared_opening_authority_matches_fresh_per_page_scope_results():
    source, published, payload = _source(page_count=3)
    indexed = module._visible_observations_by_page(
        source_producer=source,
        published=published,
    )
    shared = PhysicalOpeningAuthority(source.authority())

    for page_id in ("1", "2", "3"):
        fresh_result = module._build_scope_result(
            source_producer=source,
            published=published,
            source_bytes=payload,
            page_id=page_id,
            resolved_visible_observations=indexed.get(page_id, ()),
        )
        shared_result = module._build_scope_result(
            source_producer=source,
            published=published,
            source_bytes=payload,
            page_id=page_id,
            resolved_visible_observations=indexed.get(page_id, ()),
            physical_opening_authority=shared,
        )
        assert shared_result == fresh_result


def test_wall_candidate_producer_constructs_one_opening_authority_per_revision(
    monkeypatch,
):
    source, _published, _payload = _source(page_count=5)
    original = module.PhysicalOpeningAuthority
    constructions = 0

    def counted(authority):
        nonlocal constructions
        constructions += 1
        return original(authority)

    monkeypatch.setattr(module, "PhysicalOpeningAuthority", counted)

    producer = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source,
        page_ids=("1", "2", "3", "4", "5"),
    )
    assert producer.authority() is not None
    assert constructions == 1



def test_opening_override_proves_every_page_visible_observation_once(monkeypatch):
    source, published, _payload = _source(page_count=1)
    indexed = module._visible_observations_by_page(
        source_producer=source,
        published=published,
    )
    rows = list(indexed["1"])
    native = [
        (oid, observation)
        for oid, observation in rows
        if str(observation.source_primitive_ref).startswith("visible:segment:")
    ]
    assert len(native) >= 6

    records = tuple(
        SimpleNamespace(
            wall_candidate_id=f"wall-{index}",
            physical_identity=SimpleNamespace(
                source_primitive_ids=(
                    str(observation.source_primitive_ref)[len("visible:segment:"):],
                )
            ),
        )
        for index, (_oid, observation) in enumerate(native[:6])
    )

    calls = []

    def blocked(self, selector):
        calls.append(selector.observation_id)
        return SimpleNamespace(
            status=EvidenceResolutionStatus.ABSTAINED,
            proposition=None,
            existence_record=None,
            reason_codes=("test_blocked",),
        )

    monkeypatch.setattr(PhysicalOpeningAuthority, "prove_existence", blocked)
    result = module._producer_opening_relation_overrides(
        source_producer=source,
        published=published,
        page_id="1",
        records=records,
        resolved_visible_observations=rows,
        physical_opening_authority=PhysicalOpeningAuthority(source.authority()),
    )

    assert result == {}
    assert calls == [oid for oid, _observation in rows]


def test_fewer_than_six_wall_candidates_skips_opening_proof_entirely(monkeypatch):
    source, published, _payload = _source(page_count=1)
    indexed = module._visible_observations_by_page(
        source_producer=source,
        published=published,
    )
    rows = list(indexed["1"])
    native = [
        (oid, observation)
        for oid, observation in rows
        if str(observation.source_primitive_ref).startswith("visible:segment:")
    ]
    records = tuple(
        SimpleNamespace(
            wall_candidate_id=f"wall-{index}",
            physical_identity=SimpleNamespace(
                source_primitive_ids=(
                    str(observation.source_primitive_ref)[len("visible:segment:"):],
                )
            ),
        )
        for index, (_oid, observation) in enumerate(native[:5])
    )

    def forbidden(self, selector):
        raise AssertionError("opening proof cannot contribute with fewer than six wall candidates")

    monkeypatch.setattr(PhysicalOpeningAuthority, "prove_existence", forbidden)
    assert module._producer_opening_relation_overrides(
        source_producer=source,
        published=published,
        page_id="1",
        records=records,
        resolved_visible_observations=rows,
        physical_opening_authority=PhysicalOpeningAuthority(source.authority()),
    ) == {}



def test_page_index_does_not_bypass_generic_opening_evidence(monkeypatch):
    source, published, _payload = _source(page_count=1)
    indexed = module._visible_observations_by_page(
        source_producer=source,
        published=published,
    )
    rows = list(indexed["1"])
    native = [
        (oid, observation)
        for oid, observation in rows
        if str(observation.source_primitive_ref).startswith("visible:segment:")
    ]
    records = tuple(
        SimpleNamespace(
            wall_candidate_id=f"wall-{index}",
            physical_identity=SimpleNamespace(
                source_primitive_ids=(
                    str(observation.source_primitive_ref)[len("visible:segment:"):],
                )
            ),
        )
        for index, (_oid, observation) in enumerate(native[:6])
    )

    calls = []
    def blocked(self, selector):
        calls.append(selector.observation_id)
        return SimpleNamespace(
            status=EvidenceResolutionStatus.ABSTAINED,
            proposition=None,
            existence_record=None,
            reason_codes=("test_blocked",),
        )

    monkeypatch.setattr(PhysicalOpeningAuthority, "prove_existence", blocked)
    result = module._producer_opening_relation_overrides(
        source_producer=source,
        published=published,
        page_id="1",
        records=records,
        resolved_visible_observations=rows,
        physical_opening_authority=PhysicalOpeningAuthority(source.authority()),
    )
    assert result == {}
    assert calls == [oid for oid, _observation in rows]

