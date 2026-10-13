from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as S

import pytest

from tools import run_source_closed_project_handoff as handoff


def _plan_scope(*, positive: bool):
    return S(decisions=(
        S(page_index=0, classification="floor_plan" if positive else "unproven"),
        S(page_index=1, classification="not_floor_plan"),
    ))


@pytest.mark.parametrize("wrong", [None, True, -1, 3, "0"])
def test_source_scoped_floor_area_requires_exact_original_page(monkeypatch, tmp_path, wrong):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"synthetic original immutable bytes")
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda _path: ((0, 1), (), 3))
    import pb_source_floor_plan_page_scope as classifier
    monkeypatch.setattr(classifier, "source_floor_plan_topology_scope",
                        lambda _path, _pages: _plan_scope(positive=True))
    destination = tmp_path / "out"
    if wrong is None:
        # Missing page restriction is allowed: default production behaviour.
        assert handoff._validate_source_handoff_inputs(
            source, "test_project", 1, "floor_area"
        ) == "floor_area"
        return
    with pytest.raises((ValueError, RuntimeError)):
        handoff._generate_project_handoff_locked(
            pdf_path=source, project_id="test_project", workspace_id=1,
            output_dir=destination, family_group="floor_area",
            source_plan_page_index=wrong,
        )
    assert not (destination / "family_runs").exists()


def test_unproven_original_floor_plan_page_never_seals(monkeypatch, tmp_path):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"source-owned immutable bytes")
    import pb_source_floor_plan_page_scope as classifier
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda _path: ((0, 1), (), 3))
    monkeypatch.setattr(classifier, "source_floor_plan_topology_scope",
                        lambda _path, _pages: _plan_scope(positive=False))
    destination = tmp_path / "out"
    with pytest.raises(RuntimeError, match="source_positive_floor_plan_page_required"):
        handoff._generate_project_handoff_locked(
            pdf_path=source, project_id="test_project", workspace_id=1,
            output_dir=destination, family_group="floor_area",
            source_plan_page_index=0,
        )
    assert not (destination / "family_runs").exists()


def test_source_positive_page_runs_only_its_own_floor_area_without_finish_or_ceiling(
    monkeypatch, tmp_path,
):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"source-owned immutable bytes")
    import pb_source_floor_plan_page_scope as classifier
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda _path: ((0, 1), (), 3))
    monkeypatch.setattr(classifier, "source_floor_plan_topology_scope",
                        lambda _path, _pages: _plan_scope(positive=True))
    seen = []

    def collect(_pdf, **kwargs):
        seen.append(kwargs)
        return S(status="partial", reason_codes=(),
                 canonical_walls=(), canonical_openings=(),
                 canonical_rooms=(), canonical_floors=(),
                 canonical_ceilings=(), canonical_spaces=(),
                 room_area_quantity_evidence=(), floor_area_quantity_evidence=())

    monkeypatch.setattr(handoff, "collect_live_physical_net_wall_claim", collect)
    # This test isolates page-scope handoff control. The real floor publisher
    # correctly requires a sealed LivePhysicalNetWallClaim, not this fake.
    monkeypatch.setattr(handoff, "publish_live_floor_area_quantities", lambda _: ())
    destination = tmp_path / "scoped-output"
    result = handoff._generate_project_handoff_locked(
        pdf_path=source, project_id="test_project", workspace_id=1,
        output_dir=destination, family_group="floor_area",
        source_plan_page_index=0,
    )
    assert len(seen) == 1
    assert tuple(seen[0]["pages"]) == (0,)
    assert tuple(seen[0]["topology_pages"]) == (0,)
    assert tuple(seen[0]["surface_semantic_pages"]) == (0,)
    assert result["topology_pages"] == [1]
    assert result["execution_pages"] == [1]
    assert result["source_positive_partial_page"] == 1
    assert result["complete_project_handoff"] is False
    assert result["family_counts"]["floor_area"] == 0
    assert result["family_counts"]["floor_finish_area"] == 0
    assert result["family_counts"]["ceiling_area"] == 0
    assert result["combined_quantity_count"] == 0
    assert result["status"] == "no_sealable_quantities"
    assert result["benchmark_score_granted"] is False
    assert not (destination / "family_runs").exists()
