"""Source-native cap-cache key must match unchanged canonical SHA semantics."""
import pytest

from pb_migration_contracts import stable_contract_id
from pb_source_visibility_authority import _native_dimension_component_inputs_fingerprint


def _source():
    return (
        {
            "source-segment-a": (0.0, -0.0, 14.25, 2.0),
            "source-segment-b": (10.5, 4.25, 19.75, 4.25),
        },
        [
            {"id": "word-one", "text": "2,500", "bbox": (0., -0., 9., 2.5), "axis": (1., 0.)},
            {"id": "word-ü", "text": "250", "bbox": (1., 5., 3., 6.), "axis": (-1., 0.)},
        ],
    )


def _legacy(segments, words):
    return stable_contract_id("native_dimension_component_inputs", {
        "segments": tuple(sorted(segments.items())),
        "words": tuple(sorted(
            (w["id"], w["text"], tuple(w["bbox"]), tuple(w["axis"]))
            for w in words
        )),
    })


def test_native_cap_page_cache_key_is_byte_identical_to_original_canonical_id():
    segments, words = _source()
    assert _native_dimension_component_inputs_fingerprint(
        segments=segments, words=words,
    ) == _legacy(segments, words)
    assert _native_dimension_component_inputs_fingerprint(
        segments=dict(reversed(tuple(segments.items()))), words=list(reversed(words)),
    ) == _legacy(segments, words)


@pytest.mark.parametrize("changed", [
    "segment", "native_text", "native_axis", "native_bbox", "signed_zero",
])
def test_original_native_source_changed_receipt_cannot_reuse_cache_identity(changed):
    segments, words = _source()
    old = _native_dimension_component_inputs_fingerprint(segments=segments, words=words)
    if changed == "segment":
        segments["source-segment-b"] = (10.5, 4.25, 19.76, 4.25)
    if changed == "native_text":
        words[0]["text"] = "2,501"
    if changed == "native_axis":
        words[0]["axis"] = (0., 1.)
    if changed == "native_bbox":
        words[0]["bbox"] = (0., -0., 9.1, 2.5)
    if changed == "signed_zero":
        segments["source-segment-a"] = (0., 0., 14.25, 2.)
    changed_key = _native_dimension_component_inputs_fingerprint(
        segments=segments, words=words,
    )
    assert changed_key != old
    assert changed_key == _legacy(segments, words)


def test_nonfinite_original_geometry_never_authenticates_cached_source():
    segments, words = _source()
    segments["source-segment-a"] = (0., float("nan"), 10., 10.)
    with pytest.raises(ValueError):
        _native_dimension_component_inputs_fingerprint(
            segments=segments, words=words,
        )
