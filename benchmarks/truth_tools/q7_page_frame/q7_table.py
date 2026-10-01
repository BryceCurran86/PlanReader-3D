import json, glob, os, sys
SP = sys.argv[1]
m = json.load(open(f"{SP}/sub/map.json"))
rows = []; tops = []
for f in sorted(glob.glob(f"{SP}/rerun_*.json")):
    name = os.path.basename(f)[6:-5]; r = json.load(open(f))
    tops.append((name, r["snapshot_id_at_ingest"], r["snapshot_id_consumed"], r["unresolved_pages"], r["document_id"], r["_seconds"], r["schema_version"]))
    for i, p in enumerate(r["pages"]):
        s = p["summary"]
        rows.append(dict(src=m[name][i], sub=name, rot=p["frame"]["rotation"], frame=p["frame"]["status"], walls=s["walls"], dang=s["dangling_ends"],
                         cur=s["current_at_boundary"], shd=s["shadow_default_tol_at_boundary"], shq=s["shadow_quantised_tol_at_boundary"],
                         dd=s["divergent_default_tol"], dq=s["divergent_quantised_tol"], scope=p["scope_resolution_status"], valid=p["comparison_valid"],
                         pipe=p["pipeline_status"], xc=p["cross_check"], refreshed=p["snapshot_refreshed"], snap=p["snapshot_id_consumed"], at_ing=p["snapshot_id_at_ingest"]))
print("subset | snapshot at ingest (A) -> consumed (B) | unresolved pages | doc id | seconds")
for t in tops: print(f"{t[0]:5} | {t[1][-12:]} -> {t[2][-12:]} | {t[3]} | {t[4]} | {t[5]}s | schema {t[6]}")
print()
print("src_pg /Rotate frame  walls dangling cur shadow(def/q) div(def/q) scope      valid pipeline xcheck  refreshed")
for r in sorted(rows, key=lambda r: (r["rot"] == 0, r["src"])):
    print(f'{r["src"]:>6} {r["rot"]:>7} {r["frame"]:>6} {r["walls"]:>6} {r["dang"]:>8} {r["cur"]:>3} {r["shd"]:>5}/{r["shq"]:<3} {r["dd"]:>5}/{r["dq"]:<3} {r["scope"]:>9} {str(r["valid"]):>6} {r["pipe"]:>8} {r["xc"]:>6} {str(r["refreshed"]):>8}')
rot = [r for r in rows if r["rot"] == 90]
print(f'\nrot-90 pages: {len(rot)} | all valid: {all(r["valid"] for r in rot)} | all refreshed: {all(r["refreshed"] for r in rot)} | any at-boundary end: {any(r["cur"] or r["shd"] or r["shq"] for r in rows)} | any divergence: {any(r["dd"] or r["dq"] for r in rows)} | walls total: {sum(r["walls"] for r in rot)} | dangling total: {sum(r["dang"] for r in rot)}')
