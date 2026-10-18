"""Original selector multiplicity never becomes another physical door or host."""
from types import SimpleNamespace as Obj
from pb_migration_contracts import EvidenceResolutionStatus as Status
from tools.diag_gptmax_unmeasured_flank_capture_shadow import (
    _source_unique_original_opening_host_rows,
)


def r(physical,source,status=Status.ABSTAINED,host=None,wall=None,members=()):
    return Obj(opening_identity_id=physical,representative_observation_id=source,
               status=status,record_id=host,host_wall_id=wall,
               member_wall_candidate_ids=members,reason_codes=("source-gate",))


def test_original_two_views_of_2127_are_one_physical_instance_not_two():
    rows,count,hosts,duplicates=_source_unique_original_opening_host_rows([
        r("original-2127","p3",Status.CORROBORATED,"h1","wall",("l","r")),
        r("original-2127","p5",Status.CORROBORATED,"h1","wall",("l","r")),
    ])
    assert len(rows)==2
    assert count==1 and hosts==0 and duplicates==["original-2127"]


def test_unresolved_original_a68_33d_are_not_physical_counts():
    rows,count,hosts,duplicates=_source_unique_original_opening_host_rows([
        r(None,"source-a68-negative"),r(None,"source-33d-negative"),
        r("real-opening","source-real",Status.CORROBORATED,
          "host","original-wall",("m1",)),
    ])
    assert len(rows)==3 and count==1 and hosts==1 and duplicates==[]


def test_host_record_without_source_wall_membership_cannot_count_as_host():
    rows,count,hosts,duplicates=_source_unique_original_opening_host_rows([
        r("p1","o1",Status.CORROBORATED,"h","wall",()),
        r("p2","o2",Status.CANDIDATE,"h","wall",("member",)),
    ])
    assert count==2 and hosts==0 and duplicates==[]
