# G17 physical-opening existence remediation architecture

Base: `82ac4346ef9593d4c4b8af196d4800c7b0f74093` (merged PR #319)

This is the architecture report required by `AGENTS.md` before production mutation.

## OBSERVED repository behavior

1. `SourceObservationProducer.ingest_native_pdf_bytes()` in `pb_source_observation_authority.py` decodes the immutable PDF bytes and creates producer-owned `native_pdf_segment`, `native_pdf_word`, `native_pdf_rect`, and page observations. Native observations are page-owned and currently carry `viewport_id=None`.
2. `SourceObservationProducer.publish_derived_observation()` validates that declared parents exist in the selected base snapshot, but the caller supplies the derived observation's `page_id`, `viewport_id`, `observation_kind`, `source_primitive_ref`, and `geometry`. The function does not recompute child geometry from the parents and does not require child page/viewport ownership to equal every transitive native parent.
3. The PR #319 implementation in `pb_physical_opening_authority.py` discovers positive structural candidates from derived `wall_face_interruption` and `opening_jamb_boundary` observations. It requires four independent native lineage roots, same derived-record document/revision/source/snapshot/page/viewport scope, and exact face/jamb geometry relationships.
4. `_lineage_roots()` proves lineage ancestry and independence, but it does not prove that the derived structural geometry is a deterministic transformation of those roots and does not validate transitive root page/viewport ownership against the child record.
5. Therefore the current positive route can prove that four independent native observations existed while accepting caller-supplied derived geometry that is unrelated to those native observations. A derived record can also claim a page/viewport that its native parents did not own.
6. `pb_hosted_opening_geometry.py` already contains a diagnostic, shadow-only native-vector detector with stronger wall-band concepts, including simultaneous interruption on both faces, flanking wall material, jamb support, coverage, and ambiguity handling. `AGENTS.md` explicitly states that this module remains diagnostic-only and must not itself become firm measurement authority.
7. PR #319 is not wired into live quantity prediction, host binding, wall deductions, net wall area, commercial output, or JobHub publication.

## INFERRED authority defect

Independent lineage roots establish provenance of observations, not truth of arbitrary child geometry. Because generic derived records can choose their own geometry and scope, PR #319 currently allows semantic authority to be self-certified across the exact boundary that Phase 2 is intended to protect.

A valid positive physical-opening existence proposition therefore must be recomputed from immutable producer-owned native observations. Generic derived `wall_face_interruption`, `opening_jamb_boundary`, detector labels, tags, schedules, confidence values, or caller-authored structural geometry may remain diagnostic/candidate evidence, but cannot establish `PHYSICAL_OPENING_EXISTS`.

The existence proposition also remains strictly weaker than physical-opening identity, dimension authority, host identity/binding, opening-universe completeness, physical void, net-wall deduction, quantity authority, or commercial publication.

## PROPOSED remediation

### 1. Native-only structural evidence input

For the positive existence path, re-resolve the producer-owned snapshot and accept structural geometry only from observations satisfying all of:

- `origin_kind == "native"`;
- `observation_kind == "native_pdf_segment"`;
- current document, revision, source SHA-256, snapshot, and page ownership;
- successful Phase-1 integrity resolution.

Generic derived observations must not participate in the positive structural proof.

### 2. Deterministic structural recomputation

Add the smallest dedicated deterministic structural-evidence producer/resolver over those native segments. It may reuse reviewed geometric ideas from the existing hosted-opening diagnostic implementation, but it must not treat that diagnostic output as authority and must not import private threshold constants as an authority contract.

A positive native structural opening must prove, from source-native segments themselves:

- two locally consistent opposing wall-face runs;
- a simultaneous gap/interruption on both faces;
- real wall material flanking both sides of that gap on both faces;
- source-native jamb support spanning the wall thickness at both gap boundaries;
- no competing incompatible structural interpretation in the eligible local universe.

A rectangle made from two parallel lines and two connectors without flanking wall material is insufficient.

### 3. Scope integrity

Every source segment used in one structural proof must share exact document/revision/source SHA/snapshot/page ownership.

Native ingestion currently has no independently proven viewport ownership. The remediation must not manufacture a viewport ID. A positive native-only existence record therefore retains `viewport_id=None` unless a separate independently authoritative viewport-binding producer is introduced later.

Derived children that claim a viewport or another page cannot upgrade or transfer their native parents' scope.

### 4. Capability firewall

Restore the legacy downstream `PhysicalOpeningAuthority.capabilities()` map to all-false so no existing consumer can interpret semantic existence as permission to progress into dimensions, identity, host binding, deductions, or publication.

Expose the narrow Phase-2 semantic proposition separately (for example through `semantic_capabilities()`), with only local physical-opening existence enabled.

### 5. Fail-closed behavior

Return candidate/blocked/conflict rather than resolving when:

- only a wall gap exists without both native jambs;
- only jamb-like connectors exist without flanking wall runs;
- native snapshot members fail re-resolution;
- page/snapshot/source ownership conflicts;
- structural candidates overlap incompatibly;
- evidence is derived-only;
- source geometry is non-finite/degenerate;
- the local structural interpretation is ambiguous.

No nearest/first/smallest tie-breaking.

## Synthetic proof required before implementation is accepted

Tests must include at minimum:

1. source-native jamb-bounded two-face interruption with flanking wall material -> semantic existence resolves;
2. unrelated native roots + fabricated perfect derived opening rectangle -> fail closed;
3. page-2 native roots -> page-1 derived child -> fail closed;
4. native roots with `viewport_id=None` -> derived child claiming `vp-1` -> no viewport authority and no positive proof from child geometry;
5. two parallel native lines plus two connectors but no flanking wall material -> fail closed;
6. wall gap without both native jambs -> candidate only;
7. jambs without a valid two-face wall band -> fail closed;
8. duplicate/replayed detector records cannot create corroboration;
9. derived labels/tags/schedules/swing arcs cannot establish existence;
10. competing overlapping native structural interpretations -> `CONFLICT`/ambiguous;
11. translation/rotation metamorphic equivalents preserve outcome;
12. input-order and native-segment splitting invariance;
13. unrelated-content and page-expansion invariance;
14. deterministic replay gives stable IDs;
15. no input mutation;
16. `compare_identity()` remains unresolved;
17. dimensions, host binding, completeness, physical void, net wall area, FIRM quantity authority, live predictions, commercial rows, and JobHub publication remain unavailable/unchanged.

## Files expected to change after review

Likely:

- `pb_physical_opening_authority.py` — remove derived structural records from the positive authority route; introduce/reuse native structural recomputation and capability firewall.
- a narrowly scoped new structural helper only if required to keep native geometry recomputation independently testable.
- `tests/test_g17_physical_opening_existence_v2.py` and additive adversarial remediation tests.

`pb_source_observation_authority.py` should remain unchanged unless implementation proves a generic producer-integrity defect cannot be safely contained at the Phase-2 boundary. Broadly forbidding legitimate derived evidence there would exceed this remediation scope.

## Files and domains that stay untouched

- `pb_planreader_pdf_extractor.py`
- C15 / PR #316 ceiling-lining files
- live opening deduction pipeline
- wall-net-area/commercial adapters
- JobHub publication
- benchmark gold, expected values, mappings, scorer, tolerances, frozen holdouts
- roof/gable work
- opening identity, dimension authority, host identity/binding, completeness

## BENCHMARK observations that must not influence implementation

The controlled five-project development baseline remains **50.82% (31/61 accepted)**. PR #319 is not wired into live scored output, so the authority defect is not a benchmark regression and this remediation must make no accuracy-gain claim unless a later live-output change is separately authorized and measured.

No benchmark expected quantity, project identity, development score, or score delta may set this algorithm's thresholds or acceptance rules.
