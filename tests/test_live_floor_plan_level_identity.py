from __future__ import annotations

from types import SimpleNamespace

import pb_live_floor_plan_level_identity as level_identity
from pb_live_floor_plan_level_identity import (
    collect_source_owned_floor_plan_levels,
    enrich_live_wall_level_ownership,
)


SHA = "b" * 64


class _FakeDoc:
    def __init__(self, page_count: int = 2) -> None:
        self._pages = [object() for _ in range(page_count)]

    def __len__(self) -> int:
        return len(self._pages)

    def __getitem__(self, index: int):
        return self._pages[index]


def _viewport(
    *,
    view_id: str,
    label: str,
    page_number: int = 1,
    bbox=(20.0, 20.0, 300.0, 220.0),
):
    return SimpleNamespace(
        view_id=view_id,
        label=label,
        page_number=page_number,
        bounding_box=bbox,
        confidence=0.99,
    )


def test_explicit_ground_floor_viewport_mints_source_owned_level(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        level_identity,
        "authoritative_floor_plan_viewports",
        lambda page, *, page_number: [
            _viewport(
                view_id="floor-plan-ground",
                label="GROUND FLOOR PLAN",
                page_number=page_number,
            )
        ],
    )

    records = collect_source_owned_floor_plan_levels(
        _FakeDoc(page_count=1),
        page_indices=(0,),
        source_sha256=SHA,
    )

    assert len(records) == 1
    record = records[0]
    assert record.is_source_owned is True
    assert record.level_label == "GROUND FLOOR PLAN"
    assert record.normalized_level_label == "ground_floor"
    assert record.level_index == 0
    assert record.source_page == 1
    assert record.source_viewport_id == "floor-plan-ground"
    assert record.cross_view_identity_resolved is False


def test_same_named_views_remain_distinct_until_cross_view_equivalence(
    monkeypatch,
) -> None:
    def fake_viewports(page, *, page_number):
        return [
            _viewport(
                view_id=f"ground-{page_number}",
                label="GROUND FLOOR PLAN",
                page_number=page_number,
            )
        ]

    monkeypatch.setattr(
        level_identity,
        "authoritative_floor_plan_viewports",
        fake_viewports,
    )

    records = collect_source_owned_floor_plan_levels(
        _FakeDoc(page_count=2),
        page_indices=(0, 1),
        source_sha256=SHA,
    )

    assert len(records) == 2
    assert {record.normalized_level_label for record in records} == {
        "ground_floor"
    }
    assert len({record.canonical_level_id for record in records}) == 2
    assert all(
        record.cross_view_identity_resolved is False for record in records
    )


def test_roof_or_unlabelled_plan_does_not_mint_level(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        level_identity,
        "authoritative_floor_plan_viewports",
        lambda page, *, page_number: [
            _viewport(
                view_id="roof",
                label="ROOF PLAN",
                page_number=page_number,
            ),
            _viewport(
                view_id="plan-unlabelled",
                label="PROPOSED PLAN",
                page_number=page_number,
            ),
        ],
    )

    records = collect_source_owned_floor_plan_levels(
        _FakeDoc(page_count=1),
        page_indices=(0,),
        source_sha256=SHA,
    )

    assert records == ()


def test_wall_level_enrichment_uses_only_one_authenticated_viewport_level(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        level_identity,
        "authoritative_floor_plan_viewports",
        lambda page, *, page_number: [
            _viewport(
                view_id="first-floor-view",
                label="FIRST FLOOR PLAN",
                page_number=page_number,
            )
        ],
    )
    records = collect_source_owned_floor_plan_levels(
        _FakeDoc(page_count=1),
        page_indices=(0,),
        source_sha256=SHA,
    )
    assert len(records) == 1
    level = records[0]

    wall = {
        "canonical_wall_id": "wall-1",
        "level_ids": [],
        "plan_members": [
            {
                "wall_candidate_id": "candidate-1",
                "viewport_id": "first-floor-view",
            },
            {
                "wall_candidate_id": "candidate-2",
                "viewport_id": "first-floor-view",
            },
        ],
    }

    enriched = enrich_live_wall_level_ownership(
        (wall,),
        levels=records,
    )

    assert len(enriched) == 1
    assert enriched[0]["level_ids"] == [level.canonical_level_id]
    ownership = enriched[0]["level_ownership"]
    assert ownership["authority"] == (
        "source_owned_floor_plan_viewport_label"
    )
    assert ownership["normalized_level_label"] == "first_floor"
    assert ownership["level_index"] == 1
    assert ownership["source_viewport_id"] == "first-floor-view"
    assert ownership["cross_view_identity_resolved"] is False


def test_unknown_or_mixed_viewport_wall_stays_unassigned(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        level_identity,
        "authoritative_floor_plan_viewports",
        lambda page, *, page_number: [
            _viewport(
                view_id="ground-view",
                label="GROUND FLOOR PLAN",
                page_number=page_number,
            )
        ],
    )
    records = collect_source_owned_floor_plan_levels(
        _FakeDoc(page_count=1),
        page_indices=(0,),
        source_sha256=SHA,
    )

    wall = {
        "canonical_wall_id": "wall-1",
        "level_ids": [],
        "plan_members": [
            {
                "wall_candidate_id": "candidate-a",
                "viewport_id": "ground-view",
            },
            {
                "wall_candidate_id": "candidate-b",
                "viewport_id": "unknown-view",
            },
        ],
    }

    enriched = enrich_live_wall_level_ownership(
        (wall,),
        levels=records,
    )

    assert enriched[0]["level_ids"] == []
    assert "level_ownership" not in enriched[0]


def test_invalid_source_sha_fails_closed(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        level_identity,
        "authoritative_floor_plan_viewports",
        lambda page, *, page_number: [
            _viewport(
                view_id="ground-view",
                label="GROUND FLOOR PLAN",
                page_number=page_number,
            )
        ],
    )

    records = collect_source_owned_floor_plan_levels(
        _FakeDoc(page_count=1),
        page_indices=(0,),
        source_sha256="not-a-sha",
    )

    assert records == ()
