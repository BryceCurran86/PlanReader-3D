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
→ `StructuralMemberResolution.quantity`.

Legacy repeated-bay arithmetic, explicit count text, and structural schedule
rows are evidence only and cannot mint `masonry_piers`.

## Exact-source finding

The SHA-verified Murera probe produced:

- authenticated structural-member observation count: 0;
- authority status: `ABSTAINED`;
- quantity: unavailable;
- blocker: `structural_member_scope_incomplete`.

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
- adding an explicit count string still cannot publish without authenticated
  physical member instances.

No project name, source page, filename, source SHA, or expected quantity is used
as a production prediction input.
