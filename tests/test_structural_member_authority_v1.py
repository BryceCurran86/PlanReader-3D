from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_member_authority import *

def sel(kind="column"):
    return StructuralMemberSelector("doc","rev","a"*64,"snap","scope",kind)

def obs(name, view="plan", page="1", kind="column", definition_id=None, primitive=None):
    return StructuralMemberObservation(
        observation_id=name, member_kind=kind, page_id=page, view_id=view,
        view_type=view, source_evidence_ids=(f"e:{name}",),
        source_primitive_ids=(() if primitive is None else (primitive,)),
        definition_id=definition_id,
    )

def scope(view="plan", page="1", complete=True, reasons=()):
    return StructuralMemberViewScope(page,view,view,complete,tuple(reasons))

def rel(a,b,r):
    return StructuralMemberRelationEvidence(a,b,r,(f"r:{a}:{b}",))

def pub(observations=(), relations=(), scopes=(scope(),), definitions=(), kind="column"):
    return StructuralMemberProducer.from_authenticated_evidence(
        selector=sel(kind), definitions=definitions, observations=observations,
        relations=relations, view_scopes=scopes).publish()

def test_definition_without_instance_abstains():
    d=StructuralMemberDefinition("def","column","50 mm CHS",("sched",),"3","schedule")
    r=pub(definitions=(d,),scopes=())
    assert r.status is EvidenceResolutionStatus.ABSTAINED
    assert STRUCTURAL_MEMBER_DEFINITION_ONLY in r.reason_codes
    assert r.quantity is None

def test_four_plan_plus_same_four_elevation_count_four():
    observations=tuple([obs(f"p{i}") for i in range(4)] + [obs(f"e{i}","elev","2") for i in range(4)])
    relations=tuple(rel(f"p{i}",f"e{i}",StructuralMemberRelation.SAME_PHYSICAL_MEMBER) for i in range(4))
    r=pub(observations,relations,(scope(),scope("elev","2")))
    assert r.status is EvidenceResolutionStatus.CORROBORATED
    assert r.quantity == 4

def test_four_plan_three_elevation_conflicts():
    observations=tuple([obs(f"p{i}") for i in range(4)] + [obs(f"e{i}","elev","2") for i in range(3)])
    relations=tuple(rel(f"p{i}",f"e{i}",StructuralMemberRelation.SAME_PHYSICAL_MEMBER) for i in range(3))
    r=pub(observations,relations,(scope(),scope("elev","2")))
    assert r.status is EvidenceResolutionStatus.CONFLICT
    assert STRUCTURAL_MEMBER_COUNT_CONFLICT in r.reason_codes

def test_geometry_proximity_cannot_deduplicate_without_positive_relation():
    r=pub((obs("a",primitive="path:1"),obs("b",primitive="path:2")))
    assert r.quantity == 2

def test_duplicate_primitive_needs_positive_same_relation():
    observations=(obs("a",primitive="path:77"),obs("b",primitive="path:77"))
    assert pub(observations).quantity == 2
    r=pub(observations,(rel("a","b",StructuralMemberRelation.SAME_PHYSICAL_MEMBER),))
    assert r.quantity == 1

def test_repeated_identical_chs_instances_remain_distinct():
    observations=tuple(obs(f"c{i}",kind="chs",primitive=f"path:{i}") for i in range(4))
    assert pub(observations,kind="chs").quantity == 4

def test_cropped_view_abstains():
    r=pub((obs("a"),obs("b")),scopes=(scope(complete=False,reasons=("cropped_view",)),))
    assert r.status is EvidenceResolutionStatus.ABSTAINED
    assert "cropped_view" in r.reason_codes

def test_ambiguous_cross_view_registration_abstains():
    observations=(obs("p"),obs("e","elev","2"))
    relations=(rel("p","e",StructuralMemberRelation.AMBIGUOUS),)
    r=pub(observations,relations,(scope(),scope("elev","2")))
    assert r.status is EvidenceResolutionStatus.ABSTAINED
    assert STRUCTURAL_MEMBER_RELATION_AMBIGUOUS in r.reason_codes

def test_same_and_distinct_relation_conflict():
    observations=(obs("p"),obs("e","elev","2"))
    relations=(rel("p","e",StructuralMemberRelation.SAME_PHYSICAL_MEMBER),
               rel("p","e",StructuralMemberRelation.DISTINCT_PHYSICAL_MEMBERS))
    r=pub(observations,relations,(scope(),scope("elev","2")))
    assert r.status is EvidenceResolutionStatus.CONFLICT

def test_definition_binding_does_not_add_quantity():
    d=StructuralMemberDefinition("def-chs","chs","50 mm CHS",("detail",),"4","detail")
    observations=tuple(obs(f"c{i}",kind="chs",definition_id="def-chs") for i in range(3))
    r=pub(observations,definitions=(d,),kind="chs")
    assert r.quantity == 3
    assert all(m.definition_ids == ("def-chs",) for m in r.members)

def test_equal_complete_views_without_positive_registration_abstain():
    observations=tuple([obs(f"p{i}") for i in range(4)] + [obs(f"e{i}","elev","2") for i in range(4)])
    r=pub(observations,relations=(),scopes=(scope(),scope("elev","2")))
    assert r.status is EvidenceResolutionStatus.ABSTAINED
    assert STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE in r.reason_codes
    assert r.quantity is None

def test_partial_cross_view_registration_abstains_even_when_counts_match():
    observations=tuple([obs(f"p{i}") for i in range(3)] + [obs(f"e{i}","elev","2") for i in range(3)])
    relations=(rel("p0","e0",StructuralMemberRelation.SAME_PHYSICAL_MEMBER),)
    r=pub(observations,relations,(scope(),scope("elev","2")))
    assert r.status is EvidenceResolutionStatus.ABSTAINED
    assert STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE in r.reason_codes
