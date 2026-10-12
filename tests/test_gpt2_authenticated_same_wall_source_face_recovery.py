"""Source-equivalent physical W4 addresses must not delete a real room face."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

import pb_source_room_face_authority as R
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_identity import (
    PhysicalEquivalenceClass,
    PhysicalWallEquivalenceResolution,
    PhysicalWallIdentity,
)
from test_source_room_face_local_ownership_abstain_v1 import _record, _rooms, _scope


def _identity(row, primitive_ids):
    return PhysicalWallIdentity(
        wall_candidate_id=row.wall_candidate_id,
        viewport_id="wall-source:page-1",
        candidate_identity_id=f"identity:{row.wall_candidate_id}",
        path_fingerprint=tuple(row.wall_candidate.centerline_pts),
        source_primitive_ids=tuple(primitive_ids),
        edge_ids=(f"original-edge:{row.wall_candidate_id}",),
        status=EvidenceResolutionStatus.CORROBORATED,
        blocking_reasons=(),
    )


def _same_source_scope(*, classification="same_physical_wall",
                       shared_source=True, no_ambiguity=True,
                       same_viewport=True, original_overlap=True):
    records = list(_rooms(5))
    if original_overlap:
        extra = _record("alias", (0., 0.), (10., 0.))
    else:
        extra = _record("alias", (90., 90.), (100., 90.))
    records.append(extra)
    for row in records:
        owners = ("native:shared-original-W2",) if row.wall_candidate_id in (
            "room-top", "alias"
        ) else (f"native:{row.wall_candidate_id}",)
        if not shared_source and row.wall_candidate_id == "alias":
            owners = ("native:independent-line",)
        row.physical_identity = _identity(row, owners)
    s = _scope(records)
    equiv = PhysicalWallEquivalenceResolution(
        scope_viewport_id=(
            s.decision_scope_id if same_viewport else "foreign-scope"
        ),
        representative_wall_ids=("room-top",),
        abstained_wall_ids=(() if no_ambiguity else ("alias",)),
        equivalence_groups=(("alias", "room-top"),),
        ambiguous_wall_ids=(() if no_ambiguity else ("alias",)),
        same_wall_ids=("alias", "room-top"),
        pair_classifications=((
            "alias", "room-top", classification,
        ),),
        blocking_reasons_by_wall_id={},
    )
    s.equivalence = equiv
    return s


def test_source_positive_same_equivalence_recovers_room_without_guessing():
    original = _scope(_rooms(5))
    control = R._derive_scope(original)
    source = _same_source_scope()
    aliases = R._source_authenticated_same_wall_aliases(
        source, tuple(source.records)
    )
    assert aliases == {"alias": "room-top", "room-top": "room-top"}
    result = R._derive_scope(source)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.abstained_faces == ()
    assert result.records == control.records
    assert result.ownership_evaluation.unresolved_faces == ()
    assert len(result.records) == 5
    assert all(item.area_page_pts2 > 0 for item in result.records)
    assert all(item.bounding_wall_ids for item in result.records)


@pytest.mark.parametrize("guard", [
    {"classification": PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE.value},
    {"classification": PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS.value},
    {"shared_source": False},
    {"no_ambiguity": False},
    {"same_viewport": False},
    {"original_overlap": False},
])
def test_unproven_source_wall_equivalence_never_launders_duplicate_ownership(guard):
    source = _same_source_scope(**guard)
    assert R._source_authenticated_same_wall_aliases(
        source, tuple(source.records)
    ) == {}
    if guard.get("original_overlap", True):
        result = R._derive_scope(source)
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        assert len(result.records) == 4
        assert len(result.abstained_faces) == 1
        assert R.SOURCE_ROOM_FACE_DUPLICATE_EDGE in result.reason_codes
        assert {"room-top", "alias"} <= set(
            result.abstained_faces[0].bounding_wall_ids
        )


def test_missing_or_foreign_physical_identity_does_not_publish_duplicate_edge():
    source = _same_source_scope()
    for version in (None, "foreign-id"):
        rows = list(source.records)
        for row in rows:
            if row.wall_candidate_id == "alias":
                row.physical_identity = (
                    None if version is None
                    else replace(row.physical_identity, wall_candidate_id=version)
                )
        assert R._source_authenticated_same_wall_aliases(
            source, tuple(rows)
        ) == {}
