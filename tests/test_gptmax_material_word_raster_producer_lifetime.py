"""Regression: floor/ceiling material owners reuse the exact ordinary OCR proof.

These are source-neutral tests; original SHA/source/customer replay is a separate
release gate. No finish code, physical area or commercial row is inferred here.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import gc
from weakref import ref

import pytest

import pb_source_material_semantic_authority as material
from pb_raster_text_corroboration_authority import RasterTextCorroborationProducer
from pb_source_visibility_authority import SourceVisibilityProducer


def _source() -> SourceVisibilityProducer:
    return SourceVisibilityProducer(
        producer_method="gptmax-material-word-lifetime-test",
        producer_version="1",
    )


def _normal(source):
    return material.SourceMaterialSemanticProducer.from_source_visibility_producer(
        source
    )


def test_floor_and_ceiling_material_publishers_share_one_ordinary_source_word_proof():
    source = _source()
    floor = _normal(source)
    ceiling = material.SourceMaterialSemanticProducer.for_source_connected_original_rcp_plan_shadow(
        source, page_ids=("9",),
    )
    assert floor is not ceiling
    assert floor._raster is ceiling._raster
    assert floor._source is ceiling._source is source
    # Material results and scope ownership remain separate.
    assert floor._definition_results is not ceiling._definition_results
    assert floor._occurrence_results is not ceiling._occurrence_results
    assert floor._schedule_viewports is not ceiling._schedule_viewports


def test_ordinary_source_word_backend_is_selected_only_once(monkeypatch):
    source = _source()
    original = RasterTextCorroborationProducer.from_source_visibility_producer
    selected = []

    def counted(src):
        selected.append(src)
        return original(src)

    monkeypatch.setattr(
        RasterTextCorroborationProducer,
        "from_source_visibility_producer",
        staticmethod(counted),
    )
    floor = _normal(source)
    rcp = material.SourceMaterialSemanticProducer.for_source_connected_original_rcp_plan_shadow(
        source, page_ids=("9",),
    )
    schedule = material.SourceMaterialSemanticProducer.for_native_multirow_material_shadow(
        source
    )
    assert selected == [source]
    assert floor._raster is rcp._raster is schedule._raster
    assert floor._raster._backend is rcp._raster._backend


def test_different_producer_owned_sources_never_share_ocr_even_with_same_method():
    left = _source()
    right = _source()
    a = _normal(left)
    b = _normal(right)
    assert a._raster is not b._raster
    assert a._raster._source is left
    assert b._raster._source is right
    assert a._raster._source_producer is not b._raster._source_producer


def test_clip_only_plan_mode_remains_distinct_from_shared_ordinary_material_policy():
    source = _source()
    normal = _normal(source)
    plan = material.SourceMaterialSemanticProducer.for_physical_plan_view_shadow(
        source, page_ids=("7",),
    )
    assert plan._raster is normal._raster
    assert plan._raster._allow_clip_only_shadow is False
    assert plan._plan_raster is not normal._raster
    assert plan._plan_raster._source is source
    assert plan._plan_raster._allow_clip_only_shadow is True
    assert normal._plan_raster is None


def test_same_producer_reuses_positive_and_negative_outcome_storage_without_promotion():
    source = _source()
    floor = _normal(source)
    selector_key = ("doc", "revision", "sha", "snapshot", "observation")
    negative = object()
    floor._raster._results[selector_key] = negative
    ceiling = material.SourceMaterialSemanticProducer.for_source_connected_original_rcp_plan_shadow(
        source, page_ids=("9",),
    )
    assert ceiling._raster._results[selector_key] is negative
    assert ceiling._occurrence_results == {}
    assert ceiling._definition_results == {}
    # This is only a memo identity regression. publish() still rechecks
    # immutable source bytes before returning a previously cached outcome.


def test_poisoned_foreign_source_entry_is_rejected_not_silently_replaced():
    source = _source()
    foreign = _normal(_source())
    material._ORDINARY_WORD_RASTER_BY_SOURCE[source] = ref(foreign._raster)
    with pytest.raises(ValueError, match="source_policy_conflict"):
        _normal(source)


def test_poisoned_clip_only_entry_is_rejected():
    source = _source()
    clip = RasterTextCorroborationProducer.for_physical_plan_view_shadow(source)
    material._ORDINARY_WORD_RASTER_BY_SOURCE[source] = ref(clip)
    with pytest.raises(ValueError, match="source_policy_conflict"):
        _normal(source)


def test_poisoned_original_observation_producer_entry_is_rejected():
    source = _source()
    first = _normal(source)
    first._raster._source_producer = object()
    with pytest.raises(ValueError, match="source_policy_conflict"):
        _normal(source)


def test_material_raster_memo_never_keeps_source_alive_by_itself():
    source = _source()
    producer = _normal(source)
    raster_weak = ref(producer._raster)
    source_weak = ref(source)
    del producer
    del source
    gc.collect()
    assert raster_weak() is None
    assert source_weak() is None


def test_parallel_material_constructors_do_not_select_multiple_backends(monkeypatch):
    source = _source()
    original = RasterTextCorroborationProducer.from_source_visibility_producer
    selected = []

    def counted(src):
        selected.append(src)
        return original(src)

    monkeypatch.setattr(
        RasterTextCorroborationProducer,
        "from_source_visibility_producer",
        staticmethod(counted),
    )

    with ThreadPoolExecutor(max_workers=8) as pool:
        producers = list(pool.map(lambda _: _normal(source), range(24)))
    assert selected == [source]
    assert len({id(p._raster) for p in producers}) == 1


def test_unowned_source_object_cannot_be_material_authority():
    with pytest.raises(TypeError, match="producer-owned"):
        _normal(object())
