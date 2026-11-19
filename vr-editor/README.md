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

## Authenticated building surface meshes

An existing PlanReader original-source producer may optionally supply
`SourceVerified3DSurface` records for **floor**, **ceiling** and **roof**
surfaces in the current scene. These are independently triangulated, tied to
the immutable original PDF SHA, exact source native geometry, canonical
object revision, validated area, and separate geometry/triangulation receipts.
The renderer draws exactly those triangles, not a guessed room slab or roof.

This is deliberately a positive-evidence-only feature: absent a trusted
producer, nonwall objects remain inspector-only with no invented surface.
The feature does not synthesize wall thickness, subtract openings, invent
ceiling heights, add materials, approve measurements or publish a quantity.

Production deployment needs the existing server workspace loader to pass
`source_surfaces` from the independently authenticated original-source
triangulation producer into `compile_editor_scene(...)`. Passing
`coordinates_or_measurements` from a client or declaring a room "firm"
cannot mint a `SourceVerified3DSurface`. Source-surface area is a display
consistency cross-check, not a billable takeoff. The full room/wall/opening
BIM-authority workflow remains a separate gate.

## PlayStation VR2 PC adapter (Windows / SteamVR)

The VR editor now includes a **PS VR2 PC adapter** readiness panel with a
live `navigator.xr.isSessionSupported("immersive-vr")` check, a retry button,
left/right controller diagnostics, and Standard WebXR controller-input support.
It does **not** communicate directly with Sony's hardware, SteamVR's native
C++ APIs or a proprietary driver. The PC browser must provide an immersive
WebXR session using the Windows SteamVR/OpenXR runtime.

### Setup checklist

1. Use a compatible Windows 10/11 PC. Sony recommends RTX 3060 or RX 6600 XT
   or better for performance (higher than their minimum GPU specification).
2. Connect Sony's official PS VR2 PC adapter to a direct USB 3.0 Type-A port.
   Attach power, the PS VR2 headset and a separate DisplayPort **1.4** cable
   from the adapter to a **physical GPU DisplayPort output**. DisplayPort
   delivered via USB-C does not work with the official adapter.
3. Pair both PS VR2 Sense controllers separately over Bluetooth in Windows.
   Install Steam, SteamVR and the official PlayStation VR2 App. Complete the
   initial setup, headset tracking, controller calibration and play area.
4. Start SteamVR and ensure it is selected as the active **OpenXR runtime**.
   Keep the PlayStation VR2 App installed.
5. Open PlanReader's VR editor from the **Windows desktop browser** via
   HTTPS (or `localhost`), rather than from the PS5 browser. Use the
   **PlayStation VR2 · PC Adapter** readiness panel's **Check VR availability
   again** button after SteamVR is started.
6. If the browser reports `immersive-vr` supported, open a real scene or
   the synthetic example and click the viewer's **Enter VR** button. A
   successful capability check is **not proof of hardware compatibility**.
   Check the live left/right controller diagnostics.
7. Use either Sense controller's L2/R2 primary action (WebXR `select`)
   to point at/select an existing wall. Squeeze/grip (WebXR `squeeze`)
   cycles temporary study finish colours. For a runtime that does not emit
   native squeeze actions, a standard WebXR `xr-standard` gamepad button
   index 1 fallback acts **once on grip release**. It is never enabled for
   unknown/raw gamepad mappings and cannot publish costs or approvals.

Native `squeeze` events win over gamepad polling to avoid duplicated
corrections. The browser session and controller state are shown in the
inspector, but the Sony serial number or hardware identity is neither read
nor stored. Controller discovery uses WebXR handedness and generic profiles,
not fixed PS VR2 product strings.

### Important limitations

- **Browser support is runtime-dependent.** Some browser/SteamVR/OpenXR
  combinations do not expose immersive WebXR for the PC adapter even though
  native SteamVR games work. In those cases, the app remains usable in
  desktop 3D; a native OpenXR wrapper would be a separate deliverable.
- The headset is **not yet physically tested** with PlanReader on a PC and
  we do not claim PS VR2 adapter certification. Test target: Windows
  PC + adapter + SteamVR + Sony app + compatible browser + both controllers.
- HDR, eye tracking, headset feedback and adaptive triggers are not
  available in Sony's supported PC adapter feature set. PlanReader does not
  require them. PSVR2 inside-out tracking, Bluetooth pairing and the
  room's play area remain managed by Sony/SteamVR, not the browser app.
- If tracking or connection fails, use Sony's troubleshooting advice:
  direct USB adapter connection, correct DP cable, updated GPU drivers,
  SteamVR Direct Mode and Bluetooth adapter pairing.
- Headset rendering is a visualization of a source-scoped review scene.
  Moving, colouring or selecting objects never overrides PlanReader's
  protected source drawings, signed quantities or approval gates.

**Official references**

- [Sony PC requirements](https://www.playstation.com/en-au/support/hardware/psvr2/)
- [Sony PC setup](https://www.playstation.com/en-au/support/hardware/pc-ps-vr2-set-up/)
- [Sony PC troubleshooting](https://www.playstation.com/en-us/support/hardware/pc-ps-vr2-troubleshoot/)
- [PlayStation VR2 App on Steam](https://store.steampowered.com/app/2580190/PlayStationVR2_App/)
- [Three.js VRButton](https://threejs.org/docs/pages/VRButton.html)
- [WebXR input sources](https://developer.mozilla.org/en-US/docs/Web/API/WebXR_Device_API/Inputs)

Local checks: `cd vr-editor && npm ci && npm test && npm run build`.
Required hardware smoke: check immersive session starts/exits, left/right
controller tracking, trigger picks, grip changes once, session disconnect
clears the UI, and desktop remains functional when WebXR is unavailable.

### PS VR2 wall drag review mode

Choose **Move** in the Wall Position Editing inspector, use either Sense trigger to select a source-backed wall, then hold and move that controller's grip and release to snap its purple review ghost to a 50 mm grid. Runtime standard `squeezestart`/`squeezeend` actions take priority; the `xr-standard` grip fallback supports SteamVR configurations with no native squeeze events. Desktop arrows nudge 50 mm; Shift+arrows nudge 500 mm. Undo, redo and reset are available.

Movement is **local only**: translations do not persist, change original PDF geometry, approve hosted openings, recalculate billable quantities or price materials. Cross-wall collisions at the same level are blocked, but this does not prove complete topology. A production `MOVE_WALL` transaction and real PS VR2 headset acceptance test are separate gates.

## Place walls, doors and open frames

1. Choose a source level if the project has several levels. On desktop, **Top view** makes it easier to place points on the plan.
2. Choose **Wall**, then click its start and end. In the headset, use the floating build menu and pull either controller trigger to place each point. The length updates as you aim.
3. Choose **Door** or **Frame**, aim at a draft wall and click or pull the trigger. **Frame** leaves an open passage. Use **Undo** to remove the last placement and **Done** to return to inspection.
4. On desktop, open **Review drafts** and select a wall. Check **Exact dimensions and openings**, enter a registered assembly profile ID, and select **Calculate wall and opening costs** in an authenticated workspace.

**Placement sizes** lets you set the starting height and opening dimensions on desktop. Sketches use the editor’s level plan and remain local until you use the authenticated wall review and save flow. Doors and frames attach to newly drafted walls. The frame geometry shows an indicative opening for review.

## Materials and fixtures catalogue

Open **Items** beside the building tools. Search by product type, colour, size or profile, or pick a category. Select an option and aim at the indicated surface. In an immersive WebXR session, open **Items** on the floating build menu, choose a category and item, then use either trigger to place it.

- Plasterboard and paint apply to wall faces or ceilings. Floor coverings and wall coverings follow the surface you select.
- Skirting follows a wall base and leaves gaps at floor-level openings in drafted walls. Architraves fit the doors and frames created with the build tools.
- Place wall tapware, switches and sockets on wall faces. For benchtop mixers and basins, place a vanity or base cabinet first and aim at its worktop.
- **Draft item schedule** lists placements by selection and offers a CSV download. Undo and removal work on the current draft.

The built-in synthetic scene has two sample rooms for trying floor coverings and lighting. Catalogue geometry and finishes are editable visual choices. The schedule counts placements for review. Project estimating and pricing use the authenticated construction scope.

### Timber and exterior choices

Place timber boards, battens and mouldings on a wall face. Pick the centre of the piece and use **Rotate** to turn it. Posts stand on a floor or deck surface. Front door assemblies fit openings made with **Door**. Wider styles show the smallest draft opening they can fit. Door finish choices colour the leaf while preserving its glazing.

Pick an exterior substrate and a finish on the same wall side to see the finish and record both choices in the draft schedule. Decking and paving apply to floor surfaces. Soffit and eaves options apply to ceiling surfaces.

## Adding a wall must add its associated trades

The read-only `POST /api/editor/workspaces/{id}/walls/add/preview`
endpoint calls `pb_vr_wall_assembly_dependencies.py`, using only
server-retrieved project assembly specifications and verified existing
electric/hydraulic routes to calculate all potential dependent work:

- **Framing:** wall plate runs in lm, approximate full-height stud stock and
  stud counts from *specified* spacing, and noggins from *specified* rows.
  Door lintels, jambs and junctions remain explicit design holds.
- **Bracing:** specified schedule area only; unknown structural design is a
  hold, never a guessed amount.
- **Plasterboard:** net wall face area per specified side; deduct actual
  user-positioned openings from each affected face.
- **Skirting:** linear length per specified finished face, less floor-level
  door/passage widths, never window sills or undocumented faces.
- **Electrical and plumbing:** include only fittings/branch runs explicitly
  tied to the wall by the server-owned schedule; identify collisions with
  independently verified same-level service routes for engineering review.
  Unresolved services are flagged, not counted as zero or invented from
  generic building code assumptions.

The project source PDF, canonical object, approved quantities, ratebook and
JobHub outputs are *not modified*. The returned quantities are
`review_only`, with deterministic line identities so a wall geometry
change **replaces rather than duplicates** the dependent bill. The service
does not issue construction costs or claim electrical/plumbing design is
complete. This remains an authenticated *preview* until the future
wall-create + multi-sheet geometric revision transaction and trade-specific
approval gates are connected.

### Deploying the preview

A production app must supply all five real callbacks to
`make_wall_addition_scope_wsgi_app`: authentication, an authorized original
workspace loader, CSRF verification, a server-owned profile resolver, and a
trusted service-route census. No demo or user-submitted specification can
become authority. Real company rates can be applied only through the
existing commercial ratebook bridge after each new quantity is approved
against original/user-authorized revision evidence.

Focused tests:
```
python -m pytest -q tests/editable_3d/test_vr_wall_assembly_dependencies.py tests/editable_3d/test_vr_wall_assembly_wsgi.py
cd vr-editor && npm test && npm run build
```

### PS VR2 comfort navigation: source-floor-only teleport

The authenticated editor has a separate **Verified floor teleport** checkbox.
In immersive SteamVR, select the checkbox, aim a PS VR2 Sense trigger at a
source-attested floor and release. A green ring is displayed only on validated
floor targets. A teleport is allowed only when the existing canonical source
floor triangles match the original document SHA and snapshot, the target is
more than 12cm from the outer floor boundary and 20cm to 7m from the current
headset, and the floor is on the local ground stage (approximately Y=0).
Interior triangle seams are not confused with external room boundaries.

The navigation uses `XRReferenceSpace.getOffsetReferenceSpace` and
`XRRigidTransform`; **no source geometry, wall object, quantities, rates
or saved PDFs are moved**. Selecting a wall and grip-to-move studies are
still available when teleport mode is disabled. Local JSON/synthetic
examples without authenticated floor triangles cannot enable teleport;
decorative shadow planes never authorise movement. Vertical jumps, stairs,
physical collision and room-level accessibility routing remain unsupported
until separately verified.

This is a comfort-navigation preview pending actual SteamVR/PS VR2 PC
headset testing. The SteamVR/PS VR2 physical play-area guardian remains
in force: teleportation does not physically move a person or guarantee
there is no obstacle around them.

See the WebXR native reference-space documentation at
https://developer.mozilla.org/en-US/docs/Web/API/XRReferenceSpace/getOffsetReferenceSpace
and Three.js's official WebXR teleport example for the reference-space
offset approach.


## Multi-wall desktop / PS VR2 construction review batch (local what-if)

The wall-addition panel can now accumulate up to **25** independently validated
wall assembly previews against one exact project, drawing, source SHA, snapshot,
and model revision. When the original authenticated wall assembly API accepts a
new design, its reviewed quantities replace the previous version of that same
proposal rather than being summed twice. All active proposals appear together
as translucent purple **review ghosts** in desktop and WebXR rendering; they
are not selectable physical wall entities or a new source measurement.

Included operations:
1. Keep source-scoped independent wall proposals.
2. Replace a prior proposed wall's quantities without double billing.
3. Remove a wall from the local design review.
4. Undo local batch changes (bounded history).
5. Redo local batch changes.
6. Aggregate framing, bracing, plasterboard, skirting and specifically sourced
   electrical/plumbing work **only by identical trade, item, specification and unit**.
7. Inspect proposal quantities independently by level.
8. Flag same-level intersects, touches and collinear overlaps for structural review.
9. Show signed quantity deltas between successive accepted batch checkpoints.
10. Deduplicate outstanding MEP/structural/finish coordination holds and export
    a bounded JSON **review summary** (no replayable commands, source receipts,
    prices, or automatic approval).

The workbench resets on source-scope or authentication changes. It never creates
a new wall in the canonical PlanReader model, assigns electrical/plumbing routes
by guesswork, commits a multi-object PDF revision, derives a sell price from
browser data, or approves commercial quantities. The single-wall work package
still comes from the server's existing project assembly provider with every
missing design input placed on HOLD. Batch totals are illustrative coordination
summaries, not FIRM takeoffs. Headset output requires actual WebXR support and
PS VR2 hardware testing; green TypeScript/Node CI is not headset proof.

Test via `cd vr-editor && npm ci && npm test && npm run build`.
