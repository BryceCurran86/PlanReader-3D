"""Q7 real-source descriptor + mapping check (scratch, read-only; uses the PR's pb_page_frame_shadow unchanged).
Per page: descriptor status/extent/rotation; whether real drawing vertices fall inside the declared NATIVE extent;
and whether native_to_display lands real stroke midpoints on rendered ink, against wrong-mapping negative controls.
No thresholds or rules are derived from the source: every number below is an observation."""
import hashlib, json, sys, time
repo, pdf, doc_id, pages, out, cls = sys.argv[1:7]
sys.path.insert(0, repo)
import fitz, numpy as np
import pb_page_frame_shadow as pf
data = open(pdf, "rb").read(); sha = hashlib.sha256(data).hexdigest()
doc = fitz.open(stream=data, filetype="pdf"); rev = pf.revision_id_for(doc_id, sha)
res = {"source_class": cls, "document_id": doc_id, "sha256": sha, "pages": []}
wanted = range(1, doc.page_count + 1) if pages == "all" else [int(x) for x in pages.split(",")]
MAXPTS = 400
def alt_maps(w, h, rot):  # (name, fn native(x,y)->display(x,y)); native extent w x h
    return {
        "descriptor_native_to_display": None,
        "wrong_identity": lambda x, y: (x, y),
        "wrong_transpose": lambda x, y: (y, x),
        "wrong_rot180": lambda x, y: (w - x, h - y),
    }
for n in wanted:
    t = time.time(); page = doc[n - 1]
    f = pf.describe_page_frame(page, document_id=doc_id, source_sha256=sha, revision=rev, page_no=n)
    rec = {"page_no": n, "status": f.status.value, "rotation": f.rotation, "rotate_entry": f.rotate_entry,
           "reason_codes": list(f.reason_codes), "note_codes": list(f.note_codes), "frame_id": f.frame_id}
    ne, de = f.native_extent, f.display_extent
    rec["native_wh"] = [ne.width, ne.height] if ne else None
    rec["display_wh"] = [de.width, de.height] if de else None
    if f.status.value == "raw" and ne is not None:
        # raw geometry
        segs, xs, ys = [], [], []
        for dr in page.get_drawings():
            for it in dr["items"]:
                if it[0] == "l":
                    p, q = it[1], it[2]; segs.append((p.x, p.y, q.x, q.y)); xs += [p.x, q.x]; ys += [p.y, q.y]
                elif it[0] == "re":
                    r = it[1]; xs += [r.x0, r.x1]; ys += [r.y0, r.y1]
        rec["n_line_segments"] = len(segs)
        if xs:
            tol = f.edge_quantisation_pt or 0.0
            rec["vertex_bbox_native"] = [round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2)]
            inside = lambda x, y: -tol <= x <= ne.width + tol and -tol <= y <= ne.height + tol
            out_native = sum(1 for x, y in zip(xs, ys) if not inside(x, y))
            rec["vertices_outside_native_extent"] = out_native
            rec["vertices_total"] = len(xs)
            if f.rotation in (90, 270):  # would be inside display extent only if coords were already rotated
                outside_display_only = sum(1 for x, y in zip(xs, ys) if not (0 <= x <= de.width and 0 <= y <= de.height))
                rec["vertices_outside_display_extent"] = outside_display_only
        long_segs = [s for s in segs if ((s[2]-s[0])**2 + (s[3]-s[1])**2) ** 0.5 > 100]
        rec["n_long_segments_gt100pt"] = len(long_segs)
        if long_segs:
            stride = max(1, len(long_segs) // MAXPTS)
            sample = long_segs[::stride][:MAXPTS]
            pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), colorspace=fitz.csGRAY, alpha=False)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
            rec["pixmap_wh"] = [pix.width, pix.height]
            def hit(dx, dy):
                ix, iy = int(round(dx)), int(round(dy))
                if not (1 <= ix < pix.width - 1 and 1 <= iy < pix.height - 1): return None
                return bool(img[iy-1:iy+2, ix-1:ix+2].min() < 200)
            maps = alt_maps(ne.width, ne.height, f.rotation)
            rm = page.rotation_matrix; stats = {}
            for name, fn in maps.items():
                hits = tot = oob = 0
                for x0, y0, x1, y1 in sample:
                    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
                    if fn is None:
                        dp = pf.native_to_display(pf.NativePoint(mx, my), native_extent=ne, rotation=f.rotation)
                        dx, dy = dp.x, dp.y
                    else:
                        dx, dy = fn(mx, my)
                    r = hit(dx, dy)
                    if r is None: oob += 1
                    else: tot += 1; hits += r
                stats[name] = {"ink_hits": hits, "inside_page": tot, "outside_page": oob,
                               "hit_rate": round(hits / tot, 4) if tot else None}
            # agreement of descriptor mapping with PyMuPDF's own rotation_matrix on the sampled points
            mx_err = 0.0
            for x0, y0, x1, y1 in sample:
                mx, my = (x0 + x1) / 2, (y0 + y1) / 2
                dp = pf.native_to_display(pf.NativePoint(mx, my), native_extent=ne, rotation=f.rotation)
                pm = fitz.Point(mx, my) * rm
                mx_err = max(mx_err, abs(dp.x - pm.x), abs(dp.y - pm.y))
            rec["max_abs_diff_vs_pymupdf_rotation_matrix_pt"] = mx_err
            # round trip
            rt = 0.0
            for x0, y0, x1, y1 in sample:
                mx, my = (x0 + x1) / 2, (y0 + y1) / 2
                dp = pf.native_to_display(pf.NativePoint(mx, my), native_extent=ne, rotation=f.rotation)
                bk = pf.display_to_native(dp, display_extent=de, rotation=f.rotation)
                rt = max(rt, abs(bk.x - mx), abs(bk.y - my))
            rec["max_round_trip_error_pt"] = rt
            rec["sampled_segments"] = len(sample)
            rec["ink_test"] = stats
    rec["_seconds"] = round(time.time() - t, 1)
    res["pages"].append(rec)
    it = rec.get("ink_test", {})
    print(n, rec["status"], "rot", rec["rotation"], "native", rec["native_wh"], "outside_native", rec.get("vertices_outside_native_extent"),
          "| ink:", {k: v["hit_rate"] for k, v in it.items()}, "| vs mupdf rm (pt):", rec.get("max_abs_diff_vs_pymupdf_rotation_matrix_pt"), "|", rec["_seconds"], "s", flush=True)
    json.dump(res, open(out, "w"), indent=1, sort_keys=True, default=str)
print("DONE", flush=True)
