"""Source-neutral customer authority and physical floor ownership safety."""
from dataclasses import replace
import pytest

from pb_live_floor_finish_customer_projection import project_live_floor_finish_customer_rows
from pb_source_closed_run_export import SourceClosedRunConflictError
from test_live_floor_finish_area_source_closed_export import _claim, _quantity


def _customer(*quantities):
    return project_live_floor_finish_customer_rows(
        replace(_claim(), floor_finish_quantity_evidence=quantities),
        workspace_id=3, project_id="unseen-project-2027",
    )


def test_explicit_commercial_veto_cannot_be_upgraded_for_any_project():
    q = _quantity()
    q = replace(q, metadata={**q.metadata, "commercial_projection_allowed": False})
    with pytest.raises(SourceClosedRunConflictError, match="commercial_scope_denied"):
        _customer(q)


@pytest.mark.parametrize("attribute,bad_value", [
    ("source_sha256", "0" * 64),
    ("revision_id", "stale-revision"),
    ("document_id", "other-document"),
    ("snapshot_id", "other-snapshot"),
    ("canonical_floor_id", "different-floor"),
    ("physical_floor_surface_id", "other-physical-floor"),
    ("source_room_face_record_id", "other-room-face"),
])
def test_wrong_source_owner_never_issues_a_customer_floor(attribute, bad_value):
    q = _quantity()
    q = replace(q, metadata={**q.metadata, attribute: bad_value})
    with pytest.raises((SourceClosedRunConflictError, ValueError, TypeError)):
        _customer(q)


def test_invalid_source_area_unit_is_never_coerced_into_square_metres():
    q = replace(_quantity(), unit="ft2")
    with pytest.raises((SourceClosedRunConflictError, ValueError)):
        _customer(q)


def test_existing_source_firm_customer_floor_unchanged():
    rows = _customer(_quantity())
    assert len(rows) == 1
    assert rows[0]["quantity_id"] == _quantity().quantity_id


@pytest.mark.parametrize("scope", [None, "", "REVIEW", "EXCLUSION", False, 5])
def test_explicit_unknown_original_floor_inclusion_is_never_assumed_positive(scope):
    q = _quantity()
    source = replace(
        q, metadata={**dict(q.metadata), "inclusion_status": scope},
    )
    with pytest.raises(SourceClosedRunConflictError,
                       match="customer_source_inclusion_scope_unresolved") as raised:
        _customer(source)
    # Existing floor-first error routing and shared source-policy audit are
    # both retained. Neither is a quantity/customer permission.
    assert "floor_finish_source_inclusion_scope_unresolved" in str(raised.value)


@pytest.mark.parametrize("denied", [None, 0, "false"])
def test_explicit_unknown_commercial_floor_permission_does_not_become_true(denied):
    q = _quantity()
    source = replace(
        q, metadata={**dict(q.metadata), "commercial_projection_allowed": denied},
    )
    with pytest.raises(SourceClosedRunConflictError,
                       match="customer_source_commercial_scope_denied"):
        _customer(source)
