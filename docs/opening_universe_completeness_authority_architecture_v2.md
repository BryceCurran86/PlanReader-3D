# Opening Universe Completeness Authority — post-identity validator v2

**Exact validator base:** `e27ffad284b05123ffacbbe123c69823c5367dee`  
**Historical attack source:** PR #335 / `ee732e7a5536265cd87bfcbeb2abe180e8d1245d`  
**Lane:** TEST-ONLY validator architecture. Production completeness code is out of scope for this PR.

## Current prerequisites and boundaries

Current main includes merged physical-opening identity (#331) and the merged exact-head validator replay harness (#339). The opening authority propositions remain separate:

`existence ≠ identity ≠ dimensions ≠ host ≠ universe completeness ≠ physical void ≠ net wall area`

On this base, physical-opening existence and identity are available. Opening dimensions, host identity/binding, universe completeness, physical void, and net-wall authority remain locked. A completeness implementation must not unlock those downstream capabilities by side effect.

The existing GPT-2 branches `gpt2/authenticated-enumerator-foundation-v1` and `gpt2/completeness-authority-remediation-v1` were inspected before this successor was created. Both diverge from merge base `b76f084f8f28c7a8e2c2519386086b04fe5715a0`, predate current G17 identity and the replay harness, and contain generic/wall-length production changes. They are retained unchanged as historical architecture evidence only. Useful concepts—deterministic producer-owned enumeration and recomputation—do not make those branches current production candidates.

Historical #335 remains DRAFT / TEST-ONLY / DO NOT MERGE. This v2 successor preserves its 30-test identity while removing broken scaffolding and refreshing the authority boundary to current main.

## Trust model: structural, not cryptographic

This authority is an **in-process producer/query structural trust boundary**. It prevents ordinary consumers from constructing the proof object they ask the authority to trust. It is not a cryptographic security proof against equal-privilege Python code, and hashes are lineage/fingerprint inputs rather than proof of completeness by themselves.

A caller-supplied hash, snapshot label, count, list, radius, seal, or matching geometry cannot establish completeness. A producer-owned record can use deterministic fingerprints to bind lineage after the trusted producer has independently established the underlying facts.

## Three propositions that must remain distinct

### 1. Source decode coverage

Question: were all source pages/streams required by the source ingestion step decoded successfully?

`SourceDecodeCoverageRecord` contributes to this proposition. `state="complete"` means decode coverage succeeded for the recorded scope. It does **not** prove that all relevant semantic opening primitives were enumerated.

### 2. Semantic enumeration completeness

Question: did the trusted producer enumerate every relevant semantic primitive required for the proposition?

Positive semantic completeness must compare the producer-owned source universe with the producer-owned enumerated/accounted universe. A caller candidate list, index hits, local R-tree result, or a `claimed_complete=True` flag cannot answer this.

### 3. Decision-scope completeness

Question: for this exact opening/host decision, did the producer account for every relevant competing candidate in the required decision scope?

A local viewport, radius query, filtered subset, or page-A proof cannot certify a different page/scope. The proof must bind the exact decision scope independently of ordinary consumer claims.

## Public query boundary

The validator freezes the preferred typed boundary:

```python
authority = producer.authority()
result = authority.resolve(
    OpeningUniverseSelector(
        document_id=...,
        revision_id=...,
        source_sha256=...,
        snapshot_id=...,
        decision_scope_id=...,
    )
)
```

The final authority must not expose a giant `Any` claim object or a public `resolve_opening_universe_completeness(claim=...)` shortcut. `UniverseEnumerationClaim` remains a **test scenario fixture only**. It is never passed to `authority.resolve`.

The validator expects a trusted writer named `OpeningUniverseCompletenessProducer` and a read-only `OpeningUniverseCompletenessAuthority`. The writer may accept test/producer material in order to build trusted records; ordinary consumers receive only the authority/query surface.

## Producer-owned completeness record

A positive record must bind at least:

- document identity;
- revision identity;
- source SHA-256;
- producer snapshot;
- page/scope identity;
- enumeration state;
- decision-scope identity;
- accounted semantic members;
- deterministic universe fingerprint;
- deterministic record identity.

Production must use the repository's existing `stable_contract_id` for deterministic contract IDs. Fingerprints/ordering must be deterministic. Duplicate/replayed members must not inflate the accounted universe.

Use canonical `EvidenceResolutionStatus` only:

- `RAW`
- `CANDIDATE`
- `CORROBORATED`
- `CONFLICT`
- `ABSTAINED`

There is no `BLOCKED` evidence status. Positive completeness is `CORROBORATED`; fail-closed outcomes are `ABSTAINED` or `CONFLICT` as appropriate.

## Forbidden self-certification

None of these can establish completeness by themselves:

- `claimed_complete=True`;
- `is_complete=True`;
- `is_authenticated=True`;
- caller snapshot ID;
- caller hash or echoed hash;
- caller candidate count;
- caller radius;
- caller list;
- caller index-hit count;
- caller-provided seal;
- matching geometry alone.

The caller must not be able to construct the producer-owned completeness record that `resolve` trusts.

## Preserved historical fixture set

The v2 test support keeps the historical fixture contracts and fields intact in meaning:

- `CallerCompletenessProbe`
- `IndexedPrimitive`
- `UniverseEnumerationClaim`
- `coverage_record`
- `two_opening_page_pdf_bytes`
- `ingest_source`
- `snapshot_echo_hash`
- `FULL_PAGE_PRIMITIVES`
- `shuffle_primitives`
- `split_collinear_equivalent`

No fields were added to `UniverseEnumerationClaim`.

One producer-side fixture, `BACKGROUND_PRIMITIVE`, was added only to make historical Attack 8 executable: it represents independently held source truth that the local semantic enumeration omitted. It is not a caller proof object and is not added to `UniverseEnumerationClaim`.

## Preserved 30-test structure

The successor retains **30 tests total**: **9 current-main GREEN** fail-closed/firewall checks and **21 strict expected-RED** tests. Historical attack identities are not silently deleted or combined away.

| Attack | Intent | Required result |
|---|---|---|
| 1 | authenticated full-page positive | producer-owned full scope may CORROBORATE |
| 2 | truncated viewport | fail closed |
| 3 | unknown clipping | fail closed |
| 4 | active clipping hiding competitor | fail closed |
| 5 | caller `is_complete` | no completeness authority |
| 6 | caller echoed snapshot | no completeness authority |
| 7 | omitted source primitive | fail closed |
| 8 | unindexed visible layer | fail closed |
| 9 | partial ingestion | fail closed |
| 10 | multi-page/scope laundering | fail closed |
| 11 | revision laundering | fail closed |
| 12 | source-hash laundering | fail closed |
| 13 | snapshot laundering | fail closed |
| 14 | filtered-subset echo | fail closed |
| 15 | radius-limited universe | fail closed |
| 16 | index-count-only proof | fail closed |
| 17 | duplicate/replayed members | no inflation |
| 18 | optional-content ambiguity | fail closed |
| 19 | nested XObject omission | completeness unavailable |
| 20 | recursive XObject truncation | completeness unavailable |
| 21 | input-order determinism | identical producer-owned result identity |
| 22 | segmentation invariance | equivalent collinear segmentation does not change semantic universe fingerprint |
| 23 | downstream firewall | dimensions/host/void/net wall remain locked |

Historical #335 used unconditional placeholder `AssertionError` paths for several attacks and a claim-based public resolver. Those defects are intentionally not preserved; the **attack intent** is preserved as executable behavior.

## Replay-harness gate

The merged harness supports explicit CLI overrides for `--base-sha`, `--validator-ref`, `--validator-path`, and `--expected-validator-blob-sha`, so the historical `tools/validator_replay_lanes.json` completeness entry does not need to be rewritten for this validator PR.

Freeze command shape after blob SHA is recorded:

```text
python tools/validator_replay_harness_cli.py \
  --lane completeness \
  --production-sha e27ffad284b05123ffacbbe123c69823c5367dee \
  --base-sha e27ffad284b05123ffacbbe123c69823c5367dee \
  --validator-ref gpt2/opening-universe-completeness-post-identity-v2 \
  --validator-path tests/test_opening_universe_completeness_authority_redteam_v2.py \
  --expected-validator-blob-sha <FROZEN_BLOB>
```

Expected baseline: 9 passed / 21 controlled XFAIL. Expected `--runxfail --maxfail=1`: Attack 1 fails on the genuinely missing producer-owned completeness API, not collection/import/fixture/enum/placeholder scaffolding.

## Scope firewall

This validator PR changes **zero production files**. It does not implement or unlock:

- opening dimensions;
- host identity or host binding;
- opening void/deductions;
- net wall area;
- FIRM/commercial publication;
- JobHub authority.

It does not change benchmark gold, scorer, mappings, tolerances, denominator, or holdout data.

Controlled development benchmark remains **31 / 61 = 50.82%** until a canonical benchmark rerun proves otherwise.
