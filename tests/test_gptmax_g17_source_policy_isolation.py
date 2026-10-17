"""Opt-in G17 policy is not silently an ordinary cached page replay."""
from __future__ import annotations

from types import SimpleNamespace as Record

import pytest

from pb_source_visibility_authority import SourceVisibilityProducer


def source():
    v=SourceVisibilityProducer(producer_method="g17-policy-reuse",producer_version="1")
    v._published_by_revision["rev"]=Record(
        revision=Record(revision_id="rev", document_id="source-document"),
        coverage=Record(decoded_pages=(3,4),failed_pages=()),
    )
    v._producer.current_revision_id = lambda document_id: (
        "rev" if document_id == "source-document" else None
    )
    return v


def test_prior_ordinary_source_capture_cannot_masquerade_as_shadow(monkeypatch):
    src=source()
    src._raster_visibility_attempted_pages.add(("rev","3"))
    monkeypatch.setattr(src,"_augment_with_raster_visible_segments_source_impl",
                        lambda *args,**kwargs: pytest.fail("must abstain BEFORE production"))
    with pytest.raises(RuntimeError,match="prior raster page capture"):
        src.augment_with_unmeasured_g17_flanks_source_shadow("rev",page_ids=("3",))
    assert src._raster_visibility_attempted_pages=={("rev","3")}


def test_foreign_page_attempt_may_not_block_own_fresh_page(monkeypatch):
    src=source()
    src._raster_visibility_attempted_pages.add(("rev","4"))
    params=[]
    mark=Record(snapshot=Record(snapshot_id="fresh"))
    def own_capture(revision,*,page_ids,include_unmeasured_ink_closed_flanks_shadow):
        params.append((revision,page_ids,include_unmeasured_ink_closed_flanks_shadow))
        return mark
    monkeypatch.setattr(src,"_augment_with_raster_visible_segments_source_impl",
                        own_capture)
    assert src.augment_with_unmeasured_g17_flanks_source_shadow("rev",page_ids=("3",)) is mark
    assert params==[("rev",("3",),True)]


@pytest.mark.parametrize("pages",[None,(),("3","4"),("03",),(3,),("",),("0",),("-1",),("3","3"),[" 3 "],{"3"}, "3"])
def test_shadow_is_one_original_canonical_page_only(pages):
    src=source()
    with pytest.raises(ValueError,match="one canonical source page"):
        src.augment_with_unmeasured_g17_flanks_source_shadow("rev",page_ids=pages)


def test_missing_or_failed_source_page_fails_closed():
    src=source()
    with pytest.raises(ValueError):
        src.augment_with_unmeasured_g17_flanks_source_shadow("missing",page_ids=("3",))
    with pytest.raises(ValueError):
        src.augment_with_unmeasured_g17_flanks_source_shadow("rev",page_ids=("5",))
    src._published_by_revision["rev"].coverage.failed_pages=(3,)
    with pytest.raises(ValueError):
        src.augment_with_unmeasured_g17_flanks_source_shadow("rev",page_ids=("3",))


def test_explicit_shadow_never_changes_historical_public_signature():
    import inspect
    from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
    assert set(inspect.signature(SourceVisibilityProducer.augment_with_raster_visible_segments).parameters)=={
        "self","revision_id","page_ids"}
    assert set(inspect.signature(PhysicalWallCandidateProducer.from_source_visibility_producer).parameters)=={
        "source_visibility_producer","page_ids"}


def test_old_original_revision_cannot_publish_new_g17_wall_source(monkeypatch):
    src=source()
    src._producer.current_revision_id=lambda document_id: "newer-revision"
    monkeypatch.setattr(src,"_augment_with_raster_visible_segments_source_impl",
                        lambda *args,**kwargs: pytest.fail("stale source never renders"))
    with pytest.raises(ValueError,match="superseded"):
        src.augment_with_unmeasured_g17_flanks_source_shadow(
            "rev",page_ids=("3",))
    assert not src._raster_visibility_attempted_pages


def test_original_source_without_current_revision_authority_is_not_captured(monkeypatch):
    src=source()
    src._producer.current_revision_id=lambda document_id: None
    with pytest.raises(ValueError,match="unauthenticated"):
        src.augment_with_unmeasured_g17_flanks_source_shadow(
            "rev",page_ids=("3",))
    assert not src._raster_visibility_attempted_pages


def test_exact_current_original_revision_can_continue_to_source_capture(monkeypatch):
    src=source()
    calls=[]
    def genuine(revision_id, *, page_ids, include_unmeasured_ink_closed_flanks_shadow):
        calls.append((revision_id,page_ids,include_unmeasured_ink_closed_flanks_shadow))
        return Record(revision=src._published_by_revision["rev"].revision)
    monkeypatch.setattr(src,"_augment_with_raster_visible_segments_source_impl",genuine)
    result=src.augment_with_unmeasured_g17_flanks_source_shadow("rev",page_ids=("3",))
    assert result.revision.revision_id=="rev"
    assert calls==[("rev",("3",),True)]
