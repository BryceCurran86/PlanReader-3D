"""Bounded immutable G17 source render pair cache: source identity is required."""
from __future__ import annotations

from hashlib import sha256
from types import SimpleNamespace as Obj

import pytest

from pb_source_visibility_authority import SourceVisibilityProducer
from pb_opening_local_g17_wall_shadow import build_opening_local_g17_wall_shadow
from pb_source_observation_authority import ObservationSelector


def fixture():
    producer = SourceVisibilityProducer(producer_method="g17-cache-test", producer_version="1")
    source = b"one-original-immutable-pdf"
    digest = sha256(source).hexdigest()
    revision = "original-revision"
    snapshot = "original-snapshot"
    published = Obj(
        revision=Obj(document_id="doc", revision_id=revision, source_sha256=digest),
        snapshot=Obj(snapshot_id=snapshot),
    )
    producer._published_by_revision[revision] = published
    producer._producer._store.source_bytes_by_revision[revision] = source
    calls = []
    frame = Obj(rotation=0)
    parent = Obj(observation_id="immutable-page-parent")

    def render_native_page_png(**kw):
        calls.append((kw["page_id"], kw["images_only"] if "images_only" in kw else False))
        return (b"original-rgb-source" if kw.get("images_only") else b"original-rgb-full",
                parent, frame)

    producer._producer.render_native_page_png = render_native_page_png
    scope = dict(
        document_id="doc", revision_id=revision,
        source_sha256=digest, snapshot_id=snapshot,
        page_id="3", dpi=300,
    )
    return producer, scope, calls


def test_repeated_original_page_is_rendered_only_once_per_source_scope():
    producer, scope, calls = fixture()
    before = producer._original_g17_render_pair_shadow(**scope)
    after = producer._original_g17_render_pair_shadow(**scope)
    assert before is after
    assert calls == [("3", True), ("3", False)]
    assert len(producer._g17_original_render_pair_cache) == 1


def test_page_and_snapshot_change_never_borrow_cached_source():
    producer, scope, calls = fixture()
    producer._original_g17_render_pair_shadow(**scope)
    other_page = {**scope, "page_id": "4"}
    producer._original_g17_render_pair_shadow(**other_page)
    assert len(calls) == 4
    assert len(producer._g17_original_render_pair_cache) == 1
    producer._original_g17_render_pair_shadow(**scope)
    assert len(calls) == 6
    foreign = {**scope, "snapshot_id": "stale"}
    with pytest.raises(ValueError, match="stale"):
        producer._original_g17_render_pair_shadow(**foreign)


def test_changed_original_pdf_bytes_fail_even_on_cache_hit():
    producer, scope, calls = fixture()
    producer._original_g17_render_pair_shadow(**scope)
    producer._producer._store.source_bytes_by_revision[scope["revision_id"]] = b"wrong"
    with pytest.raises(ValueError, match="SHA mismatch"):
        producer._original_g17_render_pair_shadow(**scope)
    assert len(calls) == 2


@pytest.mark.parametrize("bad", [0, -1, 300.0, "300", None, True])
def test_untrusted_dpi_is_rejected_before_source_render(bad):
    producer, scope, calls = fixture()
    with pytest.raises(ValueError, match="positive integer"):
        producer._original_g17_render_pair_shadow(**{**scope, "dpi": bad})
    assert calls == []


def test_differing_original_frames_refuse_cache_not_force_positive():
    producer, scope, calls = fixture()
    parent = Obj(observation_id="bad-other-page")
    source_method = producer._producer.render_native_page_png

    def mismatched(**kw):
        blob, current_parent, frame = source_method(**kw)
        if not kw.get("images_only"):
            current_parent = parent
        return blob, current_parent, frame

    producer._producer.render_native_page_png = mismatched
    producer._original_g17_render_pair_shadow(**scope)
    producer._original_g17_render_pair_shadow(**scope)
    assert len(calls) == 4
    assert producer._g17_original_render_pair_cache == {}


def test_default_opening_reader_signature_refuses_forged_cache_flag():
    source = SourceVisibilityProducer(producer_method="g17-cache-test", producer_version="1")
    selector = ObservationSelector("doc", "rev", "a" * 64, "snap", "id")
    with pytest.raises(TypeError, match="explicit bool"):
        build_opening_local_g17_wall_shadow(
            source, selector, original_ink_render_cache_shadow="enabled",
        )
