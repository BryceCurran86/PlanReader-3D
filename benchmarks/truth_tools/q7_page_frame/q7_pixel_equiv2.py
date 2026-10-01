"""Q7 follow-up (scratch, read-only): is the <100% pixel match raster noise or a mapping offset?
(1) pixel-INDEX agreement of the descriptor mapping vs MuPDF's own page.rotation_matrix (raster independent);
(2) match on ink with exact index vs a +/-1 px neighbourhood; (3) rot-0 pages as a ceiling control."""
import hashlib, json, sys
repo, pdf, doc_id = sys.argv[1:4]; sys.path.insert(0, repo)
import fitz, numpy as np, pb_page_frame_shadow as pf
data = open(pdf, "rb").read(); sha = hashlib.sha256(data).hexdigest()
doc = fitz.open(stream=data, filetype="pdf"); doc0 = fitz.open(stream=data, filetype="pdf"); rev = pf.revision_id_for(doc_id, sha)
S = 13; rows = []
for n in range(1, doc.page_count + 1):
    page = doc[n - 1]; f = pf.describe_page_frame(page, document_id=doc_id, source_sha256=sha, revision=rev, page_no=n)
    ne, rot = f.native_extent, f.rotation
    p0 = doc0[n - 1]; p0.set_rotation(0)
    pu = p0.get_pixmap(matrix=fitz.Matrix(1, 1), colorspace=fitz.csGRAY, alpha=False); U = np.frombuffer(pu.samples, np.uint8).reshape(pu.height, pu.width)
    pr = page.get_pixmap(matrix=fitz.Matrix(1, 1), colorspace=fitz.csGRAY, alpha=False); R = np.frombuffer(pr.samples, np.uint8).reshape(pr.height, pr.width)
    ys, xs = np.mgrid[0:pu.height:S, 0:pu.width:S]; xs = xs.ravel(); ys = ys.ravel(); rm = page.rotation_matrix
    idx_agree = exact = tol1 = n_ink = 0; max_idx_delta = 0
    for x, y in zip(xs, ys):
        q = pf.native_to_display(pf.NativePoint(x + 0.5, y + 0.5), native_extent=ne, rotation=rot)
        m = fitz.Point(x + 0.5, y + 0.5) * rm
        di = (int(np.floor(q.x)), int(np.floor(q.y))); mi = (int(np.floor(m.x)), int(np.floor(m.y)))
        idx_agree += (di == mi); max_idx_delta = max(max_idx_delta, abs(di[0] - mi[0]), abs(di[1] - mi[1]))
        if U[y, x] < 250 and 1 <= di[0] < pr.width - 1 and 1 <= di[1] < pr.height - 1:
            n_ink += 1; u = int(U[y, x])
            exact += abs(int(R[di[1], di[0]]) - u) <= 8
            tol1 += bool((np.abs(R[di[1]-1:di[1]+2, di[0]-1:di[0]+2].astype(int) - u) <= 8).any())
    rows.append({"page": n, "rot": rot, "pts": int(len(xs)), "index_agreement_vs_mupdf": round(idx_agree / len(xs), 6), "max_index_delta_px": max_idx_delta,
                 "ink_pts": n_ink, "match_exact_index": round(exact / n_ink, 4) if n_ink else None, "match_pm1px": round(tol1 / n_ink, 4) if n_ink else None})
json.dump(rows, open(sys.argv[4], "w"), indent=1)
r90 = [r for r in rows if r["rot"] == 90]; r0 = [r for r in rows if r["rot"] == 0]
def rng(k, rs): v = [r[k] for r in rs if r[k] is not None]; return (min(v), round(float(np.median(v)), 4), max(v)) if v else None
print("rot-90 pages:", len(r90), "| index agreement vs MuPDF rotation_matrix  min/median/max:", rng("index_agreement_vs_mupdf", r90), "| max index delta px:", max(r["max_index_delta_px"] for r in r90))
print("rot-90 ink match, exact index  min/median/max:", rng("match_exact_index", r90))
print("rot-90 ink match, +/-1px nbhd  min/median/max:", rng("match_pm1px", r90))
print("rot-0 pages:", len(r0), "| index agreement:", rng("index_agreement_vs_mupdf", r0), "| exact:", rng("match_exact_index", r0), "| +/-1px:", rng("match_pm1px", r0))
print("lowest 3 rot-90 pages by pm1px:", sorted(((r["page"], r["match_pm1px"], r["match_exact_index"]) for r in r90), key=lambda t: t[1])[:3])
