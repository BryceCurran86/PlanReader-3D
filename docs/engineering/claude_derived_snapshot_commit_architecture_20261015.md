# Derived-snapshot republish: measured cost and a per-snapshot flat-map design

**Architecture report for independent review. No code is changed by this document and none will be written before it is reviewed.**
Lane: Claude (integration / CI / performance). Tracking #2608. Related measured work: #2693, #2694, #2695, #2705, #2706 (resource stack), #2784 (W2 lineage).

## Compliance block

- Read: `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, `pb_source_observation_authority.py` (`SourceObservationProducer._commit`, `publish_derived_observations`, `SourceObservationAuthority.resolve`, `_SourceObservationStore`), `pb_source_visibility_authority.py` (`authenticated_visible_observations`, `_native_dimension_source_proof_batch`), `tests/test_gpt1_historic_verified_cache_proof.py`, `tests/test_gpt1_task5_wall_runtime_followup.py`.
- Functions traced from the complete handoff: `run_source_closed_project_handoff._generate_project_handoff_locked` -> `collect_live_physical_net_wall_claim` -> `compose_live_wall_opening_authority` -> `augment_with_raster_opening_primitives` / `augment_with_raster_visible_segments` (via `_from_source_visibility_producer`) -> `publish_derived_observations` -> `_commit`.
- Authority boundary crossed: **source-observation integrity authority** (immutable records, per-snapshot fingerprints, tamper detection, verified-read cache). It grants no measurement, host, wall or quantity authority; this report proposes a data-structure change with no change to any identity, id, payload hash or output.
- Files that stay untouched by this proposal: every benchmark/gold/truth file, source PDFs, scoring code, tolerances, `stable_contract_id`, record payload definitions, snapshot-id derivation, customer sealing and export modules.

## 1. Observed repository behaviour (instrumented complete handoffs, not inference)

Complete original-source handoff of Q5446 on the rebased stack tree (main + #2693 #2694 #2695 #2705 #2706, staged GC), wrapper-only instrumentation (no result altered), uncontended local run, 253 s:

| measurement | value |
|---|---|
| `_commit` calls | 24 (2 native ingests, 22 `publish_derived_observations`) |
| records passed to each derived commit | 587,118 ... 587,972 |
| **new records per derived commit** | the first derivation adds 293 k visible-segment records; **each of the 20 later ones adds 9 to 85** (the rest are the parent snapshot's records, unchanged) |
| time in `_commit` | **60.96 s of 253 s (24 %)**, 2-4 s per derived commit |
| records ever inserted into the store | 13.5 M; store entries at the end 12.6 M (three dicts keyed by `(snapshot_id, observation_id)`) |
| peak RSS of the stack run (CI) | 4.7 GB (7.4 GB on unchanged main) |

Complete 3Laurel (CI py-spy, same tree): `_commit` 9-10 % of samples, `publish_derived_observations` 12.5 %. Per-record cost measured in isolation (approximate; another job was running): staging loop 0.6 us, `observations` + `record_fingerprints` inserts 1.0 us, verified-cache seeding (one `SourceObservationAuthorityResult` + a 5-tuple) 3.5 us, historic-cache eviction scan ~1.6 us per cached entry.

Call-path facts (from the source): `publish_derived_observations` (a) builds `inherited = [store.observations[(base, oid)] for oid in base.observation_ids]`, (b) concatenates the derived records, (c) builds `ids`, a `set` for the duplicate check and `tuple(sorted(...))` for `ProducerSnapshotRecord.observation_ids`, then (d) `_commit` stages every record into a dict, inserts it into `observations` and `record_fingerprints`, builds `frozenset(snapshot.observation_ids)`, seeds `verified_resolution_cache` for every record, and scans the whole cache for historic eviction. Everything is O(records in the snapshot) although the change after the first derivation is O(derived records). Snapshot ids already depend only on `(revision, base snapshot, sorted derived ids, generation)`.

## 2. Inference (not authenticated)

- Cost and memory are O(derived snapshots x records). The 22 derived snapshots of Q5446 are produced by independent callers (raster augmentations per page/candidate batch); batching them would change snapshot identities and therefore outputs, so the number of snapshots must stay as is.
- The three `(snapshot_id, observation_id)`-keyed dicts hold ~12 M tuple keys; most of the 4.7 GB peak is plausibly these entries (not yet attributed byte-for-byte).
- Nothing in production depends on the per-record entries being *separately allocated*; behaviour that matters is observable only through lookup, membership, replacement (tamper) and eviction semantics.

## 3. Proposed change (for review; not implemented)

1. Store each snapshot's records as a **flat `observation_id -> record` dict created by copying the parent's dict (C-level, pointer copy) and applying the derived records**; same for fingerprints. Because each snapshot owns its own dict, replacing or deleting `(S, oid)` can never affect another snapshot, exactly as today.
2. Keep the current mapping interface (`get`, `[]`, `[]=`, `in`, `pop`, `items`, `len`) on `store.observations`, `store.record_fingerprints` and `store.verified_resolution_cache` as thin views keyed by `(snapshot_id, observation_id)`, so the two production modules and the 16 test files that use them are unchanged.
3. `publish_derived_observations` passes `(base snapshot, derived records)` to `_commit` instead of the full list; duplicate detection checks only the derived ids against the parent's id set.
4. The verified-read cache keeps its exact observable policy (identity binding to revision / snapshot / record objects, fingerprint equality, parent-presence check, historic eviction target, "evicted until the next resolve"). Seeding becomes lazy for inherited records (derived from the per-snapshot committed record and fingerprint) rather than one tuple per record.
5. `ProducerSnapshotRecord.observation_ids` remains the full sorted tuple (identity and public behaviour unchanged).

Expected effect: derived commit cost O(derived) + two pointer-dict copies (about 15-30 ms for 590 k entries instead of 2-4 s), roughly 22-24 % of Q5446 and 9-10 % of 3Laurel wall time, and lower peak memory because no per-entry key tuples or result objects are allocated for inherited records.

## 4. Invariants that must be proven unchanged

Snapshot ids, observation ids, record payload hashes and fingerprints; per-snapshot tamper isolation (`observations[(S, oid)] = x` affects only `S`; deleting a parent entry is detected as `LINEAGE_UNAVAILABLE` for the same snapshot only); `snapshot_contains_observation`; verified-cache identity semantics (`cached[0] is revision`, `[1] is snapshot`, `[2] is record`, fingerprint equal, parents present) and the historic-eviction behaviour pinned by `tests/test_gpt1_historic_verified_cache_proof.py`; the internal-cache contract that the cached result retains the producer-owned frozen record while public reads are defensive copies (`tests/test_gpt1_task5_wall_runtime_followup.py`); failed-transaction atomicity (nothing visible after a raised `_commit`); duplicate-observation-id rejection; `render_native_page_png` page-parent lookup; byte-identical `source_sealed_run.json` / `verified_customer_rows.json` for the eight signed Lot16 quantities and three signed Maryborough floors.

## 5. Required tests before any promotion

Synthetic positives and look-alike negatives for every mapping operation; **differential test against the current store**: randomised sequences of ingest / derive (including empty and large deltas) / tamper / delete / evict / resolve, asserting identical observable results (statuses, reason codes, returned records) between the old and the new representation; hostile cases (replace a parent record then resolve the child; replace the child only; delete a parent id; mutate a frozen record in place; swap `source_bytes`; duplicate derived id; derived id equal to an inherited id with identical and with different payload); translation / rotation / scale are not applicable (no geometry) and are stated as such; input-order and splitting invariance of the derived batch; determinism and stable-id replay; no-mutation of inputs; memory measurement; complete 3Laurel and Q5446 handoffs with every output file byte-identical to unchanged main on the same runner; Lot16 and Maryborough signed-output replays byte-identical to the archived originals; Python 3.13 and 3.14; all existing tests unchanged.

## 6. Competing interpretations and alternatives

- **A. Micro-optimise the existing loops** (fuse the staging/insert/seed loops, build the cached result by field-for-field clone of one template, evict by snapshot list): safe, about 10-20 % of commit time (2-4 % of Q5446), keeps the structure. Compatible with the pinned `cached_result.observation is stored` contract only if each cached result still holds its own record.
- **B. Fewer derived snapshots by batching augmentations**: rejected, it changes snapshot ids and every downstream id.
- **C. Do not seed the verified cache for inherited records**: every first read then takes the full integrity path (JSON serialisation + SHA-256 per record, ~50 us), far slower than today.
- **D. This proposal** (flat per-snapshot maps + lazy seeding).
- **E. Page-scoped before/after authentication in `_native_dimension_source_proof_batch`** (a separate cost: the opening-proof subtree is 24 % of 3Laurel samples, about half of it re-authenticating the *entire* visible inventory twice per page): this is a deliberate integrity gate. Narrowing it to the page under proof is an authority-semantics change and is **not proposed here**; it needs an explicit owner decision.

## 7. Benchmark observations that must not influence the implementation

The counts above (587 k records, 9-85 new per later derivation, 24 commits) describe the two complete original projects used for measurement. No expected quantity, score, project name or file name enters the design; thresholds are not used; the design must hold for any record count and any delta size, including zero.

## 8. Decision requested

Owner of the source-observation authority (GPT1 / GPT3) to approve, amend or reject sections 3-5 before any implementation. Until then the only related code changes in flight are #2784 (W2 lineage, output-identical, separate module) and the previously posted resource stack. Release authority B1 applies to every merge.
