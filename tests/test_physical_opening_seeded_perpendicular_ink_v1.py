"""Owner directive 2026-11-02 ('solid piers retained'): ink that crosses the aperture PERPENDICULAR to the wall is ink inside
the opening, not nothing.

Written failing first: _seeded_ink_checks measured the overlap of every line with the gap ALONG the wall, which is zero for
a line running across it (a post, a mullion, a full-thickness pier), so such lines never reached the veto."""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    SEEDED_INK_ROLE_ASSERTED_ONLY_BY_CALLER,
    SEEDED_OPENING_INK_UNACCOUNTED,
)
from test_physical_opening_seeded_existence_review_v1 import POSES
from test_physical_opening_seeded_existence_v1 import LAYERED, PLAIN, _fixture, _ids, _selector

CORR = EvidenceResolutionStatus.CORROBORATED
ABST = EvidenceResolutionStatus.ABSTAINED

PIER = (((120.0, 100.0), (120.0, 110.0)),)              # full thickness, across the middle of the gap
MULLION = (((120.0, 102.0), (120.0, 108.0)),)           # between the faces, not touching them
CROSSING = (((120.0, 95.0), (120.0, 115.0)),)           # runs across both faces
RETURN_AT_JAMB = (((100.0, 102.0), (100.0, 108.0)),)    # on the jamb station: a return, not inside the gap
BEYOND_THE_GAP = (((150.0, 100.0), (150.0, 110.0)),)    # in the wall next to the opening
OUTSIDE_THE_FACES = (((120.0, 120.0), (120.0, 130.0)),)  # across the gap's line but outside the wall band


@pytest.mark.parametrize("kw", POSES)
@pytest.mark.parametrize("name,extra", [("pier", PIER), ("mullion", MULLION), ("crossing", CROSSING)])
def test_ink_running_across_the_aperture_is_interior_ink_in_every_pose(kw, name, extra):
    physical, published, ids, kw = _fixture(PLAIN + extra, **kw)
    members = _ids(ids, PLAIN, kw)
    ink = _ids(ids, extra, kw)
    selector = _selector(published, members[4])
    unnamed = physical.prove_seeded_existence(selector, members)
    assert unnamed.status is ABST and unnamed.existence_record is None, name
    assert unnamed.reason_codes == (SEEDED_OPENING_INK_UNACCOUNTED,), name
    named = physical.prove_seeded_existence(selector, members, ink)
    assert named.status is ABST and named.existence_record is None, name
    assert named.reason_codes == (SEEDED_INK_ROLE_ASSERTED_ONLY_BY_CALLER,), name


@pytest.mark.parametrize("name,extra", [("return_at_jamb", RETURN_AT_JAMB), ("beyond_the_gap", BEYOND_THE_GAP),
                                        ("outside_the_faces", OUTSIDE_THE_FACES)])
def test_perpendicular_lines_on_a_jamb_station_beside_the_gap_or_outside_the_wall_are_not_inside_the_opening(name, extra):
    physical, published, ids, kw = _fixture(PLAIN + extra)
    members = _ids(ids, PLAIN, kw)
    proof = physical.prove_seeded_existence(_selector(published, members[4]), members)
    assert proof.status is CORR and proof.opposing_evidence_atoms == (), name


def test_a_pier_in_one_layer_of_a_layered_opening_is_inside_the_opening_too():
    pier_in_first_layer = (((120.0, 100.0), (120.0, 105.0)),)
    physical, published, ids, kw = _fixture(LAYERED + pier_in_first_layer)
    members = _ids(ids, LAYERED, kw)
    proof = physical.prove_seeded_existence(_selector(published, members[8]), members)
    assert proof.status is ABST and proof.existence_record is None
    assert SEEDED_OPENING_INK_UNACCOUNTED in proof.reason_codes
