# Handoff — Lamu DPC / dimension-binding / envelope-decomposition lane

Session end-of-turn handoff. Covers everything from the KSTVET window lane close-out
through the envelope-decomposition investigation and the PR #552 close-out. Written
so a fresh agent or Bryce can pick this up without re-deriving anything below.

**`main` at end of session: `29e245c` (includes PR #552's merge below). Branches in
§2/§3 were cut from `7a498ef` and have not been rebased onto `29e245c` — `gh pr view
890` still reports `MERGEABLE` as of last check; re-check before merging if much
time has passed.**

## TL;DR — what's safe to act on right now

0. **[PR #552](https://github.com/BryceCurran86/PlanReader-3D/pull/552) is MERGED** (`29e245c`) — rebased onto current main, re-verified, CI-green, merged this session. Nothing further to do here. See §0 for detail.
1. **[PR #890](https://github.com/BryceCurran86/PlanReader-3D/pull/890)** is a draft, CI-green, isolated, real bug fix — ready for a merge decision. Nothing else here is.
2. Two more branches hold real, tested, but **intentionally unmerged** work — read why before touching them.
3. LMU-E3-B (Lamu DPC) is **not** resolved and, on current evidence, may not be resolvable from this source page — see "Disproven / closed" below before re-opening it.

---

## 0. PR #552 — item35 opening-count/schedule test coverage (MERGED, closed out)

**Was:** `claude/item35-pr3-additional-test-coverage-v1`, 209 commits stale against main, open since 2026-09-20.
**Action taken this session:** rebased cleanly onto `main` @ `a7980ed` (no conflicts), verified every test against the current, live architecture before touching anything:
- `pb_generic_opening_count_authority.py` (the module these tests exercise) is still imported by `pb_item35_production_authority_shadow.py`, which is wired directly into `pb_planreader_pdf_extractor.py` (lines ~2690/2703) — confirmed still live, not superseded, despite 209 commits of intervening item35 work (semantic opening disposition, opening-universe-by-source-candidate-closure, etc.).
- `test_producer_signature_cannot_accept_caller_instance_bundles` — a structural introspection test of `GenericOpeningCountProducer.from_authorities`'s exact parameter set — still passed unmodified, proving the core producer contract has not drifted.
- All 176 targeted tests passed; broader sweep (+ `test_item35_production_authority_shadow_v1.py`, `test_opening_universe_completeness_source_adapter_v1.py`, `test_opening_universe_page_scope_coverage_v1.py`, `test_source_opening_universe_evidence_v1.py`) — 296 passed.
- `compileall`, `ruff F821/F823`, benchmark-gold separation, provider-gold isolation, `ci_smoke.py` — all passed locally.
- Force-pushed the rebase to the PR's own branch, updated the PR description with the rebase/re-verification detail, waited for GitHub Actions (`test`+`fastpath`, 3.13/3.14 — all passed), then **merged** (`--merge`, branch deleted): commit `29e245c6a9d108bf421a8017384c663c90b5328e`.

**Conclusion:** none of the 10 added tests were obsolete or tested replaced architecture — all still represented valid, current, live-consumed contracts. No "close as superseded" path was needed. Nothing further to do here.

---

## 1. PR #890 — dimension-line fragment merge (ready for review)

**Branch:** `fix/dimension-line-fragment-merge-v1`
**Commit:** `9273a472ec28d0cc606aac3085fd0adaa725431a`
**Base:** `main` @ `7a498ef` (main has since moved to `a7980ed` via unrelated PR #888 — GitHub reports PR #890 still cleanly `MERGEABLE`, no rebase needed unless you want one)
**Files:** `pb_figured_dimension_evidence.py`, `tests/test_figured_dimension_line_fragment_merge_v1.py` only.
**Status:** Draft, open, CI green — confirmed via `gh pr checks 890`:
```
fastpath (3.13)  pass
fastpath (3.14)  pass
test (3.13)      pass
test (3.14)      pass
```
(This is the authoritative full-suite result — a local `PYTHONPATH=. pytest -q tests/` run I also kicked off never finished in this session; trust the GitHub Actions result above, not that stalled local process if you find it still listed.)

**What it fixes:** `bind_observation_to_vector_geometry` classified a figured dimension as `AMBIGUOUS` whenever two candidate dimension-line segments were spatially indistinguishable. A very common CAD export convention breaks one visual dimension line into two collinear vector fragments where the figured-dimension text sits directly on top of it. This treated the two halves as competing lines and discarded real evidence. Added a narrow pre-ambiguity merge: same orientation, same axis coordinate, gap bracketing *only this observation's own* text — never touches distant/overlapping/different-axis/different-orientation candidates (14 synthetic tests enforce this).

**Real effect:** KSTVET p54 witness-bound dimensions 36→63 (ambiguous 55→25). Ghazi p167 unaffected (near-zero vector geometry there). No benchmark values used to design or validate it.

**Next step:** your merge decision. Nothing blocks it structurally.

---

## 2. Preserved, NOT for merge yet — F.23 secondary-footprint fix

**Branch:** `investigate/lamu-dpc-residual-v1`
**Commit:** `75c5302f9deffed1a78f05a1a45f6564981b3efa`
**Base:** `main` @ `7a498ef`
**File:** `pb_secondary_footprint_evidence.py` only.
**Status:** Committed, pushed. **Depends on PR #890** — on its own, current main's dimension binding still returns `AMBIGUOUS` for the real Lamu veranda-depth chain, so this branch alone resolves nothing live.

**What it does (correctly, per your explicit approval earlier in this session):** replaces `_spatially_associated_with_edge` (required the dimension caption text to sit near the secondary-space label along the edge, and inside the viewport's own strict frame bbox) with `_witnesses_bracket_edge_strip` (requires the dimension's own witness endpoints — not the caption text — to bracket the secondary strip: one endpoint at the viewport's outer edge, the other a genuine interior boundary not itself at the opposite edge). Once PR #890 is merged, this correctly resolves Lamu's real veranda depth to `width_m=1.5`.

**Why it's held back — do not merge without also addressing §3 below:** once the veranda width resolves, `MultiSpaceFootprintBuilder`'s main room still uses `_detect_outer_envelope`'s width=8.2m (the *compound* overall depth, not the primary room's own ~6.5–6.7m enclosed depth). With the verandah component now also resolving, its floor area gets double-counted — once already baked into the inflated main room, once again as its own component. `external_perimeter_m` goes 48.4→51.4m, `gross_floor_area_m2` goes 131.2→155.2 m² (true value closer to ~128 m²). Merging this fix alone would make Lamu's DPC/floor-area accuracy *worse*, not better.

**Next step:** merge only together with, or after, a fix to the main-room-vs-compound-depth conflation in `_detect_outer_envelope`/`MultiSpaceFootprintBuilder` (see §3 — that fix does not yet exist).

---

## 3. Preserved, NOT for merge yet — compound-span decomposition evidence (shadow)

**Branch:** `investigate/footprint-envelope-decomposition-v1`
**Commit:** `83bf6a71a1822d551330dd3fd04ca216ee44eee9`
**Base:** `main` @ `7a498ef`
**Files:** new `pb_compound_span_evidence.py`, new `tests/test_compound_span_evidence_v1.py`.
**Status:** Committed, pushed. **Shadow only — not imported by any live extraction path.** Does not alter floor area, perimeter, wall geometry, or DPC publication in any way.

**What it is:** a generic authority that proves whether a large "overall" figured dimension is a compound span composed of a contiguous run of smaller witness-bound members (e.g. primary-room depth + secondary-strip depth), using only witness-endpoint continuity + an independent value-sum cross-check (5% relative tolerance) — never picking a decomposition because a term is round, small, or convenient. Assigns descriptive-only roles (`PRIMARY_ENCLOSED`, `SECONDARY_STRIP`, `BOUNDARY_THICKNESS`, `UNCLASSIFIED_MEMBER`) that carry no wall/DPC authority (structurally verified by its own test). 17 synthetic tests pass, all arbitrary values.

**Real validation:**
- **Lamu p41:** finds the real run [6100mm, 1500mm] and the real overall [8200mm] with matching endpoints on both ends of the run's own bracket, but correctly **ABSTAINS** (`member_sum_does_not_match_overall_value`, 7600 vs 8200, 7.3% error). This is the honest, final result for this page — see §4, "disproven."
- **KSTVET p54:** `CONFLICT` on both axes (multiple plausible decompositions on this dense multi-room sheet) — an honest fail-closed outcome, not a false positive.
- **Ghazi p167:** `ABSTAINED` (insufficient witness-bound members) — expected, near-zero vector geometry.
- **Murera:** not run — raster-only evidence, out of scope for a module that only consumes vector dimension geometry.

**Next step:** none currently planned. This module is a real, tested, useful piece of shadow infrastructure, but has no live consumer and no further work is queued against it — it sits ready if a future task needs compound-span proof for some other project/page.

---

## 4. Disproven / closed — do not re-attempt without new evidence

**The "boundary-thickness binding gap" I described in my previous report was wrong. I retract it.**

I had claimed the residual 600mm gap (8200 − 7600) between Lamu's proven run and its overall dimension was explained by three separate 200mm boundary-thickness figures that just needed better dimension-line binding. On closer inspection of the *real* witness endpoints (not just the text values):

```
overall (8200mm):  110.08 -----------------------------------> 339.76
6100mm:             110.08 --------------------------> 288.76
1500mm:                                        288.76 --> 336.88
```

- 6100's start is **exactly** the overall's own start (zero gap).
- 6100's end is **exactly** 1500's start (zero gap).
- The only real residual is 339.76 − 336.88 = 2.88pt ≈ **98mm** — not 600mm, and not split three ways.

I had also visually confirmed the three "200" marks aren't dimension lines at all — they're text sitting beside a horizontal step/jog connector between two parallel offset dimension tracks (the outer 8200 line and inner 6100/1500 line). I measured that jog's actual length (23.28pt) against the page's real scale (29.29pt/m): 200mm should render as ~5.86pt. It doesn't match — **the jog's geometric length carries no relationship to the value written next to it.** It's a fixed drafting offset, not a scaled measurement. There is no witness-bound geometry for these three "200" values to bind to, because none was ever drawn.

**Conclusion:** the compound-span module's `ABSTAIN` on Lamu is correct and, on current evidence, final for this drawing. There is nothing here for a dimension-binding fix to recover — the missing geometry genuinely doesn't exist in the source. Building a "text-asserted gap-filler" mechanism to force a match would manufacture a result the geometry doesn't support. **Do not reopen this specific sub-question without new source evidence** (e.g., a higher-resolution scan, a different revision, or a second corroborating sheet) — re-deriving the above from scratch would waste a full investigation cycle for the same negative result.

I started a branch for this (`fix/boundary-thickness-dimension-binding-v1`) and deleted it — it never got past investigation, nothing was committed, there is nothing to recover there.

---

## 5. LMU-E3-B (Lamu DPC) — overall status

**Not resolved.** Current live output (54.5 LM) is fully traced and understood (see git history / prior session transcript for the exact 48.4+6.1 derivation). Whether it can become more accurate depends on fixing the main-room-vs-compound-depth conflation (§2/§3) — and even then, per §4, the Lamu page's own source evidence may not support a materially different number for the specific 200mm boundary members. **Recommended next step if this lane reopens:** design the `_detect_outer_envelope`/`MultiSpaceFootprintBuilder` fix using `pb_compound_span_evidence.py` (§3) as the proof source, decide how the model should represent "primary component proven, secondary component proven, overall only 93% corroborated" (a case the current module doesn't yet have an explicit answer for — right now it just abstains), then re-run DPC only after that's settled. Do not compute 75.0 − 54.5 or search for a matching wall run — that was explicitly forbidden earlier in this lane and remains forbidden.

---

## 6. Other branches touched this session, no code produced

- `investigate/kstvet-window-instance-counts-v1` — pure investigation, no commits beyond its base (`70ad47a`). Conclusion: type/deduplication/cross-view-identity blockers documented in-conversation; correct current behavior is abstain (verified zero window/door predictions currently publish, zero hallucination).
- `investigate/ghazi-gable-walling-v1` — pure investigation, no commits beyond its base (`ec0423d`). Conclusion: `GZ-E3-D = SOURCE_BLOCKED_MISSING_DRAWING_SHEETS`, confirmed via a real, documented public-source search (tenders.go.ke, NG-CDF Voi site) that found no additional drawing sheets. Do not re-search without a new source lead.

---

## 7. Test/CI status summary

| Branch / PR | Local targeted tests | GitHub Actions CI |
|---|---|---|
| PR #552 (`claude/item35-pr3-additional-test-coverage-v1`) | 176 passed (targeted) + 296 passed (broader sweep) | **Green, MERGED** — `test` + `fastpath`, both 3.13/3.14 |
| `fix/dimension-line-fragment-merge-v1` (PR #890) | 220+ passed (dimension/wall-span/opening-binding/F.23 sweep) | **Green** — `test` + `fastpath`, both Python 3.13/3.14 (confirmed via `gh pr checks 890`) |
| `investigate/lamu-dpc-residual-v1` | 70 passed (F.23 + merge-fix + mutation suites, tested together with PR #890's fix temporarily applied) | Not opened as a PR, no CI run |
| `investigate/footprint-envelope-decomposition-v1` | 17/17 new tests + 119 passed regression sweep | Not opened as a PR, no CI run |

No benchmark gold, mappings, scorer, tolerances, denominator, or source hashes were touched by any of this work. No live extraction path currently imports `pb_compound_span_evidence.py`, and `pb_secondary_footprint_evidence.py`'s change is not live until PR #890 merges.

---

## 8. Untracked file note

`CURSOR_HANDOFF_SCHEDULE_PARSING.md` exists untracked at repo root on every branch I touched this session — it predates this work, is not mine, and I left it alone throughout. Not part of this handoff.
