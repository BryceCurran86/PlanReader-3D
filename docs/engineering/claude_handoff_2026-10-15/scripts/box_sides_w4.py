import sys, json
sys.argv=[sys.argv[0]]
src=open("C:/claude-work/audit-out/ft3/wall_registration_nongrid.py",encoding="utf-8").read().split("def overlap(")[0]
exec(src)
W7, W11 = globals()["W7"], globals()["W11"]  # defined by the exec'd registration script above
D=[251.04,1382.72,394.80,1585.04]
import bisect
def lines_cov(L,o,c,lo,hi,tol):
    K=sorted(L[o]); i=bisect.bisect_left(K,c-tol); out=[]
    while i<len(K) and K[i]<=c+tol:
        cov=sum(max(0,min(b,hi)-max(a,lo)) for a,b in L[o][K[i]])/(hi-lo); out.append((round(K[i]-c,2),round(cov,3))); i+=1
    return out
for page,L,box,label in ((7,W7,[D[0]-78,D[1],D[2]-78,D[3]],"p7 nongrid-W4"),(11,W11,D,"p11 nongrid-W4")):
    x0,y0,x1,y1=box
    print(label)
    for name,o,c,lo,hi,sg in (("x0","V",x0,y0,y1,-1),("x1","V",x1,y0,y1,1),("y0","H",y0,x0,x1,-1),("y1","H",y1,x0,x1,1)):
        face=lines_cov(L,o,c,lo,hi,0.06)
        out=[(round((k-c)*sg,2),round(sum(max(0,min(b,hi)-max(a,lo)) for a,b in L[o][k])/(hi-lo),3)) for k in sorted(L[o]) if 3.0<=(k-c)*sg<=15.0]
        out=[r for r in out if r[1]>=0.5]
        print("  ",name,"face",face,"outward",out)
