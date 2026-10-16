# Complete-project handoff: where the time and memory go (3Laurel, Q5446) - measurement record

Status: measurement record, 2026-10-15 (supersedes the 2026-10-14 draft). Nothing here changes a gate, cap, tolerance, authority, quantity or
benchmark file. The 20,000-primitive complexity cap, source-SHA / lineage / mutation checks and the signed-quantity rules are untouched by every
change listed below. Tracking #2608. Raw sampled stacks: GitHub Actions run 38700279027 (artifacts `profile-3laurel`, `profile-q5446`).

## 1. Observed repository behaviour

`tools/run_source_closed_project_handoff.py --family-group all` decodes **every page** of the original PDF as the evidence universe, builds
wall/opening topology for the source-classified floor-plan page(s), then runs a second, independent ceiling/lining collector with its own source
producer (its producer identity is part of every snapshot id, so its second full ingest cannot be shared without rekeying).

On GitHub Actions (ubuntu, single-threaded) the unmodified handoff completes in 15-23 min / ~6.4 GB (3Laurel, 18 pages) and 6-9 min / ~7.6 GB (Q5446,
10 pages). Shared runners differ by up to 2x from job to job, so **time is only compared between variants run sequentially on the same runner**
(`diag-claude-full-project-handoff-bounded.yml`, `diag-claude-lineage-attach-original-source.yml`); memory is deterministic enough to compare.

## 2. Profile of unmodified main (py-spy, 20 Hz, 3Laurel, 924 s sampled, 2026-10-14)

| share | where |
|---|---|
| 89% | `collect_live_physical_net_wall_claim` |
| 33% | `_producer_opening_relation_overrides` -> `_producer_proven_page_opening_records` (full-page G17 proof) |
| 21.8% | `authenticated_visible_observations` (whole-source authentication; 4 reads per `_native_dimension_source_proof_batch`) |
| 23% / 33% (3Laurel / Q5446) | `dataclasses.replace` |
| 9% / 22% | the derived-generation clone loop in `publish_derived_observations` |
| 5.2% | `_physical_opening_geometry_identity` (scans every visible record once per candidate observation) |
| 15% | `compose_live_physical_opening_voids`: per-opening label/semantic/schedule text re-resolution |
| up to 22% | Python's cyclic garbage collector on 3.0 M stored entries (Q5446 pages 1-3) |

## 3. Changes (each a separate PR; all draft, none merged)

| PR | mechanism | what stays the same |
|---|---|---|
| #2693 | derived snapshot generations share the immutable base record objects instead of cloning all N records per generation; snapshot/generation re-bound at the read boundary | every store key, snapshot id, fingerprint, check and defensive copy |
| #2694 | the native-dimension transaction hands its own just-proven whole-source read to the inner proof (4 -> 2 reads per transaction); per-snapshot lookup replaces the quadratic opening-identity scan | entry and exit authentication, bytes/receipt/text/geometry re-proof |
| #2695 | the handoff runner pauses the cyclic collector (mode `staged`: one collection after each major stage) | nothing observable |
| #2706 (stacked on #2693) | field-for-field defensive copies instead of `dataclasses.replace` (import-time guarded) | the copy contract |
| #2705 | label-line construction resolves only the opening's own page of text words | the lines (proved identical) |
| #2784 | W2 `attach_lineage_to_split_fragments`: margin-expanded box prefilter (a proven superset of the exact predicate) on the bucket AND the 64 pt grid candidates, per-source / per-parent-set caching, type-exact payload copy | the exact containment predicate, candidate order, emitted payload |

## 4. Verification

* Every variant's `production_summary.json` and `source_attempt_preflight.json` are byte-compared with unchanged main in the same workflow run (both projects).
* Original-source signed outputs: `source_sealed_run.json` and `verified_customer_rows.json` of the Lot16 and Maryborough replays are `cmp`-identical to the archived signed originals on each PR head, on #2784, and on the combined branch `claude/resource-stack-integration-20261015`.
* Each change carries equivalence tests against the previous implementation (#2784: 115 tests with the old function embedded verbatim, plus exact equality on the real captured Q5446 call) and production mutation tests.
* Integration dry run, 23 eligible PRs merged onto `40d8e849`: 0 conflicts; the 29 test files they change = 664 passed; full suite 14,748 passed / 19 failed, the same 19 failing on pristine main in the Windows environment.

## 5. Results (same runner, sequential, every output byte-identical, all exit 0)

Resource stack (DIAG run 38687716754):

| project | variant | CPU s | vs base | peak RSS GB | vs base |
|---|---|---|---|---|---|
| 3Laurel | base / base2 | 1109.9 / 1101.1 | 1.000 | 6.34 | 1.000 |
| 3Laurel | #2738 alone | 1100.4 | 0.995 | 6.35 | 1.002 |
| 3Laurel | stack (staged GC) | 604.7 | 0.547 | 4.19 | 0.661 |
| Q5446 | base / base2 | 550.9 / 548.9 | 1.000 | 7.40 | 1.000 |
| Q5446 | #2738 alone | 543.2 | 0.988 | 6.92 | 0.935 |
| Q5446 | stack (staged GC) | 290.3 | 0.528 | 4.70 | 0.635 |

W2 lineage change (DIAG run 38708678556): 3Laurel main 919.1 s -> main + #2784 859.3 s (0.935); stack 468.6 s (0.510) -> stack + #2784 412.2 s (0.448);
Q5446 stack 300.3 s (0.537) -> 296.6 s (0.530). Peak RSS unchanged by #2784.

## 6. Profile of the stack (py-spy, run 38700279027), where the time goes now

3Laurel (21.7 k samples): opening-proof subtree 24% (about half of it the deliberate before/after full-inventory authentication in
`_native_dimension_source_proof_batch`, cost O(pages x visible observations)); W2 lineage 16% (addressed by #2784); derived-snapshot `_commit` 9%;
page renders 5%; scale-scope publication 3.6%; staged GC boundaries 2.3%; ceiling-lining collector 8%.
Q5446 (instrumented local run, 253 s): 22 of 24 source-snapshot commits republish ~587 k records to add 9-85 new ones = 61 s (24%); 10 of 28 page renders repeat identical requests with byte-identical PNGs (~2-3%); scale scope 16 s for ten distinct viewports (no repeats).

## 7. Not done, with the reason (owner decisions are marked)

* **Derived-snapshot republish (24% of Q5446):** a data-structure change in the integrity store; architecture report #2785, awaiting GPT1 / GPT3. **Owner decision.**
* **Before/after full-source authentication per page in the opening-proof batch:** a deliberate integrity gate; narrowing it to the page under proof changes authority semantics. **Owner decision.**
* PNG render reuse (~2-3%): would make two existing determinism tests vacuous (the second call hits the cache). Not done.
* A shared result template in `_commit`: breaks GPT1's pinned contract `cached_result.observation is stored`. Not done.
* Swapping the scale resolver `_visible_segments` to the batch authenticator: changes tamper-time semantics (skip vs raise). Not done.
* Cross-producer cache of the native page decode for the second (ceiling) ingest: decode is only ~2% of Q5446 and ~1% of 3Laurel; the rest of the second ingest is per-producer derivation. Not worth a global cache.
* pytest-xdist for CI (597 s -> 302 s): blocked by SQLite-backed tests that share state (6 / 13 extra failures on 3.13 / 3.14); a task to isolate them was raised.
