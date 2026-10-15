"""Synthetic original-word provenance and no-commercial-promotion regression suite."""
from __future__ import annotations

from types import SimpleNamespace
from tools.diag_gpt1_original_area_line_first_failure import inspect_source_area_lines
import pytest

SHA = "a" * 64


def word(text, n, *, trusted=True, block=2, line=1, part="native:page3", bbox=None, reason=()):
    return SimpleNamespace(text=text, observation_id=f"ob-{block}-{line}-{n}",
        page_id="3", source_partition_id=part, block_no=block,
        line_no=line, word_no=n, trusted=trusted, reason_codes=reason,
        bbox=bbox or (5.0 + 12 * n, 10., 15.0 + 12 * n, 18.))


def view(vid="source-view", kind="floor_plan", bbox=(0., 0., 100., 100.)):
    return SimpleNamespace(view_id=vid, view_type=kind, bounding_box=bbox)


def run(words, views=(view(),)):
    return inspect_source_area_lines(words, views, source_sha256=SHA,
        revision_id="original-r1", snapshot_id="snapshot-r1", page_id="3")


def assert_shadow_only(output):
    assert output["diagnostic_only"] is True
    assert output["published_quantities"] == []
    assert output["customer_rows"] == []
    assert output["benchmark_scored"] is False
    for row in output["literal_area_candidates"]:
        assert row["source_physical_room_face_authenticated"] is False
        assert row["room_area_measurement_authority_granted"] is False
        assert row["canonical_floor_metric_authority_granted"] is False
        assert row["quantity_evidence_published"] is False


def test_complete_trusted_line_does_not_create_area_quantity():
    out = run([word("12.64", 0), word("m²", 1)])
    assert out["literal_area_candidate_count"] == 1
    row = out["literal_area_candidates"][0]
    assert row["source_text_integrity_all_words"]
    assert row["first_unclosed_gate"] == "source_physical_room_face_and_exact_area_line_owner_unproven"
    assert row["candidate_printed_area_m2_not_measurement"] == 12.64
    assert_shadow_only(out)


def test_untrusted_glyph_remains_first_failure():
    out = run([word("12.64", 0), word("m²", 1, trusted=False, reason=("glyph_unresolved",))])
    assert out["literal_area_candidates"][0]["first_unclosed_gate"] == "source_area_literal_word_integrity_unavailable"
    assert "glyph_unresolved" in out["literal_area_candidates"][0]["source_text_reason_codes"]
    assert_shadow_only(out)


def test_schedule_and_competing_scopes_not_promoted():
    words = [word("12.64", 0), word("m²", 1)]
    for scopes in ((view("schedule", "schedule"),),
                   (view(), view("conflict", "legend"))):
        out = run(words, scopes)
        assert out["literal_area_candidates"][0]["first_unclosed_gate"] == "source_floor_plan_viewport_unavailable_or_ambiguous"
        assert_shadow_only(out)


def test_separate_source_blocks_never_fused():
    out = run([word("12.64", 0), word("m²", 1, block=3)])
    assert out["literal_area_candidate_count"] == 0
    assert_shadow_only(out)


def test_unrelated_870_door_2100_height_and_labels_not_measured():
    out = run([word("870", 0), word("2100", 1, line=2),
               word("BED", 2, block=4), word("1", 3, block=4),
               word("11.88", 0, block=8), word("m2", 1, block=8)])
    assert out["literal_area_candidate_count"] == 1
    assert out["literal_area_candidates"][0]["literal_original_text"] == "11.88 m2"
    assert_shadow_only(out)


def test_nonconsecutive_ordinals_and_replayed_ids_fail_closed():
    out = run([word("12.64", 0), word("m²", 2)])
    assert out["literal_area_candidates"][0]["first_unclosed_gate"] == "source_native_word_ordinal_conflict"
    with pytest.raises(ValueError, match="duplicate"):
        run([word("12.64", 0), word("m²", 0)])


def test_foreign_page_invalid_bbox_and_sha_denied():
    with pytest.raises(ValueError, match="foreign_page"):
        run([SimpleNamespace(**{**vars(word("12.64", 0)), "page_id": "2"})])
    with pytest.raises(ValueError, match="bbox"):
        run([word("12.64", 0, bbox=(0., 0., 0., 1.))])
    with pytest.raises(ValueError, match="identity"):
        inspect_source_area_lines([], [], source_sha256="unverified",
            revision_id="r", snapshot_id="s", page_id="3")


def test_area_outside_and_ambiguous_plan_ownership():
    tokens = [word("11.70", 0), word("m²", 1)]
    out = run(tokens, (view(bbox=(100., 100., 200., 200.)),))
    assert out["literal_area_candidates"][0]["containing_source_floor_plan_viewport_ids"] == []
    assert out["literal_area_candidates"][0]["first_unclosed_gate"] == "source_floor_plan_viewport_unavailable_or_ambiguous"
    out = run(tokens, (view("a"), view("b")))
    assert out["literal_area_candidates"][0]["containing_source_floor_plan_viewport_ids"] == ["a", "b"]
    assert_shadow_only(out)


def test_input_order_translation_unrelated_content_preserve_gate():
    words = [word("12.64", 0), word("m²", 1)]
    before = run(words)
    assert run(list(reversed(words))) == before
    translated = [SimpleNamespace(**{**vars(w), "bbox": tuple(x + (
                  50 if i % 2 == 0 else 60) for i, x in enumerate(w.bbox))}) for w in words]
    out = run(translated, (view(bbox=(50., 60., 150., 160.)),))
    assert out["literal_area_candidates"][0]["first_unclosed_gate"] == before["literal_area_candidates"][0]["first_unclosed_gate"]
    assert run(words + [word("FREEZER", 0, block=99)])["literal_area_candidates"] == before["literal_area_candidates"]
    assert_shadow_only(out)


def test_same_area_value_in_two_source_blocks_keeps_both():
    a = [word("12.64", 0), word("m²", 1)]
    b = [word("12.64", 0, block=15), word("m²", 1, block=15)]
    out = run(a + b)
    assert len(out["literal_area_candidates"]) == 2
    assert_shadow_only(out)


def test_unbounded_invalid_view_has_no_plan_owner():
    out = run([word("12.64", 0), word("m²", 1)], (view(bbox=None),))
    assert out["literal_area_candidates"][0]["first_unclosed_gate"] == "source_floor_plan_viewport_unavailable_or_ambiguous"


def test_source_room_labels_are_independent_corroborated_candidates_not_area_owners():
    # Existing generic room-label language is used, not text proximity to m².
    words = [
        word("BED", 0, block=16), word("1", 1, block=16),
        word("12.64", 0, block=17), word("m²", 1, block=17),
    ]
    out = run(words)
    assert out["literal_area_candidate_count"] == 1
    assert out["literal_room_label_candidate_count"] == 1
    label = out["literal_room_label_candidates"][0]
    assert label["literal_original_room_label"] == "BED 1"
    assert label["source_text_integrity_all_words"] is True
    assert label["first_unclosed_gate"] == "source_room_face_and_exact_label_owner_unproven"
    assert label["area_annotation_to_label_binding_granted"] is False
    assert out["literal_area_candidates"][0]["source_physical_room_face_authenticated"] is False
    assert_shadow_only(out)


def test_untrusted_or_nonplan_original_room_label_remains_unowned():
    words = [word("BED", 0, block=16), word("2", 1, block=16, trusted=False)]
    for views, reason in (
        ((view(),), "source_room_label_text_integrity_unavailable"),
        ((view("legend", "legend"),), "source_room_label_text_integrity_unavailable"),
    ):
        out = run(words, views)
        assert out["literal_room_label_candidate_count"] == 1
        assert out["literal_room_label_candidates"][0]["first_unclosed_gate"] == reason
        assert_shadow_only(out)
    fully_trusted = [word("BED", 0, block=16), word("2", 1, block=16)]
    out = run(fully_trusted, (view("legend", "legend"),))
    assert out["literal_room_label_candidates"][0]["first_unclosed_gate"] == (
        "source_room_label_plan_viewport_unavailable_or_ambiguous")
    assert out["published_quantities"] == []


def test_room_label_and_area_lines_do_not_cross_partition_or_replay_join():
    data = [word("BED", 0, block=6, part="partition-A"),
            word("3", 1, block=6, part="partition-A"),
            word("11.70", 0, block=4, part="partition-B"),
            word("m²", 1, block=4, part="partition-B")]
    out = run(data)
    assert out["literal_room_label_candidate_count"] == 1
    assert out["literal_area_candidate_count"] == 1
    assert out["literal_room_label_candidates"][0]["source_partition_id"] != (
        out["literal_area_candidates"][0]["source_partition_id"])
    assert out["literal_room_label_candidates"][0]["area_annotation_to_label_binding_granted"] is False
    assert_shadow_only(out)
