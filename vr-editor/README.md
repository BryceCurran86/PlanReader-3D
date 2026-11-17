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
