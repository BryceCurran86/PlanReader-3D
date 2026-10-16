import json, re, subprocess, itertools
R="BryceCurran86/PlanReader-3D"
prs=json.loads(subprocess.run(["gh","pr","list","-R",R,"--state","open","--limit","100","--json","number,title,isDraft,headRefName,baseRefOid,files,mergeable"],capture_output=True,text=True,encoding="utf-8").stdout)
PROD=re.compile(r"^(pb_[a-z0-9_]+\.py|tools/run_source_closed_project_handoff\.py)$")
info={}
for p in prs:
    prod={f["path"] for f in p["files"] if PROD.match(f["path"])}
    allf={f["path"] for f in p["files"]}
    info[p["number"]]=(prod,allf,p)
print("PR pairs sharing a production file (excluding pure-shadow pb_g17_*):")
for a,b in itertools.combinations(sorted(info),2):
    s=info[a][0]&info[b][0]
    s={x for x in s if not x.startswith("pb_g17_")}
    if s: print(f"  #{a} x #{b}: {sorted(s)}")
print("\nPR pairs sharing ANY file (docs/tests/workflows too), at least one production-touching:")
for a,b in itertools.combinations(sorted(info),2):
    if not (info[a][0] or info[b][0]): continue
    s=info[a][1]&info[b][1]
    if s and not (info[a][0]&info[b][0]): print(f"  #{a} x #{b}: {sorted(s)[:4]}")
print("\nconflicting with main:",[n for n,(_,_,p) in info.items() if p["mergeable"]=="CONFLICTING"])
