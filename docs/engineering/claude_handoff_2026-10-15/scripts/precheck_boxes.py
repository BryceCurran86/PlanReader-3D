import sys
sys.path.insert(0,"C:/claude-work/ft3-p11-p7")
sys.argv=[sys.argv[0]]
src=open("C:/claude-work/audit-out/ft3/wall_registration_nongrid.py",encoding="utf-8").read().split("def overlap(")[0]
exec(src)
W7, W11 = globals()["W7"], globals()["W11"]  # defined by the exec'd registration script above
from tools import diag_ft3_p11_p7_floor_correspondence as d
boxes={"OFFICE":(251.04,1382.72,394.80,1585.04),
       "FOOD PREP (native-dim approx)":(483.12,578.48,678.48,811.04),
       "COLD ROOM (native-dim approx)":(442.32,811.04,666.24,1175.12)}
marks=[("FT3",(327.779,1437.473)),("FT3",(316.259,622.912)),("FT3",(324.419,1022.272)),("FT3",(586.74,642.832)),("FT3",(736.98,507.952)),("EPX",(572.82,993.962)),("EPX",(572.82,1227.722)),("FT2",(484.26,1483.792)),("FT1",(935.46,1081.064))]
for name,b in boxes.items():
    corr=d.box_correspondence(b,lines_support=W11,lines_target=W7,orientation="identity",translation=(-78.0,0.0))
    print(name,corr["side_kinds"],"bounded",corr["wall_bounded_on_both_sheets"],"identical",corr["wall_evidence_identical_on_both_sheets"])
    for s,v in corr["sides"].items(): print("   ",s,"p11 cov",v["support_sheet"]["face_coverage"],"2nd",v["support_sheet"]["second_face"][:2],"| p7 cov",v["target_sheet"]["face_coverage"],"2nd",v["target_sheet"]["second_face"][:2],"iou",None if v["covered_interval_iou"] is None else round(v["covered_interval_iou"],3))
    print("   marks inside:",[(c,round(d.point_margin(p,b),1)) for c,p in marks if d.point_margin(p,b)>0])
