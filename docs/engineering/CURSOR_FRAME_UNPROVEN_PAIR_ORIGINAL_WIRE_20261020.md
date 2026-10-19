# Cursor — Lot16 frame unproven-pair original-source wire (2026-10-20)

**Status:** Architecture first deliverable for mission item 3 wire. Review-only.

## Observed

- `pb_frame_unproven_pair_shadow.build_frame_unproven_pair_ledger` already classifies
  `opening_host_frame_unproven_wall_pair:*` reasons against producer equivalence
  as SAME / DISTINCT / AMBIGUOUS / UNRECORDED. It grants no frame.
- Lot16 host/frame GPT1 handoff
  (`tools/diag_gptmax_lot16_host_frame_gpt1_handoff.assess_gpt1_opening_candidates`)
  emits `frame_reason_codes` but does not attach the typed pair ledger.
- Opt-in `source_fragment_roles_shadow` (requires isolated G17 capture) is the
  producer path that emits the unproven-pair reason codes (#3338).

## Inference

Frame-blocked openings that already have a host cannot move past
`whole_wall_frame_unavailable` until aligned competitors are typed. A ledger
that only reads producer receipts does not invent DISTINCT.

## Proposed

Default-off diagnostic that (1) recomposes Lot16 page 3 from original PDF bytes,
(2) optionally enables fragment-role shadow, (3) attaches the unproven-pair
ledger per frame-blocked opening, (4) proves signed quantity/customer receipt
IDs unchanged. No FIRM, no JobHub, no frozen evaluator edit.

## Benchmark observations that must not influence implementation

Expected BOQ areas, “8 of 21”, STACKER 5.67 m², and project names are not inputs.
Retention compares quantity_id / fingerprint identity only.
