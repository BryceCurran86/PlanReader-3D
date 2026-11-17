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
