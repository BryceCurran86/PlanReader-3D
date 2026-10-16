import sys, json, math
sys.modules["rapidocr"]=None; sys.modules["onnxruntime"]=None
sys.path.insert(0,"C:/claude-work/ft3-p11-p7")
import fitz
from shapely.geometry import Polygon, box as sbox, Point
D=[251.04,1382.72,394.80,1585.04]; T=(-78.0,0.0)
Dp=[D[0]+T[0],D[1]+T[1],D[2]+T[0],D[3]+T[1]]
faces=json.load(open("faces.json")); S={s["tag"]:s for s in faces["scopes"]}
live=json.load(open("p7_live.json"))
b7=sbox(*Dp)
print("D' (p7):",Dp,"area pt2",round(b7.area,1))
s7=S["p7_viewport"]; pub={f["face_id"] for f in s7["faces"]}
inside=[];cross=[]
for f in s7["faces"]+s7["abstained_faces"]:
    p=Polygon(f["polygon_pdf_pts"]).buffer(0)
    if p.is_empty: continue
    inter=p.intersection(b7).area
    if inter<=1e-6: continue
    if p.within(b7.buffer(0.06)): inside.append((f["face_id"],p.area,f["face_id"] in pub))
    else: cross.append((f["face_id"],round(p.area,1),round(inter,1),f["face_id"] in pub))
print("p7 faces fully inside D':",len(inside),"area sum",round(sum(a for _,a,_ in inside),1),"(%.1f%% of D')"%(100*sum(a for _,a,_ in inside)/b7.area),"| published",sum(1 for *_,p in inside if p),"withheld",sum(1 for *_,p in inside if not p))
print("p7 faces crossing D' boundary:",cross)
# labelled/measured faces inside D'
rec2face={f["record_id"]:f["face_id"] for f in s7["faces"]}
for r in live["rooms"]:
    if r.get("room_label"):
        fid=rec2face[r["source_room_face_record_id"]]
        poly=Polygon(r["polygon_pdf_pts"]).buffer(0)
        print("  labelled face",r["room_label"],"inside D':",poly.within(b7.buffer(0.06)))
# p11 side: faces inside D (p11)
s11=S["p11_page"]; b11=sbox(*D); cnt=0;ar=0;cr=[]
for f in s11["faces"]+s11["abstained_faces"]:
    p=Polygon(f["polygon_pdf_pts"]).buffer(0)
    inter=p.intersection(b11).area
    if inter<=1e-6: continue
    if p.within(b11.buffer(0.06)): cnt+=1; ar+=p.area
    else: cr.append((f["face_id"][-6:],round(p.area,1),round(inter,1)))
print("p11 faces inside D:",cnt,"area %.1f%%"%(100*ar/b11.area),"| crossing:",cr[:8],len(cr))
# words inside D on p11 and on p7 D'
doc=fitz.open("C:/claude-work/ft3-p11-p7/documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
for pg,bx,label in ((10,D,"p11 words inside D"),(6,Dp,"p7 words inside D'")):
    ws=[(w[4],round((w[0]+w[2])/2,1),round((w[1]+w[3])/2,1)) for w in doc[pg].get_text("words") if bx[0]<=(w[0]+w[2])/2<=bx[2] and bx[1]<=(w[1]+w[3])/2<=bx[3]]
    print(label,":",ws)
# mark margins
m=(327.8,1437.5)
print("M1 margins to D sides:",[round(v,1) for v in (m[0]-D[0],D[2]-m[0],m[1]-D[1],D[3]-m[1])])
