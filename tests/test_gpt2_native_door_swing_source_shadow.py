"""Original-source door motif gates: no walls/counts/finish or metric grants."""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import os
import fitz
import pytest
from pb_gpt2_native_door_swing_source_shadow import inspect_native_door_swing_source_shadow as inspect

import math

# Source-neutral synthetic fixture, intentionally NOT owner-original CAD
# geometry. The private-original replay below uses only SHA/native selectors.
HINGE=(100.0,100.0)
RADIUS=50.0
_PTS=tuple((HINGE[0]+RADIUS*math.cos(i*math.pi/18),
            HINGE[1]-RADIUS*math.sin(i*math.pi/18)) for i in range(10))
ARC=tuple(zip(_PTS, _PTS[1:]))
LEAF=[((100.,100.),(100.,50.)),
 ((102.,100.),(100.,100.)),
 ((102.,50.),(102.,100.)),
 ((100.,50.),(102.,50.))]
JAMBS=[((98.,107.),(98.,100.)),
 ((152.,100.),(152.,107.))]

def pdf(*, arc_gap=False, fake_bubble=False, leaf_broken=False, bad_ink=False, remote_label=False, second_local_label=False):
    d=fitz.open();p=d.new_page(width=400,height=400)
    for i,(a,b) in enumerate(LEAF):
        p.draw_line(a,(b[0]+3 if leaf_broken and i==3 else b[0],b[1]),color=(0,0,0),width=.96)
    for i,(a,b) in enumerate(ARC):
        p.draw_line(((a[0]+2,a[1]) if arc_gap and i==4 else a),b,
                    color=(.2,0,0) if bad_ink and i==0 else (0,0,0),width=.48)
    for a,b in JAMBS:p.draw_line(a,b,color=(0,0,0),width=.96)
    if fake_bubble:
        for i in range(8):
            p.draw_line((40+i,200),(41+i,200),color=(0,0,0),width=.48)
    p.insert_text((124,275 if remote_label else 104),'D15',fontsize=10)
    if second_local_label:p.insert_text((135,114),'D07',fontsize=10)
    data=d.tobytes();d.close()
    return data


def check(raw,**kw):
    args=dict(expected_source_sha256=sha256(raw).hexdigest(),page_number=1,
        word_address=(0,0,0),leaf_path_ids=(0,1,2,3),
        swing_path_ids=tuple(range(4,13)),jamb_path_ids=(13,14))
    args.update(kw)
    return inspect(raw,**args)


def test_native_source_original_swing_is_candidate_and_never_metric_or_quantity():
    r=check(pdf())
    assert r.native_door_label=='D15'
    assert r.status=='source_door_swing_ink_candidate_only'
    assert r.leaf_length_pt==pytest.approx(50.0,abs=.001)
    assert r.swing_radius_pt==pytest.approx(50.0,abs=.001)
    assert not any([r.physical_door_identity_issued,r.structural_wall_host_issued,
         r.doorway_threshold_issued,r.source_metric_dimension_issued,
         r.floor_finish_area_issued,r.opening_count_issued,r.commercial_projection_allowed])


def test_unrelated_circle_is_not_a_swing_source_parent():
    raw=pdf(fake_bubble=True)
    r=check(raw)
    assert r.swing_path_ids==tuple(range(4,13))
    with pytest.raises(ValueError):
        check(raw,swing_path_ids=tuple(range(15,23)))


def test_wrong_original_sha_fails_even_for_unchanged_valid_geometry():
    with pytest.raises(ValueError,match='SHA'):
        check(pdf(),expected_source_sha256='0'*64)


@pytest.mark.parametrize('change',[
    {'swing_path_ids':tuple(range(4,12))+(4,)},
    {'leaf_path_ids':(0,1,1,3)},
    {'word_address':(3,0,0)},
    {'page_number':2},
    {'tolerance_pt':2.5},
])
def test_borrowed_or_repeated_source_reference_never_passes(change):
    with pytest.raises(ValueError):check(pdf(),**change)


def test_gapped_arc_and_invalid_ink_fail_closed():
    with pytest.raises(ValueError):check(pdf(arc_gap=True))
    with pytest.raises(ValueError,match='opaque black'):
        check(pdf(bad_ink=True))


def test_invalid_leaf_end_cap_fails_closed():
    with pytest.raises(ValueError):check(pdf(leaf_broken=True))


def test_reversing_complete_arc_source_order_is_invariant():
    raw=pdf()
    assert check(raw,swing_path_ids=tuple(reversed(range(4,13)))).hinge_pt==check(raw).hinge_pt


def test_private_original_maryborough_source_if_provisioned():
    loc=os.environ.get('PLANREADER_MARYBOROUGH_ORIGINAL_PDF')
    if not loc:pytest.skip('private original PDF not provisioned on public CI')
    b=Path(loc).read_bytes()
    expected='b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007'
    assert sha256(b).hexdigest()==expected
    r=inspect(b,expected_source_sha256=expected,page_number=7,
        word_address=(183,0,0),leaf_path_ids=tuple(range(69400,69404)),
        swing_path_ids=tuple(range(69404,69413)),jamb_path_ids=(69419,69421))
    assert r.native_door_label=='D15'
    assert r.swing_radius_pt==pytest.approx(52.08,abs=.001)
    assert r.status=='source_door_swing_ink_candidate_only'

def test_same_page_remote_door_word_cannot_claim_this_swing():
    with pytest.raises(ValueError,match='remote'):
        check(pdf(remote_label=True))

def test_competing_original_door_code_inside_same_jamb_scope_blocks_candidate():
    with pytest.raises(ValueError,match='competing'):
        check(pdf(second_local_label=True))

@pytest.mark.parametrize('degrees,reason',[
    (tuple(-90-30*i for i in range(10)), 'quarter sweep'),
    ((-90,-78,-60,-72,-51,-40,-30,-15,-7,0), 'changes direction'),
])
def test_angular_winding_and_backtracking_are_not_source_door_swings(degrees, reason):
    # A 270-degree winding ends on the SAME perpendicular vector as a
    # true quarter turn. Source-monotone orientation must also be proven.
    d=fitz.open()
    page=d.new_page(width=400,height=400)
    for a,b in LEAF:
        page.draw_line(a,b,color=(0,0,0),width=.96)
    pts=[(100+50*math.cos(math.radians(a)),
          100+50*math.sin(math.radians(a))) for a in degrees]
    for a,b in zip(pts,pts[1:]):
        page.draw_line(a,b,color=(0,0,0),width=.48)
    for a,b in JAMBS:
        page.draw_line(a,b,color=(0,0,0),width=.96)
    page.insert_text((124,104),'D15',fontsize=10)
    raw=d.tobytes()
    d.close()
    with pytest.raises(ValueError,match=reason):
        check(raw)

def test_equal_length_but_oblique_door_leaf_faces_are_not_parallel():
    # Demonstrated red before patch: two long edges each length 50 and
    # end caps close, but this is an oblique wedge, not a door leaf.
    doc=fitz.open()
    p=doc.new_page(width=400,height=400)
    far=(102+50*math.sin(.12),100-50*math.cos(.12))
    leaf=((LEAF[0][0],LEAF[0][1]),
          ((102.,100.),LEAF[0][0]),
          (far,(102.,100.)),
          (LEAF[0][1],far))
    for a,b in leaf:
        p.draw_line(a,b,color=(0,0,0),width=.96)
    for a,b in ARC:
        p.draw_line(a,b,color=(0,0,0),width=.48)
    for a,b in JAMBS:
        p.draw_line(a,b,color=(0,0,0),width=.96)
    p.insert_text((124,104),'D15',fontsize=10)
    raw=doc.tobytes()
    doc.close()
    with pytest.raises(ValueError,match='parallel'):
        check(raw)

def test_single_source_wall_stroke_cannot_claim_both_door_jambs():
    # A single black horizontal bridge touching BOTH opening termini used
    # to satisfy the two independent any(jamb) checks. The unrelated second
    # line is not a genuine far-side jamb. Must fail closed, not grant a door.
    d=fitz.open()
    p=d.new_page(width=400,height=400)
    for a,b in LEAF:
        p.draw_line(a,b,color=(0,0,0),width=.96)
    for a,b in ARC:
        p.draw_line(a,b,color=(0,0,0),width=.48)
    for a,b in (((100.,100.),(150.,100.)),
                ((250.,250.),(255.,250.))):
        p.draw_line(a,b,color=(0,0,0),width=.96)
    p.insert_text((124,104),'D15',fontsize=10)
    raw=d.tobytes()
    d.close()
    with pytest.raises(ValueError,match='bridges both ends'):
        check(raw)
