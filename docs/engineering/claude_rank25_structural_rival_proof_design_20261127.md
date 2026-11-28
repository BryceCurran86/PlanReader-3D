# Rank 25: positive structural proof for off-centre raster rivals

Date: 2026-11-27. Order: #4764 7203705398 ("retain existing band; implement positive structural rival proof only"). AGENTS.md: design first, no code changed; stop for review.

## Observed (current `main` behaviour)

- `pb_opening_host_frame_authority._shared_host_frame`, raster components: another wall candidate is a rival when one of its segments lies within `_RASTER_WHOLE_WALL_CENTER_TOL_PT + _COORD_TOL` of the host centre line. Each rival needs positive DISTINCT proof against every member or the frame abstains (the drafting-motif census may skip repeated families under its shadow flag). The band was narrowed to this tolerance by 1e39b96c4.
- Synthetic: a second candidate inside the wall body but past that tolerance is ignored and the frame corroborates (#4764 7200530978).
- Originals: a full wall-body band instead changes 7 decisions on one source; all 19 distinct fragments it adds to the 4 frames it drops are drafting content (7203420229).
- The same module already reads the page's authenticated raster opening primitives (`raster_wall_band_face` / `_end`, in `_scope_bindings`). They come from an images-only render at 300 DPI and only exist for solid ink at least 2 pt thick in both directions, bands up to 12 pt.
- Local probe with the repository's own band detector on the same render: 0 of the 19 fragments lie, over their whole length, inside a solid band; 15 of 15 host wall segments do, with band thickness 0.93 to 1.08 times the host thickness.

## Inference

Drafting strokes are thinner than the detector's solid-ink minimum, so a band-containment proof rejects them without any content-specific rule. An off-centre piece of real wall is solid ink, so the proof can admit it.

## Proposed change (not built)

Keep today's centre-tolerance rival set exactly as it is. Add a second, positive-only way for a raster fragment to become a rival:

1. its segment is offset from the host centre line by more than that tolerance but by no more than half the host thickness plus one primitive pixel;
2. two authenticated `raster_wall_band_face` receipts of this page and snapshot, parallel to the host axis, bracket that offset (within one pixel) and cover the whole segment;
3. their spacing is within the module's existing thickness tolerance of the host (`max(0.75 pt, 15 %)`).

An admitted rival goes through the existing DISTINCT requirement unchanged. Missing or unauthenticated band receipts admit nothing (today's behaviour). The change can only turn a frame into an abstention; it never creates or widens one.

Authority boundaries: only source-visibility receipts the module already consumes; no new detector, resolver, evidence vocabulary or schema. Untouched: source visibility authority, detectors, W4 candidates, wall equivalence, quantities, projection, benchmark files.

Rollout: shadow first (record would-be rivals; no decision change), then the census on the originals (expected: nothing would change), then a separate promotion review to enforce.

## Synthetic tests required

- Positive: an off-centre solid continuation inside the host body is admitted, and the frame abstains unless DISTINCT.
- Negatives shaped like the observed kinds: a dimension line with ticks, label text strokes, an appliance outline beside a face, a title-block table line: none admitted.
- A band covering only part of the fragment, or much thinner or thicker than the host: not admitted.
- Translation, rotation (vertical walls), input order and segment splitting; deterministic replay; no input mutation; shadow leaves live results unchanged.

## Must not influence the implementation

The 19 fragments, source names, counts and published rows: no coordinates, page numbers or values in code or tests. Constants come from the existing detector and the module's own tolerances.

## Questions for the reviewer

1. Thickness condition: the host's tolerance (proposed), or any band the detector finds (also catches a thinner partition continuing the line)?
2. Coverage: the whole segment (proposed), or most of it?
