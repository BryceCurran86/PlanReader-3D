"""Original six G17 opening-local source: no W4/host promotion by shadow."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace as NS

import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from tools.diag_gptmax_six_opening_local_g17_source import (
    summarize_local_source_shadow, original_unhosted_source_role_replay,
)


def record(wallid, sid, *, usable=True):
    return NS(wall_candidate_id=wallid,
              physical_identity=NS(usable=usable,candidate_identity_id="cid-"+wallid,
                                  source_primitive_ids=(sid,),edge_ids=(wallid+"-e1",)))


def flank(prefix, *, ink=True, rows=(), exact=(), collapsed=0):
    return NS(source_observation_ids=(prefix+"a",prefix+"b",prefix+"c"),
              source_parent_ids=(prefix+"p1",prefix+"p2",prefix+"p3"),
              source_ink_supported=ink,reason_codes=(),
              default_records=tuple(rows),exact_coordinate_records=tuple(exact),
              default_snap_collapsed_count=collapsed,
              default_junction_types=("L",) if ink else (),
              exact_junction_types=("L",) if ink else ())


def shadow(flanks):
    return NS(physical_opening_id="id-one",status=Status.ABSTAINED,
              scope_complete=False,physical_wall_role_granted=False,
              opening_host_granted=False,metric_quantity_granted=False,
              flanks=tuple(flanks))


def test_complete_original_two_flanks_remain_not_physical_wall():
    source=record("wall-a","raster_opening_primitive:source:2.0.0:raster_wall_band_face:1")
    r=summarize_local_source_shadow(
        shadow((flank("first",ink=True,rows=(source,),exact=(source,),collapsed=1),
                flank("other",ink=False))),"id-one")
    assert len(r["opening_local_original_source_flanks"])==2
    assert not any(r[k] for k in (
        "real_original_candidate_scope_complete","physical_equivalence_granted",
        "new_host_granted","new_frame_granted","new_metric_quantity_granted",
        "opening_count_granted"))
    assert r["all_W4_competing_wall_ids_preserved"]
    assert sum(v["original_default_2_5pt_w2_snap_collapsed_count"]
               for v in r["opening_local_original_source_flanks"])==1


@pytest.mark.parametrize("mutation",[
    lambda s: setattr(s,"physical_opening_id","foreign"),
    lambda s: setattr(s,"status",Status.CORROBORATED),
    lambda s: setattr(s,"scope_complete",True),
    lambda s: setattr(s,"physical_wall_role_granted",True),
    lambda s: setattr(s,"opening_host_granted",True),
    lambda s: setattr(s,"metric_quantity_granted",True),
    lambda s: setattr(s,"flanks",s.flanks[:1]),
    lambda s: setattr(s,"flanks",(s.flanks[0],s.flanks[0])),
])
def test_foreign_missing_or_promoted_source_fails_closed(mutation):
    s=shadow((flank("first"),flank("other")))
    mutation(s)
    with pytest.raises(ValueError):
        summarize_local_source_shadow(s,"id-one")


def test_non_solid_original_paint_cannot_create_wall():
    sid="raster_opening_primitive:source:2.0.0:raster_wall_band_face:1"
    s=shadow((flank("a",ink=False,rows=(record("wall1",sid),)),
              flank("b",ink=True)))
    with pytest.raises(ValueError,match="non-solid"):
        summarize_local_source_shadow(s,"id-one")


def test_bogus_source_candidate_namespace_fails():
    s=shadow((flank("a",rows=(record("wall1","raster_segment:untrusted"),)),
              flank("b")))
    with pytest.raises(ValueError,match="ancestry"):
        summarize_local_source_shadow(s,"id-one")


def test_duplicate_w4_candidate_identity_fails_not_first_wins():
    sid="raster_opening_primitive:source:2.0.0:raster_wall_band_face:1"
    record1=record("w",sid)
    s=shadow((flank("a",rows=(record1,record1)),flank("b")))
    with pytest.raises(ValueError,match="duplicate"):
        summarize_local_source_shadow(s,"id-one")


def test_invalid_snap_counter_fails_closed():
    s=shadow((flank("a",collapsed=-1),flank("b")))
    with pytest.raises(ValueError,match="collapse"):
        summarize_local_source_shadow(s,"id-one")


def test_does_not_allocate_physical_identity_from_original_pdf_hash_alone():
    with pytest.raises(ValueError,match="hash"):
        original_unhosted_source_role_replay(
            b"not a real PDF",expected_sha256="a"*64)


def test_non_original_selected_page_scope_rejected():
    with pytest.raises(ValueError):
        original_unhosted_source_role_replay(
            b"some test bytes",
            expected_sha256=__import__("hashlib").sha256(b"some test bytes").hexdigest(),
            page_id="4")
