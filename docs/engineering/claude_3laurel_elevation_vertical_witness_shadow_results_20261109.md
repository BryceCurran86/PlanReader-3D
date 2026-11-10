# Claude: elevation vertical witness SHADOW (diagnostic only, default off). Results

Date: 2026-11-09. Base `22ebd4e3c`. Implements decision (C) of MAX 6731795141 (already approved by the owner). Short ids, counts and point coordinates only.

## What changed

New files only: `pb_elevation_door_vertical_witness_shadow.py`, `tests/test_elevation_door_vertical_witness_shadow_v1.py`, `tools/diag_elevation_door_vertical_witness_shadow.py`. **No existing production module, benchmark-defining file, identity map, signed fixture, 2.5 pt snap or 20k cap is edited.** No production module imports the shadow (a test enforces it). It writes no kind, host, frame, quantity or customer field.

## Rule (diagnostic evidence, never authority)

1. **Datum calibration.** The view's FFL and head levels are joined by figured vertical dimensions. Drawn spacing times one common scale must reproduce every printed value within 0.5 percent, or the view abstains. The title-block scale is never used.
2. **Registration.** One (sign, offset) must explain at least two elevation outlines of different widths and strictly more than every other hypothesis (equal widths in points also prove one shared scale). Symmetric or single-anchor scenes abstain; ambiguity is a conflict.
3. **Witness.** The outline at the registered interval (width and both edges) must have its head on exactly one datum level and its base on FFL (leaf base or an enclosing frame base). Two plan records that match the same outline are both held (no winner). A stated competing height conflicts.
4. **Height definition (MAX 6731795141 B).** `opening_height_mm` is the printed datum value (FFL to head). The drawn leaf height is a separate field with its own provenance and is never substituted. A positive is `CANDIDATE`, never `CORROBORATED`; kind, host and frame gates stay closed.

## Measured (3Laurel original, read in place; plan page 3, elevation pages 4 and 5)

| Measure | Result |
|---|---|
| Elevation views with a figured datum chain | 4 (Front, Lhs, Rear, Rhs) |
| Views with one unique plan registration | 3 (Front offset 984.286 pt, sign -1; Lhs offset 15.496 pt, sign +1; Rhs registered) |
| Not registered / not usable | Rear: no unique registration. Rhs: its chain picked up a window dimension that does not self-calibrate, so every record there abstains on the datum |
| Candidates | **2**: `22e7e155` (opening 2,100 mm, leaf 2,020 mm) and `a93486dc` (opening 2,100 mm, leaf 2,105 mm because that door has no sill band) |
| Nested frame record `1cd959cc` | `ABSTAINED`, `elevation_head_not_on_datum`: its outline is the door frame, head 0.85 pt above the datum. Held, not merged into `22e7e155` |
| Interior doors `be1e67bf`, `9d4dc1b3` | no elevation outline at their registered intervals |
| First gate per plan record, aggregated across views (one row per record) | no outline 164, competing outlines 5, head not on datum 6, base not on FFL 3 (windows), candidate 2 |

Registration found the same offsets as my manual measurement (Front 984.285, Lhs 15.5), independently, from widths alone.

## Proof

68 source-neutral tests: positives; sign x scale x translation metamorphic; input order, unrelated content and viewport expansion; replay and stable ids; no mutation; duplicate physical candidate (both held), nested frame record, interior doorway, wrong elevation, single anchor, symmetric (ambiguous) scene, foreign or stale scope (four fields), competing explicit height, two outlines at one interval, head off datum, base off FFL, non-calibrating datum, leaf-vs-opening confusion; extractor on a synthetic drawing (nested frame and leaf, contaminated chain, no chain); default-off strict-bool; no production importer; no project or id special case. One original-source test (skipped without the private PDF). Thirteen single-line mutations of the rule (including leaf height used as opening height, and every check added after review) were each caught; two survivors found along the way were closed with new tests.


## Review fixes (MAX 6732228656, head `c9e76a8f2`)

1. **Non-finite values fail closed.** `calibrate_datum` rejects NaN, infinity, booleans, strings, zero or negative spacing and values, and an overflowing ratio whose mean is infinite (inf/inf is NaN and would otherwise slip past the tolerance). Plan spans and outlines are validated (finite, `a0 < a1`, `x0 < x1`, head above base, finite positive explicit height) before any selection, and abstain with `elevation_witness_input_invalid`.
2. **No silent pick on a duplicate identity.** A repeated `record_id` or `outline_id` (even with different geometry) is a `CONFLICT` (`elevation_witness_duplicate_identity`); the old `next(...)` is gone and input order cannot choose.
3. **Cross-view uniqueness gate.** `assess_elevation_vertical_witness_shadow` now returns ONE result per record through `aggregate_across_views`. Two views that both witness a record, or a candidate plus a record-level conflict elsewhere, are a `CONFLICT` (`competing_elevation_views`). A view that cannot calibrate or register says nothing about the record and does not poison a clean candidate. The diagnostic tool uses the same gate, so its candidate list cannot be cherry-picked.
4. **Production note (accepted, not built).** The PyMuPDF extraction remains a diagnostic. A production slice must source-authenticate exact revision, snapshot, page and viewport native witness observations, a unique registered physical instance, door semantic kind and host binding, and must not select the nested frame record or the two interior openings.


## Source-owned input path with receipts (MAX 6732848990, next work item 1)

`pb_elevation_source_owned_witness_adapter.py` reads the elevation facts only from producer-owned authorities and carries the observation ids that drew each one, so a witness result names its receipts (`source_observation_ids`):

- **Segments:** `SourceVisibilityAuthority` visible native observations for the exact revision and snapshot (corroborated visibility receipt required, page must match).
- **Outlines:** `SourceVisibilityProducer.native_paint_facts` (authenticated paint provenance). The four edges of one filled path share a `path_index`, so a filled rectangle is rebuilt from the observations that actually draw it; a path that is not axis-aligned or whose edges disagree on fill is not an outline.
- **Words:** `PdfTextIntegrityAuthority` receipts, accepted by the same rule as the opening label authority.
- A foreign or advanced revision returns nothing (no facts without an intact lineage). The adapter asserts no role and writes no kind, host, frame, quantity or customer field; only the diagnostic tool imports it.

**Original (3Laurel, read in place):** reading page 4 takes about 4 s and page 5 about 10 s. The source-owned path gives the same four views, datum levels and FFL as the PyMuPDF diagnostic, the same unique registrations (Front 984.286 pt, Lhs 15.496 pt), the same two candidates (`22e7e155`, `a93486dc`; 444 and 238 receipt ids) and identical per-record first-gate counts. The frame record `1cd959cc` and the two interior openings are still held out. The outline sets are not identical to the PyMuPDF ones (visibility and paint facts differ), but the witness result is.

**Proof added:** 76 source-neutral tests (receipts flow from drawn facts to the result, enclosing-frame receipts, ambiguous figure not read, page filter across a two-page synthetic PDF, diagonal fill path, mixed-fill path, stale visibility receipt, foreign revision, a synthetic PDF through the real ingest, visibility, paint-fact and text-integrity producers) plus two original-source tests (skipped without the private PDF). Ten single-line mutations of the adapter were each caught after the first pass exposed five test gaps.

**Still open (not built):** door kind attached to the same physical instance (the label leader needs its own trace), a genuine host binding for `22e7e155` and an independent terminator witness for the slider, and the production opening quantity, seal and customer gates. This adds receipts to a diagnostic; it is not a physical authority and no quantity, score or customer row follows.


## Fail-closed text trust (MAX 6733270532, head `53ddbfaab`)

**Defect found in review:** the raw-text fallback accepted an `ABSTAINED`, untrusted word when `set(reason_codes).issubset(approved)`. An empty reason set is a subset of every set, so a word with **no** stated reason passed as a datum figure. (The same expression exists in the opening label authority's text fallback; that module is not changed here.)

**Fix:** the fallback now needs a **non-empty** reason set that is a subset of the two approved reasons (glyph mapping unverified, clip state unresolved), an `ABSTAINED` status and an untrusted receipt. Every word carries an explicit trust tag (`corroborated` or `raw_unverified`); the tag flows into `DatumLevel.text_trust`, and the witness result reports the worst-of value as `text_trust` (`corroborated`, `raw_unverified_diagnostic_only`, or empty when a plain input claims nothing). The tag is part of the result identity, so a raw-text result can never alias a verified one, and a raw-text result stays `CANDIDATE`-only.

**Rule for promotion (MAX):** a commercial source-owned kind or height requires text-integrity `CORROBORATED` (or a separately authenticated native glyph closure), not this fallback.

**Original (read in place):** both candidates (`22e7e155`, `a93486dc`) currently rest on `raw_unverified` datum figures under the default producer, so the printed 2,100 is **not** yet a verified source word. The geometry independently agrees with it (the drawn spacing reproduces every printed figure within 0.5 percent), but that is not the authority's required status.

**Proof added:** empty reason set, unknown or mixed reasons, a non-abstained untrusted word, approved-only reasons tagged raw, trust propagation (worst-of, never stronger than `CANDIDATE`), and identity separation. Eight single-line mutations of these rules were each caught.


## Opening measurement composition (owner request: turn the evidence into authenticated opening measurements)

`compose_opening_measurement` composes two independent source views of one physical opening and lists exactly what still gates it:

- **Height** is the printed elevation datum (FFL to head) the witness found; the drawn leaf height is a separate field and is never substituted.
- **Width** is the plan's single printed figure, read through the existing label authority; the trust of **every word it used** is re-checked against text integrity (so the label authority's own raw fallback cannot pass as verified).
- **Cross-check:** the witnessed elevation outline width at the datum-calibrated scale must agree with the printed width within 0.5 percent. It corroborates; it never replaces the printed value. A disagreement is a `CONFLICT`.
- **Gates, in order:** text integrity not corroborated, door kind not authenticated, host binding not authenticated; when none is open, `authority_promotion_review_required_existing_issuer_untouched`. The result is `CANDIDATE` only: an authenticated quantity is issued by the existing issuer or not at all.

**A defect the width check caught.** The source-owned extractor had merged two 0.14 pt hairline fills (edge lines drawn as fills) into the Lhs door outline, so it measured 24.95 pt (880 mm) against the printed 870 mm; the witness's 0.15 pt edge tolerance had admitted it. Fills thinner than 0.3 pt are now excluded from unions (regression test; disabling the filter fails it).

**Original (read in place, default producer, so text trust is raw):**

| Opening | Printed width | Elevation width | Opening height | Area | Drawn leaf | Open gates |
|---|---|---|---|---|---|---|
| `22e7e155` | 1,200 mm | 1,200.2 mm | 2,100 mm | 2.52 m2 | 2,020 mm (80 mm sill band) | text integrity, kind, host |
| `a93486dc` (not a mapped item) | 870 mm | 870.3 mm | 2,100 mm | 1.827 m2 | 2,100 mm (no sill band) | text integrity, kind, host |

With the opt-in glyph-ledger text trust, every datum word on page 4 (including both 2,100 words) is text-integrity `CORROBORATED` (`amortized_glyph_verified`, two `raster_corroborated_direct`); that run takes about 20 minutes per page.

## Host binding: first failed predicate, traced from the original (no host is invented)

Read-only trace on page 3 of the original with the live composition (`include_unmeasured_ink_closed_flanks_shadow`, `source_fragment_roles_shadow`), current main modules. Counts and point coordinates only. All three records bind to `abstained` / `no_authenticated_host_wall_band`; the trace says why.

| Fact (source coordinates, pt) | `22e7e155` (Front entry) | `a93486dc` (Lhs, not a mapped item) |
|---|---|---|
| Opening length / thickness | 34.02 / 2.551, axis (0,1) | 24.66 / 2.551, axis (1,0) |
| Opening face stubs | four 0.85 pt reveal returns at x 947.56 and 950.11 | four 0.85 pt reveal returns at y 426.12 and 428.67 |
| Stub owners among W4 candidates | **none of the four** | **none of the four** |
| Wall face lines the stubs should continue | x 947.27 and 949.83: the stubs sit **0.29 pt** off them | y 426.40 and 428.95: the stubs sit **0.28 pt** off them |
| Face line across the opening span | west face has the gap (299.44 to 335.15); **east face x 949.83 runs continuously 298.45 to 336.15, owned by one W4 candidate (`537b8fa8`, 5 primitives)** | **both** faces are drawn across the span (y 426.40 unowned, y 428.95 owned by one candidate) |

First failed predicate: the exact-contact flank lineage needs the four face stubs to be owned by W4 candidates and to coincide with the flanking wall faces (contact is exact source coincidence, 1e-3 pt; 2.5 pt snap is candidate locality only). The stubs are unowned and offset by about 0.28 pt, so no flank pair can be formed. Independently, a face line that is continuous across the opening span (the east face of the entry wall, both faces of the Lhs opening) is not an interrupted through-wall face: the original does not draw, for those faces, a collinear face on each side that ends at the jamb. The source does not say whether that continuous line is a threshold, a frame head or a porch edge, so this module does not say either. **Outcome: ABSTAIN, first failed predicate recorded, no default host, no corner promotion on the shadow-only slider match, no frame, no quantity.** The nested frame record `1cd959cc` shows the same pattern (its west-face stubs are owned by `1272732b` and `56099100`, its east-face stubs are about 1 pt and unowned).

A host will need either a source-owned return that coincides with the wall face (not present here) or the separate wall-band authority MAX owns; neither is changed here.

## Door kind from a stroked leader (proposal only; the kind authority is untouched)

`pb_elevation_label_kind_proposal_shadow.py` (pure core), `label_blocks` / `kind_proposal_for_outline` / `is_stroke_ink` in the source-owned adapter, and `kind_proposals` in the counts-only tool (schema 1.4.0). Default off, never wired.

Rules: the kind comes only from an explicit `DOOR` / `WINDOW` token in the label's own words (no height, no 2,100, no leaf, no outline shape, no width input exists in the module). A label attaches to an instance only through a leader of **opaque stroke-only, axis-aligned** segments (so fill edges, translucent lines and diagonal hatching never count) that starts within 6 pt of the label's extent, leads away from it and joins end to end at exact source coordinates. A fork is explored on every branch; **only a route end that lies strictly inside an outline attaches anything**, so a branch into blank space changes nothing, but more than 16 routes or a route longer than 6 segments abstains. Every route end inside an outline must lie inside **one nested chain** (leaf inside frame inside surround) that contains the witnessed outline: two overlapping outlines that do not nest, or routes into different instances, abstain (`label_leaders_reach_different_instances`); two labels with different kinds on one instance are a `CONFLICT`. Result is `CANDIDATE` with receipts (label words, leader strokes, outlines), `text_trust` worst-of its words, never `CORROBORATED`.

**A failure mode the original revealed (geometry, not a benchmark value).** The first run on the original abstained on the Front entry label (`leader_chain_branches_or_is_unfinished`) because brick/ground hatching sits within 2.1 pt of the label: diagonal hatch strokes and one short vertical-then-diagonal polyline qualified as "leader starts" and one of them forked. Two principled changes, no threshold tuned to a value: leaders are orthogonal only (a diagonal leader abstains), and a fork matters only where a route end lands in an outline.

**Original (read in place, default producer so the words are raw, 3Laurel p4):**

| Opening | Kind proposal | Label block (2 stacked lines) | Nested outlines | Text trust | Receipts |
|---|---|---|---|---|---|
| `22e7e155` (Front entry) | door, `CANDIDATE` | at (609.10, 303.30) | 3 | raw_unverified_diagnostic_only | 215 |
| `a93486dc` (Lhs, not a mapped item) | door, `CANDIDATE` | at (302.93, 619.85) | 3 | raw_unverified_diagnostic_only | 233 |

The Front entry leader is the stroked polyline (647.25, 308.17) to (658.91, 308.17) to (658.91, 264.24) starting inside the label's extent; nothing else touches its end within 1.2 pt. The nested frame record `1cd959cc`, `be1e67bf` and `9d4dc1b3` have no witnessed outline, so they get no proposal.

**Still open for kind:** the words are raw. A kind needs text-integrity `CORROBORATED` words (explicit glyph-ledger opt-in, about 20 minutes a page) and the hand-over of this proposal to the existing kind authority, which stays MAX's. Nothing here writes a kind.

**Proof:** 62 source-neutral tests (positives, look-alike negatives, ambiguity and conflict, translation, input-order, segment-splitting and segment-direction invariance, unrelated-content invariance, deterministic replay, no mutation, non-finite and duplicate input, real producers through a synthetic PDF) and 30 single-line mutations of the core rules and the adapter extraction, all caught (a first run left four survivors; each closed with a test or by removing a redundant branch).

## Review fixes (MAX review 5834419211 on head `4c10ad613`, 2026-11-10)

Both reproduced counterexamples are fixed on this child branch; the diagnostic stays default-off and candidate-only.

1. **Compound filled paths no longer become a phantom rectangle** (`read_source_owned_page`). The edges of one path were grouped by `path_index` and given one bounding box, so two disjoint rectangles in one `Shape` produced a single rectangle spanning the blank gap between them. `rectangle_components` now builds connected components from exactly shared corners and accepts a component only when it is one simple closed loop of axis-aligned edges (a side may be split into collinear pieces) with exactly four corners on two distinct x and two distinct y values and one fill. Disjoint rectangles stay separate, each carrying only its own edges' receipts; an L-shaped or concave loop, a bowtie with diagonals, a loop with a tail or junction, and rectangles touching at a corner yield nothing. Real-producer regression: two filled rectangles in one `Shape` give two rectangles and nothing spanning the 30 pt gap; an L-shaped path gives none.
2. **Ambiguity that reaches the witnessed instance survives beside a usable DOOR label** (`propose_kind_from_leader`). Ambiguous outcomes were only consulted when no usable label remained. They now accumulate as vetoes: a label whose leaders end inside non-nested outlines that include the witnessed one; an overflowing label (too many or too long routes) whose connected stroke network has any point inside the witnessed outline (a network larger than 512 segments is assumed to reach); and a label naming both kinds that reaches it. Any veto abstains in a fixed order (`leader_tip_inside_non_nested_outlines`, then `leader_routes_overflow_or_are_unfinished`, then `label_has_both_door_and_window_tokens`) whatever the input order. Unrelated labels, and token-less labels such as a bare size, stay harmless. The reviewer's exact fixture (A=(20,20,40,40), B=(30,30,50,50), DOOR bbox (0,21,5,23) with stroke (5,22)-(25,22), WINDOW bbox (0,34,5,36) with stroke (5,35)-(35,35)) is a test: each label alone, both together in all four input orders and 20 random orders.

Proof: 54 kind-core tests, 16 kind-adapter tests, 19 rectangle-component tests and the 105-test witness suite (192 pass; 2 original-source tests skipped without the private PDF) and 25 single-line mutations of the new code, all caught (two redundant degree and count guards were collapsed and one equivalent corner-count guard removed from the mutation list as unreachable). Not a protected-runner result and not a re-run of the original; the earlier measurements on the original are unchanged except that the extractor can no longer invent a spanning rectangle, which the three-view original run did not rely on.

## Not proven / limits

The source-owned adapter (not the PyMuPDF diagnostic) is the input path for the witness, the measurement and the kind proposal; the PyMuPDF path is kept only to cross-check it. Door kind for `22e7e155` and `a93486dc` is a **raw-text `CANDIDATE` proposal only**: text integrity is not corroborated by default, the existing kind authority has not received it, and no kind is written. Host binding **abstains** for both (first failed predicate recorded above; no default host, no corner promotion on the shadow-only slider match). No frame, no quantity, no seal, no customer row, no score, no benchmark item newly eligible. Protected exact-head original replay and Lot16-eight / Maryborough-three retention for the head that carries this are MAX's to run and are not run here (no production code changed).
