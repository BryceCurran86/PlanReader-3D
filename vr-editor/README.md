# PlanReader 3D + VR evidence viewer (desktop / WebXR)

This is an **additive, read-only** React + Three.js viewer for the EXISTING
PlanReader model. It does not create a second wall detector, construction model,
correction ledger, approval path, or quantity engine.

## Run locally

```sh
cd vr-editor
npm install
npm run build
npm run dev
```

Open the URL printed by Vite and import an actual source-bound scene manifest
produced by `pb_vr_editor_scene_manifest.compile_editor_scene`. Imported
local files are **always displayed as untrusted/review**, even if they claim
`verified`. No file is transmitted to a server.

For a deployed workspace the browser requests
`GET /api/editor/workspaces/{workspace_id}/manifest` using same-origin
credentials. The server-side WSGI endpoint factory exists in the separate
stacked PR #4425, but **real production session/tenant callbacks have not been
connected**. Do not treat a URL query parameter as authorization.
Without an authenticated backend, use the local-file preview or click the
clearly marked **synthetic 3D / VR example** in the empty viewer.

The inspector can also request a **preview only** through
`POST /api/editor/workspaces/{workspace_id}/commands/preview` (separate
stacked PR #4427). It requires authenticated same-origin fetch and a verified
`<meta name="planreader-csrf-token" content="...">` inserted by the owning
server; the standalone Vite page has no such token. Missing auth/CSRF fails
closed. A preview NEVER persists geometry, approves corrections or publishes
commercial quantities.

## What the first functional slice does

- Desktop orbit, pan, zoom and ray selection of registered wall objects.
- Three.js zero-thickness wall-face panels ONLY where existing wall geometry,
  length and documented/approved height are supplied by the Python backend.
- Plan lines for walls with unverified height; **no default 2.7m extrusion**.
- WebXR browser button and headset controller ray selection (requires a
  supported headset, compatible browser, HTTPS/secure context).
- Inspector for object revision, optional canonical ID, source sheet/page,
  original geometry reference and linked quantity IDs.
- Review/unresolved highlighting, level filter, strict JSON validation and
  20,000-object upper bound.
- Source input and render meshes remain separate. No client-side geometry
  calculation gains commercial authority.

## Not implemented or not verified

- Server authentication/session, source/tenant binding or authenticated API.
- A production-wired editable command gateway, persisted draft or approval UI.
  The typed, source-checked **impact preview only** is implemented in a
  separate stacked backend PR and is disabled without an authenticated session.
- Wall thickness/solid generation, authenticated room/floor/ceiling meshes,
  opening volumes, materials/finishes and IFC.
- Teleport navigation, snap-turn, accessibility/headset acceptance,
  production hosting and stress testing.
- Browser/backend schema version migration, quantity recalculation and
  commercial approval integration.

Actual commercial edits must continue through
`pb_editable_3d_correction_model`, `pb_editable_3d_correction_persistence`,
`pb_editable_3d_quantity_recalculation`, and
`pb_editable_3d_commercial_sync` with authenticated, current source context.
A mesh selection is not permission to change a canonical wall or invoice.

## Release gates

This viewer must pass its own strict TypeScript build, Python 3.13 and 3.14
tests for the backend manifest, server-side source/security checks, and
headset/browser smoke tests before it is considered production-capable.

## Local finish-colour study (noncommercial)

Select an existing **wall face with documented height**, then choose one of four
illustrative colours in the object inspector. The same temporary tint appears
in the desktop renderer and headset view. Clearing the study, switching scenes
or reloading removes it. Unknown-height wall lines and non-wall objects cannot
be coloured as surfaces. The palette is not a materials/finish schedule and
has **no pricing, quantity, persistence, canonical approval or source authority**.
For a genuine finish-code quantity-impact proposal, use the existing separate
authenticated + CSRF-bound **Controlled Correction Preview**. That preview is
also non-persistent and is never automatically applied from a colour choice.

With a supported WebXR controller, **trigger** selects an existing source object and **grip/squeeze** cycles the temporary wall colour palette (last squeeze clears it). Non-wall items and source lines with unknown height cannot be given a visual wall face. VR squeeze never sends a server command.\n
## Multi-wall VR review workbench

The inspector now offers a **strictly local what-if draft** for walls already represented
by a source-bound wall face with an existing documented height. Ten workflow
capabilities are grouped in this review slice:

1. Scope-lock each local session to workspace, document, revision, SHA256, snapshot
   and model revision; switching source resets the local session.
2. Maintain independently selected colours on multiple existing wall faces.
3. Show an illustrative height as a translucent ghost of an existing wall mesh
   without changing any backend geometry, scale, source receipt or quantity.
4. Apply a colour in one bounded operation to up to 500 existing wall faces on
   an explicitly selected level (never silently across all levels).
5. Undo local visual studies with a bounded 30-step history.
6. Redo or clear local studies without affecting approved corrections.
7. Compare original and proposed visual heights and swatches by source object ID.
8. Export a deterministic, review-only, local JSON file.
9. Import only a strictly validated file matching the exact current source scope
   and every current object revision; malformed, stale or oversized payloads fail.
10. Use VR grip/squeeze for per-wall colour cycling and keyboard Ctrl/Cmd+Z
    (Shift+Ctrl/Cmd+Z for redo) away from text inputs.

An additional bridge prefills **SET_WALL_HEIGHT** in the existing authenticated
correction-preview form from a selected ghost proposal. This cannot automatically
submit or approve anything. The user must supply an evidence-based reason and
click Preview; CSRF, workspace access, canonical identity and source-witness
checks remain server-owned. Preview quantity impacts are not a monetary quote.
There is still no persistent VR correction/approval endpoint or live pricing.
The Python correction ledger remains the only source of commercial revisions.

To test locally, run `npm ci && npm test && npm run build` in `vr-editor`.
On headsets, source-trace, browser compatibility, controller grip mapping and
production tenant authentication still require hardware and real-original replay.

## Physically plausible lighting (visual realism)

The viewer offers three **illustrative** lighting presets: architectural daylight,
neutral studio and warm dusk. These use ACES filmic tone mapping, physically based
rough dielectric wall materials, sRGB output, hemisphere fill and directional
lighting with soft contact-shadow presentation. Neutral wall colours avoid
mistaking the old teal highlight for actual paint. Review-only walls remain warm
and translucent. The shadows are a rendering aid, not a construction witness.

Balanced rendering limits desktop pixel density to 1.5 and directional shadow
resolution to 1024; High mode uses at most 2 and 2048. Headset rendering respects
the XR compositor and limits extra desktop pixel density. The non-selectable
shadow-catching ground plane is purely a visual reference, **not a measured floor
or slab**. Unknown-height walls remain source lines and no fake thickness, rooms,
doors, windows, floor coverings or fixtures are synthesized.

These presets improve the lighting of available evidence; they do **not** establish
photorealistic source materials, missing 3D BIM geometry or headset compatibility.
Use original-source floor/ceiling and opening witnesses before extending to
measured interiors. Profile on real desktop GPUs and supported headsets before
shipping as an immersive production feature.

## Evidence-safe wall surface microdetail

The renderer can optionally show subtle deterministic micro-roughness on existing,
source-verified wall faces, scaled to the real source wall-face length and
height in texture coordinates. No material schedule is inferred: the pattern
is **a generic presentation aid**, not an actual plaster or paint system.
Unresolved/review-only wall faces keep their translucent appearance and do not
cast false complete-enclosure shadows. Selected faces receive a restrained
presentation highlight rather than replacing the colour of a finish study.
The wall geometry, original-source witness, ledger, frozen quantities and
commercial controls do not change. The effect is off by default and uses one
small disposable texture for the whole scene, with no asset downloads.

## Source-bound immersive review navigation (20+ workflows)

The evidence inspector now includes:
1. Fit the active scene in 3D perspective.
2. Top-down plan camera view (perspective, not a surveyed orthophoto).
3. Front elevation-like camera view.
4. Side elevation-like camera view.
5. Focus on the selected source object.
6. Reset to the whole-scene isometric camera.
7. Search by source object ID.
8. Search by canonical object ID.
9. Search by source primitive path.
10. Restrict to only source-verified objects.
11. Restrict to unresolved/review objects.
12. Restrict to unknown-height source wall lines.
13. Select source drawing sheet.
14. Jump to the next unresolved object.
15. Jump to the previous unresolved object.
16. Isolate the selected existing object.
17. Restore all inspection filters and camera.
18. Toggle presentation grid.
19. Toggle presentation shadows.
20. Toggle the selected source label.
21. Toggle local ghost-height proposals.
22. Inspect visible evidence totals and source status counts.
23. Copy a selected object's source identification to the clipboard.

The controls only change local camera pose, visibility and read-only inspection
metadata. They do not modify manifest objects, canonical identity, approvals,
wall heights, finish tags, measurements or quotes. Unknown-height wall lines
stay source lines. Camera modes are perspective review aids, **not** surveyed
elevations, orthophotos or accuracy proofs. Hidden objects continue to exist
in the source manifest and must not be omitted from commercial takeoffs.

## Source-locked reviewer findings

The VR review notes panel lets a reviewer pin up to 250 bounded questions to
specific source object IDs and their exact object revisions. It supports
low/normal/high priority, open/reviewed local state, find-in-model navigation,
and handoff import/export. Imports fail closed on stale workspace, drawing SHA,
snapshot, model revision or object revision. Data stays in memory unless the
reviewer explicitly downloads a local JSON handoff (max 256 KB).

No notes go into the construction source, correction ledger, commercial
takeoff, quote, pricing or original PDF. "Reviewed" means a reviewer has
looked at a note; it does **not** mean source-verified, approved or FIRM.
Uploaded handoff files remain untrusted and cannot carry authority fields.

## Explicit visual review image export

Use **Export watermarked review PNG** to capture the current desktop WebGL
view, including local visual proposals and source filters. The resulting
image is stamped with project/document/revision/snapshot and an unavoidable
**not a source measurement or approved quote** watermark. Browser export is
bounded to 4096 pixels per axis; no screenshot is automatically uploaded,
saved or shared. WebXR headset screenshot export is intentionally disabled
until hardware/browser consent and privacy support are validated. This is
not a certified drawing sheet or a source-authenticated quantity record.

## Evidence-bound dimensions in desktop/VR

An optional **Source dimensions** toggle shows length and height on the selected
wall face, but only when the server-provided scene has a verified, issue-free
wall object with a canonical ID, original source path and documented height.
Local JSON files are downgraded to REVIEW, and unknown-height source lines
never receive numerical overlays. This is a visual inspection of supplied
source geometry, not a new independent measured takeoff, pricing authority or
approval. The original 120 benchmark items remain unchanged.

## Source-authenticated live costing preview

The selected-wall correction inspector now has two explicit options:
**Preview quantity only** (the existing authenticated endpoint) and
**Recalculate live costs** (the new source-checked, rate-book-bound endpoint).
The second option displays prior/proposed material, waste, labour, plant,
subcontract, overhead, contingency, gross margin, tax, selling price and signed
price impact. The UI never accepts browser-supplied rates, tax or publishing
claims, and will invalidate a previous result when the proposal changes.
Every incomplete price total is marked PARTIAL; missing rates are unpriced
rather than free work.

This is a server-owned **what-if estimate** only, not a persisted correction,
approved client quote, JobHub publication, invoice or sale. It needs a genuine
production company rate-book callback; the frontend never supplies a fallback.
See [the live costing formula and deployment contract](../docs/engineering/VR_LIVE_COSTING_IMPLEMENTATION.md).

## Source-preserving VR wall position studies

The reviewer can explicitly switch from **Inspect** to **Move** mode. In
Move mode, select an existing wall with the VR trigger, squeeze and move a
controller, then release to propose a source-relative displacement. The
same gesture is available from desktop arrow-key / nudge controls; Shift
changes desktop step from 50mm to 500mm. Proposed offsets snap to a 50mm
metre grid and reject nonfinite, excessive and crossing same-level wall
segments. Undo/redo uses Ctrl/Cmd+Z and Shift+Ctrl/Cmd+Z in move mode.

Every proposed movement is *local, reversible and review-only*. Existing
source model endpoints and geometry buffers are untouched; only Three.js
Object3D.position is translated. Collision checks do not prove all wall
junctions or hosted opening integrity. A backend MOVE_WALL approval/
quantity/revision command is **not yet available**, so position drafts are
never offered as persisted changes or priced commercial quantities.
User-confirmed source projection, wall-host continuity and true room closure
are separate prerequisites. Headset grip must be smoke-tested on real
devices before shipping the interaction as production editing.
