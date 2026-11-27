# Combining room rings of two builder settings (task C06, 2026-11-28)

Architecture note (AGENTS); ordered by MAX 7227402524. Report only; the builder's defaults do not change.

## Observed
`door_jamb_returns` gives one real room its own ring and takes another room's ring away (it merges into an open region),
and changes nothing on the other plan sheets compared. Neither setting alone is safe.

## Inference
Both runs' rings are plausible candidates. A candidate only one run finds is not contradicted by an open (abstained)
region in the other run; two different candidate rings that overlap are a real disagreement.

## Built (shadow)
`pb_room_ring_candidate_union_shadow.union_room_ring_candidates(default_result, alternative_result)`: identical rings
agree; a ring one run finds stays CANDIDATE unless a different candidate ring overlaps it (a shared edge or rounding is
not an overlap), in which case every ring involved is ABSTAINED; each ring lists the doorway closures that bound it per
run, and a closure edge without source paths abstains its ring; runs from different sources or pages abstain everything.
Nothing is chosen by size, score or run, nothing is promoted, and no live path imports it.

## Must not influence
Any expected area or room list. Originals: counts only, before any wiring.
