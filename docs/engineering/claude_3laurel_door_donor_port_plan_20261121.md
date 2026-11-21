# Port of the closed 3Laurel door stack: plan, audit and piece A

Date: 2026-11-21 (Brisbane). Base: `origin/main` `73d710872e25178ce1f5b8bf9eefb8c5605b2b21`. Branch `claude/port-3laurel-door-kind-identity-20261121`.
Authority: owner answered "Yes, port it" in chat after the donor stack was found (it is the base for the interior door lane, see `claude_interior_topology_openings_architecture_report_20261121.md`). On 2026-11-18 the stack was closed unmerged as an "archival engineering donor for a later clean, individually audited original-app port". This is that port, in small default-off shadow pieces. Nothing here is wired, so no production behaviour, quantity or score changes.

## 1. Donor inventory (observed)

Branch `one-app/3laurel-swing-figured-width-20261115`, head `f7711743f`, 14 commits not on main, 33 files, +5,277/-58, all by the shared account (Cursor lane). PRs 4323, 4337 and 4343 were closed unmerged on 18 Nov; 4338 merged only into its stacked parent (merge commit `a52456f33`, not an ancestor of main). Six new shadow modules with tests, plus edits to shared modules:

| Piece | Files | Needs from shared modules |
|---|---|---|
| A. kind and identity | `pb_source_quarter_swing_opening_kind_shadow`, `pb_source_opening_identity_partition_shadow`, two structural door patterns in `pb_opening_kind_authority` | the swing detector's open tip |
| B. in-swing figured width | `pb_source_swing_figured_width_shadow` | A |
| C. unique-swing host, issued-receipt rebind | `pb_source_unique_swing_opening_host_shadow`, `pb_source_issued_host_binding_rebind_shadow` | A, plus stacker-leaf closures in the ring module (+562 lines there) |
| D. cased openings | `pb_source_dashed_outer_line_cased_opening_shadow` | A, plus a cased-opening collector in the ring module that names one CAD layer |
| E. wiring and policy | `pb_live_physical_net_wall_integration` (+174), publication and estimate edits, AGENTS.md, the 2100 mm rule for internal doors | A to C |

## 2. Order and decisions

A now (this PR). B next, small. C needs a decision on the stacker-leaf closure edit to the ring module, which changes `build_layered_wall_doorway_room_rings` and so the canonical preview; it gets its own architecture note first. D waits: its collector hard-codes a layer name and fails the universal rule until it reads layer-free evidence. E last, with the authority-promotion review AGENTS.md requires, and only after C produces producer-issued host receipts.

## 3. Audit of piece A (what changed from the donor and why)

The donor files are committed verbatim first (original author name, source commits in the trailer); every change is in later commits.

1. **Swing detector.** The donor edited the shared `_swing_arcs` to drop invisibly painted strokes and to return the open tip. Dropping strokes would change the canonical trace, so only the additive `open_tip` key is taken; the paint rule lives in the kind shadow (arc and leaf must have finite positive stroke opacity; zero, NaN and boolean abstain).
2. **Identity partition.** The binding branch required the receipt on both records' evidence; the frame branch compared strings only, so a caller-built or forged matching frame string made two records one aperture. It now needs the same evidence rule. The two identical trailing returns collapse to one and an unused constant is removed. Behaviour for issued receipts is unchanged.
3. **Original-source tests.** The donor tests read an environment variable and skipped silently, and one loaded an unversioned pickle with hard-coded opening ids. They now use the repository resolver (skip only under the public policy, fail on a wrong digest) and the pickle test is dropped.
4. **Review findings of the donor stack.** GPT1's P1 (unissued receipts and trace strings, host rebind) was fixed on the donor child and belongs to piece C; the P2 (identity partition without scope proof) and the P1 on DISTINCT foreign-viewport tips are in this piece and covered by the ported tests plus the new ones.

Limits kept and recorded, not hidden: swing and leaf rows come from explicit wall-layer names (the same universality gap as the internal door detectors, 7 of 9 surveyed drawings carry none); only axis-aligned quarter swings are read (a 30 degree look-alike abstains, tested); the 45 degree leaf length window is 10 to 140 pt, absolute; the opening-to-swing snap is the production 2.5 pt; the cluster comparison is quadratic in the openings of a page; the viewport rule compares records with each other, not with the drawing. Only an already hosted, unkinded opening with an issued receipt can be kinded, so for the interior doors on main (no host on any record) this piece changes nothing until host evidence exists.

## 4. Evidence

Tests: 59 audit tests added; the three donor test files (47 tests, including the existing kind authority tests) all pass, and the original-source test runs against the real original when it is provisioned. Mutation check: 41 of 42 single-line mutants caught; the survivor replaces the canonical-id shortcut for SAME, which the physical-id shortcut subsumes because a live object's two ids are equal by contract (equivalent mutant). Regression: 596 tests across 27 files that touch the ring module, swing arcs, the kind authority, the canonical preview and the route guard pass. The private-source, truth-separation, canonical-route and provider-isolation guards pass locally. Observed on the donor (not changed here): its own original-source collect still left eight hinges without producer receipts and ten unhosted ticks failing closed, which agrees with the host-binding gate measured on main.

## 5. Not proven

No wiring, no kind written on any live opening, no quantity, seal, customer row or score; Python 3.14 and exact-head CI pending; the protected replay not run.

## 6. Untouched

`pb_physical_opening_authority.py`, host binding and frame authorities, the area issuer and estimate publication, the extractor, the canonical preview and its ring options, MAX exterior host code, Cursor's branches, frozen files, signed receipts and identity maps.
