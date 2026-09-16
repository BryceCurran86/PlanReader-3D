# Opening Universe Completeness Authority — architecture report (test-first)

Base: merged G17 main `62a161519e617cdf9ce23069820dbf7c68aaf521`

Lane: architecture / adversarial tests only. **Production completeness
implementation is out of scope.** Frozen prior lanes: #331 identity,
#332 dimensions, #334 host-binding.

Axes stay separate:

`existence ≠ identity ≠ width ≠ height ≠ type ≠ host ≠ universe_completeness`

Critical contract: a positive completeness proof must answer

> “What authenticated upstream universe was supposed to be enumerated, and
> how do we know every member relevant to this proposition was accounted for?”

Not merely “how many candidates did this function return?”

Compliance (this report)

- Files read: `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`,
  `docs/g17_upstream_authority_producer_architecture.md` (§3.8–3.10, §14),
  `pb_source_observation_authority.py`,
  `pb_source_visibility_authority.py`,
  `pb_wall_net_area_quantity.py`,
  `pb_opening_deduction_readiness.py`,
  `pb_wall_length_quantity.py` (`_scale_universe_completeness_blockers`),
  `pb_physical_opening_authority.py` (`capabilities`),
  `pb_vector_geometry_v130.py` (clip ternary),
  `pb_wall_room_topology_primitive_lineage.py` (`clip_known`),
  `pb_migration_contracts.py` (`DocumentEvidence` / evidence ownership).
- Functions traced: `SourceObservationProducer.ingest_pdf_bytes` (coverage),
  `SourceObservationAuthority.resolve` (`semantic_enumeration_complete=None`),
  `build_net_wall_area_quantity` (always appends
  `opening_universe_completeness_not_authenticated`),
  `_host_blockers` (`opening_host_universe_completeness_not_authenticated`),
  `_scale_universe_completeness_blockers`,
  `_resolve_clip_fields` / extract clip ternary.
- Authority boundaries: decode coverage ≠ semantic enumeration ≠
  decision-complete scope; local candidate list ≠ universe; caller
  `opening_set_complete` / `is_complete=True` / snapshot hash echo ≠
  authenticated completeness.
- Untouched: all production modules, #331/#332/#334 artifacts, gold,
  commercial, JobHub, sealed holdouts.

---

## OBSERVED (repository behavior)

### No modules named “C1” / “C5”

Repo search finds **no** production types named C1/C5 completeness
contracts or spatial-query certificates. Closest adopted surfaces:

| Concern | Existing surface |
|---|---|
| Decoder coverage | `SourceDecodeCoverageRecord` (`state` complete/partial) |
| Semantic enumeration | `SourceObservationAuthorityResult.semantic_enumeration_complete` — **always `None` on resolve** |
| Decision scope | `decision_scope_complete` — **always `None` on resolve** |
| Opening-set echo | EvidenceAtom `kind="opening_set_complete"` |
| Host-universe gate | `opening_host_universe_completeness_not_authenticated` |
| Scale-binding universe | `_scale_universe_completeness_blockers` (sibling viewport presence only) |
| Architecture contract | `docs/g17_upstream_authority_producer_architecture.md` Capability D |

Do **not** invent a second completeness framework; extend these seams later.

### Source / decoder coverage (not semantic completeness)

`SourceObservationProducer` publishes `SourceDecodeCoverageRecord` with:

- `decoded_pages` / `failed_pages` / `total_pages`
- `state="complete"` iff `failed_pages` is empty

That `state="complete"` means **page decode succeeded**, not that every
eligible opening/wall semantic instance was enumerated. Authority resolve
explicitly leaves `semantic_enumeration_complete=None`.

### Caller `opening_set_complete` (diagnostic only)

`build_net_wall_area_quantity` validates ownership/metadata of a caller
`opening_set_complete` atom, then **always** appends
`opening_universe_completeness_not_authenticated`. Comment in module:

> an ordinary EvidenceAtom and a caller declared list cannot prove that
> omitted physical openings do not exist.

Same pattern for host: even `host_status="hosted"` with cardinality 1 gets
`opening_host_universe_completeness_not_authenticated`.

### Scale-binding universe (partial sibling check)

`_scale_universe_completeness_blockers` catches omitted sibling viewports
known to `context.viewport_page_ownership`. It does **not** prove no second
competing binding hides under the same `viewport_id` unless the caller uses
the `page_viewports`-derived path.

### Clip / visibility provenance

`extract_native_page` preserves `clip_known` / `clip_present` / `clip`.
`clip_known=False` is unresolved association — never evidence of unclipped.
Visibility authority refuses unresolved/non-rectangular clips for positive
visible claims. Absence of optional-content / XObject traversal completeness
records is itself a fail-closed gap for “no competitor” claims.

### Spatial index / R-tree

No production R-tree completeness certificate module found. Candidate counts
from detectors or bbox queries must not be treated as source completeness.

### G17 capability lock

`PhysicalOpeningAuthority.capabilities()["opening_universe_complete"]` is
`False`. Completeness alone must not unlock dimensions, host binding, void,
deductions, net wall, FIRM, or JobHub.

### Prefiltered APIs (observed risk surface)

Several consumers accept caller-supplied sequences (`opening_deductions`,
`scale_bindings`, wall lists for diagnostic binders, `OpeningHostCandidate`
lists). On main these paths fail closed for FIRM when completeness is
required, but they remain the primary self-certification attack surface if
a future producer incorrectly trusts list cardinality or `is_complete`.

---

## INFERENCE

- Live FIRM net-wall and opening-deduction routes cannot reach firm
  publication today because completeness is unauthenticated.
- Decode-complete snapshots can still be semantically incomplete.
- Viewport-scoped topology (W2–W7) enumerates walls inside a scoped bbox;
  that local enumeration cannot certify competitors outside the viewport
  frontier without an independent decision-scope proof.
- Architecture doc Capability D describes the intended producer-owned
  universe service; it is **not** implemented as a production authority
  module on this base SHA.

---

## PROPOSED (not implemented in this PR)

A later **OpeningUniverseCompletenessAuthority** (name illustrative) that:

1. Reuses `SourceDecodeCoverageRecord`, producer snapshots, and the G17
   upstream three-way split (coverage / semantic enumeration /
   decision-complete scope) — no parallel vocabulary.
2. Accepts selectors (document, revision, source hash, snapshot, proposition
   scope) — never caller-authored `is_complete=True`, never caller member
   lists as the universe boundary, never echoed snapshot hashes as proof.
3. Requires authenticated upstream enumeration of the decision-complete
   source domain; traces every accounted member to producer-owned
   observations; retains unresolved/ambiguous members in the accounting set.
4. Fails closed on truncated viewport, unresolved clip, active clip hiding
   competitors, partial page ingestion, unindexed layers, page/revision/
   source/snapshot laundering, radius-only queries, index-count-only proofs,
   optional-content ambiguity, incomplete XObject traversal / silent
   recursion truncation.
5. Keeps dimensions, host binding, voids, deductions, FIRM, JobHub closed
   even when completeness resolves.

---

## BENCHMARK (must not drive algorithms)

Observation only: **31/61 = 50.82%**. Holdout exposure **NONE**.

---

## Attack surface map

| # | Case | Expected |
|---|---|---|
| 1 | Full-page authenticated index | RED — may resolve |
| 2 | Truncated viewport | BLOCKED |
| 3 | Unknown clipping | BLOCKED |
| 4 | Active clip hides competitor | local set incomplete |
| 5 | Caller `is_complete=True` | no authority (GREEN today) |
| 6 | Caller echoes snapshot hash | no authority |
| 7 | Missing source primitive from index | completeness failure |
| 8 | Unindexed background layer | BLOCKED |
| 9 | Partial page ingestion | BLOCKED |
| 10 | Multi-page laundering | BLOCKED |
| 11 | Revision laundering | BLOCKED |
| 12 | Source-hash laundering | BLOCKED |
| 13 | Snapshot laundering | BLOCKED |
| 14 | Filtered candidate echo | cannot certify exclusions |
| 15 | Radius-limited query | BLOCKED without topology bound |
| 16 | R-tree / index count alone | BLOCKED |
| 17 | Duplicate/replayed objects | no inflate |
| 18 | Hidden/optional-content ambiguity | fail closed |
| 19 | Nested XObject omission | completeness unavailable |
| 20 | Recursive XObject silent truncate | must not mark complete |
| 21 | Input-order determinism | same result |
| 22 | Segmentation invariance | count≠universe if equivalence proven |
| 23 | Downstream firewall | dims/host/void/deduction/FIRM/JobHub closed |

---

## Unsafe self-certification routes found (current main)

1. Caller `EvidenceAtom(kind="opening_set_complete")` with `opening_ids` list
   — validated then blocked (`opening_universe_completeness_not_authenticated`).
2. Caller `host_status="hosted"` with one wall — blocked
   (`opening_host_universe_completeness_not_authenticated`).
3. `SourceDecodeCoverageRecord.state="complete"` naming — decoder-only;
   must not be read as semantic universe complete.
4. `semantic_filter_applied=True` / empty `opening_ids` — still blocked
   (documented in p0 tests).
5. Legacy `reconciliation_complete=True` on opening deduction rows (v174 /
   B5) — separate legacy gate; must not become opening-universe authority.
6. Diagnostic binders accepting prefiltered wall arrays — local uniqueness
   ≠ universe completeness.
7. No spatial-query certificate type exists — any future R-tree hit-count
   must not be treated as completeness.
