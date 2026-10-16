import sys, bisect, collections, math, json
sys.modules["rapidocr"]=None; sys.modules["onnxruntime"]=None
sys.path.insert(0,"C:/claude-work/ft3-p11-p7")
import fitz
from pb_vector_geometry_v130 import extract_native_page
PDF="C:/claude-work/ft3-p11-p7/documents/sources/Arch_Combined_Maryborough_Service_Station.pdf"
doc=fitz.open(PDF)
def lines(n,minw=0.0):
    raw={"H":collections.defaultdict(list),"V":collections.defaultdict(list)}
    for s in extract_native_page(doc[n-1])["segments"]:
        a,b,c,d=s["x1"],s["y1"],s["x2"],s["y2"]
        if math.hypot(c-a,d-b)<3: continue
        if abs(d-b)<0.02: raw["H"][round(b,2)].append((min(a,c),max(a,c)))
        elif abs(c-a)<0.02: raw["V"][round(a,2)].append((min(b,d),max(b,d)))
    def merge(v):
        out=[]
        for lo,hi in sorted(v):
            if out and lo<=out[-1][1]+1e-6: out[-1][1]=max(out[-1][1],hi)
            else: out.append([lo,hi])
        return out
    L={o:{k:merge(v) for k,v in raw[o].items()} for o in "HV"}
    return L,{o:sorted(L[o]) for o in "HV"}
LW={7:lines(7),11:lines(11)}
D=[251.04,1382.72,394.80,1585.04]   # OFFICE dimension box on p11 (cross-view record metadata)
def side_report(page,box,tol):
    x0,y0,x1,y1=box; L,K=LW[page]; out=[]
    for name,o,c,lo,hi in (("x=x0","V",x0,y0,y1),("x=x1","V",x1,y0,y1),("y=y0","H",y0,x0,x1),("y=y1","H",y1,x0,x1)):
        keys=K[o]; best=None
        i=bisect.bisect_left(keys,c-tol)
        cands=[]
        while i<len(keys) and keys[i]<=c+tol:
            cov=sum(max(0,min(b,hi)-max(a,lo)) for a,b in L[o][keys[i]])
            cands.append((round(keys[i]-c,2),round(cov/(hi-lo),3)))
            i+=1
        out.append((name,round(c,2),cands))
    return out
for page,box,label in ((11,D,"p11 box"),(7,[D[0]-78,D[1],D[2]-78,D[3]],"p7 box = T0(box)")):
    print("==",label,[round(v,2) for v in box])
    for r in side_report(page,box,1.5): print("  ",r)

print("\n-- outward second-face search (3..15 pt outside each side) --")
def outward(page,box,label):
    x0,y0,x1,y1=box; L,K=LW[page]
    for name,o,c,lo,hi,sgn in (("x0","V",x0,y0,y1,-1),("x1","V",x1,y0,y1,+1),("y0","H",y0,x0,x1,-1),("y1","H",y1,x0,x1,+1)):
        res=[]
        for k in K[o]:
            d=(k-c)*sgn
            if 3.0<=d<=15.0:
                cov=sum(max(0,min(b,hi)-max(a,lo)) for a,b in L[o][k])/(hi-lo)
                if cov>=0.5: res.append((round(d,2),round(cov,3)))
        print(label,name,res)
outward(7,[D[0]-78,D[1],D[2]-78,D[3]],"p7 ")
outward(11,D,"p11")
