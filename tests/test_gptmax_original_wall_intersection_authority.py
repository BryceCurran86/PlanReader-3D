from copy import deepcopy
import fitz
import pytest
from tools.gptmax_original_wall_intersection_authority import source_t_junction,source_perpendicular_return

LAYER='S-WALL-25CO'
def path(*segs,layer=LAYER):
 return {'layer':layer,'items':[('l',fitz.Point(*a),fitz.Point(*b)) for a,b in segs]}
def t_data():
 return [path(((0,10),(4,10))),path(((6,10),(10,10))),
         path(((4,0),(4,10))),path(((6,0),(6,10))),path(((0,12),(10,12)))]
def t_args():
 return dict(upper_left_path=0,upper_right_path=1,vertical_left_path=2,
  vertical_right_path=3,opposite_path=4,wall_layer=LAYER,x_outer_left=0,
  x_gap_left=4,x_gap_right=6,x_outer_right=10,y_upper=10,y_opposite=12,
  vertical_left_start_y=0,vertical_right_start_y=0)
def r_data():
 return [path(((5,10),(7,10)),((7,10),(7,12)),((7,12),(5,12))),
         path(((5,0),(5,10))),path(((5,12),(5,20))),path(((3,0),(3,20)))]
def r_args():
 return dict(cap_path=0,upper_vertical_path=1,lower_vertical_path=2,
  opposite_vertical_path=3,wall_layer=LAYER,x_face=5,x_cap=7,x_opposite=3,
  y_cap_top=10,y_cap_bottom=12,y_upper_start=0,y_lower_end=20,
  y_opposite_start=0,y_opposite_end=20)

def test_t_junction_positive_is_source_only():
 d=t_data(); before=deepcopy(d); r=source_t_junction(d,**t_args())
 assert r['status']=='SOURCE_PERPENDICULAR_T_JUNCTION_OBSERVATION_ONLY'
 assert r['exact_cad_gap_pt']==2
 assert r['horizontal_bridge_paths']==[]
 assert r['canonical_w4_host']==r['opening_area']=='ABSTAIN'
 assert r['new_firm_quantity'] is False and d==before

def test_t_junction_rejects_wrong_layer_displaced_face_and_duplicate():
 d=t_data();d[2]['layer']='G-TEXT-25CO'
 with pytest.raises(ValueError,match='layer mismatch'):source_t_junction(d,**t_args())
 d=t_data();d[3]=path(((6,0),(6.02,10)))
 with pytest.raises(ValueError,match='missing'):source_t_junction(d,**t_args())
 d=t_data()+[path(((0,10),(4,10)))]
 assert source_t_junction(d,**t_args())['status'].startswith('ABSTAIN_')

def test_t_junction_refuses_undrawn_bridge_or_competing_bridge():
 d=t_data()+[path(((4,10),(6,10)))]
 r=source_t_junction(d,**t_args())
 assert r['horizontal_bridge_paths']==[5]
 assert r['status'].startswith('ABSTAIN_')

def test_perpendicular_return_positive_is_source_only():
 d=r_data();before=deepcopy(d);r=source_perpendicular_return(d,**r_args())
 assert r['status']=='SOURCE_PERPENDICULAR_RETURN_OBSERVATION_ONLY'
 assert r['return_cap_width_pt']==2
 assert r['canonical_w4_host']==r['opening_frame']==r['opening_area']=='ABSTAIN'
 assert d==before

def test_perpendicular_return_rejects_missing_cap_wrong_layer_and_duplicate():
 d=r_data();d[0]=path(((5,10),(7,10)),((7,10),(7,12)))
 with pytest.raises(ValueError,match='three-sided'):source_perpendicular_return(d,**r_args())
 d=r_data();d[3]['layer']='G-TEXT-25CO'
 with pytest.raises(ValueError,match='layer mismatch'):source_perpendicular_return(d,**r_args())
 d=r_data()+[path(((5,10),(7,10)))]
 assert source_perpendicular_return(d,**r_args())['status']=='ABSTAIN_COMPETING_SOURCE'

@pytest.mark.parametrize('bad',[float('nan'),float('inf'),True,'4'])
def test_invalid_geometry_fails_closed(bad):
 with pytest.raises(ValueError):source_t_junction(t_data(),**{**t_args(),'x_gap_left':bad})
 with pytest.raises(ValueError):source_perpendicular_return(r_data(),**{**r_args(),'x_cap':bad})

def test_t_junction_rejects_partial_same_layer_duplicate():
 d=t_data()+[path(((1,10),(3,10)))]
 r=source_t_junction(d,**t_args())
 assert r['status']=='ABSTAIN_COMPETING_OR_BRIDGED_STRUCTURAL_SOURCE'
 assert r['competing_paths']==[5]

def test_t_junction_rejects_partial_bridge_without_fabricating_wall():
 d=t_data()+[path(((4,10),(5,10)))]
 r=source_t_junction(d,**t_args())
 assert r['status']=='ABSTAIN_COMPETING_OR_BRIDGED_STRUCTURAL_SOURCE'
 assert r['horizontal_bridge_paths']==[5]

def test_t_junction_endpoint_touch_is_not_false_competition():
 d=t_data()+[path(((4,10),(4,11)))]
 r=source_t_junction(d,**t_args())
 assert r['status']=='SOURCE_PERPENDICULAR_T_JUNCTION_OBSERVATION_ONLY'

def test_perpendicular_return_rejects_partial_same_layer_duplicate():
 d=r_data()+[path(((5,10.2),(5,11.8)))]
 r=source_perpendicular_return(d,**r_args())
 assert r['status']=='SOURCE_PERPENDICULAR_RETURN_OBSERVATION_ONLY'
 d=r_data()+[path(((7,10.2),(7,11.8)))]
 r=source_perpendicular_return(d,**r_args())
 assert r['status']=='ABSTAIN_COMPETING_SOURCE'

@pytest.mark.parametrize('scale,dx,dy',[(1,100,300),(2,0,0),(.5,-20,8)])
def test_t_junction_translation_scale_source_role_invariant(scale,dx,dy):
 d=[]
 for entry in t_data():
  segs=[]
  for item in entry['items']:
   a,b=item[1:3]
   segs.append(((a.x*scale+dx,a.y*scale+dy),(b.x*scale+dx,b.y*scale+dy)))
  d.append(path(*segs))
 args=t_args()
 for key in ('x_outer_left','x_gap_left','x_gap_right','x_outer_right'):
  args[key]=args[key]*scale+dx
 for key in ('y_upper','y_opposite','vertical_left_start_y','vertical_right_start_y'):
  args[key]=args[key]*scale+dy
 r=source_t_junction(d,**args)
 assert r['status']=='SOURCE_PERPENDICULAR_T_JUNCTION_OBSERVATION_ONLY'
 assert r['canonical_w4_host']=='ABSTAIN'

def test_input_order_permutation_preserves_source_role():
 d=t_data();order=[4,2,0,3,1]
 new=[d[i] for i in order]
 args=t_args()
 for key in ('upper_left_path','upper_right_path','vertical_left_path','vertical_right_path','opposite_path'):
  args[key]=order.index(args[key])
 r=source_t_junction(new,**args)
 assert r['status']=='SOURCE_PERPENDICULAR_T_JUNCTION_OBSERVATION_ONLY'
 assert r['canonical_w4_host']=='ABSTAIN'
