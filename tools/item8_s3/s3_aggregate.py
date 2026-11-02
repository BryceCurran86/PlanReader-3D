"""Apply the PRE-REGISTERED S3 rules (docs/engineering/claude_item8_s3_population_study_20261102.md, Part A) to the census output.

usage: python tools/item8_s3/s3_aggregate.py <out_dir>   (the directory the driver wrote its per-page JSON counts to)"""
import collections
import json
import sys
from pathlib import Path

OUT = Path(sys.argv[1])
MIN_ITEMS = 20          # A4.1
CLEAN = 0.90            # A4.2
SPREAD = 0.15           # A4.2
DECISIVE_RATIO = 10.0   # A3 R-B

pages = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(OUT.glob("*_p*.json"))]
print("PAGES (document, page, status, structures found / processed, seconds)")
by_doc = collections.defaultdict(list)
for page in pages:
    by_doc[page["label"]].append(page)
    print("  %-12s p%-3d %-22s %5d / %-5d %7.1f s" % (page["label"], page["page"], page["status"], page["structures_found"],
                                                   page["structures_processed"], page["seconds"]))
print()
stats = {}
for label, plist in sorted(by_doc.items()):
    rows = [r for p in plist for r in p["rows"] if "anomaly" not in r]
    anomalies = sum(1 for p in plist for r in p["rows"] if "anomaly" in r)
    a_items = [r for r in rows if r["interior"] and all(i["available"] for i in r["interior"])]
    r_a_true = sum(1 for r in a_items if all(i["order"] in ("before_all", "after_all") for i in r["interior"]))
    b_lines = [f for r in rows if r["interior"] for f in r["face_ink"] if f["available"] and f["d_I"] is not None and f["d_M"] is not None]
    decisive = nearer_i = nearer_w = tie = 0
    for f in b_lines:
        lo, hi = sorted((f["d_I"], f["d_M"]))
        if f["d_I"] == f["d_M"]:
            tie += 1
        elif lo == 0 or hi / lo >= DECISIVE_RATIO:
            decisive += 1
            if f["d_I"] < f["d_M"]:
                nearer_i += 1
            else:
                nearer_w += 1
    c_lines = [f for r in rows for f in r["face_ink"] if f["available"]]
    c_same = sum(1 for f in c_lines if f["same_style"])
    by_locality = collections.Counter((f["locality"], "same_style" if f["same_style"] else "other_style") for f in c_lines)
    stats[label] = dict(structures=len(rows), anomalies=anomalies, with_interior=len(a_items), r_a_true=r_a_true,
                        b_items=len(b_lines), b_decisive=decisive, b_nearer_interior=nearer_i, b_nearer_wall=nearer_w, b_tie=tie,
                        c_items=len(c_lines), c_same=c_same, by_locality=by_locality)
    s = stats[label]
    print("DOCUMENT %s: %d structures (%d anomalies)" % (label, s["structures"], anomalies))
    print("   R-A items %d: interior ink entirely outside the face-line paint range in %d (%.1f%%)" % (
        s["with_interior"], s["r_a_true"], 100.0 * s["r_a_true"] / s["with_interior"] if s["with_interior"] else float("nan")))
    print("   R-B items %d: decisive %d (%.1f%%) [nearer interior %d, nearer wall %d], undecided %d (ties %d)" % (
        s["b_items"], decisive, 100.0 * decisive / s["b_items"] if s["b_items"] else float("nan"), nearer_i, nearer_w,
        s["b_items"] - decisive, tie))
    print("   R-C items %d: same style as a face line %d (%.1f%%)" % (
        s["c_items"], c_same, 100.0 * c_same / s["c_items"] if s["c_items"] else float("nan")))
    print("   face ink by locality and style:", dict(by_locality))
print()


def judge(name, per_doc):
    """per_doc: {doc: (n, fraction_in_dominant_value, dominant_value, extra_fraction_for_spread)}"""
    qualifying = {d: v for d, v in per_doc.items() if v[0] >= MIN_ITEMS}
    print("%s: qualifying documents (>= %d items): %s" % (name, MIN_ITEMS, sorted(qualifying) or "none"))
    if len(qualifying) < 2:
        print("   VERDICT: INCONCLUSIVE (fewer than two qualifying documents); the question stays ABSTAIN")
        return
    clean = all(v[1] >= CLEAN for v in qualifying.values())
    same_direction = len({v[2] for v in qualifying.values()}) == 1
    fractions = [v[1] for v in qualifying.values()]
    close = (max(fractions) - min(fractions)) <= SPREAD
    print("   per document: %s" % {d: (v[0], round(v[1], 3), v[2]) for d, v in qualifying.items()})
    print("   >=90%% in every qualifying document: %s | same dominant value: %s | within 15 points: %s" % (clean, same_direction, close))
    print("   VERDICT: %s" % ("CLEAN SEPARATOR" if clean and same_direction and close else "NOT a clean separator; the question stays ABSTAIN"))


judge("R-A (interior ink is its own paint block)", {
    d: (s["with_interior"], (s["r_a_true"] / s["with_interior"]) if s["with_interior"] else 0.0, "outside")
    for d, s in stats.items()})
judge("R-B (face ink falls decisively into one of two blocks)", {
    d: (s["b_items"], (s["b_decisive"] / s["b_items"]) if s["b_items"] else 0.0,
        "nearer_interior" if s["b_nearer_interior"] >= s["b_nearer_wall"] else "nearer_wall")
    for d, s in stats.items()})
judge("R-C (face ink has the wall's style, or does not)", {
    d: (s["c_items"], max(s["c_same"], s["c_items"] - s["c_same"]) / s["c_items"] if s["c_items"] else 0.0,
        "same_style" if s["c_same"] * 2 >= s["c_items"] else "other_style")
    for d, s in stats.items()})
