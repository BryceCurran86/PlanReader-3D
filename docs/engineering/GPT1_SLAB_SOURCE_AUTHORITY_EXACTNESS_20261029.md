# Slab canonical source and metric-authority receipt exactness

Base inspected: `f36d67ecf7f0efa22575ca23b0143488a157c034`.
Coordination: #3462, claim 6477429010. GPT1 quantity lane.

## Observed repository behavior

Read `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, its W1-W10 topology,
wall/room specification, benchmark-firewall and CI references, and the shared
accuracy-levers instructions. Traced F.21 in
`GenericPlanReaderExtractor.extract_from_pdf`: the existing confirmed footprint
is supplied to `resolve_slabs_from_page` / `resolve_slab_entity`, then
`project_resolved_slab_entity`. The resulting slab can be reissued by
`publish_live_slab_area_quantity`; coverage reports QUANTIFIED, with
`commercial_projection_allowed=False`.

`project_resolved_slab_entity` currently tests `units_authoritative` by
truthiness, trims/string-coerces document, revision, source digest, snapshot,
boundary and resolver IDs, and accepts a 64-zero source digest. The area
reissuer also accepts that digest. A local execution on this base through the
actual projection and area publisher produced a corroborated area for each of
`"false"`, `1`, and `{"verified": False}` as the metric-authority flag.
Padded document/revision/snapshot labels and the zero digest also produced
quantities. These are executable source-shaped synthetic examples, not a
private-original PDF replay.

## Inference

The existing explicit Boolean metric flag cannot be replaced by a truthy
object. Altered source tokens must not borrow an original token's identity
through normalization. An all-zero digest does not authenticate an original
source. These checks add rejection at the existing seam; passing them does
not independently prove scale or establish new source/measurement authority.

## Implemented change and expected abstentions

Require exact native nonblank, unpadded source lineage and physical receipt
strings before canonical projection, preserving genuine SHA hex case-folding.
Require `units_authoritative is True`. Compare the boundary provenance token
without coercion. Reject the zero digest at projection and at the final area
reissuer, including replayed canonical objects. Keep valid physical IDs,
quantities, schemas, formulas, receipts and coverage behavior unchanged.

Test the actual positioned slab annotation resolver, canonical projection,
area publication and coverage consumer. Include original positives,
false/truthy/untyped flags, padded/stringified source aliases, zero digest,
boundary receipt substitution, unchanged-input and deterministic replay,
translation/rotation/scale and polygon order controls. Existing metric
geometry and source-scope tests remain required. Invalid inputs must abstain;
no fallback unit, source, quantity or commercial permission is introduced.

Only the canonical slab projection, slab area reissuer, dedicated regression
tests and this report are owned here. Upstream geometry/resolver, live PDF
extractor, customer writers, GPT2 room/finish/RCP, MAX structural/opening,
GPT3 signing/scoring, other active GPT1 PRs, 20,000 primitive cap and 2.5pt snap
stay untouched.

## Benchmark firewall and release evidence

No benchmark values, project names, mappings or expected BOQ entries select
the rule. Frozen truth, evaluator, original PDFs, archived signed/customer
fixtures and credentials are not changed. Synthetic source bytes do not
prove owner-original preservation. Keep the PR draft until exact-head
automated checks and applicable trusted original-source/retention gates are
demonstrated. No new FIRM/customer quantity or score improvement is claimed.

Executed validation:

- New regression suite on the untouched base: 31 failed / 14 passed,
  reproducing the authority/identity bypasses with positive controls.
- New regressions plus existing canonical slab, slab quantity, metric integrity,
  cross-trade slab and coverage suites: **175 passed on Python 3.13.16 and
  175 passed on Python 3.14.8**. Existing extreme-geometry negative tests emit
  two Shapely overflow warnings per runtime and still pass.
- Valid existing synthetic projection + quantity serialization unchanged:
  SHA-256 `7915a234d05afd805d38bd81819a7ddf52a4414b65cc73da5f4b42c52a1d1e29`.
- Provider/gold isolation, frozen V2 integrity, undefined-name/scope lint and
  diff whitespace checks passed. No frozen evaluator was executed.

The new synthetic PDF fixture initially used an unsupported thickness phrase
and correctly abstained upstream. The fixture now uses the existing parser's
explicit `150mm THICK RC SLAB`; no thickness parser was changed.
Full immutable-head remote CI and trusted owner-original production/signed
retention remain separate release gates. No original-source replay is claimed.


## 2026-10-29 continuation: original annotation page receipt exactness

**Observed producer:** `pb_slab_classification_geometry.resolve_slab_entity` stores
`annotation.source_page` as the integer `annotation_source_page` in the
resolved slab provenance. Before this repair, canonical projection accepted
missing page receipts by substituting `boundary.source_page` and coerced
numeric-looking strings using `int(...)`. The independent quantity issuer
also accepted equivalent printable page aliases from copied canonical objects.

**Source-safe correction:** Both canonical projection and the actual
`publish_live_slab_area_quantity` issuer now require a present, exact built-in
integer annotation page equal to the separately authenticated boundary page.
No page is inferred, no new source or metric authority is granted, and a
missing or ambiguous receipt abstains. The genuine original producer's integer
page is unchanged. Adversarial tests exercise `"1"`, `"01"`, `"+1"`,
padded strings, float, Boolean, null and omitted receipts at BOTH real seams,
plus original synthetic-PDF producer→canonical→quantity→coverage preservation.

This remains an integrity-only, DRAFT source-gated proposal. New exact-head
dual-Python 3.13/3.14 CI and signed/customer companions must complete, then
SHA-verified original-source issuer/customer replay must be demonstrated before
merge. No new FIRM, official frozen score or merged milestone is claimed.
