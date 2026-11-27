# Lot16 sheet 3 native candidate groups, 125 -> 189 (geometry task C21, 2026-11-27)

Private original read locally; counts only. **No pin, scorer or behaviour is changed here.**

## Cause

Exactly one change: the wall-continuation check added in #3079 (`65de56a75`; its parent `01b78c4d7` gives 125). With only that
check disabled in a throwaway copy, the groups equal the parent's 125 one for one (same members): 10 return, 115 are kept and
none of the 74 new ones appears. Every group is `unresolved_source_only`; canonical openings, host bindings, voids and
composition status are identical across the change. Only diagnostics and verify tools read these groups.

## The 10 removed

Each is a face break with a collinear wall stub **strictly inside** its gap, so its two sides are not adjacent wall faces. The
rule is generic geometry; the removals were not checked by eye.

## The 74 "added"

They are not new candidates. With the check off, every one of their 444 observation lookups (74 groups x 6 supports) returns
`conflict` / `ambiguous_physical_opening_candidates`: each support is shared with another candidate (including the stub-spanning
ones), and the closure only records a candidate that a lookup returns. Removing the spanning breaks resolves that ambiguity, so
the 74 now appear.

## Retention gap (separate from the count)

A candidate whose every support is contested is listed nowhere in the closure's raw membership, so the audit silently omitted 74
candidates until a rule change happened to uncover them. AGENTS.md asks to retain all plausible candidates. A follow-up could
list contested candidates beside the unresolved groups (diagnostic only, authority unchanged).

## Recommendation (MAX decides)

Re-baseline the membership pin to 189 as candidate-only once the 10 removals are accepted. Do not treat 189 as existence or
opening counts.
