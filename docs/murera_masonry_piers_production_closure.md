# Murera masonry_piers production closure review

Status: production authority reviewed; publication remains fail-closed.

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
- the resulting decision is consumed through `StructuralMemberAuthority`;
- full-document live extraction does not publish `masonry_piers`.

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
