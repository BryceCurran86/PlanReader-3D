import sys, json, math, collections, bisect
sys.modules["rapidocr"]=None; sys.modules["onnxruntime"]=None
sys.path.insert(0,"C:/claude-work/ft3-p11-p7")
import fitz
from shapely.geometry import Polygon, Point
from pb_vector_geometry_v130 import extract_native_page
D="C:/claude-work/audit-out/ft3/"
faces=json.load(open(D+"faces.json")); S={s["tag"]:s for s in faces["scopes"]}
doc=fitz.open("C:/claude-work/ft3-p11-p7/documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
T=(-78.0,0.0)
marks={"M1 OFFICE":(327.779,1437.473),"M2 DRY STORE":(324.419,1022.272),"M3 WASH UP":(316.259,622.912),"M4 FOOD PREP":(586.74,642.832),"M5 FOOD SERVICE":(736.98,507.952),"sched":(1383.39,2205.645)}
def polys(scope):
    out={}
    for f in scope["faces"]: out[f["face_id"]]=(Polygon(f["polygon_pdf_pts"]).buffer(0),True)
    for f in scope["abstained_faces"]: out[f["face_id"]]=(Polygon(f["polygon_pdf_pts"]).buffer(0),False)
    return out
P7=polys(S["p7_viewport"]); P11=polys(S["p11_page"])
from shapely.affinity import translate
rows=[]
for name,(x,y) in marks.items():
    pt11=Point(x,y); pt7=Point(x+T[0],y+T[1])
    h11=[(fid,p,pub) for fid,(p,pub) in P11.items() if p.contains(pt11)]
    h7=[(fid,p,pub) for fid,(p,pub) in P7.items() if p.contains(pt7)]
    row={"mark":name,"p11_faces":[],"p7_faces_at_T0":[]}
    for fid,p,pub in h11:
        t=translate(p,*T)
        ov=[]
        for g,(q,qpub) in P7.items():
            if q.is_empty or not t.intersects(q): continue
            inter=t.intersection(q).area
            if inter<=1e-6: continue
            ov.append((g[-6:],round(inter/(t.union(q).area),4),round(q.area,1),qpub))
        ov.sort(key=lambda r:-r[1])
        row["p11_faces"].append({"face":fid[-6:],"published":pub,"area_pt2":round(p.area,1),"overlapping_p7_faces_by_iou":ov[:5],"n_p7_overlaps":len(ov),
                                 "n_iou_ge_0.98":sum(1 for r in ov if r[1]>=0.98)})
    for fid,p,pub in h7: row["p7_faces_at_T0"].append({"face":fid[-6:],"published":pub,"area_pt2":round(p.area,1)})
    rows.append(row)
    print(name,json.dumps(row)[:900])
json.dump(rows,open(D+"p0_mark_faces.json","w"),indent=1)
# face-level equivalence statistics over ALL p11 published faces
n=0;exact=0;cells=0
for fid,(p,pub) in P11.items():
    if not pub: continue
    t=translate(p,*T); n+=1
    best=0.0
    for g,(q,qp) in P7.items():
        if not t.intersects(q): continue
        inter=t.intersection(q).area
        if inter<=0: continue
        best=max(best,inter/t.union(q).area)
    if best>=0.98: exact+=1
print("p11 published faces",n,"with a p7 face at IoU>=0.98 under T0:",exact)
# W4 ownership behind OFFICE box sides
NS={7:{s["id"]:s for s in extract_native_page(doc[6])["segments"]},11:{s["id"]:s for s in extract_native_page(doc[10])["segments"]}}
box11=(251.04,1382.72,394.80,1585.04); box7=(box11[0]+T[0],box11[1],box11[2]+T[0],box11[3])
def owners(scope,page,box):
    prim_to_c=collections.defaultdict(set); grid={}
    for r in scope["w4_records"]:
        grid[r["wall_candidate_id"]]=r["grid_fully_opposed"]
        for pid in r["source_primitive_ids"]: prim_to_c[pid].add(r["wall_candidate_id"])
    x0,y0,x1,y1=box; res={}
    for name,o,c,lo,hi in (("x0","V",x0,y0,y1),("x1","V",x1,y0,y1),("y0","H",y0,x0,x1),("y1","H",y1,x0,x1)):
        prims=[]
        for pid,s in NS[page].items():
            a,b,cc,d=s["x1"],s["y1"],s["x2"],s["y2"]
            if o=="V" and abs(a-cc)<0.02 and abs(a-c)<=0.06 and min(b,d)<hi and max(b,d)>lo and math.hypot(cc-a,d-b)>=3: prims.append(pid)
            if o=="H" and abs(b-d)<0.02 and abs(b-c)<=0.06 and min(a,cc)<hi and max(a,cc)>lo and math.hypot(cc-a,d-b)>=3: prims.append(pid)
        cands=collections.Counter()
        owned=0; multi=0; unowned=0
        for pid in prims:
            cs=prim_to_c.get(pid,set())
            if not cs: unowned+=1
            else:
                owned+=1
                if len(cs)>1: multi+=1
                for cc2 in cs: cands[cc2]+=1
        res[name]={"primitives_on_side":len(prims),"owned_by_any_w4":owned,"unowned":unowned,"owned_by_multiple_candidates":multi,"distinct_candidates":len(cands),
                   "candidates_grid_opposed":sum(1 for k in cands if grid.get(k)),"top_candidates":[(k[-8:],v) for k,v in cands.most_common(3)]}
    return res
for tag,page,box in (("p7 (viewport scope, scope_complete=False)",7,box7),("p11 (page scope, scope_complete=True)",11,box11)):
    sc=S["p7_viewport"] if page==7 else S["p11_page"]
    print("W4 owners behind OFFICE box sides on",tag)
    for k,v in owners(sc,page,box).items(): print("  ",k,v)
