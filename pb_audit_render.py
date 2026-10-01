"""Clean / audit 3D render of ONE production model (shadow, read-only).

Consumes ``CanonicalLevel`` objects (the production canonical schema) plus a
``CoverageRecordProvider`` and produces a scene that a lean Three.js template
draws in two modes from identical cameras:

* ``clean``  - neutral materials, no coverage claims;
* ``audit``  - materials chosen by coverage state (ACCOUNTED neutral, PARTIAL
  amber, UNACCOUNTED bright red, ABSTAINED grey ghost) plus callouts that carry
  the object id, reason code and source page.

Authority rules kept here:

* Nothing is dropped silently. Every canonical object either has geometry in the
  scene or is listed in ``scene["not_drawn"]`` with a reason and an audit state.
* Geometry has a ``basis``: ``canonical`` (metre coordinates on the canonical
  object), ``display_only`` (caller-supplied projection, e.g. PDF points at a
  non-firm nominal scale - never authority) or ``none``.
* When a canonical height / elevation is unresolved the renderer uses
  ``DISPLAY_ONLY_UNRESOLVED_HEIGHT_M`` purely so the footprint is visible; the
  object carries ``height_basis="display_only_unresolved"`` and an
  ``unresolved_attributes`` entry, so it can never be ACCOUNTED.
* This module never mutates its inputs and never touches ``takeoff_eligible`` or
  ``deduction_authority``.
"""
from __future__ import annotations

import base64
import json
import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from pb_audit_coverage_record import (
    AuditObjectRecord,
    CoverageRecordProvider,
    CoverageState,
    REASON_NOT_DRAWABLE,
    summarise_records,
)
from pb_canonical_building import CanonicalLevel, ReviewState

DISPLAY_ONLY_UNRESOLVED_HEIGHT_M = 1.2
DISPLAY_ONLY_UNRESOLVED_THICKNESS_M = 0.1

CAMERA_PRESETS = ("front_left", "rear_right", "top_iso")

_REFUSING_TOPOLOGY_STATUSES = frozenset({"ABSTAINED", "CONFLICT"})

_CALLOUT_LABELS = {
    ("WALL", CoverageState.UNACCOUNTED): "UNACCOUNTED WALL",
    ("WALL", CoverageState.PARTIAL): "PARTIAL WALL COVERAGE",
    ("OPENING", CoverageState.UNACCOUNTED): "UNACCOUNTED OPENING",
    ("OPENING", CoverageState.PARTIAL): "OPENING NOT FULLY RESOLVED",
    ("SPACE", CoverageState.UNACCOUNTED): "ROOM AREA NOT RECONCILED",
    ("SPACE", CoverageState.PARTIAL): "ROOM AREA NOT RECONCILED",
    ("FLOOR", CoverageState.UNACCOUNTED): "ROOM AREA NOT RECONCILED",
    ("ROOF", CoverageState.UNACCOUNTED): "ROOF PLANE NOT LINKED",
    ("ROOF", CoverageState.PARTIAL): "ROOF PLANE NOT LINKED",
    ("COLUMN", CoverageState.UNACCOUNTED): "POST/PIER NOT COUNTED",
    ("COLUMN", CoverageState.PARTIAL): "POST/PIER NOT COUNTED",
}


def callout_label(object_type: str, state: CoverageState) -> Optional[str]:
    """Human callout for a non-accounted object; None for ACCOUNTED."""
    if state is CoverageState.ACCOUNTED:
        return None
    if state is CoverageState.ABSTAINED:
        return "AUTHORITY ABSTAINED"
    base = "OPENING" if object_type in ("DOOR", "WINDOW", "OPENING") else object_type
    return _CALLOUT_LABELS.get((base, state), f"{state.value} {object_type}")


# ---------------------------------------------------------------- geometry ---

def _finite(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _pt(p: Any) -> Optional[Tuple[float, float]]:
    x, y = getattr(p, "x", None), getattr(p, "y", None)
    return (float(x), float(y)) if _finite(x) and _finite(y) else None


def _review(value: Any) -> str:
    return value.value if isinstance(value, ReviewState) else str(value or "REVIEW_REQUIRED")


def _prov(element: Any) -> Dict[str, Any]:
    prov = getattr(element, "provenance", None)
    return prov.to_dict() if prov is not None else {}


def _geometry(kind: str, pts: Sequence[Sequence[float]], basis: str) -> Dict[str, Any]:
    return {"kind": kind, "pts": [[float(x), float(y)] for x, y in pts], "basis": basis}


def _resolve_segment(
    element: Any, display: Mapping[str, Mapping[str, Any]]
) -> Optional[Dict[str, Any]]:
    a, b = _pt(element.start_point), _pt(element.end_point)
    if a and b and math.dist(a, b) > 1e-6:
        return _geometry("segment", [a, b], "canonical")
    disp = display.get(element.id)
    if disp and len(disp.get("pts") or ()) >= 2:
        return _geometry("segment", [disp["pts"][0], disp["pts"][-1]], str(disp.get("basis") or "display_only"))
    return None


def _resolve_polygon(
    element: Any, points: Iterable[Any], display: Mapping[str, Mapping[str, Any]]
) -> Optional[Dict[str, Any]]:
    pts = [_pt(p) for p in points]
    if len(pts) >= 3 and all(pts):
        return _geometry("polygon", pts, "canonical")  # type: ignore[arg-type]
    disp = display.get(element.id)
    if disp and len(disp.get("pts") or ()) >= 3:
        return _geometry("polygon", disp["pts"], str(disp.get("basis") or "display_only"))
    return None


def _base(element: Any, obj_type: str, level: CanonicalLevel) -> Dict[str, Any]:
    prov = _prov(element)
    return {
        "id": element.id,
        "type": obj_type,
        "name": getattr(element, "name", None),
        "level_id": level.id,
        "review_state": _review(element.review_state),
        "provenance": prov,
        "source_pages": [],
        "geometry": None,
        "height_m": None,
        "height_basis": "none",
        "unresolved_attributes": [],
        "refusal_reason": None,
    }


def _topology_refusal(element: Any) -> Optional[str]:
    status = str((getattr(element, "metadata", None) or {}).get("topology_status") or "")
    return f"topology_status:{status}" if status in _REFUSING_TOPOLOGY_STATUSES else None


def collect_scene_objects(
    levels: Sequence[CanonicalLevel],
    display_geometry: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Flatten canonical levels into scene objects. Pure; inputs are not mutated."""
    display = display_geometry or {}
    out: List[Dict[str, Any]] = []

    for lvl in levels:
        elev_ok = _finite(lvl.elevation_m)
        level_unresolved = [] if elev_ok else ["level_elevation"]
        z0 = float(lvl.elevation_m) if elev_ok else 0.0

        def finish(obj: Dict[str, Any], geom: Optional[Dict[str, Any]], *, height: Any = None,
                   thickness: Any = None) -> None:
            obj["geometry"] = geom
            obj["z0_m"] = z0
            obj["unresolved_attributes"] = list(obj["unresolved_attributes"]) + level_unresolved
            if geom is not None and geom["basis"] != "canonical":
                obj["unresolved_attributes"].append("geometry_" + geom["basis"])
            if _finite(height) and float(height) > 0:
                obj["height_m"], obj["height_basis"] = float(height), "canonical"
            else:
                obj["height_m"] = DISPLAY_ONLY_UNRESOLVED_HEIGHT_M
                obj["height_basis"] = "display_only_unresolved"
                obj["unresolved_attributes"].append("height")
            if thickness is not None:
                if _finite(thickness) and float(thickness) > 0:
                    obj["thickness_m"] = float(thickness)
                else:
                    obj["thickness_m"] = DISPLAY_ONLY_UNRESOLVED_THICKNESS_M
                    obj["unresolved_attributes"].append("thickness")
            obj["unresolved_attributes"] = sorted(set(obj["unresolved_attributes"]))
            out.append(obj)

        for w in lvl.walls:
            obj = _base(w, "WALL", lvl)
            obj["is_external"] = bool(w.is_external)
            obj["interior_exterior"] = (w.metadata or {}).get("interior_exterior_topology_status")
            obj["refusal_reason"] = _topology_refusal(w)
            geom = _resolve_segment(w, display)
            finish(obj, geom, height=w.height_m, thickness=w.thickness_m)
            for op in w.openings:
                declared = str(op.opening_type or "").upper()
                otype = declared if declared in ("DOOR", "WINDOW") else str(getattr(op.object_type, "value", op.object_type))
                oobj = _base(op, otype, lvl)
                oobj["wall_id"] = w.id
                oobj["physical_state"] = (op.metadata or {}).get("physical_state")
                oobj["opening_type"] = op.opening_type
                wall_geom = obj["geometry"]
                ogeom = None
                if (
                    wall_geom is not None
                    and _finite(op.offset_along_wall_m)
                    and _finite(op.width_m)
                    and float(op.width_m) > 0
                ):
                    (ax, ay), (bx, by) = wall_geom["pts"]
                    length = math.hypot(bx - ax, by - ay)
                    if length > 1e-9 and wall_geom["basis"] == "canonical":
                        ux, uy = (bx - ax) / length, (by - ay) / length
                        s0, s1 = float(op.offset_along_wall_m), float(op.offset_along_wall_m) + float(op.width_m)
                        ogeom = _geometry(
                            "segment", [(ax + ux * s0, ay + uy * s0), (ax + ux * s1, ay + uy * s1)], "canonical"
                        )
                oobj["sill_m"] = float(op.sill_height_m) if _finite(op.sill_height_m) else 0.0
                if not _finite(op.sill_height_m):
                    oobj["unresolved_attributes"].append("sill_height")
                finish(oobj, ogeom, height=op.height_m, thickness=(w.thickness_m if _finite(w.thickness_m) else None))
                if ogeom is None and "opening_placement" not in oobj["unresolved_attributes"]:
                    oobj["unresolved_attributes"] = sorted(set(oobj["unresolved_attributes"]) | {"opening_placement"})

        for sp in lvl.spaces:
            obj = _base(sp, "SPACE", lvl)
            obj["refusal_reason"] = _topology_refusal(sp)
            geom = _resolve_polygon(sp, sp.boundary_polygon, display)
            obj["height_m"] = None
            finish(obj, geom)
            obj["height_m"], obj["height_basis"] = 0.0, "flat_zone"
            obj["unresolved_attributes"] = sorted(set(obj["unresolved_attributes"]) - {"height"})
            if sp.name and sp.name != "Unnamed Element":
                obj["label"] = sp.name

        for group, typ in ((lvl.floors, "FLOOR"), (lvl.ceilings, "CEILING"), (lvl.roofs, "ROOF"),
                           (lvl.soffits, "SOFFIT"), (lvl.balconies, "BALCONY")):
            for item in group:
                obj = _base(item, typ, lvl)
                geom = _resolve_polygon(item, item.polygon, display)
                finish(obj, geom)
                obj["height_m"], obj["height_basis"] = 0.0, "flat_zone"
                obj["unresolved_attributes"] = sorted(set(obj["unresolved_attributes"]) - {"height"})

        for group, typ in ((lvl.parapets, "PARAPET"), (lvl.balustrades, "BALUSTRADE"), (lvl.screens, "SCREEN")):
            for item in group:
                obj = _base(item, typ, lvl)
                finish(obj, _resolve_segment(item, display), height=item.height_m,
                       thickness=getattr(item, "thickness_m", None) or DISPLAY_ONLY_UNRESOLVED_THICKNESS_M)

        for col in lvl.columns:
            obj = _base(col, "COLUMN", lvl)
            c = _pt(col.center) if col.center is not None else None
            geom = _geometry("point", [c], "canonical") if c else None
            if geom is None and display.get(col.id) and display[col.id].get("pts"):
                geom = _geometry("point", [display[col.id]["pts"][0]], str(display[col.id].get("basis") or "display_only"))
            obj["width_m"] = float(col.width_m) if _finite(col.width_m) and col.width_m > 0 else 0.2
            obj["depth_m"] = float(col.depth_m) if _finite(col.depth_m) and col.depth_m > 0 else obj["width_m"]
            finish(obj, geom, height=col.height_m)
    return out


# ------------------------------------------------------------------- scene ---

def _bounds(objects: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, float]]:
    xs: List[float] = []
    ys: List[float] = []
    zmax = 0.0
    for o in objects:
        g = o.get("geometry")
        if not g:
            continue
        for x, y in g["pts"]:
            xs.append(x)
            ys.append(y)
        zmax = max(zmax, float(o.get("z0_m") or 0.0) + float(o.get("height_m") or 0.0))
    if not xs:
        return None
    return {"min_x": min(xs), "max_x": max(xs), "min_y": min(ys), "max_y": max(ys), "max_z": zmax}


def camera_for(bounds: Optional[Mapping[str, float]], preset: str) -> Dict[str, Any]:
    """Deterministic camera from scene bounds. Model (x, y, z-up) -> three (x, z, -y).

    front = -Y side of the plan coordinates, left = -X side.
    """
    if preset not in CAMERA_PRESETS:
        raise ValueError(f"unknown camera preset {preset!r}")
    if not bounds:
        return {"preset": preset, "position": [10, 10, 10], "target": [0, 0, 0], "fov": 40}
    cx = (bounds["min_x"] + bounds["max_x"]) / 2
    cy = (bounds["min_y"] + bounds["max_y"]) / 2
    cz = bounds["max_z"] / 2
    radius = max(bounds["max_x"] - bounds["min_x"], bounds["max_y"] - bounds["min_y"], bounds["max_z"], 1.0)
    d = radius * 1.35
    if preset == "front_left":
        pos = (cx - d * 0.7, cy - d * 0.8, cz + d * 0.55)
    elif preset == "rear_right":
        pos = (cx + d * 0.7, cy + d * 0.8, cz + d * 0.55)
    else:
        pos = (cx + d * 0.15, cy - d * 0.25, cz + d * 1.5)
    # model -> three
    return {
        "preset": preset,
        "position": [pos[0], pos[2], -pos[1]],
        "target": [cx, cz, -cy],
        "fov": 40,
    }


def build_audit_scene(
    levels: Sequence[CanonicalLevel],
    provider: CoverageRecordProvider,
    display_geometry: Optional[Mapping[str, Mapping[str, Any]]] = None,
    *,
    title: str = "PlanReader 3D audit",
) -> Dict[str, Any]:
    objects = collect_scene_objects(levels, display_geometry)
    records: List[AuditObjectRecord] = []
    drawn: List[Dict[str, Any]] = []
    not_drawn: List[Dict[str, Any]] = []
    for obj in objects:
        rec = provider.record_for(obj)
        if obj["geometry"] is None:
            # cannot be placed without inventing geometry: never ACCOUNTED
            if rec.coverage_state is CoverageState.ACCOUNTED:
                rec = AuditObjectRecord(**{**rec.__dict__, "coverage_state": CoverageState.PARTIAL,
                                           "reason_code": REASON_NOT_DRAWABLE})
            entry = dict(obj, audit=rec.to_dict(),
                         not_drawn_reason=rec.reason_code if rec.coverage_state is CoverageState.ABSTAINED else "no_geometry")
            not_drawn.append(entry)
        else:
            drawn.append(dict(obj, audit=rec.to_dict()))
        records.append(rec)
    for entry in drawn + not_drawn:
        label = callout_label(entry["type"], CoverageState(entry["audit"]["coverage_state"]))
        entry["audit"]["callout"] = label
    coverage_bases = sorted({rec.coverage_basis for rec in records if rec.coverage_basis})
    family_states = sorted(
        {rec.expected_family_completeness for rec in records if rec.expected_family_completeness}
    )
    return {
        "title": title,
        "objects": drawn,
        "not_drawn": not_drawn,
        "summary": summarise_records(records),
        "bounds": _bounds(drawn),
        "display_only_height_m": DISPLAY_ONLY_UNRESOLVED_HEIGHT_M,
        "coverage_semantics": {
            "coverage_basis": coverage_bases[0] if len(coverage_bases) == 1 else None,
            "expected_family_completeness": family_states[0] if len(family_states) == 1 else None,
        },
    }


# -------------------------------------------------------------------- html ---

_TEMPLATE = r"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
html,body{margin:0;height:100%;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}
#c{width:100%;height:100%;display:block}
#hud{position:absolute;left:12px;top:10px;font-size:13px;background:#0f172acc;padding:8px 10px;border-radius:6px;max-width:420px}
#hud b{font-size:15px}
.sw{display:inline-block;width:11px;height:11px;margin-right:6px;border-radius:2px;vertical-align:-1px}
#nd{position:absolute;right:12px;top:10px;font-size:11px;background:#0f172acc;padding:8px 10px;border-radius:6px;max-width:330px;max-height:60%;overflow:auto}
</style></head><body><canvas id="c"></canvas><div id="hud"></div><div id="nd"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
const SCENE = JSON.parse(new TextDecoder().decode(Uint8Array.from(atob("__B64__"), c => c.charCodeAt(0))));
const MODE = "__MODE__";           // clean | audit
const CAMERA = __CAMERA__;
const MAXC = __MAXC__;
const COL = {ACCOUNTED:null, PARTIAL:0xf59e0b, UNACCOUNTED:0xff1a1a, ABSTAINED:0x9ca3af};
const NEUTRAL = {WALL:0xe2e8f0, DOOR:0xb45309, WINDOW:0x7dd3fc, OPENING:0x94a3b8, SPACE:0xcbd5e1, FLOOR:0xcbd5e1,
  CEILING:0xf1f5f9, ROOF:0x64748b, COLUMN:0xa8a29e, SOFFIT:0x94a3b8, BALCONY:0x94a3b8, PARAPET:0x94a3b8, BALUSTRADE:0x94a3b8, SCREEN:0x94a3b8};
function mat(o){
  const st = o.audit.coverage_state; let color = NEUTRAL[o.type] || 0xcbd5e1, op = 1, tr = false;
  const flat = (o.geometry.kind === 'polygon');
  if (flat || o.type === 'WINDOW'){ op = 0.7; tr = true; }
  if (MODE === 'audit' && st !== 'ACCOUNTED'){
    color = COL[st];
    if (st === 'ABSTAINED'){ op = 0.28; tr = true; }
    else if (flat){ op = 0.55; tr = true; }
    else { op = 1; tr = false; }
  }
  return new THREE.MeshStandardMaterial({color, opacity: op, transparent: tr, roughness: .6, depthWrite: !tr,
    side: flat ? THREE.DoubleSide : THREE.FrontSide});
}
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({canvas, antialias:true, preserveDrawingBuffer:true});
renderer.setPixelRatio(1);
const scene = new THREE.Scene(); scene.background = new THREE.Color(0x0f172a);
scene.add(new THREE.AmbientLight(0xffffff,.8));
const sun = new THREE.DirectionalLight(0xffffff,.7); sun.position.set(20,40,30); scene.add(sun);
const cam = new THREE.PerspectiveCamera(CAMERA.fov, 1, .1, 5000);
function sz(){ const w = innerWidth, h = innerHeight; renderer.setSize(w,h,false); cam.aspect = w/h; cam.updateProjectionMatrix(); }
addEventListener('resize', sz); sz();
cam.position.set(...CAMERA.position); cam.lookAt(new THREE.Vector3(...CAMERA.target));
const T = (x,y,z) => new THREE.Vector3(x, z, -y);
const byId = {}; SCENE.objects.forEach(o => byId[o.id] = o);
const callouts = [];
function segMesh(o, m){
  const [a,b] = o.geometry.pts; const len = Math.hypot(b[0]-a[0], b[1]-a[1]); if (len < 1e-6) return null;
  const th = o.thickness_m || 0.1, h = o.height_m || 1, z0 = (o.z0_m||0) + (o.sill_m||0);
  const g = new THREE.BoxGeometry(len, h, o.type==='WALL' ? th : th*1.15);
  const mesh = new THREE.Mesh(g, m);
  const c = T((a[0]+b[0])/2, (a[1]+b[1])/2, z0 + h/2); mesh.position.copy(c);
  mesh.rotation.y = Math.atan2(b[1]-a[1], b[0]-a[0]);
  return mesh;
}
function polyMesh(o, m){
  const s = new THREE.Shape(o.geometry.pts.map(p => new THREE.Vector2(p[0], p[1])));
  const g = new THREE.ShapeGeometry(s); g.rotateX(-Math.PI/2);
  const mesh = new THREE.Mesh(g, m);
  const lift = {SPACE:0.02, FLOOR:0.01, ROOF: (o.height_basis==='flat_zone'? 2.6 : 2.6), CEILING:2.5}[o.type];
  mesh.position.y = (o.z0_m||0) + (lift===undefined? 0.02 : lift);
  return mesh;
}
function ptMesh(o, m){
  const c = o.geometry.pts[0]; const g = new THREE.BoxGeometry(o.width_m||.2, o.height_m||1, o.depth_m||.2);
  const mesh = new THREE.Mesh(g, m); mesh.position.copy(T(c[0], c[1], (o.z0_m||0)+(o.height_m||1)/2)); return mesh;
}
function centroid(o){
  const p = o.geometry.pts; const n = p.length;
  return [p.reduce((s,q)=>s+q[0],0)/n, p.reduce((s,q)=>s+q[1],0)/n];
}
SCENE.objects.forEach(o => {
  const m = mat(o); let mesh = null;
  if (o.geometry.kind === 'segment') mesh = segMesh(o, m);
  else if (o.geometry.kind === 'polygon') mesh = polyMesh(o, m);
  else if (o.geometry.kind === 'point') mesh = ptMesh(o, m);
  if (mesh){ mesh.userData.id = o.id; scene.add(mesh);
    if (o.geometry.kind==='polygon' && MODE==='audit' && o.audit.coverage_state!=='ACCOUNTED'){
      const e = new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry), new THREE.LineBasicMaterial({color: COL[o.audit.coverage_state]}));
      e.position.copy(mesh.position); scene.add(e);} }
  if (MODE==='audit' && o.audit.callout) callouts.push(o);
});
function size(o){ const p=o.geometry.pts; if (o.geometry.kind==='segment') return Math.hypot(p[1][0]-p[0][0],p[1][1]-p[0][1]);
  if (o.geometry.kind==='point') return 0.1; let a=0; for (let i=0;i<p.length;i++){const q=p[(i+1)%p.length]; a+=p[i][0]*q[1]-q[0]*p[i][1];} return Math.abs(a)/2; }
function sprite(text, color){
  const cv = document.createElement('canvas'); const ctx = cv.getContext('2d'); ctx.font = 'bold 26px sans-serif';
  const lines = text.split('\n'); const w = Math.max(...lines.map(l => ctx.measureText(l).width)) + 20; cv.width = w; cv.height = 36*lines.length + 10;
  ctx.font = 'bold 26px sans-serif'; ctx.fillStyle = '#0f172aee'; ctx.fillRect(0,0,cv.width,cv.height);
  ctx.strokeStyle = color; ctx.lineWidth = 4; ctx.strokeRect(2,2,cv.width-4,cv.height-4); ctx.fillStyle = '#fff';
  lines.forEach((l,i)=>ctx.fillText(l, 10, 32+36*i));
  const s = new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(cv), depthTest:false, depthWrite:false}));
  s.renderOrder = 999;
  const k = 0.0075 * (SCENE.bounds ? Math.max(SCENE.bounds.max_x-SCENE.bounds.min_x, SCENE.bounds.max_y-SCENE.bounds.min_y, 8) : 10)/10*10;
  s.scale.set(cv.width*k/10, cv.height*k/10, 1); return s;
}
const perState = {}; const shown = [];
callouts.slice().sort((a,b)=> size(b)-size(a) || (a.id<b.id?-1:1)).forEach(o => {
  const st = o.audit.coverage_state; perState[st] = (perState[st]||0)+1; if (perState[st] > MAXC) return;
  const c = centroid(o); const top = (o.z0_m||0) + (o.height_m||1) + 0.5 + 0.9*((perState[st]-1)%3);
  const hex = '#'+(COL[st]).toString(16).padStart(6,'0');
  const page = (o.audit.source_pages||[]).length ? ' p'+o.audit.source_pages.join(',') : '';
  const sp = sprite(o.audit.callout + '\n' + o.id.slice(0,26) + ' · ' + (o.audit.reason_code||'') + page, hex);
  sp.position.copy(T(c[0], c[1], top)); scene.add(sp); shown.push(o.id);
});
const S = SCENE.summary; const rows = Object.keys(S).map(t => t.padEnd(8,' ') + ' ' + Object.entries(S[t]).map(([k,v])=>k.slice(0,3)+' '+v).join(' '));
const legend = MODE==='audit'
  ? ['ACCOUNTED','PARTIAL','UNACCOUNTED','ABSTAINED'].map(k=>'<span class="sw" style="background:'+(COL[k]?('#'+COL[k].toString(16).padStart(6,'0')):'#e2e8f0')+'"></span>'+k).join('<br>')
  : 'Neutral materials. No coverage claims.';
const CS = SCENE.coverage_semantics || {};
const semantics = (MODE==='audit' && CS.coverage_basis==='EXPLICIT_DEPENDENCIES_ONLY')
  ? '<div style="font-size:11px;opacity:.9">ACCOUNTED = explicit dependencies only · expected-family completeness: '+(CS.expected_family_completeness==='UNKNOWN'?'UNKNOWN':'not declared')+' · not complete trade/BOQ scope.</div>'
  : '';
document.getElementById('hud').innerHTML = '<b>'+(MODE==='audit'?'AUDIT':'CLEAN')+' 3D VIEW</b> · '+CAMERA.preset+'<br>'+legend+
  (MODE==='audit' ? '<pre style="margin:6px 0 0;font-size:11px">'+rows.join('\n')+'</pre>' : '')+semantics+
  '<div style="font-size:11px;opacity:.8">Unresolved heights drawn at '+SCENE.display_only_height_m+' m (display only). Callouts shown: '+shown.length+' of '+callouts.length+'.</div>';
const nd = SCENE.not_drawn;
document.getElementById('nd').innerHTML = (MODE==='audit' && nd.length)
  ? '<b>NOT DRAWABLE ('+nd.length+')</b><br>'+nd.slice(0,14).map(o=>o.audit.coverage_state+' '+o.type+' '+o.id.slice(0,22)+' · '+(o.not_drawn_reason||'')).join('<br>')+(nd.length>14?'<br>…':'')
  : '';
if (!nd.length || MODE!=='audit') document.getElementById('nd').style.display='none';
renderer.render(scene, cam); window.__READY = true;
</script></body></html>"""


def render_audit_html(
    scene: Mapping[str, Any],
    *,
    mode: str,
    camera_preset: str = "front_left",
    max_callouts_per_state: int = 4,
) -> str:
    """HTML for one mode + camera. Cameras depend only on the scene bounds, so the
    clean and audit renders of one scene are pixel-aligned."""
    if mode not in ("clean", "audit"):
        raise ValueError("mode must be 'clean' or 'audit'")
    camera = camera_for(scene.get("bounds"), camera_preset)
    payload = base64.b64encode(json.dumps(scene, sort_keys=True).encode("utf-8")).decode("ascii")
    title = str(scene.get("title") or "PlanReader 3D audit").replace("<", "&lt;")
    return (
        _TEMPLATE.replace("__TITLE__", title)
        .replace("__B64__", payload)
        .replace("__MODE__", mode)
        .replace("__CAMERA__", json.dumps(camera))
        .replace("__MAXC__", str(int(max_callouts_per_state)))
    )
