# Producer-owned G17 wall-source shadow

## Observed repository behavior

`SourceVisibilityAuthority.resolve_raster_opening_primitive` validates the
isolated observation, its exact source-segment parent, immutable snapshot and
native page parent. `PhysicalOpeningAuthority.prove_existence` separately
proves the opening; neither operation proves a host wall.

`PhysicalWallCandidateProducer._from_source_visibility_producer` augments the
ordinary visible source before assembling W2/W3/W4. Its supplemental constructor
uses that same augmented source. It cannot safely consume isolated G17 source
observations without changing the accepted snapshot. The host helper
`_authenticated_raster_source_lines` consumes ordinary raster visible segments,
whose source-primitive namespace differs from isolated G17 primitives.

The merged #2700 tool consumes serialized diagnostic reports, not sealed
producer inputs. Its source-ribbon result cannot establish production authority.

## Inference

An immutable opening-local candidate scope can be derived directly from the
existing producer and an observation selector. No source augmentation is needed.
Retaining the original primitive references through W2 and W4 removes the
namespace/ownership seam for later review, but cannot by itself establish
structural role or equivalence with competing ordinary W4 walls.

## Proposed change and review

Add an opt-in shadow builder accepting only an actual `SourceVisibilityProducer`
and an `ObservationSelector`. Re-prove opening existence and every isolated
face/end observation, then render the same source page to check original solid
ink and unchanged full-page paint using the existing mass/minimum-span policies.
Run the existing W2/W3/W4 and physical candidate-identity functions per flank.
Retain default-snap loss beside exact-coordinate shadow results. Keep W3 review
junctions explicit. Return existing `PhysicalWallCandidateRecord` objects only
inside a shadow wrapper, never a sealed wall producer or complete host universe.

Expected abstentions: foreign/stale selectors, incomplete source, non-solid or
changed paint, unsupported source frame/registration, snap-collapsed jambs,
identity collisions and incomplete/ambiguous structural role. The wrapper stays
ABSTAINED for wall/host authority even when original candidate geometry closes.
No diagnostic JSON, consumer geometry, pixels or caller-supplied completeness
flag may enter the builder. Tests must cover actual producer inputs, tampering,
order/replay, transforms, no augmentation and stable published snapshots.

Review: this is an isolated shadow seam, not an authority promotion. It must
not be wired into host selection, quantities or commercial output. Ordinary
W4 competitors remain outside its authority and cannot be displaced. Future
promotion needs a separate complete competing-role/equivalence proof.

## Benchmark observations excluded from implementation

Original Lot16 has six unhosted G17 hypotheses. The 15 existing hosts, nine
frames and eight areas are retention controls only. No project names, source
SHA, physical opening IDs, figured quantities or benchmark mappings belong in
the predicate. Frozen truth/evaluator and the 20,000 input cap stay unchanged.

## Untouched boundaries

Ordinary source publication, global W2 snap, existing wall/host producers,
quantity and customer writers, W10 defaults, and frozen V2 data remain unchanged.
