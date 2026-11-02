"""Study B step 1: build the local owner viewer for ONE page of ONE original. Read-only; the PDF is never copied.

usage: python tools/item8_b/b_enumerate.py <label> <pdf> <page_number> <out_dir>

Writes into <out_dir> (a `.gitignore` containing `*` is written there first, so nothing in it can be committed):
  <label>_p<page>_viewer.html      self-contained local viewer (page render + structure extents; no network, no external file)
  <label>_p<page>_structures.json  structure ids and extents, for the analysis step
Both files hold the owner's private drawing content. They stay on this machine: never commit, upload or attach them to a PR,
a workflow run or a hosted page. Pre-registration: docs/engineering/claude_item8_labelled_window_study_20261103.md."""
from __future__ import annotations

import base64
import json
import sys
import time
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import fitz  # noqa: E402

from tools.item8_b.b_core import build_viewer_html, structures_digest  # noqa: E402
from tools.item8_b.b_pipeline import enumerate_page  # noqa: E402

LONG_SIDE_PX = 6000


def build(label: str, pdf: Path, page_no: int, out_dir: Path) -> dict:
    t0 = time.time()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / ".gitignore").write_text("*\n", encoding="utf-8")
    page = enumerate_page(label, pdf, page_no)
    with fitz.open(pdf) as doc:
        pg = doc[page_no - 1]
        zoom = LONG_SIDE_PX / max(pg.rect.width, pg.rect.height)
        # Producer coordinates are the unrotated page space (probed on a rotated and an unrotated page); the render is of the
        # rotated page, so each extent is carried through the page's own rotation matrix and then the zoom.
        matrix = pg.rotation_matrix * fitz.Matrix(zoom, zoom)
        pix = pg.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        png = pix.tobytes("png")
        structures_px = []
        for cid, (x0, y0, x1, y1) in sorted(page.extents.items()):
            corners = [fitz.Point(x, y) * matrix for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
            structures_px.append(dict(id=cid, bbox=[min(p.x for p in corners), min(p.y for p in corners),
                                                    max(p.x for p in corners), max(p.y for p in corners)]))
    digest = structures_digest(structures_px)
    render_sha = sha256(png).hexdigest()
    html = build_viewer_html(title="Mark framed windows (%s p%d)" % (label, page_no),
                             image_data_url="data:image/png;base64," + base64.b64encode(png).decode("ascii"),
                             image_size=(pix.width, pix.height), structures_px=structures_px, document=label, page=page_no,
                             structures_sha256=digest, render_sha256=render_sha)
    stem = "%s_p%d" % (label, page_no)
    (out_dir / (stem + "_viewer.html")).write_text(html, encoding="utf-8")
    (out_dir / (stem + "_structures.json")).write_text(json.dumps(dict(
        document=label, page=page_no, pdf_sha256=page.pdf_sha256, structures_sha256=digest, render_sha256=render_sha,
        zoom=zoom, rotation=0, structures=structures_px)), encoding="utf-8")
    return dict(label=label, page=page_no, structures=len(structures_px), image=[pix.width, pix.height],
                html_bytes=len(html), seconds=round(time.time() - t0, 1))


if __name__ == "__main__":
    summary = build(sys.argv[1], Path(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4]))
    print(json.dumps(summary))
