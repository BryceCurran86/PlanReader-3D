"""Source-independent ceiling customer exclusion guards on both live paths."""
from dataclasses import replace

import pytest

from pb_live_ceiling_area_customer_projection import (
    project_live_ceiling_area_customer_rows, _customer_quantity,
)
from pb_live_ceiling_customer_projection import project_live_ceiling_customer_rows
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_ceiling_area_quantity_publication import (
    _result as legacy_result, _shadow_quantity,
)
from test_live_ceiling_lining_source_closed_export import _claim, _quantity


def _project(source, variant):
    if variant == "canonical":
        claim = replace(_claim(source), ceiling_lining_quantity_evidence=(source,))
        return project_live_ceiling_customer_rows(
            claim, workspace_id=3, project_id="arbitrary-building",
        )
    original = replace(legacy_result(), quantity_evidence=(source,))
    return project_live_ceiling_area_customer_rows(
        original, workspace_id=3, project_id="arbitrary-building",
    )


@pytest.mark.parametrize("variant", ["canonical", "legacy"])
@pytest.mark.parametrize("scope", ["EXCLUSION", "EXCLUDED", "ABSTAIN", "REVIEW", "", None, 12, True])
def test_excluded_or_unresolved_original_ceiling_cannot_be_included(variant, scope):
    source = _quantity() if variant == "canonical" else _shadow_quantity()
    source = replace(source, metadata={
        **dict(source.metadata), "inclusion_status": scope,
    })
    with pytest.raises(
        SourceClosedRunConflictError,
        match="customer_source_inclusion_scope_unresolved",
    ):
        _project(source, variant)


@pytest.mark.parametrize("variant", ["canonical", "legacy"])
def test_source_inclusion_still_produces_authorised_ceiling_customer(variant):
    source = _quantity() if variant == "canonical" else _shadow_quantity()
    source = replace(source, metadata={
        **dict(source.metadata), "inclusion_status": "INCLUSION",
    })
    rows = _project(source, variant)
    assert len(rows) == 1
    assert rows[0]["quantity_family"] == "ceiling_lining"
    if variant == "canonical":
        assert rows[0]["quantity_id"] == source.quantity_id


def test_direct_legacy_adapter_cannot_overwrite_exclusion():
    source = _shadow_quantity()
    source = replace(source, metadata={
        **dict(source.metadata), "inclusion_status": "EXCLUSION",
    })
    with pytest.raises(SourceClosedRunConflictError):
        _customer_quantity(
            source, room_entity_id="arbitrary-room", finish_descriptor="acoustic",
        )


@pytest.mark.parametrize("variant", ["canonical", "legacy"])
def test_duplicate_canonical_ceiling_cannot_choose_last_customer_owner(variant):
    source = _quantity() if variant == "canonical" else _shadow_quantity()
    if variant == "canonical":
        claim = replace(_claim(source), ceiling_lining_quantity_evidence=(source,))
        assert claim.canonical_ceilings
        claim = replace(claim, canonical_ceilings=(claim.canonical_ceilings[0],) * 2)
        with pytest.raises(
            SourceClosedRunConflictError,
            match="duplicate_canonical_ceiling_customer_owner",
        ):
            project_live_ceiling_customer_rows(
                claim, workspace_id=3, project_id="unknown-project",
            )
    else:
        original = replace(legacy_result(), quantity_evidence=(source,))
        assert original.canonical_ceilings
        original = replace(
            original, canonical_ceilings=(original.canonical_ceilings[0],) * 2,
        )
        with pytest.raises(
            SourceClosedRunConflictError,
            match="duplicate_canonical_ceiling_customer_owner",
        ):
            project_live_ceiling_area_customer_rows(
                original, workspace_id=3, project_id="unknown-project",
            )


@pytest.mark.parametrize("variant", ["canonical", "legacy"])
@pytest.mark.parametrize("denied", [False, None, 0, "false"])
def test_explicit_source_commercial_denial_never_becomes_customer_ceiling(variant, denied):
    source = _quantity() if variant == "canonical" else _shadow_quantity()
    source = replace(source, metadata={
        **dict(source.metadata), "commercial_projection_allowed": denied,
    })
    with pytest.raises(
        SourceClosedRunConflictError,
        match="customer_source_commercial_scope_denied",
    ):
        _project(source, variant)


@pytest.mark.parametrize("variant", ["canonical", "legacy"])
@pytest.mark.parametrize("field,incorrect", (
    ("source_sha256", "f" * 64),
    ("revision_id", "other-revision"),
    ("document_id", "other-document"),
    ("snapshot_id", "stale-snapshot"),
    ("canonical_ceiling_id", "foreign-ceiling"),
    ("canonical_room_id", "another-canonical-room"),
    ("room_area_quantity_id", "different-source-area"),
))
def test_customer_ceiling_cannot_move_to_foreign_original_owner(variant, field, incorrect):
    source = _quantity() if variant == "canonical" else _shadow_quantity()
    source = replace(source, metadata={
        **dict(source.metadata), field: incorrect,
    })
    with pytest.raises((SourceClosedRunConflictError, ValueError, TypeError)):
        _project(source, variant)


@pytest.mark.parametrize("variant", ["canonical", "legacy"])
def test_source_ceiling_must_be_square_metres_not_implicit_area_conversion(variant):
    source = _quantity() if variant == "canonical" else _shadow_quantity()
    source = replace(source, unit="ft2")
    with pytest.raises((SourceClosedRunConflictError, ValueError)):
        _project(source, variant)


def test_physical_room_id_may_differ_from_source_canonical_room_id():
    source = _quantity()
    assert source.metadata["physical_room_id"] != source.metadata["canonical_room_id"]
    assert len(_project(source, "canonical")) == 1


def test_legacy_customer_adapter_denial_never_overwritten():
    source = replace(
        _shadow_quantity(),
        metadata={**dict(_shadow_quantity().metadata),
                  "commercial_projection_allowed": False},
    )
    with pytest.raises(SourceClosedRunConflictError,
                       match="customer_source_commercial_scope_denied"):
        _customer_quantity(
            source, room_entity_id="source-owning-room",
            finish_descriptor="ceiling finish",
        )
