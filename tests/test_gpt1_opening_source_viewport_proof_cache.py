"""Original-source viewport proof cache: source lineage and negative ownership regressions."""
from types import SimpleNamespace
import fitz
import pb_physical_opening_viewport_scope_authority as scope
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer


def _producer():
    document = fitz.open()
    page = document.new_page(width=700, height=500)
    page.draw_rect(fitz.Rect(20, 20, 300, 320))
    page.draw_rect(fitz.Rect(300, 20, 600, 320))
    page.insert_text((70, 300), "GROUND FLOOR PLAN")
    page.insert_text((360, 300), "FRONT ELEVATION")
    payload = document.tobytes()
    document.close()
    source = SourceVisibilityProducer(
        producer_method="gpt1-viewport-source-proof-cache", producer_version="1"
    )
    published = source.ingest_native_pdf_bytes(
        document_id="source-doc", source_bytes=payload, source_locator="memory://source"
    )
    return source, published


def _scope(source, published, *, candidate="floor", segment=(50, 100, 150, 100), snapshot=None):
    return scope.classify_opening_candidate_viewport_scopes(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id, page_id="1",
        snapshot_id=snapshot or published.snapshot.snapshot_id,
        candidates=(SimpleNamespace(candidate_id=candidate, source_observation_ids=("source-ink",)),),
        records=(SimpleNamespace(observation_id="source-ink", geometry=segment),),
    )


def test_immutable_source_page_reuses_proof_but_each_candidate_is_reclassified(monkeypatch):
    source, published = _producer()
    original = scope._authenticated_viewports
    calls = []
    def counted(*args, **kwargs):
        calls.append(None)
        return original(*args, **kwargs)
    monkeypatch.setattr(scope, "_authenticated_viewports", counted)
    plan = _scope(source, published, candidate="plan")
    replay = _scope(source, published, candidate="plan")
    elevation = _scope(source, published, candidate="elev", segment=(350,100,450,100))
    straddle = _scope(source, published, candidate="straddle", segment=(250,100,350,100))
    assert len(calls) == 1
    assert plan == replay
    assert plan.decisions["plan"].scope == scope.IN_AUTHENTICATED_FLOOR_PLAN
    assert elevation.decisions["elev"].scope == scope.IN_AUTHENTICATED_NON_PLAN
    assert straddle.decisions["straddle"].scope == scope.AMBIGUOUS_AUTHENTICATED_OWNERSHIP
    assert not elevation.decisions["elev"].promotable
    assert not straddle.decisions["straddle"].promotable


def test_cache_cannot_override_original_snapshot_or_sha_mismatch():
    source, published = _producer()
    first = _scope(source, published)
    wrong = _scope(source, published, snapshot="foreign-snapshot")
    assert wrong.status is EvidenceResolutionStatus.ABSTAINED
    assert wrong.reason_codes == (scope.OPENING_VIEWPORT_SCOPE_SNAPSHOT_MISMATCH,)
    original = source._producer._store.source_bytes_by_revision[published.revision.revision_id]
    try:
        source._producer._store.source_bytes_by_revision[published.revision.revision_id] = b"tampered"
        result = _scope(source, published)
        assert result.status is EvidenceResolutionStatus.ABSTAINED
        assert result.reason_codes == (scope.OPENING_VIEWPORT_SCOPE_SOURCE_UNAVAILABLE,)
    finally:
        source._producer._store.source_bytes_by_revision[published.revision.revision_id] = original
    assert _scope(source, published) == first


def test_other_producer_has_independent_immutable_viewport_proof():
    source, published = _producer()
    other, other_published = _producer()
    assert _scope(source, published).status is EvidenceResolutionStatus.CORROBORATED
    assert _scope(other, other_published).status is EvidenceResolutionStatus.CORROBORATED
    assert len(scope._VIEWPORT_PROOF_CACHE[source]) == 1
    assert len(scope._VIEWPORT_PROOF_CACHE[other]) == 1
    assert scope._VIEWPORT_PROOF_CACHE[source] is not scope._VIEWPORT_PROOF_CACHE[other]
