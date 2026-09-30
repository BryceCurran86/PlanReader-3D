# Murera masonry_piers production closure review

Status: production authority reviewed; native candidate lead closed as unsupported.
Physical-instance and complete-view evidence remain unavailable; publication
continues to abstain. No benchmark row is claimed recovered.

## Scope

This review covers the structural-member lane only. It does not change opening
identity/closure, Item 35, UI responsiveness, raster dimension/substructure,
benchmark gold, expected quantities, mappings, scorer tolerances, denominator,
or commercial/JobHub publication.

## Governing source

Official Murera source SHA-256:

`84dec737ede7adfa32b02c6732d4289a6a2d25f7ae50cf07209428f1b4e0c94b`

The prior TEST-ONLY source probe inspected pages 219-238 from that exact source.

## Observed production path

Structural support quantity publication is owned by:

`AuthenticatedStructuralMemberObservation`
→ `build_structural_member_registration_authority()`
→ `StructuralMemberProducer.publish()`
→ `StructuralMemberAuthority.resolve()`
→ `StructuralMemberResolution.quantity`.

`GenericPlanReaderExtractor.extract_from_pdf()` treats masonry-pier count text
and legacy structural schedule rows as unresolved evidence. Its authenticated
secondary-support adapter publishes only eligible verandah support instances;
it does not establish masonry-pier semantics or completeness.

Legacy repeated-bay arithmetic, explicit count text, and structural schedule
rows are evidence only and cannot mint `masonry_piers`.

## Exact-source finding

The SHA-verified diagnostic probe in closed, unmerged PR #1052 produced:

- authenticated structural-member observation count: 0;
- authority status: `ABSTAINED`;
- quantity: unavailable;
- blocker: `structural_member_scope_incomplete`.

Its deliberately incomplete view records and source-probe candidates are
diagnostic evidence only. They are not production physical-member inputs, and
none of that probe's geometry/text intersection rules is adopted here.

On the relevant page-225 source evidence the probe found one compact/elongated
closed primitive and nearby numeric tokens, but no masonry/pier member-role
block, no bound source instance mark, and no positive member proposition.

Therefore none of the following can raise physical-member authority:

- the rectangle/closed primitive itself;
- nearby numeric or axis-like text;
- nearest text/callout;
- matching geometry;
- a BOQ/specification count;
- the benchmark expected quantity.

## Current trusted definition

Fresh production main `f1653a4d7046592c532abbcaaf2b3fced9aa843e`, including
the exact-fill text-integrity fix in #1087, exposes trusted source words on
page 183. `compile_structural_definition_source_shadow()` compiles a generic
`pier` definition with section specification `masonry; 300 x 300mm; pier`.

That definition owns source revision, snapshot, page, and text-block evidence.
Its view remains `source-page:183:unscoped`. It proves neither a physical
instance nor a link to drawing geometry. The definition-only structural
authority therefore abstains with `structural_member_definition_only`.

This is separate from the masonry-pier instance scope, which still abstains
with `structural_member_scope_incomplete`. The registration evidence producer
rejects a production caller's unsupported `complete=True` claim. Decoding a
page or authenticating visible primitives does not prove the member universe
complete.

Fresh main `84a74c8817dc72c568099e827eb69d17e8428588` also includes #1091's
neutral physical-geometry shadow. Exact-source candidates retain their visible
source backing but have no view ownership, member role, definition link, or
completeness proof. Passing those candidate records directly to public member
registration is rejected as unauthenticated input; they cannot raise quantity
authority.

## Production conclusion

There is no source-owned evidence presently sufficient to publish a
`masonry_piers` quantity without inventing a member proposition.

The production-safe closure is therefore to preserve the existing abstention
until a separate source-owned semantic producer can prove both:

1. each physical masonry-pier instance; and
2. completeness of the relevant member universe.

This is a closure of the authority decision, not an accuracy claim.

## Regression lock

`tests/test_murera_masonry_pier_authority_boundary.py` protects the exact
failure class using synthetic values only:

- unowned pier-like geometry + nearby numbers cannot publish;
- filled and outlined squares + nearby unbound pier specifications cannot
  publish;
- adding an explicit count string still cannot publish without authenticated
  physical member instances.

`tests/test_murera_masonry_pier_exact_source_integration.py` exercises production
APIs against the SHA-locked official PDF:

- trusted page-183 text produces definition metadata but no physical members;
- all source-visible primitives on pages 223 and 225, submitted without a
  member proposition, are rejected by public structural registration;
- incomplete view scopes remain incomplete, and source receipts cannot
  authenticate a caller's complete-view claim;
- source-backed neutral geometry candidates are rejected as member inputs;
- the resulting decision is consumed through `StructuralMemberAuthority`;
- full-document live extraction does not publish `masonry_piers`.

The full-document test uses the existing quantity-extraction invocation with
`collect_item35_shadow=False`; all PDF pages remain in scope. Item 35's
separate full-document diagnostic replay owns no scored quantities and is
outside this structural review. Its implementation and default are unchanged.

Run the exact-source tests explicitly with a locally downloaded official PDF:

```sh
PLANREADER_MURERA_SOURCE_PDF=/absolute/path/to/official-source.pdf \
  PYTHONPATH=. python -m pytest -q \
  tests/test_murera_masonry_pier_authority_boundary.py \
  tests/test_murera_masonry_pier_exact_source_integration.py --durations=5
```

Without that environment variable, the exact-source tests skip; a skipped run
does not count as exact-source validation. A configured missing or wrong-hash
PDF fails. The fixture's source hash and page selection are test inputs only.

No project name, source page, filename, source SHA, or expected quantity is used
as a production prediction input.

## Final native-source candidate check — 30 September 2026

Source evidence was inspected at production main
`b274e1782c3f6ec8416b201e484eb35c5d603b65` using the same SHA-locked
official PDF. This documentation update is based on freshly fetched main
`1e5e9f78a390b5fbb762e4ef861cb4639a4aa191`. This completes the outstanding check of the three neutral
page-223 candidates; it does not promote the diagnostic probes.

### Observed source evidence

- Closed, unmerged TEST-ONLY #1120 / run `36677794416` reports three
  `vertical_profile_candidate` records on page 223 and none on page 225.
  The page-title and sheet-number authorities did not resolve those views.
- The source-backed paths are indices 10, 11 and 16. Their bounding boxes
  are respectively `(317.40, 559.32, 321.36, 571.56)`,
  `(319.44, 550.44, 321.36, 558.12)` and
  `(345.36, 557.16, 348.72, 573.72)` in page points.
- Direct inspection of an exact-PDF render, including a crop
  `(255, 525, 390, 603)`, shows those shapes are filled outline lettering
  in the source label **LPG storage door**. This is visual source evidence,
  not a new automated glyph classifier or a rule that deletes candidates.
- Closed, unmerged TEST-ONLY #1121 / run `36678276527` inspected all
  238 pages. Its text census found the masonry-pier specification on
  page 183, but no drawing-text pier/pillar instance proposition. Absence
  from that text census alone does not prove that no physical pier exists.

The evidence artifacts are `murera-pier-bounded-view-census`
(`11079853876`) and `murera-full-document-pier-source-census`
(`11080817114`). Both are diagnostics only, with the exact source hash
recorded in their JSON. No expected quantities or scorer output were used.

### Authority decision

The verified boundaries are:

- `SourceVisibilityProducer.ingest_native_pdf_bytes()` supplies the
  receipted immutable source snapshot.
- `compile_structural_physical_candidate_shadow()` returns neutral
  candidates; it does not call member registration or the live extractor.
- `build_structural_member_registration_authority()` rejects those
  candidate records as unauthenticated member inputs.
- `StructuralMemberProducer.publish()` and
  `StructuralMemberAuthority.resolve()` preserve the incomplete-scope
  abstention. There is no live physical-instance bridge from this shadow.

Source visibility authenticates the three paths' provenance; it does not
turn vector lettering into physical structural members. The page-183
definition also supplies no explicit instance binding or complete member
view. `StructuralMemberRegistrationEvidenceProducer.view()` rejects a
production caller's unsupported `complete=True` claim. The public
registration builder rejects neutral candidate records as member inputs.

No positive member observation or completeness proof can be minted from
this lead. The missing upstream producer remains a real capability gap;
wiring these diagnostic records into it would fabricate evidence. The
permitted outcome is `ABSTAINED`, no physical members and no quantity.
Do not describe this as masonry-pier recovery or current-head accuracy.

### Stop/reopen condition

Do not repeat the page-223 candidate probe or treat these three shapes as
piers. Reopen instance production only with new source-owned evidence
that proves individual physical masonry-pier propositions, exact view
ownership and completeness of the relevant member universe. A successful
definition parse, a count string, a grid/bay pattern, or these diagnostic
candidates cannot discharge those requirements.

### Validation

The exact-source regression suite must run with
`PLANREADER_MURERA_SOURCE_PDF` configured to the SHA-verified official
PDF; skipped exact-source tests are not a pass. The existing tests exercise
trusted definitions, neutral-candidate rejection, unsupported complete-view
claims and full-document extraction through production APIs.

This addendum changes documentation only. All production code, opening
identity/closure, Item 35, KSTVET work, benchmark files, scoring and commercial
publication remain untouched.
