"""Q7 real-source exact mapping test (scratch, read-only). The same real page is rendered twice by MuPDF: as displayed
(its own /Rotate) and with rotation forced to 0 on an in-memory copy. For a dense grid of NATIVE points the descriptor's
native_to_display must land on the displayed pixel carrying the same value. Wrong mappings are negative controls.
Descriptor = PR's pb_page_frame_shadow, unchanged. No thresholds/rules are derived from the source."""
import hashlib, json, sys, time
repo, pdf, doc_id, pages, out, cls = sys.argv[1:7]
sys.path.insert(0, repo)
import fitz, numpy as np
import pb_page_frame_shadow as pf
data = open(pdf, "rb").read(); sha = hashlib.sha256(data).hexdigest()
doc = fitz.open(stream=data, filetype="pdf"); doc0 = fitz.open(stream=data, filetype="pdf")
rev = pf.revision_id_for(doc_id, sha)
res = {"source_class": cls, "document_id": doc_id, "sha256": sha, "grid_stride_px": 13, "pages": []}
wanted = range(1, doc.page_count + 1) if pages == "all" else [int(x) for x in pages.split(",")]
STRIDE = 13
for n in wanted:
    t = time.time(); page = doc[n - 1]
    f = pf.describe_page_frame(page, document_id=doc_id, source_sha256=sha, revision=rev, page_no=n)
    rec = {"page_no": n, "status": f.status.value, "rotation": f.rotation, "native_wh": [f.native_extent.width, f.native_extent.height] if f.native_extent else None}
    if f.status.value != "raw" or f.native_extent is None:
        rec["skipped"] = "descriptor not coherent"; res["pages"].append(rec); print(n, rec); continue
    ne, de, rot = f.native_extent, f.display_extent, f.rotation
    p0 = doc0[n - 1]; p0.set_rotation(0)           # in-memory copy only
    U = np.frombuffer(p0.get_pixmap(matrix=fitz.Matrix(1, 1), colorspace=fitz.csGRAY, alpha=False).samples, np.uint8)
    pu = p0.get_pixmap(matrix=fitz.Matrix(1, 1), colorspace=fitz.csGRAY, alpha=False); U = U.reshape(pu.height, pu.width)
    pr = page.get_pixmap(matrix=fitz.Matrix(1, 1), colorspace=fitz.csGRAY, alpha=False)
    R = np.frombuffer(pr.samples, np.uint8).reshape(pr.height, pr.width)
    rec["unrotated_render_wh"] = [pu.width, pu.height]; rec["displayed_render_wh"] = [pr.width, pr.height]
    rec["render_shapes_consistent_with_descriptor"] = (pu.width, pu.height) == (round(ne.width), round(ne.height)) and (pr.width, pr.height) == (round(de.width), round(de.height))
    ys, xs = np.mgrid[0:pu.height:STRIDE, 0:pu.width:STRIDE]; xs = xs.ravel(); ys = ys.ravel()
    ink = U[ys, xs] < 250
    rec["grid_points"] = int(len(xs)); rec["grid_points_on_ink"] = int(ink.sum())
    def evaluate(fn):
        ok_all = ok_ink = n_all = n_ink = oob = 0
        for x, y, is_ink in zip(xs, ys, ink):
            dx, dy = fn(x + 0.5, y + 0.5)
            ix, iy = int(np.floor(dx)), int(np.floor(dy))
            if not (0 <= ix < pr.width and 0 <= iy < pr.height): oob += 1; continue
            same = abs(int(R[iy, ix]) - int(U[y, x])) <= 8
            n_all += 1; ok_all += same
            if is_ink: n_ink += 1; ok_ink += same
        return {"match_all": round(ok_all / n_all, 4) if n_all else None, "match_on_ink": round(ok_ink / n_ink, 4) if n_ink else None,
                "points_inside": n_all, "points_outside_displayed_page": oob}
    d2d = lambda x, y: (lambda q: (q.x, q.y))(pf.native_to_display(pf.NativePoint(x, y), native_extent=ne, rotation=rot))
    wrong_rot = lambda x, y: (lambda q: (q.x, q.y))(pf.native_to_display(pf.NativePoint(x, y), native_extent=ne, rotation=(rot + 180) % 360)) if rot else (ne.width - x, ne.height - y)
    rec["mapping"] = {"descriptor_native_to_display": evaluate(d2d), "wrong_identity": evaluate(lambda x, y: (x, y)),
                      "wrong_transpose": evaluate(lambda x, y: (y, x)), "wrong_opposite_rotation": evaluate(wrong_rot)}
    rec["_seconds"] = round(time.time() - t, 1); res["pages"].append(rec)
    m = rec["mapping"]
    print(n, "rot", rot, "ink pts", rec["grid_points_on_ink"], "| match_on_ink:", {k: v["match_on_ink"] for k, v in m.items()}, "| shapes ok:", rec["render_shapes_consistent_with_descriptor"], "|", rec["_seconds"], "s", flush=True)
    json.dump(res, open(out, "w"), indent=1, sort_keys=True, default=str)
print("DONE", flush=True)
