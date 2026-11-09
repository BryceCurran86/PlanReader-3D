# Claude: corner-terminated two-face reveal-stub host SHADOW (diagnostic only). Results

Date: 2026-11-09. Base `22ebd4e3c`. Implements decision (a) of the MAX reply to the architecture report
(`claude_3laurel_slider_host_corner_architecture_report_20261109.md`). Counts, short ids and point coordinates only.

## What changed

New files only: `pb_opening_corner_terminated_host_shadow.py`, `tests/test_opening_corner_terminated_host_shadow_v1.py`,
`tools/diag_corner_terminated_host_shadow.py`. **No existing production module, benchmark-defining file, identity map, signed
fixture, 2.5 pt snap or 20 000 cap is edited.** No production module imports the new module (a test enforces it).

## Rule (diagnostic evidence, never authority)

Default off: `assess_corner_terminated_host_shadow(composition, enabled=False)` returns `()`; `enabled` must be a real `bool`.
For each NON-hosted `jamb_bounded_two_face_interruption` opening it asks whether

1. one flank independently owns a collinear host lineage on BOTH faces (wall-owned drawn flank primitive touching the stub end
   exactly, owned by a locally reaching, boundary-clean, unambiguous W4 candidate group per face), and
2. the other flank's two stubs end exactly on the two ends of a DRAWN wall-owned mitre, whose end points are also the starts of
   two parallel perpendicular wall-owned faces on the same side, exactly one host thickness apart, with the outer corner on the
   correct face, no collinear continuation and no second terminator,
3. the terminator witnesses are distinct from the host lineage (never merged into its equivalence group).

A positive is `EvidenceResolutionStatus.CANDIDATE`, never `CORROBORATED`. It does not touch the binding registry,
`host_wall_id`, `host_binding_record_id`, a frame, a quantity or a customer row; `_opening_quantity`'s host gate is unchanged.
Contact means exact source-coordinate coincidence (1e-3 pt). The existing 2.5 pt gap snap is used unchanged only to decide
whether an already drawn-connected W4 piece locally owns a stub end; it never closes an undrawn connection. Every wall-owned
drawn primitive on the page participates (not the pre-filtered local scope).

## Measured (3Laurel original, page 3, read in place, RapidOCR environment)

| Measure | Result |
|---|---|
| Openings in composition / hosted by existing authority | 180 / 53 |
| Non-hosted two-face openings assessed | **127** |
| Shadow candidates | **1** |
| Composition bindings before vs after the diagnostic | identical |
| First remaining gate, candidate | `authority_promotion_review_required_registry_untouched` (host registry untouched by design) |
| First remaining gate, the other 126 | stubs not staggered 100 (not this pattern), perpendicular face not drawn 9, collinear continuation 5, mitre not drawn 4, terminator ambiguous 2, flank ambiguous 2, unexplained wall contact 2, flank unmapped 1, perpendicular wall passes through 1 |

The single candidate is the two-figure sliding door from the architecture report: collinear flank on one side (2 host members),
mitre plus two perpendicular faces on the other (4 distinct terminator witnesses), perpendicular thickness 2.5512 pt against a
host thickness of 2.5512 pt. The rule contains no project, file or id special case (a test scans for them).

## Proof

56 synthetic tests (source-neutral, plain tuples moved rigidly): positive; rotation 0/90/180/270/37 degrees x mirror x flipped
frame (flank on either side); translation x scale 1.0/1.5/2.0; input-order, segment-splitting, unrelated-content and
viewport-expansion invariance; deterministic replay and stable ids; no mutation; look-alike negatives (missing mitre, unowned
furniture/dimension/joinery ink, detached pier, wrong-thickness wall, collinear continuation, through wall, two terminators,
unexplained contact, inverted stagger, symmetric opening, unsupported faces); stale/foreign/ambiguous evidence (unclean terminator,
unclean flank, far-piece owner, snap boundary 2.4 vs 2.6 pt, two groups, pairwise ambiguity, terminator overlapping host, no flank);
default-off strict-bool adapter; no production importer. One original-source test (skipped without the private PDF) proves the
adapter is read-only and finds exactly one candidate. Eight single-line mutations of the rule were each caught by the matrix.

## Not proven

Protected-environment (Tesseract) behaviour; Python 3.14 beyond public CI; Maryborough signed-three retention (no Tesseract on
this machine; MAX's protected runner owns it); that any host from this rule would be accepted by authority review. No quantity,
score or authority is claimed. No benchmark item is newly eligible. The slider's quantity needs the production host gate,
which this change leaves closed.
