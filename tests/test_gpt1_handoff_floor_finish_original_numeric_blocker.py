"""Original contradictory FIRM floor finish must reach the real source seal.

These are source-neutral boundary tests. They do not grant a source mark,
floor identity, square metres or benchmark score.
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_source_closed_project_handoff import _quantity
from tools import run_source_closed_project_handoff as handoff


def _source_claim(finishes):
    return SimpleNamespace(
        status=SimpleNamespace(value="abstained"),
        reason_codes=("source_measurement_incomplete",),
        canonical_walls=(),
        canonical_openings=(),
        canonical_rooms=(),
        canonical_floors=(),
        canonical_spaces=(),
        room_area_quantity_evidence=(),
        floor_finish_quantity_evidence=tuple(finishes),
        opening_quantity_evidence=(),
        opening_dimension_quantity_evidence=(),
        opening_count_quantity_evidence=(),
        ceiling_lining_quantity_evidence=(),
        publication=None,
    )


def _source_stub(monkeypatch, finishes):
    claim=_source_claim(finishes)
    monkeypatch.setattr(handoff, "_source_page_scopes",
                        lambda path: ((0,), (), 1))
    monkeypatch.setattr(handoff, "collect_live_physical_net_wall_claim",
                        lambda *args, **kwargs: claim)
    monkeypatch.setattr(handoff, "collect_live_ceiling_lining_claims",
                        lambda *args, **kwargs: SimpleNamespace())
    monkeypatch.setattr(handoff, "publish_live_ceiling_area_quantities",
                        lambda result: ())
    monkeypatch.setattr(handoff, "publish_live_floor_area_quantities",
                        lambda claim: ())
    return claim


@pytest.mark.parametrize("family_group", ("all", "surfaces"))
@pytest.mark.parametrize("include_independent_firm", (False, True))
def test_handoff_sends_blocked_numeric_floor_finish_to_required_source_seal(
    tmp_path, monkeypatch, family_group, include_independent_firm,
):
    """An eligible-family prefilter cannot erase contradictory FIRM evidence."""
    source=tmp_path / "source.pdf"
    source.write_bytes(b"source-neutral-boundary-fixture")
    blocked=replace(
        _quantity("blocked-original-floor-finish", "floor_finish_area"),
        blocking_reasons=("original_material_occurrence_conflict",),
    )
    eligible=_quantity("independent-firm-floor-finish", "floor_finish_area")
    finishes=(blocked,eligible) if include_independent_firm else (blocked,)
    _source_stub(monkeypatch, finishes)
    calls=[]

    def required_original_seal(*args, **kwargs):
        calls.append(tuple(args[0].floor_finish_quantity_evidence))
        raise SourceClosedRunConflictError(
            "non-abstained original floor-finish quantity carries blockers"
        )

    monkeypatch.setattr(
        handoff, "seal_live_floor_finish_area_run", required_original_seal
    )
    out=tmp_path / "out"
    with pytest.raises(
        SourceClosedRunConflictError,
        match="non-abstained original floor-finish quantity carries blockers",
    ):
        handoff.generate_project_handoff(
            pdf_path=source, project_id="source-test",
            workspace_id=1, output_dir=out, family_group=family_group,
        )
    assert calls==[finishes]
    assert not (out / "source-test.json").exists()


@pytest.mark.parametrize("family_group", ("all", "surfaces"))
def test_genuine_abstained_floor_finish_is_not_promoted_to_sealer(
    tmp_path, monkeypatch, family_group,
):
    """An honestly abstained source has no numeric FIRM conflict to publish."""
    source=tmp_path / "source.pdf"
    source.write_bytes(b"source-neutral-abstained-fixture")
    abstained=replace(
        _quantity("source-abstained-floor-finish", "floor_finish_area"),
        value=None, abstained=True,
        blocking_reasons=("physical_room_owner_unavailable",),
    )
    _source_stub(monkeypatch, (abstained,))
    def unexpected_seal(*args, **kwargs):
        raise AssertionError("abstained source must remain unavailable")
    monkeypatch.setattr(
        handoff, "seal_live_floor_finish_area_run", unexpected_seal,
    )
    out=tmp_path / "out"
    summary=handoff.generate_project_handoff(
        pdf_path=source, project_id="source-test",
        workspace_id=1, output_dir=out, family_group=family_group,
    )
    assert summary["family_counts"]["floor_finish_area"]==0
    assert summary["status"]=="no_sealable_quantities"
    assert not (out / "source-test.json").exists()
