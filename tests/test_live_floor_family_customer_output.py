from __future__ import annotations

from types import SimpleNamespace

import pytest

import pb_live_floor_family_customer_output as module
from pb_live_external_physical_net_wall_publication import (
    LiveExternalPhysicalNetWallPublication,
)
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_closed_run_export import SourceClosedRunConflictError


def _publication() -> LiveExternalPhysicalNetWallPublication:
    return LiveExternalPhysicalNetWallPublication(
        revision_id="rev-1",
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=("test",),
        quantity_evidence=None,
        canonical_walls=(),
        external_wall_ids=(),
        gross_geometry_record_ids=(),
        whole_wall_role_record_ids=(),
        physical_void_record_ids=(),
        opening_universe_record_ids=(),
    )


def _claim() -> LivePhysicalNetWallClaim:
    return LivePhysicalNetWallClaim(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=("test",),
        quantity_m2=None,
        source_pages=(),
        canonical_walls=(),
        canonical_wall_status=EvidenceResolutionStatus.ABSTAINED,
        canonical_wall_reason_codes=(),
        canonical_wall_source_pages=(),
        unresolved_wall_candidate_ids=(),
        canonical_openings=(),
        canonical_rooms=(),
        canonical_floors=(),
        canonical_floor_status=EvidenceResolutionStatus.ABSTAINED,
        canonical_floor_reason_codes=(),
        canonical_floor_source_pages=(),
        canonical_room_status=EvidenceResolutionStatus.ABSTAINED,
        canonical_room_reason_codes=(),
        canonical_room_source_pages=(),
        external_wall_ids=(),
        evidence_ids=(),
        quantity_id=None,
        confidence=0.0,
        publication=_publication(),
    )


def _fake_run(*quantity_ids: str):
    return SimpleNamespace(
        quantities=tuple(
            SimpleNamespace(quantity_id=quantity_id)
            for quantity_id in quantity_ids
        )
    )


def test_combines_floor_area_and_floor_finish_without_supersedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    floor_run = _fake_run("floor-area-q")
    finish_run = _fake_run("floor-finish-q")
    combined = _fake_run("floor-area-q", "floor-finish-q")
    calls = {}

    monkeypatch.setattr(
        module,
        "project_live_floor_area_customer_rows",
        lambda *args, **kwargs: ({"quantity_id": "floor-area-q"},),
    )
    monkeypatch.setattr(
        module,
        "project_live_floor_finish_customer_rows",
        lambda *args, **kwargs: ({"quantity_id": "floor-finish-q"},),
    )
    monkeypatch.setattr(
        module,
        "seal_live_floor_area_run",
        lambda *args, **kwargs: floor_run,
    )
    monkeypatch.setattr(
        module,
        "seal_live_floor_finish_area_run",
        lambda *args, **kwargs: finish_run,
    )

    def combine(runs, *, project_id):
        calls["runs"] = tuple(runs)
        calls["project_id"] = project_id
        return combined

    def verify(run, rows):
        calls["verify_run"] = run
        calls["verify_rows"] = tuple(rows)

    monkeypatch.setattr(module, "combine_source_closed_runs", combine)
    monkeypatch.setattr(module, "verify_sealed_customer_output", verify)

    actual_run, rows = module.project_live_floor_family_customer_output(
        _claim(),
        workspace_id=1,
        project_id="project-1",
    )

    assert actual_run is combined
    assert calls["runs"] == (floor_run, finish_run)
    assert calls["project_id"] == "project-1"
    assert rows == (
        {"quantity_id": "floor-area-q"},
        {"quantity_id": "floor-finish-q"},
    )
    assert calls["verify_run"] is combined
    assert calls["verify_rows"] == rows


def test_preserves_existing_floor_area_when_finish_family_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    floor_run = _fake_run("floor-area-q")
    monkeypatch.setattr(
        module,
        "project_live_floor_area_customer_rows",
        lambda *args, **kwargs: ({"quantity_id": "floor-area-q"},),
    )
    monkeypatch.setattr(
        module,
        "project_live_floor_finish_customer_rows",
        lambda *args, **kwargs: (),
    )
    monkeypatch.setattr(
        module,
        "seal_live_floor_area_run",
        lambda *args, **kwargs: floor_run,
    )
    monkeypatch.setattr(
        module,
        "seal_live_floor_finish_area_run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()),
    )
    monkeypatch.setattr(
        module,
        "combine_source_closed_runs",
        lambda runs, *, project_id: floor_run,
    )
    monkeypatch.setattr(
        module,
        "verify_sealed_customer_output",
        lambda *args, **kwargs: None,
    )

    run, rows = module.project_live_floor_family_customer_output(
        _claim(),
        workspace_id=1,
        project_id="project-1",
    )
    assert run is floor_run
    assert rows == ({"quantity_id": "floor-area-q"},)


def test_rejects_duplicate_quantity_id_across_floor_families(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duplicate = {"quantity_id": "same-q"}
    monkeypatch.setattr(
        module,
        "project_live_floor_area_customer_rows",
        lambda *args, **kwargs: (duplicate,),
    )
    monkeypatch.setattr(
        module,
        "project_live_floor_finish_customer_rows",
        lambda *args, **kwargs: (dict(duplicate),),
    )
    monkeypatch.setattr(
        module,
        "seal_live_floor_area_run",
        lambda *args, **kwargs: _fake_run("same-q"),
    )
    monkeypatch.setattr(
        module,
        "seal_live_floor_finish_area_run",
        lambda *args, **kwargs: _fake_run("same-q"),
    )

    with pytest.raises(
        SourceClosedRunConflictError,
        match="quantity IDs are not unique",
    ):
        module.project_live_floor_family_customer_output(
            _claim(),
            workspace_id=1,
            project_id="project-1",
        )


def test_rejects_empty_floor_family_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        module,
        "project_live_floor_area_customer_rows",
        lambda *args, **kwargs: (),
    )
    monkeypatch.setattr(
        module,
        "project_live_floor_finish_customer_rows",
        lambda *args, **kwargs: (),
    )

    with pytest.raises(
        SourceClosedRunConflictError,
        match="no source-closed floor-family",
    ):
        module.project_live_floor_family_customer_output(
            _claim(),
            workspace_id=1,
            project_id="project-1",
        )


@pytest.mark.parametrize(
    ("workspace_id", "project_id"),
    [(True, "project-1"), (0, "project-1"), (1, ""), (1, " project-1")],
)
def test_rejects_malformed_project_scope(
    workspace_id,
    project_id,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        module.project_live_floor_family_customer_output(
            _claim(),
            workspace_id=workspace_id,
            project_id=project_id,
        )



def _production_shaped_source_area_and_finish_claim():
    """Use the real original-source sealers, not monkeypatched family runs."""
    from dataclasses import replace
    from tests.test_live_floor_finish_area_source_closed_export import (
        _claim as _finish_claim,
        _independent_source_room_area,
    )

    return replace(
        _finish_claim(),
        room_area_quantity_evidence=(_independent_source_room_area(),),
    )


def test_real_source_floor_area_and_finish_are_two_distinct_verified_customer_rows():
    from pb_customer_output_verification import verify_sealed_customer_output
    from pb_live_floor_area_quantity_publication import (
        publish_live_floor_area_quantities,
    )

    claim = _production_shaped_source_area_and_finish_claim()
    original_floor_area = publish_live_floor_area_quantities(claim)
    assert len(original_floor_area) == 1

    signed, rows = module.project_live_floor_family_customer_output(
        claim, workspace_id=1, project_id="project-1",
    )
    assert len(signed.quantities) == len(rows) == 2
    by_family = {row["quantity_family"]: row for row in rows}
    assert set(by_family) == {"floor_area", "floor_finish_area"}
    plain = by_family["floor_area"]
    finish = by_family["floor_finish_area"]
    assert plain["quantity_id"] == original_floor_area[0].quantity_id
    assert plain["quantity"] == finish["quantity"] == 8.64
    assert finish["element"] == "Floor finish area (FT1)"
    assert finish["finish_system"] == "tile"
    assert plain["quantity_id"] != finish["quantity_id"]
    assert all(row["quantity_status"] == "To review" for row in rows)
    verified = verify_sealed_customer_output(signed, rows)
    assert set(verified.verified_quantity_ids) == {
        row["quantity_id"] for row in rows
    }


def test_forged_finish_cannot_reclassify_or_erase_original_source_floor_area():
    from dataclasses import replace
    from pb_customer_output_verification import verify_sealed_customer_output
    from pb_live_floor_area_customer_projection import (
        project_live_floor_area_customer_rows,
    )
    from pb_live_floor_area_source_closed_export import seal_live_floor_area_run

    original = _production_shaped_source_area_and_finish_claim()
    baseline = seal_live_floor_area_run(
        original, workspace_id=1, project_id="project-1",
    )
    plain_rows = project_live_floor_area_customer_rows(
        original, workspace_id=1, project_id="project-1",
    )
    assert len(baseline.quantities) == len(plain_rows) == 1

    material = original.floor_finish_quantity_evidence[0]
    forged = replace(
        original,
        floor_finish_quantity_evidence=(replace(
            material, metadata={**material.metadata, "finish_code": "FT3"},
        ),),
    )
    with pytest.raises(SourceClosedRunConflictError):
        module.project_live_floor_family_customer_output(
            forged, workspace_id=1, project_id="project-1",
        )
    # Rejecting the foreign finish code is NOT permission to retract or
    # overwrite the separately signed original whole-room floor area.
    assert seal_live_floor_area_run(
        forged, workspace_id=1, project_id="project-1",
    ).to_dict() == baseline.to_dict()
    assert verify_sealed_customer_output(
        baseline, plain_rows,
    ).verified_quantity_ids == (baseline.quantities[0].quantity_id,)


def test_real_original_floor_area_customer_row_has_all_workspace_required_fields():
    """Original sealed 8.64 m² must not vanish for an empty source label."""
    from pb_customer_output_verification import verify_sealed_customer_output

    claim = _production_shaped_source_area_and_finish_claim()
    original_room = claim.room_area_quantity_evidence[0]
    assert not original_room.metadata.get("location")
    signed, rows = module.project_live_floor_family_customer_output(
        claim, workspace_id=1, project_id="project-1",
    )
    assert len(rows) == len(signed.quantities) == 2
    area = next(row for row in rows if row["quantity_family"] == "floor_area")
    assert area["section"] == "Internal"
    assert area["element"] == "Floor area"
    assert area["location"] == "room-1"
    assert area["substrate"] == "Floor"
    assert area["row_role"] == "floor_area"
    assert area["quantity_status"] == "To review"
    assert area["quantity"] == 8.64
    assert original_room.metadata.get("location") is None
    assert set(verify_sealed_customer_output(
        signed, rows,
    ).verified_quantity_ids) == {row["quantity_id"] for row in rows}


def test_original_source_owned_room_label_projects_onto_floor_area_without_quantity_change():
    from dataclasses import replace
    from pb_live_floor_area_customer_projection import (
        project_live_floor_area_customer_rows,
    )
    from pb_live_floor_area_source_closed_export import seal_live_floor_area_run
    from pb_customer_output_verification import verify_sealed_customer_output
    from tests.test_live_floor_finish_area_source_closed_export import (
        _original_labeled_room,
    )

    source = _production_shaped_source_area_and_finish_claim()
    claim = replace(source, canonical_rooms=(_original_labeled_room(),))
    signed = seal_live_floor_area_run(
        claim, workspace_id=1, project_id="project-1",
    )
    rows = project_live_floor_area_customer_rows(
        claim, workspace_id=1, project_id="project-1",
    )
    assert len(rows) == len(signed.quantities) == 1
    assert rows[0]["location"] == "OFFICE"
    assert rows[0]["section"] == "Internal"
    assert rows[0]["substrate"] == "Floor"
    assert rows[0]["quantity"] == 8.64
    assert verify_sealed_customer_output(
        signed, rows,
    ).verified_quantity_ids == (signed.quantities[0].quantity_id,)


@pytest.mark.parametrize("bad_original", (
    {"location": "FREEZER"},
    {"location": " OFFICE "},
    {"location": 123},
    {"section": 123},
    {"substrate": True},
    {"inclusion_status": 0},
))
def test_source_floor_area_customer_fields_cannot_be_forged_or_type_coerced(
    bad_original,
):
    from dataclasses import replace
    from pb_live_floor_area_customer_projection import (
        project_live_floor_area_customer_rows,
    )
    from tests.test_live_floor_finish_area_source_closed_export import (
        _original_labeled_room,
    )

    claim = _production_shaped_source_area_and_finish_claim()
    source_area = claim.room_area_quantity_evidence[0]
    altered = replace(
        source_area, metadata={**source_area.metadata, **bad_original},
    )
    claim = replace(
        claim,
        room_area_quantity_evidence=(altered,),
        canonical_rooms=(_original_labeled_room(),),
    )
    with pytest.raises(SourceClosedRunConflictError):
        project_live_floor_area_customer_rows(
            claim, workspace_id=1, project_id="project-1",
        )
    assert claim.room_area_quantity_evidence[0].value == 8.64


def test_original_source_floor_area_exclusion_remains_exclusion_in_customer_output():
    from dataclasses import replace
    from pb_live_floor_area_customer_projection import (
        project_live_floor_area_customer_rows,
    )
    from pb_live_floor_area_source_closed_export import seal_live_floor_area_run
    from pb_customer_output_verification import verify_sealed_customer_output

    claim = _production_shaped_source_area_and_finish_claim()
    source_area = claim.room_area_quantity_evidence[0]
    excluded = replace(
        source_area,
        metadata={**source_area.metadata, "inclusion_status": "EXCLUSION"},
    )
    claim = replace(claim, room_area_quantity_evidence=(excluded,))
    sealed = seal_live_floor_area_run(
        claim, workspace_id=1, project_id="project-1",
    )
    rows = project_live_floor_area_customer_rows(
        claim, workspace_id=1, project_id="project-1",
    )
    assert len(rows) == len(sealed.quantities) == 1
    assert rows[0]["inclusion_status"] == "EXCLUSION"
    assert rows[0]["quantity"] == 8.64
    assert verify_sealed_customer_output(
        sealed, rows,
    ).verified_quantity_ids == (sealed.quantities[0].quantity_id,)
