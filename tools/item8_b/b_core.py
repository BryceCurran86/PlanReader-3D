"""Study B (owner-labelled framed windows): pure helpers. No PDF access, no network, no producer imports.

Pre-registration: docs/engineering/claude_item8_labelled_window_study_20261103.md (Part A). Everything here is a STUDY
instrument. It decides nothing, publishes nothing and is not an input to any producer. The relation definitions and the
decision rules are S3's (docs/engineering/claude_item8_s3_population_study_20261102.md, tools/item8_s3/s3_aggregate.py),
re-expressed as pure functions over per-structure rows so they can be tested on synthetic data."""
from __future__ import annotations

import json
from hashlib import sha256
from typing import Iterable, Mapping, Sequence

SCHEMA = "item8-b-labels-v1"
MIN_ITEMS = 20          # A4.1 (S3's bar: items are structures for R-A, face lines for R-B and R-C)
MIN_STRUCTURES = 5      # A4.1 (Study B addition: items must come from at least this many distinct labelled structures)
CLEAN = 0.90            # A4.2
SPREAD = 0.15           # A4.2
DECISIVE_RATIO = 10.0   # S3 A3 R-B

OUTCOME_PICKED = "picked"
OUTCOME_NO_OUTLINE_FITS = "no_outline_fits"
OUTCOME_NO_CONTAINING_STRUCTURE = "no_containing_structure"
OUTCOMES = (OUTCOME_PICKED, OUTCOME_NO_OUTLINE_FITS, OUTCOME_NO_CONTAINING_STRUCTURE)


def bbox_of_lines(lines: Iterable[Sequence[float]]) -> tuple[float, float, float, float] | None:
    """Axis-aligned extent of segments given as (x0, y0, x1, y1). Order- and splitting-invariant."""
    xs: list[float] = []
    ys: list[float] = []
    for line in lines:
        xs.extend((float(line[0]), float(line[2])))
        ys.extend((float(line[1]), float(line[3])))
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def structures_digest(structures: Iterable[Mapping[str, object]]) -> str:
    """Order-free fingerprint of a structure enumeration (ids only; no geometry)."""
    ids = sorted(str(item["id"]) for item in structures)
    return sha256("\n".join(ids).encode("ascii")).hexdigest()


def containing_structures(structures: Iterable[Mapping[str, object]], x: float, y: float) -> list[str]:
    """EVERY structure whose extent contains the point, in id order. Never picks one: no nearest, first or smallest."""
    found = []
    for item in structures:
        x0, y0, x1, y1 = item["bbox"]  # type: ignore[misc]
        if x0 <= x <= x1 and y0 <= y <= y1:
            found.append(str(item["id"]))
    return sorted(found)


def validate_labels(labels: Mapping[str, object], known_ids: Iterable[str], structures_sha256: str) -> list[str]:
    """Return a list of problems (empty means usable). Never repairs or drops anything."""
    problems: list[str] = []
    if labels.get("schema") != SCHEMA:
        problems.append("schema_mismatch")
    if labels.get("structures_sha256") != structures_sha256:
        problems.append("structures_enumeration_changed")
    known = set(known_ids)
    marks = labels.get("marks")
    if not isinstance(marks, list):
        return problems + ["marks_missing"]
    for index, mark in enumerate(marks):
        outcome = mark.get("outcome") if isinstance(mark, dict) else None
        picked = mark.get("picked") if isinstance(mark, dict) else None
        if outcome not in OUTCOMES:
            problems.append("mark_%d_unknown_outcome" % index)
        elif outcome == OUTCOME_PICKED:
            if picked not in known:
                problems.append("mark_%d_picked_id_not_in_enumeration" % index)
        elif picked is not None:
            problems.append("mark_%d_unpicked_outcome_carries_an_id" % index)
    return problems


def label_counts(labels: Mapping[str, object]) -> dict:
    """A5 counts. A structure picked twice is counted once in `picked_unique` and once in `picked_duplicates`."""
    marks = list(labels.get("marks", []))  # type: ignore[arg-type]
    picked = [m["picked"] for m in marks if m.get("outcome") == OUTCOME_PICKED]
    unique = sorted(set(picked))
    return dict(
        marks=len(marks),
        picked_marks=len(picked),
        picked_unique=len(unique),
        picked_duplicates=len(picked) - len(unique),
        no_outline_fits=sum(1 for m in marks if m.get("outcome") == OUTCOME_NO_OUTLINE_FITS),
        no_containing_structure=sum(1 for m in marks if m.get("outcome") == OUTCOME_NO_CONTAINING_STRUCTURE),
        more_than_one_containing=sum(1 for m in marks if int(m.get("containing_count", 0)) > 1),
    )


def picked_ids(labels: Mapping[str, object]) -> tuple[str, ...]:
    """Unique picked structure ids in id order (so the result does not depend on the order the owner clicked)."""
    return tuple(sorted({m["picked"] for m in labels.get("marks", []) if m.get("outcome") == OUTCOME_PICKED}))  # type: ignore[union-attr]


def summarise_rows(rows: Sequence[Mapping[str, object]]) -> dict:
    """S3's R-A, R-B and R-C counts over per-structure rows (the S3 census row schema). Rows with an `anomaly` key are skipped
    and counted."""
    anomalies = sum(1 for r in rows if "anomaly" in r)
    good = [r for r in rows if "anomaly" not in r]
    a_items = [r for r in good if r["interior"] and all(i["available"] for i in r["interior"])]
    r_a_true = sum(1 for r in a_items if all(i["order"] in ("before_all", "after_all") for i in r["interior"]))
    b_lines = [f for r in good if r["interior"] for f in r["face_ink"]
               if f["available"] and f["d_I"] is not None and f["d_M"] is not None]
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
    c_lines = [f for r in good for f in r["face_ink"] if f["available"]]
    c_same = sum(1 for f in c_lines if f["same_style"])
    b_structures = sum(1 for r in good if r["interior"] and any(
        f["available"] and f["d_I"] is not None and f["d_M"] is not None for f in r["face_ink"]))
    c_structures = sum(1 for r in good if any(f["available"] for f in r["face_ink"]))
    return dict(structures=len(good), anomalies=anomalies, with_interior=len(a_items), r_a_true=r_a_true,
                b_items=len(b_lines), b_structures=b_structures, b_decisive=decisive, b_nearer_interior=nearer_i,
                b_nearer_wall=nearer_w, b_tie=tie, c_items=len(c_lines), c_structures=c_structures, c_same=c_same)


def relation_tuples(stats: Mapping[str, Mapping[str, int]]) -> dict:
    """Per relation, per document: (items, share of the dominant value, dominant value, contributing structures). Mirrors S3's
    `judge` inputs plus the distinct-structure count."""
    ra, rb, rc = {}, {}, {}
    for doc, s in stats.items():
        ra[doc] = (s["with_interior"], (s["r_a_true"] / s["with_interior"]) if s["with_interior"] else 0.0, "outside",
                   s["with_interior"])
        rb[doc] = (s["b_items"], (s["b_decisive"] / s["b_items"]) if s["b_items"] else 0.0,
                   "nearer_interior" if s["b_nearer_interior"] >= s["b_nearer_wall"] else "nearer_wall", s["b_structures"])
        rc[doc] = (s["c_items"], (max(s["c_same"], s["c_items"] - s["c_same"]) / s["c_items"]) if s["c_items"] else 0.0,
                   "same_style" if s["c_same"] * 2 >= s["c_items"] else "other_style", s["c_structures"])
    return {"R-A": ra, "R-B": rb, "R-C": rc}


def judge(per_doc: Mapping[str, tuple[int, float, str, int]]) -> dict:
    """A4.1 and A4.2. Returns a verdict dictionary; the verdict string is one of INCONCLUSIVE, CLEAN_SEPARATOR, NOT_CLEAN."""
    qualifying = {d: v for d, v in per_doc.items() if v[0] >= MIN_ITEMS and v[3] >= MIN_STRUCTURES}
    out = dict(qualifying=sorted(qualifying))
    if len(qualifying) < 2:
        out["verdict"] = "INCONCLUSIVE"
        return out
    values = list(qualifying.values())
    clean = all(v[1] >= CLEAN for v in values)
    same_direction = len({v[2] for v in values}) == 1
    fractions = [v[1] for v in values]
    close = (max(fractions) - min(fractions)) <= SPREAD
    out.update(at_least_90_everywhere=clean, same_direction=same_direction, within_15_points=close,
               verdict="CLEAN_SEPARATOR" if (clean and same_direction and close) else "NOT_CLEAN")
    return out


def decide(stats: Mapping[str, Mapping[str, int]]) -> dict:
    return {name: judge(per_doc) for name, per_doc in relation_tuples(stats).items()}


def build_viewer_html(*, title: str, image_data_url: str, image_size: tuple[int, int], structures_px: Sequence[Mapping[str, object]],
                      document: str, page: int, structures_sha256: str, render_sha256: str) -> str:
    """Self-contained local viewer. No external resource, no network call, no cookie: the page, the structure extents and the
    marks live in this one file and in the owner's browser. The owner downloads the label file from the page."""
    payload = dict(document=document, page=page, structures_sha256=structures_sha256, render_sha256=render_sha256,
                   width=image_size[0], height=image_size[1],
                   structures=[dict(id=s["id"], bbox=list(s["bbox"])) for s in structures_px])
    html = _VIEWER_TEMPLATE
    html = html.replace("__TITLE__", _escape(title))
    html = html.replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":")).replace("</", "<\\/"))
    html = html.replace("__IMAGE__", image_data_url)
    return html


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_VIEWER_TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#f5f5f2;--fg:#1c1c1a;--panel:#ffffff;--line:#c9c9c2;--accent:#1f5fbf}
@media (prefers-color-scheme: dark){:root{--bg:#1b1b19;--fg:#ececE6;--panel:#262624;--line:#454540;--accent:#6aa3ff}}
html,body{margin:0;height:100%;background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif}
#app{display:flex;height:100%}
#stage{flex:1;position:relative;overflow:hidden;cursor:crosshair}
canvas{position:absolute;left:0;top:0}
#side{width:340px;max-width:42vw;padding:12px 14px;background:var(--panel);border-left:1px solid var(--line);overflow:auto}
h1{font-size:15px;margin:0 0 6px}
button{font:inherit;padding:6px 10px;margin:3px 4px 3px 0;border:1px solid var(--line);background:var(--bg);color:var(--fg);border-radius:6px;cursor:pointer}
button.primary{background:var(--accent);color:#fff;border-color:var(--accent)}
.sw{display:inline-block;width:12px;height:12px;margin-right:6px;vertical-align:-1px;border:1px solid #0006}
.muted{opacity:.75}
@media (max-width:700px){#app{flex-direction:column}#side{width:auto;max-width:none;border-left:0;border-top:1px solid var(--line);max-height:46vh}}
</style></head><body>
<div id="app"><div id="stage"><canvas id="cv"></canvas></div>
<div id="side">
<h1>Framed windows: mark each one</h1>
<p class="muted">Click a window. Every outline that contains the click is drawn and listed; pick the one that is that window's frame, or say none fits. Windows only (not doors). Drag to pan, wheel to zoom. Nothing leaves this browser tab until you download the file.</p>
<div id="count"></div>
<div id="current"></div>
<div id="actions">
<button id="undo">Undo last mark</button>
<button id="dl" class="primary">Download labels file</button>
</div>
<p class="muted" id="status"></p>
</div></div>
<script>
"use strict";
const P = __PAYLOAD__;
const COLORS = ["#d7191c","#2b83ba","#1a9641","#b2182b","#7b3294","#e08214","#01665e","#8c510a"];
const img = new Image();
const cv = document.getElementById("cv"), ctx = cv.getContext("2d");
const stage = document.getElementById("stage");
let scale = 1, ox = 0, oy = 0, marks = [], pending = null, drag = null;
const KEY = "item8b:" + P.render_sha256;
try { const s = localStorage.getItem(KEY); if (s) marks = JSON.parse(s).marks || []; } catch (e) {}
function save() { try { localStorage.setItem(KEY, JSON.stringify({marks: marks})); } catch (e) {} }
let fitted = false;
function fit() {
  cv.width = stage.clientWidth; cv.height = stage.clientHeight;
  if (!fitted && cv.width > 0 && cv.height > 0 && img.complete) { scale = Math.min(cv.width / P.width, cv.height / P.height); fitted = true; }
  draw();
}
function draw() {
  ctx.clearRect(0, 0, cv.width, cv.height);
  ctx.save(); ctx.translate(ox, oy); ctx.scale(scale, scale);
  ctx.drawImage(img, 0, 0);
  const lw = 2 / scale;
  marks.forEach(function (m, i) {
    ctx.strokeStyle = "#0b8f2b"; ctx.lineWidth = lw; ctx.beginPath(); ctx.arc(m.cx, m.cy, 14 / scale, 0, 6.2832); ctx.stroke();
    ctx.fillStyle = "#0b8f2b"; ctx.font = (14 / scale) + "px sans-serif"; ctx.fillText(String(i + 1), m.cx + 16 / scale, m.cy - 16 / scale);
  });
  if (pending) {
    ctx.strokeStyle = "#ff00ff"; ctx.lineWidth = lw; ctx.beginPath(); ctx.arc(pending.cx, pending.cy, 14 / scale, 0, 6.2832); ctx.stroke();
    pending.ids.forEach(function (id, k) {
      const s = P.structures.find(function (t) { return t.id === id; });
      ctx.strokeStyle = COLORS[k % COLORS.length]; ctx.lineWidth = (pending.hot === k ? 6 : 2.5) / scale;
      ctx.strokeRect(s.bbox[0], s.bbox[1], s.bbox[2] - s.bbox[0], s.bbox[3] - s.bbox[1]);
      ctx.fillStyle = COLORS[k % COLORS.length]; ctx.font = "bold " + (16 / scale) + "px sans-serif";
      ctx.fillText(String(k + 1), s.bbox[0], s.bbox[1] - 3 / scale);
    });
  }
  ctx.restore();
}
function ui() {
  const done = marks.length;
  document.getElementById("count").textContent = done + " mark" + (done === 1 ? "" : "s") + " recorded";
  const el = document.getElementById("current"); el.innerHTML = "";
  if (!pending) return;
  const h = document.createElement("div");
  h.textContent = pending.ids.length ? pending.ids.length + " outline(s) contain this click:" : "No outline contains this click.";
  el.appendChild(h);
  pending.ids.forEach(function (id, k) {
    const b = document.createElement("button");
    b.innerHTML = '<span class="sw" style="background:' + COLORS[k % COLORS.length] + '"></span>Outline ' + (k + 1) + " is the window frame";
    b.onclick = function () { record("picked", id); };
    b.onmouseenter = function () { pending.hot = k; draw(); };
    b.onmouseleave = function () { pending.hot = null; draw(); };
    el.appendChild(b); el.appendChild(document.createElement("br"));
  });
  const none = document.createElement("button");
  none.textContent = pending.ids.length ? "None of these fits" : "Record: no outline here";
  none.onclick = function () { record(pending.ids.length ? "no_outline_fits" : "no_containing_structure", null); };
  el.appendChild(none);
  const cancel = document.createElement("button");
  cancel.textContent = "Cancel (mis-click)"; cancel.onclick = function () { pending = null; ui(); draw(); };
  el.appendChild(cancel);
}
function record(outcome, id) {
  marks.push({outcome: outcome, picked: id, containing_count: pending.ids.length, cx: pending.cx, cy: pending.cy});
  pending = null; save(); ui(); draw();
}
function pt(e) { const r = cv.getBoundingClientRect(); return [(e.clientX - r.left - ox) / scale, (e.clientY - r.top - oy) / scale]; }
cv.addEventListener("mousedown", function (e) { drag = {x: e.clientX, y: e.clientY, ox: ox, oy: oy, moved: false}; });
window.addEventListener("mousemove", function (e) {
  if (!drag) return;
  const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
  if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true;
  if (drag.moved) { ox = drag.ox + dx; oy = drag.oy + dy; draw(); }
});
window.addEventListener("mouseup", function (e) {
  if (!drag) return;
  const was = drag; drag = null;
  if (was.moved) return;
  const p = pt(e);
  const ids = P.structures.filter(function (s) { return s.bbox[0] <= p[0] && p[0] <= s.bbox[2] && s.bbox[1] <= p[1] && p[1] <= s.bbox[3]; })
    .map(function (s) { return s.id; }).sort();
  pending = {cx: p[0], cy: p[1], ids: ids}; ui(); draw();
});
cv.addEventListener("wheel", function (e) {
  e.preventDefault();
  const r = cv.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
  const k = Math.exp(-e.deltaY * 0.0015), ns = Math.max(0.02, Math.min(40, scale * k));
  ox = mx - (mx - ox) * (ns / scale); oy = my - (my - oy) * (ns / scale); scale = ns; draw();
}, {passive: false});
document.getElementById("undo").onclick = function () { marks.pop(); pending = null; save(); ui(); draw(); };
document.getElementById("dl").onclick = function () {
  const out = {schema: "item8-b-labels-v1", document: P.document, page: P.page, structures_sha256: P.structures_sha256,
               render_sha256: P.render_sha256,
               marks: marks.map(function (m) { return {outcome: m.outcome, picked: m.picked, containing_count: m.containing_count}; })};
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 1)], {type: "application/json"}));
  a.download = "item8b_labels_" + P.document + "_p" + P.page + ".json"; document.body.appendChild(a); a.click(); a.remove();
  document.getElementById("status").textContent = "Downloaded " + marks.length + " marks.";
};
window.addEventListener("resize", fit);
img.onload = function () { fit(); ui(); };
img.src = "__IMAGE__";
</script></body></html>
"""
