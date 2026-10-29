"""Original native PDF page scope is an all-or-nothing source authority input.

No private originals, benchmark gold, scale/geometry promotion or customer rows.
"""
from __future__ import annotations


import fitz
import pytest

import pb_live_physical_net_wall_integration as live


@pytest.mark.parametrize("pages,expected", (
    (None, (0, 1, 2)),
    ((0,), (0,)),
    ([2, 0, 1], (0, 1, 2)),
    ((2, 1, 2, 0), (0, 1, 2)),
))
def test_exact_original_source_page_scope_preserves_valid_inputs(pages, expected):
    before = tuple(pages) if pages is not None else None
    assert live._selected_page_indices(3, pages) == expected
    assert (tuple(pages) if pages is not None else None) == before


@pytest.mark.parametrize("pages", (
    (), [],
    (True,), (False,), (0, True), [1, False],
    (0, 1.0), (0, "1"), (0, None),
    (0, -1), (0, 3), (0, 10**400),
    (0, float("nan")), (0, float("inf")),
    (0, (1,)), (0, object()),
    "0", range(2), {0, 1},
))
def test_original_source_scope_rejects_entire_malformed_universe(pages):
    with pytest.raises(ValueError):
        live._selected_page_indices(3, pages)


def test_one_shot_page_universe_is_not_silently_consumed_or_repaired():
    pages = (i for i in (0, 1))
    with pytest.raises(ValueError):
        live._selected_page_indices(3, pages)
    # Refusal occurs before any item is consumed: a later source competitor
    # cannot disappear because the scope was exhausted in validation.
    assert tuple(pages) == (0, 1)


def test_real_original_source_scope_examples_are_not_rewritten():
    assert live._selected_page_indices(11, (6,)) == (6,)
    assert live._selected_page_indices(11, (10,)) == (10,)
    assert live._selected_page_indices(11, (6, 10)) == (6, 10)


def _generated_three_page_pdf(tmp_path):
    path = tmp_path / "native-three-page-scope.pdf"
    with fitz.open() as document:
        for _ in range(3):
            document.new_page(width=612, height=792)
        document.save(path)
    return path


@pytest.mark.parametrize("scope,invalid", (
    ("pages", (0, True)),
    ("topology_pages", (0, 3)),
    ("room_area_support_pages", (2, "1")),
    ("surface_semantic_pages", (2, -1)),
))
def test_real_pdf_entrypoint_abstains_before_source_producer_on_bad_scope(
    tmp_path, monkeypatch, scope, invalid
):
    pdf = _generated_three_page_pdf(tmp_path)
    def source_must_not_start(*args, **kwargs):
        raise AssertionError("invalid source-page universe reached original producer")
    monkeypatch.setattr(live, "SourceVisibilityProducer", source_must_not_start)
    scopes = {
        "pages": (0,),
        "topology_pages": (0,),
        "room_area_support_pages": (1,),
        "surface_semantic_pages": (2,),
    }
    scopes[scope] = invalid
    with pytest.raises(ValueError):
        live.collect_live_physical_net_wall_claim(pdf, **scopes)


def test_real_pdf_entrypoint_valid_all_scope_types_reach_original_producer(
    tmp_path, monkeypatch
):
    pdf = _generated_three_page_pdf(tmp_path)
    def source_started(*args, **kwargs):
        raise RuntimeError("native_source_producer_started")
    monkeypatch.setattr(live, "SourceVisibilityProducer", source_started)
    with pytest.raises(RuntimeError, match="native_source_producer_started"):
        live.collect_live_physical_net_wall_claim(
            pdf,
            pages=(1, 0, 1),
            topology_pages=(0,),
            room_area_support_pages=(2,),
            surface_semantic_pages=(2,),
        )


def test_source_scope_is_deterministic_for_input_order_and_duplicate_replay():
    cases = ((2, 0, 1), (1, 2, 0), (0, 1, 2, 1), [1, 0, 2])
    assert all(live._selected_page_indices(3, case) == (0, 1, 2) for case in cases)
