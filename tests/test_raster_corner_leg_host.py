from copy import deepcopy
from types import SimpleNamespace

import pb_opening_host_binding_authority as host
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_physical_wall_identity import PhysicalEquivalenceClass as Class
from test_raster_opening_split_centerline_host import OPENING, _equivalence, _record


def _support():
    return tuple(SimpleNamespace(observation_kind=kind, geometry=line) for kind, line in (
        ("raster_wall_band_face", (140.0, 50.0, 220.0, 50.0)),
        ("raster_wall_band_face", (140.0, 60.0, 220.0, 60.0)),
        ("raster_wall_band_end", (140.0, 50.0, 140.0, 60.0)),
        ("raster_line_run", (100.0, 53.0, 140.0, 53.0)),
        ("raster_line_run", (100.0, 57.0, 140.0, 57.0)),
    ))


def _fixture():
    records = (_record("right", start=140.0, end=220.0, offset=1.0, source_ids=("raw:right",)),)
    return records, {"raw:right": (140.0, 56.0, 220.0, 56.0)}


def _resolve(records, lines, support=None, opening=OPENING, pairs=()):
    return host._resolve_raster_corner_leg_host_from_records(
        _support() if support is None else support, records, opening,
        _equivalence(records, pair_classifications=pairs), lines,
    )


def test_one_terminating_flank_binds_its_unique_local_owner() -> None:
    records, lines = _fixture()
    before = deepcopy((records, lines))
    result = _resolve(records, lines)
    assert result.status is Status.CORROBORATED
    assert result.reason_codes == (host.RASTER_CORNER_LEG_HOST_RESOLVED,)
    assert result.bands[0].member_ids == ("right",)
    assert (records, lines) == before
    assert _resolve(tuple(reversed(records)), lines, tuple(reversed(_support()))) == result


def test_missing_jamb_or_second_collinear_flank_does_not_bind() -> None:
    records, lines = _fixture()
    two_flanks = _support() + (
        SimpleNamespace(observation_kind="raster_wall_band_face", geometry=(20.0, 50.0, 100.0, 50.0)),
        SimpleNamespace(observation_kind="raster_wall_band_face", geometry=(20.0, 60.0, 100.0, 60.0)),
        SimpleNamespace(observation_kind="raster_wall_band_end", geometry=(100.0, 50.0, 100.0, 60.0)),
    )
    assert _resolve(records, lines, two_flanks).bands == ()
    assert _resolve(records, lines, _support()[:2]).bands == ()


def test_two_competing_jamb_owners_conflict_without_ranking() -> None:
    records, lines = _fixture()
    extra = _record("other", start=140.0, end=220.0, offset=-1.0, source_ids=("raw:other",))
    lines["raw:other"] = (140.0, 54.0, 220.0, 54.0)
    result = _resolve(
        (*records, extra), lines, pairs=(("right", "other", Class.DISTINCT_PHYSICAL_WALLS.value),))
    assert result.status is Status.CONFLICT
    assert result.bands == ()
    assert result.reason_codes == ("multiple_authenticated_raster_corner_leg_hosts",)


def test_remote_fragment_sharing_the_primitive_does_not_compete() -> None:
    records, lines = _fixture()
    remote = _record("remote", start=180.0, end=220.0, offset=1.0, source_ids=("raw:right",))
    result = _resolve((*records, remote), lines)
    assert result.bands[0].member_ids == ("right",)
