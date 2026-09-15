from __future__ import annotations

from pb_native_fixture_label_evidence import count_standalone_chalkboard_spans


def _span(text: str, bbox: tuple[float, float, float, float] | None = None) -> dict:
    item = {"text": text}
    if bbox is not None:
        item["bbox"] = bbox
    return item


def _text_dict(*spans: dict) -> dict:
    return {"blocks": [{"lines": [{"spans": list(spans)}]}]}


def test_counts_two_independent_native_chalkboard_labels() -> None:
    text_dict = _text_dict(
        _span("Chalkboard", (10.0, 20.0, 50.0, 30.0)),
        _span("Chalkboard", (110.0, 20.0, 150.0, 30.0)),
    )

    assert count_standalone_chalkboard_spans(text_dict) == 2


def test_deduplicates_duplicate_rendering_at_same_bbox() -> None:
    text_dict = _text_dict(
        _span("Chalkboard", (10.0, 20.0, 50.0, 30.0)),
        _span("Chalkboard", (10.0, 20.0, 50.0, 30.0)),
    )

    assert count_standalone_chalkboard_spans(text_dict) == 1


def test_prose_containing_blackboard_word_is_not_an_instance() -> None:
    text_dict = _text_dict(
        _span(
            "painted surface to be used as the black board",
            (10.0, 20.0, 250.0, 30.0),
        )
    )

    assert count_standalone_chalkboard_spans(text_dict) == 0


def test_mixed_prose_and_one_standalone_label_counts_only_label() -> None:
    text_dict = _text_dict(
        _span("NOTE: provide chalkboard finish to wall", (10.0, 20.0, 220.0, 30.0)),
        _span("Blackboard", (10.0, 50.0, 60.0, 60.0)),
    )

    assert count_standalone_chalkboard_spans(text_dict) == 1


def test_dimensioned_chalkboard_note_is_not_a_standalone_instance() -> None:
    text_dict = _text_dict(
        _span("Chalkboard 2400 x 1200", (10.0, 20.0, 160.0, 30.0))
    )

    assert count_standalone_chalkboard_spans(text_dict) == 0


def test_conservative_identity_normalization() -> None:
    text_dict = _text_dict(
        _span("  CHALKBOARD:  ", (10.0, 20.0, 70.0, 30.0)),
        _span("Black board.", (100.0, 20.0, 160.0, 30.0)),
    )

    assert count_standalone_chalkboard_spans(text_dict) == 2


def test_malformed_text_dict_fails_closed() -> None:
    assert count_standalone_chalkboard_spans({}) == 0
    assert count_standalone_chalkboard_spans({"blocks": None}) == 0
    assert count_standalone_chalkboard_spans({"blocks": [{"lines": None}]}) == 0


def test_same_label_without_bbox_is_counted_once_not_multiplied() -> None:
    text_dict = _text_dict(_span("Chalkboard"), _span("Chalkboard"))

    assert count_standalone_chalkboard_spans(text_dict) == 1


def test_different_label_bboxes_remain_distinct_despite_same_text() -> None:
    text_dict = {
        "blocks": [
            {"lines": [{"spans": [_span("Blackboard", (1.0, 1.0, 5.0, 2.0))]}]},
            {"lines": [{"spans": [_span("Blackboard", (20.0, 1.0, 24.0, 2.0))]}]},
        ]
    }

    assert count_standalone_chalkboard_spans(text_dict) == 2
