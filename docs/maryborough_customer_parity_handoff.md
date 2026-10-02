# Maryborough customer parity handoff

Review date: 2 October 2026. PR #1202 is draft and must remain unmerged until
the failed source/customer room gate is resolved. The integration repairs
isolated cache, import, viewport and allocation defects; it does not redesign
the room architecture. The accuracy failure below is returned to the room
authority owner under the user's integration instructions.

## Source and runtime boundary

The source is the unchanged, 31-page Maryborough architecture PDF, 5,709,675
bytes, SHA-256
`b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`.
The deployed entry point is `pb_planreader_v133_app`, through its complete
v1.5.1 startup chain. The local customer probe writes the uploaded bytes and
document record using the normal upload contract, indexes the real pages,
selects pages 7/9/11 (A110/A120/A140), and calls normal `process_document`.
It supplies no room dimensions, scale overrides, geometry or expected areas.
Supported non-AI reading is enabled; optional ONNX/RapidOCR dependencies are
absent and local Tesseract is available.

Automatic processing completes in 658.991 seconds, returning `[3, "Processed"]`.
The completed checkpoint records both bad cold-room quantities before an
additional manual refresh. The later SQLite export has 56 rows; that redundant
refresh is interrupted without a second completed-result claim. Exported page
calibrations may reflect the partial refresh. This is a normal upload with
three selected pages, not an all-31-page extraction or a UI visual audit.

## Source control versus customer result

| Object / physical identity | Source-backed geometry and quantity | Canonical identity | Observed customer result | Gate |
| --- | --- | --- | --- | --- |
| Food Prep, existing A140 dimensioned partition span | 4025 x 3297 mm; requested control 13.270425 m², reproduced independently. The source ledger does not promote this span to a new full-room closure. | Unavailable in the completed A140 live composition. | No named Food Prep row and no publication of the required result. | Failed. |
| Cold Room, WA06 interior panels, north D16 and south D20-D27, east of Freezer | 6425 x 3950 mm; 25.37875 m² envelope; ceiling 2400 mm. Net wall finish deductions unavailable because display-door dimensions are unspecified. | Unavailable; the label and SQLite row ID are not canonical physical identity. | Automatic report: 1.765 m², Measured. SQLite row 53: `COLDROOM`, 1.76 m², Measured. | Failed; incorrect quantity. |
| Freezer, separate instance west of Cold Room, D17 and south D18-D19, WA07/WA06 panels | 1700 x 3875 mm; 6.5875 m² envelope; ceiling 2400 mm. Depth is 3950 - (150 - 75), with common datums independently checked. Net wall finish deductions unavailable. | Unavailable; do not merge it with Cold Room because the legacy areas match. | Automatic report: 1.765 m², Measured. SQLite row 50: `FREEZER`, 1.76 m², Measured. | Failed; incorrect quantity. |
| Dry Store, open storage bay beside Wash Up | Authored division/boundary unavailable; dependent quantities must abstain. | Unavailable. | No named Dry Store row. This does not prove a room-owned abstention decision. | Correct abstention still unproven in the customer contract. |

Cold Room route A uses explicit A140 dimensions and native witness/panel
evidence. Route B independently inspects Poppler render/bboxes, corroborates
A120's 1625 + 3200 + 1600 width chain, and checks A110/A600 door identities.
Freezer route A uses the A140 1700 dimension, authored WA07/WA06 thicknesses
and common interior/outer datums. Route B uses independent Poppler face/leader
inspection, A120's 1000 + 700 chain and ceiling height, and the distinct
A110/A600 doors. These are two evidence routes through the authored source;
PDF coordinates identify faces, not an inferred metric scale.

Previously closed WC/Shower, PWD, Airlock, Laundry, Office and Food Prep remain
in the project census. Wash Up, M-AMB, F-AMB, Food Service, Sales, POS Counter
and Truck Driver Lounge retain their unresolved source boundaries/extents.
The diagnostic Anti Gravity report's 1700 x 3950 Freezer claim and title-block
scale conversions are not adopted as source closure or production inputs.

## Production seams for owner review

The canonical route is `GenericPlanReaderExtractor` -> live physical net wall
composition -> producer-owned source visibility / wall-opening composition ->
`compose_live_canonical_rooms` -> canonical floor projection. The A140 probe
completes in 340.071 seconds with no predictions and these room reason codes:
`live_canonical_room_composition_unavailable` and
`source_room_face_scope_unavailable`. Floor surfaces are also unavailable.

Read-only tracing finds that the live wall candidate constructor uses
`from_source_visibility_producer`. Room composition requests
`wall-source:page-{page_id}` without a viewport and requires CORROBORATED,
complete source-room-face records. Its available canonical room projection
does not itself mint metric geometry (`metric_geometry_complete=False`).
The authenticated-viewport producer exists, but changing this seam requires
owner design and source-scope proof. A page-wide promotion would weaken the
existing fail-closed boundary.

`pb_source_room_area_bridge` composes sealed source room faces, an owned entity
index and existing room-area quantities. It is explicitly shadow-only and
does not publish extractor predictions or customer rows. It requires a
current FIRM calibration or owned corroborated area evidence. There is no
reviewed production room-area bridge imported by this integration.

The normal customer has a separate legacy quantity path:
`pb_planreader_v126_app` -> `pb_room_face_takeoff.apply` patch of
`pb_auto_geometry_v1219._build_unit_rows` -> raw vector room-face extraction ->
label/filter/calibration -> room takeoff rows -> ordinary publication ->
SQLite/UI consumer. The page reader reduces native words to text/bounds;
native block/line/word ownership is not retained. This path assigns high
calibration confidence when a scale factor exists and can publish Measured
areas without canonical room identity or sealed room-face authority.

Both incorrect rows cite
`PB Auto Geometry v1.2.19 · PB RoomFace v2 · A210 · page:7`, the same 11.36 m
legacy perimeter and empty commercial-authority fields. The source sheet is
A110; the customer also registers source A140 as `Finishes Schedule`, while
the legacy room selector admits only floor/partition pages. This is observed
classification/path evidence. The exact physical polygons behind the bad
areas are not yet source-owned; attributing them to a particular legend cell
would be inference and is not claimed.

Do not solve this by allowing more unowned raw faces, inventing geometry,
relabelling the wrong quantities as canonical, or changing coverage. The owner
must establish the same source-owned physical room and metric authority in the
normal customer contract, retaining separate instances and explicit abstention.

## AG-09 and performance

The completed customer registry reports 267 opening objects DETECTED,
AUTHENTICATED and CANONICALIZED; zero QUANTIFIED and zero PUBLISHED. Their
dropout reason is `explicit_quantity_link_unavailable`. These counts are not
room counts. The 56 legacy SQLite rows do not demonstrate publication of the
267 canonical openings. Room canonical availability remains abstained.

The A140 extractor's peak RSS is 3,827.008 MiB. The customer's observed
high-water RSS is 3,174,252 kB, about 3,100 MiB. A focused paint-log regression
reduces repeated reads from five to one with identical trusted decisions and
unchanged abstention. The exact raw-polygon allocation probe improves from
1.07749 seconds to 0.023749 seconds for 2,500 unmeasured loops, preserving no
room output. Those isolated gains and green synthetic performance CI do not
prove that normal-upload freezes or high memory use are resolved.

## Validation and commit order

Validated published code head:
`b9ad1aaa924b5b5a91708c0091cb2d72d9fab426`, tree
`1992bec04e8ee20b1b3f2f3c80ed2bc23aa3245b`, exactly equal to local tested
`a9cca38a5c43bb3e5908e54938e974873ed5aced`. This handoff is a subsequent
documentation-only commit.

| Published commit | Scope |
| --- | --- |
| `68f0728242fc9685d0769523ebecbbf30d484b48` | Reviewed #1197 performance changes plus original source guards, missing typing imports and preserved normal Item 35 default. |
| `40198e568b65d5c4318f3c497f3bc796c0ddbacb` | Only phrase-first room labels from owner commit `d009d573`. |
| `b4c39333037141d1f80095188610fa05d993bf0f` | Only owner room-label tests from `11dd6f51`; unrelated parent history excluded. |
| `043438dc453ad789e24302a7f6b7bfe2c4536367` | Missing `math` import exposed by real pytest. |
| `405df8efefc8c5723080cee08be19f68b1ae8f63` | Reuse opening membership only for its exact authenticated candidate tuple. |
| `528b1439ed901722bf2ed1430f2cd02a9405e275` | Reuse existing page paint-log cache for exact overprint proof, with hostile regressions. |
| `d7baba8aabca478e768e30b312c43abb96c54b8f` | Count the live source-owned opening constructor in the existing one-construction test. |
| `b9ad1aaa924b5b5a91708c0091cb2d72d9fab426` | Build the identical raw polygon list once before filtering; no geometry, filter or quantity-rule changes. |

Actual pytest: 585 performance/authority tests; 107 owner room-face tests after
the import fix; 222 combined tests after the viewport fix; 94 text-integrity
tests; 19 constructor/scope checks; final 193 focused integration tests. Ten
stale-source cases pass on main, fail on the original performance cache code,
and pass after the existing guards are restored. Full CI run `36959502724`
passes on Python 3.13 (7,332 passed / 55 skipped / 13 xfailed, 319.47 seconds)
and Python 3.14 (same counts, 322.51 seconds), with CI smoke passing on both.
Performance Fastpath `36959502736`, Docker Runtime Smoke `36959502734` and
Wall Equivalence Grid Shadow `36959502697` pass. Ruff F821/F823, V2
integrity/separation, provider isolation and `git diff --check` pass.

No benchmark/golden, V2 truth/scoring, costing or VR UI changes are included.
The retired canonical-five percentage runner is not restored. The active
four-source benchmark release gate is not asserted while Maryborough fails;
the user's final canonical gate remains pending a stable integration.

Main `b4c71c22` already includes #1140. Do not merge the original #1197 head
`62485426` separately: this integration contains its reviewed changes and the
required guard corrections. Do not merge the entire room-label branch history.
Keep #1202 draft until owner room changes are reviewed and the Food Prep ->
Cold Room -> Freezer / Dry Store customer gate and real performance rerun pass.
Only then refresh main, rebase reviewed isolated changes as needed, rerun
regressions and the active release gate, and prepare final merge order.

#1201's dense-CAD hatch guard is a separate lane, not imported here. The exact
18-page 3LAUREL #1140 runtime exited 139 without a completed result; its merged
CI does not close that source gate. Validate the resource guard and rerun that
source independently. #1198/#1199 and foreign dirty worktrees are not mixed
into this integration.

## Required handoff fields

| Field | Result |
| --- | --- |
| TASK | Integrate reviewed performance and phrase-first room-label fixes; execute real Maryborough source/customer gate. Integration and regression checks completed; accuracy gate failed. |
| OBJECT FAMILY | Room / Space and Floor Surface; underlying Wall / Opening authority and opening AG-09 dropout observed. |
| PHYSICAL IDENTITY | Source-owned Cold Room and separate Freezer identities above; Food Prep existing control and Dry Store unresolved bay retained. Legacy labels are insufficient physical identity. |
| CANONICAL IDENTITY | Unavailable for the tested rooms; no fabricated IDs. Opening registry reaches canonical identity but lacks quantity links. |
| GEOMETRY | Source ledger envelopes above; live metric room geometry unavailable. No PDF-coordinate scaling or hidden defaults introduced. |
| QUANTITY | Food Prep control missing; Cold Room and Freezer wrongly publish 1.76 m² each; Dry Store dependent quantities unavailable. |
| CUSTOMER CONSUMER | Deployed normal upload -> automatic analysis -> takeoff SQLite; existing UI reads those rows. No visual UI verification claimed. |
| AG-09 STAGE | Rooms abstain at canonical composition; 267 openings die at QUANTIFIED with `explicit_quantity_link_unavailable`, zero PUBLISHED. |
| TESTS | Focused pytest and both full Python CI suites green; exact-source customer accuracy and production-performance closure failed/unproven. |
| COMMIT | Validated code `b9ad1aaa924b5b5a91708c0091cb2d72d9fab426`; final handoff follows as documentation only. |
| PR | #1202, draft, unmerged; #1140 already merged, #1201 separate. |
| UNRESOLVED | Source-owned room scope, metric/canonical bridge and weaker customer path; Dry Store contract abstention; high runtime/memory; #1140 private-source crash gate; final release gate. |
| NEXT TASK | Room-authority owner reviews the major seam failure, supplies isolated source-preserving fix, then normal customer Food Prep -> Cold Room -> Freezer / Dry Store and performance gates rerun before release. |
