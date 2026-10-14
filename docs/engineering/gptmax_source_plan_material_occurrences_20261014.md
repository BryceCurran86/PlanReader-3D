# Source-owned plan material occurrence consumption

## Observed repository behavior

Read AGENTS.md, AI_ENGINEERING_PLAYBOOK.md and its topology, benchmark and CI
references. Traced SourceMaterialSemanticProducer.publish through
_trusted_words_by_page, native schedule cluster authentication,
segment_page_viewports, _viewport_is_authoritative,
_recover_admissible_viewport_words, _trusted_lines_for_viewport and occurrence
record construction. Traced CrossViewFloorFinishProducer's material consumer:
it requires CORROBORATED and scope_complete before a physical floor grant.

Merged #2716's segment_source_page_viewports authenticates bounded source-owned
plans, but the material producer still calls the ordinary page-only segmenter.
Its current drawing path discards all records when any intersecting source word
is untrusted or crosses the viewport. Scope completeness is correctly strict;
discarding independently proven marks prevents useful partial-source handoff.

Independently downloaded #2716 artifact 11887756581, producer head 4aea189,
and verified its ZIP digest and both original PDF hashes. Both original views
have positive F.07 migration ownership, unchanged snapshots/default behavior,
whole-sheet completeness FALSE, metric authority FALSE and no quantities.

## Inference

The next seam is source-owned view consumption and individually authenticated
material marks, not physical room matching. A bounded plan and one proven mark
cannot close the whole sheet or an unreadable text universe. An incomplete
scope must remain ABSTAINED even when it retains positive individual records.

## Proposed change

Add a separate SourceMaterialSemanticProducer.for_physical_plan_view_shadow
factory with explicit source page IDs. Keep the ordinary factory and schedule
authentication unchanged. Generate the views internally from the actual source
producer, then require the existing F.07 migration ownership boundary against
its exact document/revision/SHA/snapshot.

Once the unchanged schedule dictionary is authenticated, nominate only exact
native lines containing dictionary codes. Every word in a nominated original
line must authenticate, lie wholly inside the view, and retain its original
source partition/block/line/word identity. Untrusted words use the fixed
original 300/450-DPI source/glyph proof from #2716. No OCR corrections, retries,
nearby label assignment, caller viewport, fabricated schedule or raw JSON
receipt may supply authority.

Retain positive records and unresolved source observation IDs in an ABSTAINED,
scope_complete=False result when any original intersecting text remains
untrusted, a line crosses the boundary, or a relevant definition conflicts.
The existing cross-view consumer must continue rejecting that incomplete
scope. A complete result means only the selected bounded viewport.

## Review and expected abstentions

Review the source ownership, partial-line and definition-conflict boundaries
before implementation; synthetic positives, negatives and immutable original
replays follow. The user's continuation authorizes completing this isolated
shadow seam and review. Commercial activation is outside this change.

Absent/competing/stale/foreign views, hidden or contradictory mark text,
partial native lines and unconfirmed definitions produce no occurrence grant.
Partial scope retains only independently proven complete lines. Serialized
diagnostics are evidence for review, never in-process authority seals.

## Benchmark observations excluded from implementation

Original PDF names/hashes/pages and material-mark counts are replay inputs and
assertions only. They cannot select marks, drawing extents or thresholds.
No benchmark truth, expected quantities, floor names or scoreboard inputs enter
the producer. Frozen sources/evaluator/denominators/tolerances, global snap,
20,000 safety cap, W10 eligibility, scale/measurement, physical room identity,
existing source snapshots and all commercial writers remain untouched.

## Implemented authority review

The explicit shadow factory generates its own views and obtains the existing
F.07 ownership proof against exact source lineage. Occurrence records retain
original observation IDs plus actual fixed-source OCR record IDs when needed;
scope results retain migration ownership and unresolved source IDs. These are
optional audit fields, with unchanged defaults and existing stable IDs in the
ordinary producer. No caller geometry or OCR claim enters the factory.

The native-line reader groups by source partition/block/line, requires every
original word ordinal from zero, and rejects the whole line if any word is
untrusted or outside the view. It cannot publish a readable code fragment from
an otherwise unresolved source line. Independently resolved definitions and
marks survive unrelated unknown text, while their universe remains ABSTAINED.
Conflicting definitions never supply marks.

28 new source-PDF tests and 177 existing authority/floor-seal/publication tests
pass. Controls include actual hidden/occluded source paint, boundary-crossing
lines, competing incomplete view families, copied/foreign/stale products,
definition conflicts, translation/90-degree rotation/scaling, split/input-order
and page-expansion controls, stable replay and unchanged definitions/snapshots.
The real existing floor consumer rejects retained incomplete scopes. Provider
isolation, frozen V2 integrity, compilation and undefined-name checks pass.

Original replays use tools/diag_source_plan_material_occurrences.py and the
dedicated exact-head CI workflow. SHA/count assertions live only in validation;
the producer never reads them. Lot16's original page-3 proof consumes one view,
retains 36 unresolved source IDs and grants no material mark or complete scope.
The full source receipts are retained as CI review artifacts.

## Original replay: FT3 definition remains blocked

The first exact-head artifact 11901536438 correctly withheld FT3 semantic
occurrences while retaining all five exact original 300/450-DPI FT3 text
proofs. Three independently authenticated WA02/WA05 material occurrences
survive in an ABSTAINED, incomplete scope with 190 unresolved source IDs.

Only 21/24 original words in FT3 definition block 262 authenticate. The dash,
`“DURA` and `GREY”` remain unresolved. At 450/600 DPI the original whole-line
OCR fragments spell straight quotation marks; 600-DPI line detection also
omits the dash. No punctuation deletion, quote substitution, alternate engine
or benchmark assumption may turn that into a complete definition.

The default rawdict block profile also points published block 262 at FT2;
TEXTFLAGS_WORDS correctly locates FT3. A source-only diagnostic using the
correct profile still authenticates 21/24 words. That index observation does
not close the literal text disagreement, so no crop/profile/definition
authority change is included in this PR.

The replay now observes every real native-block recovery, returning its exact
unmodified result and restoring the observer on failure. It retains failed
word IDs, source partition/block/line/word ownership and exact unchanged
definition results. CI requires the five positive FT3 word proofs and checks
that semantic marks depend on an actually authenticated complete definition.
The next FT3 gate is original-source punctuation/glyph text ownership, followed
by closed physical room ownership; both remain independent of this consumer.
