"""Explicit legend word recognition keeps ordinary and clip policies separate."""

import pytest

import pb_raster_text_corroboration_authority as raster
import pb_source_material_semantic_authority as material
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_physical_plan_word_recognition_shadow import _case
from tests.test_raster_text_corroboration_authority_v1 import _Setup, _both, _pdf


def _legend(monkeypatch, **kwargs):
    setup, ordinary, selector, calls = _case(monkeypatch, shadow=False, **kwargs)
    producer = material._ordinary_source_word_raster(
        setup.svp, native_word_recognition_shadow=True,
    )
    return setup, ordinary, producer, selector, calls


def test_legend_word_mode_uses_two_independent_recognition_views(monkeypatch):
    setup, ordinary, producer, selector, calls = _legend(monkeypatch)
    result = producer.publish(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert [(row["dpi"], row["detect"]) for row in calls] == [(300, False), (450, False)]
    assert producer._allow_clip_only_shadow is False
    assert producer._recognize_native_words_shadow is True
    assert "native-word-recognition-shadow:detect=False" in result.record.backend_version
    calls.clear()
    default = ordinary.publish(selector)
    assert default.status is EvidenceResolutionStatus.CORROBORATED
    assert [(row["dpi"], row["detect"]) for row in calls] == [(300, True), (450, True)]
    assert default.record.record_id != result.record.record_id
    assert material._ordinary_source_word_raster(
        setup.svp, native_word_recognition_shadow=True,
    ) is producer


def test_material_plan_mode_wires_legend_recognition_without_changing_default(monkeypatch):
    setup, _ordinary, selector, calls = _case(monkeypatch, shadow=False)
    default = material.SourceMaterialSemanticProducer.from_source_visibility_producer(setup.svp)
    plan = material.SourceMaterialSemanticProducer.for_physical_plan_view_shadow(
        setup.svp, page_ids=("1",),
    )
    assert default._raster is not plan._raster
    assert default._raster._recognize_native_words_shadow is False
    assert plan._raster._recognize_native_words_shadow is True
    assert plan._raster._allow_clip_only_shadow is False
    assert plan._plan_raster._allow_clip_only_shadow is True
    assert plan._raster.publish(selector).status is EvidenceResolutionStatus.CORROBORATED
    assert all(row["detect"] is False for row in calls)
    assert material.SourceMaterialSemanticProducer.from_source_visibility_producer(
        setup.svp,
    )._raster is default._raster


def test_recognition_does_not_admit_clip_only_legend_receipts(monkeypatch):
    _setup, _ordinary, _producer, _selector, calls = _legend(monkeypatch)
    triangle = "q 10 100 m 250 100 l 10 190 l h W n 0 0 5 5 re f "
    setup = _Setup(_pdf(triangle + "BT /F1 14 Tf 40 120 Td (FT3) Tj ET 0 0 5 5 re f Q"), _both("FT3"))
    selector = setup.selector(setup.oid_of("FT3"))
    producer = raster.RasterTextCorroborationProducer.for_native_word_recognition_shadow(setup.svp)
    result = producer.publish(selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert raster.RASTER_TEXT_INTEGRITY_NOT_GLYPH_ONLY in result.reason_codes
    assert calls == []


@pytest.mark.parametrize("readings,reason", [
    ({300: (), 450: ()}, raster.RASTER_TEXT_NO_READING),
    ({300: ("FT3",), 450: ("FT2",)}, raster.RASTER_TEXT_VIEW_DISAGREEMENT),
    ({300: ("EPX",), 450: ("EPX",)}, raster.RASTER_TEXT_NATIVE_MISMATCH),
    ({300: ("FT3", "EPX"), 450: ("FT3", "EPX")}, raster.RASTER_TEXT_COMPETING_READINGS),
])
def test_legend_reading_failures_still_abstain(monkeypatch, readings, reason):
    _setup, _ordinary, producer, selector, calls = _legend(monkeypatch, readings=readings)
    result = producer.publish(selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert reason in result.reason_codes and result.record is None
    assert all(row["detect"] is False for row in calls)


def test_failed_legend_recognition_is_memoized_without_retry(monkeypatch):
    _setup, _ordinary, producer, selector, calls = _legend(monkeypatch, fail=True)
    first = producer.publish(selector)
    assert first == producer.publish(selector)
    assert raster.RASTER_TEXT_BACKEND_ERROR in first.reason_codes
    assert [(row["dpi"], row["detect"]) for row in calls] == [(300, False)]


def test_legend_mode_cannot_bypass_invalid_geometry_or_source(monkeypatch):
    setup, _ordinary, producer, selector, calls = _legend(monkeypatch, invalid_geometry=True)
    result = producer.publish(selector)
    assert raster.RASTER_TEXT_OCR_GEOMETRY_INVALID in result.reason_codes
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    setup.svp._producer._store.source_bytes_by_revision[selector.revision_id] = b"changed-source"
    calls.clear()
    result = producer.publish(selector)
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert calls == []


@pytest.mark.parametrize("value", [None, 1, "true"])
def test_mode_requires_explicit_boolean(monkeypatch, value):
    setup, _ordinary, _selector, _calls = _case(monkeypatch, shadow=False)
    with pytest.raises(ValueError, match="native_word_recognition_shadow_requires_explicit_bool"):
        material._ordinary_source_word_raster(setup.svp, native_word_recognition_shadow=value)


def test_cached_mode_policy_is_revalidated(monkeypatch):
    setup, _ordinary, producer, _selector, _calls = _legend(monkeypatch)
    producer._recognize_native_words_shadow = False
    with pytest.raises(ValueError, match="ordinary_material_word_raster_source_policy_conflict"):
        material._ordinary_source_word_raster(setup.svp, native_word_recognition_shadow=True)


def test_recognition_cache_is_source_owned_even_for_identical_source_bytes(monkeypatch):
    setup, _ordinary, first, _selector, _calls = _legend(monkeypatch)
    second_setup, _ordinary, second, _selector, _calls = _legend(monkeypatch)
    assert first is not second
    assert first._source is setup.svp and second._source is second_setup.svp
    attribute = material._ORDINARY_WORD_RASTER_CACHE_ATTR + "_native_word_recognition_shadow"
    setattr(setup.svp, attribute, second)
    with pytest.raises(ValueError, match="ordinary_material_word_raster_source_policy_conflict"):
        material._ordinary_source_word_raster(setup.svp, native_word_recognition_shadow=True)
