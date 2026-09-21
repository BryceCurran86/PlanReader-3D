# PlanReader-3D Accuracy-22 Temporary Evidence Ledger

> Diagnostic development ledger only. This file is **not** benchmark gold, scoring logic, report generation, or an acceptance source. Only the repaired canonical benchmark may mark an item RECOVERED.

Allowed item states in this ledger:
- FIX IMPLEMENTED — AWAITING CANONICAL VALIDATION
- ROOT CAUSE FOUND
- INVESTIGATING
- BLOCKED

## Running summary

- Production benchmark/scoring/gold/report code touched by this workstream: **none**
- Generic schedule split-row fix: draft PR #602, full CI + Performance Fastpath green
- Source-authenticated explicit aperture-tag relation bridge: draft PR #603, full CI + Performance Fastpath green
- OCR tag -> source snapshot -> existing schedule binder handoff: draft PR #605, full CI + Performance Fastpath green
- Live Item35 classified-count composition remains shadow-only: draft PR #610, CI in progress at ledger creation
- No item below is marked RECOVERED.

---

## 1. LMU-E3-A

ITEM: LMU-E3-A  
EXPECTED: 136 SM natural-stone walling.  
CURRENT OUTPUT: Historical committed report: 135.52 SM; later fail-closed host-binding work removed the heuristic opening-to-wall shortcut that had made this near-pass possible, so current publishability requires revalidation.  
SOURCE EVIDENCE: Lamu page 41 floor plan/elevations; wall envelope plus openings/deductions.  
FIRST PIPELINE FAILURE: Authenticated opening-to-wall host binding / net-wall deduction publication, not a BOQ-row problem.  
ROOT CAUSE: Prior acceptable number depended on a heuristic single-wall shortcut; after integrity hardening the deduction path correctly abstains without authenticated host binding.  
FIX: Reuse source-authenticated opening identity/host-binding work; do not reinstate single-wall or bbox-overlap shortcuts.  
TESTS ADDED: Existing authenticated host-binding/deduction regressions plus Item35 opening authority work; item-specific recovery test pending.  
TEST RESULT: Underlying authority suites green; row not canonically validated.  
EXPECTED BENCHMARK IMPACT: Potential restoration of the prior near-pass once host binding is genuinely proven.  
COMMIT/BRANCH: Item35/OCR work: PRs #603/#605/#610.  
STATUS: ROOT CAUSE FOUND

## 2. LMU-E3-C

ITEM: LMU-E3-C  
EXPECTED: 132 SM 1000-gauge polythene DPM.  
CURRENT OUTPUT: Older committed report: absent.  
SOURCE EVIDENCE: Lamu page 41 floor/slab footprint plus explicit DPM specification.  
FIRST PIPELINE FAILURE: DPM specification/footprint association does not produce the commercial DPM row for this source.  
ROOT CAUSE: Exact first loss still requires page-level trace; this is a slab-area/specification lane, not opening/schedule identity.  
FIX: Trace explicit DPM note -> authoritative floor/footprint area -> slab-bound quantity publication with no default multiplier.  
TESTS ADDED: Pending focused Lamu-neutral DPM scope/mutation fixture.  
TEST RESULT: Pending.  
EXPECTED BENCHMARK IMPACT: One row if explicit DPM scope binds to the existing evidenced floor area.  
COMMIT/BRANCH: Pending.  
STATUS: INVESTIGATING

## 3. LMU-E4-A

ITEM: LMU-E4-A  
EXPECTED: 172 SM prepainted GCI roof covering.  
CURRENT OUTPUT: Older committed report: absent.  
SOURCE EVIDENCE: Lamu page 41 plan/elevations/section; roof geometry and roof-covering specification.  
FIRST PIPELINE FAILURE: No live generic roof-covering quantity is published for this source.  
ROOT CAUSE: Roof-covering area support is incomplete in the live extractor; this is not a schedule-row problem.  
FIX: Bind authenticated roof plan/elevation geometry, slope/pitch and explicit roof finish to a roof-surface area; fail closed if pitch/slope extent is absent.  
TESTS ADDED: Pending roof-area mutation/invariance tests.  
TEST RESULT: Pending.  
EXPECTED BENCHMARK IMPACT: One row.  
COMMIT/BRANCH: Pending.  
STATUS: ROOT CAUSE FOUND

## 4. LMU-E7-A

ITEM: LMU-E7-A  
EXPECTED: 268 SM internal wall plaster.  
CURRENT OUTPUT: Older committed report: absent.  
SOURCE EVIDENCE: Lamu page 41 wall geometry, wall height, openings and plaster finish text.  
FIRST PIPELINE FAILURE: Wall-face/net-area authority does not provide a publishable finish extent.  
ROOT CAUSE: Same wall/opening/finish binding family as LMU-E3-A, not door-swing detection by itself.  
FIX: Complete authenticated net wall face + finish assignment, then propagate the same proven finish extent to plaster.  
TESTS ADDED: Pending cluster regression with LMU-E7-C.  
TEST RESULT: Pending.  
EXPECTED BENCHMARK IMPACT: Likely paired with LMU-E7-C.  
COMMIT/BRANCH: Pending.  
STATUS: ROOT CAUSE FOUND

## 5. LMU-E7-C

ITEM: LMU-E7-C  
EXPECTED: 268 SM wall paint.  
CURRENT OUTPUT: Older committed report: absent.  
SOURCE EVIDENCE: Same plastered wall faces as LMU-E7-A plus explicit paint finish.  
FIRST PIPELINE FAILURE: No publishable finish-face extent reaches paint output.  
ROOT CAUSE: Shared with LMU-E7-A.  
FIX: Reuse the proven plastered-wall face extent; paint may inherit area only after same-scope finish assignment is proven.  
TESTS ADDED: Pending paired finish-propagation regression.  
TEST RESULT: Pending.  
EXPECTED BENCHMARK IMPACT: Likely paired with LMU-E7-A.  
COMMIT/BRANCH: Pending.  
STATUS: ROOT CAUSE FOUND

## 6. masonry_piers — Murera

ITEM: masonry_piers  
EXPECTED: 13 NO, 300 x 300 mm masonry piers.  
CURRENT OUTPUT: Older committed report: absent.  
SOURCE EVIDENCE: Murera foundation/section raster-heavy drawing evidence.  
FIRST PIPELINE FAILURE: Fine structural pier primitives/instances are not published into a count authority.  
ROOT CAUSE: Raster-heavy structural-instance recognition remains incomplete; text-only explicit-count regex is insufficient.  
FIX: Use authenticated raster primitive observations -> pier candidate grouping/classification -> unique physical-instance count.  
TESTS ADDED: Pending raster pier symbol mutation/grouping fixture.  
TEST RESULT: Pending.  
EXPECTED BENCHMARK IMPACT: One row.  
COMMIT/BRANCH: Pending.  
STATUS: INVESTIGATING

## 7. steel_casement_windows — Murera

ITEM: steel_casement_windows  
EXPECTED: 12 NO.  
CURRENT OUTPUT: Older committed report: absent; OCR/tag evidence has partial recovery but no validated commercial total.  
SOURCE EVIDENCE: Murera scanned plan/schedule, OCR W/D marks, source-proven physical openings and schedule text.  
FIRST PIPELINE FAILURE: Authenticated OCR tags previously stopped before the existing schedule-opening binding authority.  
ROOT CAUSE: OCR tag observations were outside the schedule binder's producer-owned text universe; live Item35 also lacked classified-count composition.  
FIX: PR #605 hands producer-owned OCR tags into the same immutable source snapshot and existing aperture/schedule binder. PR #610 composes classified family/mark counts in live Item35 shadow, still without commercial publication.  
TESTS ADDED: OCR-in-aperture binding, outside-aperture abstention, duplicate native/OCR same-mark dedupe, competing-mark conflict, API injection guard; live classified-count shadow integration.  
TEST RESULT: PR #605 full CI + Performance Fastpath green. PR #610 pending at ledger creation.  
EXPECTED BENCHMARK IMPACT: Removes a principal evidence-loss seam; commercial row still requires real-source classified count and reviewed publication.  
COMMIT/BRANCH: PR #605 `gpt/accuracy22-ocr-tags-into-schedule-binding-v1`; PR #610 `gpt/accuracy22-item35-live-classified-count-shadow-v1`.  
STATUS: ROOT CAUSE FOUND

## 8. doors_complete — Murera

ITEM: doors_complete  
EXPECTED: 5 NO.  
CURRENT OUTPUT: Older committed report: absent; partial OCR/evidence progress exists.  
SOURCE EVIDENCE: Murera scanned plan/door schedule, OCR D-marks, physical door openings.  
FIRST PIPELINE FAILURE: Same authenticated OCR-tag -> aperture -> schedule-binding/live-classification seam as windows, plus door physical-path coverage on raster geometry.  
ROOT CAUSE: Typed classification was not composed live; some raster doors may also lack a sufficiently proven aperture path.  
FIX: PR #605/#610 for tag/binding composition; extend only genuinely evidenced alternate door existence paths if real-source diagnostics show missing apertures.  
TESTS ADDED: Same OCR/schedule binding tests; door-specific real-source regression pending.  
TEST RESULT: Shared authority tests green; row not canonically validated.  
EXPECTED BENCHMARK IMPACT: Could recover with steel_casement_windows if all five physical members classify.  
COMMIT/BRANCH: PR #605/#610.  
STATUS: ROOT CAUSE FOUND

## 9. GZ-E3-B

ITEM: GZ-E3-B  
EXPECTED: 109 SM external coral-block walling.  
CURRENT OUTPUT: Committed report: 135.24 SM, 24.07% high.  
SOURCE EVIDENCE: Ghazi page 167 is raster/scanned for meaningful wall geometry; prior vector candidates were page furniture/legend, not walls.  
FIRST PIPELINE FAILURE: Live extractor does not compose the merged authenticated raster wall-network / wall-role / wall-geometry authority stack.  
ROOT CAUSE: Existing Item 25/28 raster-wall and wall/finish recovery authorities are not imported or wired by GenericPlanReaderExtractor.  
FIX: Build source-bound live/shadow composition from raster wall observations -> scale -> physical wall candidates -> roles -> gross/net wall geometry, then review publication.  
TESTS ADDED: Existing Item25/28 authority suites; live real-source adapter test pending.  
TEST RESULT: Authority suites green; no live recovery.  
EXPECTED BENCHMARK IMPACT: Correct external wall geometry could move GZ-E3-B and unlock related finish rows.  
COMMIT/BRANCH: Existing merged Item25/28; live wiring pending.  
STATUS: ROOT CAUSE FOUND

## 10. GZ-E3-C

ITEM: GZ-E3-C  
EXPECTED: 41 SM internal coral-block walling.  
CURRENT OUTPUT: Committed report: absent.  
SOURCE EVIDENCE: Ghazi raster wall network and room/internal-wall topology.  
FIRST PIPELINE FAILURE: No live authenticated internal wall-role/length/height composition.  
ROOT CAUSE: Same raster wall authority wiring gap as GZ-E3-B, with additional internal/external role classification requirement.  
FIX: Compose raster wall network -> physical wall identity -> internal role -> gross/net area.  
TESTS ADDED: Existing wall-role/Item28 tests; real-source integration pending.  
TEST RESULT: Pending.  
EXPECTED BENCHMARK IMPACT: One wall row and prerequisite for internal finishes.  
COMMIT/BRANCH: Pending live adapter.  
STATUS: ROOT CAUSE FOUND

## 11. GZ-E3-D

ITEM: GZ-E3-D  
EXPECTED: 12 SM gable walling.  
CURRENT OUTPUT: Committed report: absent.  
SOURCE EVIDENCE: Ghazi source package contains only drawing sheet 1 of 3; elevation/section sheets referenced by title block are not present in the registered document.  
FIRST PIPELINE FAILURE: Required gable vertical/pitch evidence is absent from the available source package or not independently proven.  
ROOT CAUSE: Potential genuine source-evidence limitation, not schedule binding.  
FIX: Search available page for explicit roof pitch/gable-height evidence; if absent, remain fail-closed. Do not infer from benchmark quantity.  
TESTS ADDED: Pending source-evidence trace.  
TEST RESULT: Pending.  
EXPECTED BENCHMARK IMPACT: May remain BLOCKED if the registered source genuinely lacks required vertical evidence.  
COMMIT/BRANCH: Pending.  
STATUS: INVESTIGATING

## 12. GZ-E8-A

ITEM: GZ-E8-A  
EXPECTED: 203 SM internal plaster.  
CURRENT OUTPUT: Committed report: absent.  
SOURCE EVIDENCE: Ghazi internal wall faces + explicit plaster finish.  
FIRST PIPELINE FAILURE: Live extractor never reaches the merged Item28 wall/finish recovery stack.  
ROOT CAUSE: Raster internal wall-role/net-area plus finish assignment not composed live.  
FIX: Same live raster-wall adapter as GZ-E3-C, then producer-owned finish propagation.  
TESTS ADDED: Existing Item28 and WallFinishPropagation suites; live integration pending.  
TEST RESULT: Pending.  
EXPECTED BENCHMARK IMPACT: Likely paired with GZ-E8-C once internal face extent resolves.  
COMMIT/BRANCH: Pending.  
STATUS: ROOT CAUSE FOUND

## 13. GZ-E8-C

ITEM: GZ-E8-C  
EXPECTED: 203 SM internal paint.  
CURRENT OUTPUT: Committed report: absent.  
SOURCE EVIDENCE: Same plastered internal wall faces as GZ-E8-A plus paint specification.  
FIRST PIPELINE FAILURE: Same live wall/finish composition gap.  
ROOT CAUSE: Shared with GZ-E8-A.  
FIX: Paint inherits only the same producer-proven plastered wall face extent after explicit same-scope finish assignment.  
TESTS ADDED: Pending paired finish-propagation integration.  
TEST RESULT: Pending.  
EXPECTED BENCHMARK IMPACT: Likely paired with GZ-E8-A.  
COMMIT/BRANCH: Pending.  
STATUS: ROOT CAUSE FOUND

## 14. GZ-E8-H

ITEM: GZ-E8-H  
EXPECTED: 160 SM chipboard ceiling lining.  
CURRENT OUTPUT: Committed report: absent.  
SOURCE EVIDENCE: Explicit ceiling-lining evidence plus authoritative floor/room/footprint area.  
FIRST PIPELINE FAILURE: Ceiling-lining quantity/provider exists only in shadow and its authenticated room-topology/finish-scope seam is not live.  
ROOT CAUSE: Existing ceiling-lining modules are not commercially wired; raster/OCR finish scope may also require authenticated semantic corroboration.  
FIX: Complete producer-owned room/topology scope binding and same-scope ceiling finish -> authoritative area reuse; no raw floor-area copying without scope proof.  
TESTS ADDED: Existing ceiling lining shadow/quantity tests; live adapter pending.  
TEST RESULT: Shadow suites exist; commercial output absent.  
EXPECTED BENCHMARK IMPACT: One row if same-scope finish + area resolves.  
COMMIT/BRANCH: Pending.  
STATUS: ROOT CAUSE FOUND

## 15. BOQ-C36-A

ITEM: BOQ-C36-A  
EXPECTED: 58 SM concrete block walling.  
CURRENT OUTPUT: Latest recovered real-source KSTVET artifact: matched production tag but quantity is null/blocked; older committed report had 103.6 SM gross mismatch.  
SOURCE EVIDENCE: Page 54 wall geometry plus opening deductions.  
FIRST PIPELINE FAILURE: Authenticated opening-to-wall host/deduction chain blocks publishable net wall quantity.  
ROOT CAUSE: Same net-wall/opening deduction authority gap as KSTVET C46-A/C.  
FIX: Complete physical opening classification and authenticated host binding; do not restore whole-wall heuristic.  
TESTS ADDED: Item35 OCR/tag/binding work plus existing net-wall fail-closed tests.  
TEST RESULT: Opening authority pieces green; row still awaiting live/canonical validation.  
EXPECTED BENCHMARK IMPACT: Could recover C36-A and improve C46-A/C together.  
COMMIT/BRANCH: PR #603/#605/#610 plus future host-binding integration.  
STATUS: ROOT CAUSE FOUND

## 16. BOQ-C41-B

ITEM: BOQ-C41-B  
EXPECTED: 2 NO, 3000 x 1200 steel casement window.  
CURRENT OUTPUT: Latest real-source artifact: absent.  
SOURCE EVIDENCE: Page 54 opening schedule/drawing evidence. Historical F24 trace found W1/W2 identities were not available in native text, so dimensions alone cannot mint identities.  
FIRST PIPELINE FAILURE: Explicit window identity is absent from the native text path; split logical-row association is also a generic weakness.  
ROOT CAUSE: Identity evidence must come from authenticated raster/OCR or other explicit source mark, then bind to schedule quantity/geometry.  
FIX: PR #602 adds generic stacked logical-row reconciliation; PR #605 enables authenticated OCR tag handoff. Neither dimensions-only inference nor project-specific W1 constants are allowed.  
TESTS ADDED: Six stacked-row regressions; OCR schedule-binding regressions.  
TEST RESULT: PR #602 and #605 full CI + Performance Fastpath green.  
EXPECTED BENCHMARK IMPACT: Probable only if real-source OCR produces the missing explicit identity and existing schedule row is unique.  
COMMIT/BRANCH: PR #602; PR #605.  
STATUS: ROOT CAUSE FOUND

## 17. BOQ-C41-C

ITEM: BOQ-C41-C  
EXPECTED: 3 NO, 2900 x 1200 steel casement window.  
CURRENT OUTPUT: Latest real-source artifact: absent.  
SOURCE EVIDENCE: Same schedule/drawing authority path as C41-B.  
FIRST PIPELINE FAILURE: Same explicit-identity/OCR + logical-row binding family as C41-B.  
ROOT CAUSE: Shared with C41-B.  
FIX: PR #602 + PR #605; fail closed on competing identities/rows.  
TESTS ADDED: Shared stacked-row and OCR-binding regressions.  
TEST RESULT: Green.  
EXPECTED BENCHMARK IMPACT: Could recover with C41-B if explicit source tags are recovered.  
COMMIT/BRANCH: PR #602; PR #605.  
STATUS: ROOT CAUSE FOUND

## 18. BOQ-C46-A

ITEM: BOQ-C46-A  
EXPECTED: 69 SM internal plaster.  
CURRENT OUTPUT: Latest real-source artifact: matched tag but quantity null/blocked; older report had 100.24 SM gross mismatch.  
SOURCE EVIDENCE: Internal wall faces, openings, wall height/thickness and plaster finish.  
FIRST PIPELINE FAILURE: Net internal wall face/opening deduction is unresolved after fail-closed host-binding hardening.  
ROOT CAUSE: Not BOQ continuation-row classification. It is the wall/opening/finish extent authority.  
FIX: Complete authenticated opening host binding and independent internal-face extent; plaster propagates from that net face.  
TESTS ADDED: Existing wall/opening deduction tests; targeted real-source regression pending.  
TEST RESULT: Pending canonical validation.  
EXPECTED BENCHMARK IMPACT: Likely paired with C46-C and C36-A.  
COMMIT/BRANCH: Opening authority work PR #603/#605/#610; host-binding work pending.  
STATUS: ROOT CAUSE FOUND

## 19. BOQ-C46-C

ITEM: BOQ-C46-C  
EXPECTED: 69 SM internal paint.  
CURRENT OUTPUT: Latest real-source artifact: matched tag but quantity null/blocked; older report had 100.24 SM.  
SOURCE EVIDENCE: Same internal plastered faces plus paint finish.  
FIRST PIPELINE FAILURE: Same unresolved net internal wall face as C46-A.  
ROOT CAUSE: Shared with C46-A.  
FIX: Reuse the producer-proven internal plaster face extent; no independent area guess for paint.  
TESTS ADDED: Pending paired finish propagation regression.  
TEST RESULT: Pending.  
EXPECTED BENCHMARK IMPACT: Likely paired with C46-A.  
COMMIT/BRANCH: Pending host-binding completion.  
STATUS: ROOT CAUSE FOUND

## 20. BOQ-C47-A

ITEM: BOQ-C47-A  
EXPECTED: 60 SM key pointing externally.  
CURRENT OUTPUT: Latest real-source artifact: absent. Older report incorrectly copied 103.6 SM whole wall area.  
SOURCE EVIDENCE: Key-pointing specification plus only the external masonry faces to which the finish actually applies.  
FIRST PIPELINE FAILURE: Finish specification is detected, but no producer-owned finish->face extent exists.  
ROOT CAUSE: The previously fixed defect was over-publication: page-wide keyword incorrectly inherited the whole wall area. Current fail-closed absence is correct until face scope is proven.  
FIX: Build explicit external finish-to-face binding and measured extent; never restore wall-area copying.  
TESTS ADDED: Existing regression locks out the unsafe copy; positive binding tests pending.  
TEST RESULT: Safety fix effective; benchmark recovery unproven.  
EXPECTED BENCHMARK IMPACT: One row when finish-face extent resolves.  
COMMIT/BRANCH: Prior key-pointing safety fix on main; positive authority pending.  
STATUS: ROOT CAUSE FOUND

## 21. BOQ-C47-B

ITEM: BOQ-C47-B  
EXPECTED: 20 SM external plaster to walls/beams/columns.  
CURRENT OUTPUT: Latest real-source artifact: absent.  
SOURCE EVIDENCE: External plaster specification plus a subset of external walls/beams/columns.  
FIRST PIPELINE FAILURE: No live producer-owned external plaster finish/face scope and aggregate extent.  
ROOT CAUSE: Distinct from C47-A even if both need finish->face binding; beam/column scope may add non-wall surfaces.  
FIX: Resolve explicit finish scope to authenticated wall/beam/column surface instances; aggregate only resolved members.  
TESTS ADDED: Pending.  
TEST RESULT: Pending.  
EXPECTED BENCHMARK IMPACT: One row.  
COMMIT/BRANCH: Pending.  
STATUS: INVESTIGATING

## 22. BOQ-C47-D

ITEM: BOQ-C47-D  
EXPECTED: 4 NO verandah CHS pillars.  
CURRENT OUTPUT: Latest real-source artifact: absent.  
SOURCE EVIDENCE: Verandah/support specification and physical support instances.  
FIRST PIPELINE FAILURE: Existing repeated-bay support authority abstains on this real source because no trustworthy unique repeated-bay chain was proven; explicit-text count path also does not fire.  
ROOT CAUSE: A different physical support-instance/count path is required; relabeling bay-count heuristics would be unsafe.  
FIX: Trace raster/vector repeated support symbols, support labels and geometry grouping; count only unique authenticated support instances.  
TESTS ADDED: Existing bay-count abstention tests; physical support-symbol tests pending.  
TEST RESULT: Current generic bay path correctly abstains.  
EXPECTED BENCHMARK IMPACT: One row.  
COMMIT/BRANCH: Pending.  
STATUS: ROOT CAUSE FOUND
