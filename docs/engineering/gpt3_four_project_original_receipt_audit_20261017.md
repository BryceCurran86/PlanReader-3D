# GPT3 — original four-job receipt audit and signed-source release gates (2026-10-17)

**Type:** read-only, benchmark-neutral engineering evidence review. **Status:** `DIAGNOSTIC_UNPUBLISHED`. This document is not an additional producer, a customer approval, an identity map, a change to signed V1 receipts, a benchmark result, or a review grant. The first-difference and SHA results were independently calculated in a GitHub-connected GPT3 session, not by re-running the owner's private PDFs on a second machine. GitHub trackers: #2004, #2297, #2608. Machine-run session issued by Claude in merged #2846. The library contains *derived receipts only*; no private PDF is distributed by this report.

## Sources read and authority boundaries

- Repository `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md` §13, and `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`.
- Original owner-machine derived receipts: `docs/engineering/four_job_runs/20261016_47c8031a/` (`RUN_RECEIPT.json`, `SHA256SUMS`, all four `source_package_preflight.json`, `production_summary.json`, `source_attempt_preflight.json`, sealed Lot16 family and combined run).
- Original archived Lot16 signed/customer baseline: `docs/engineering/lot16_original_signed_eight_row_20261015/production/source_sealed_run.json`, `production/verified_customer_rows.json`, immutable identity map and exact project development report.
- Production and checking call path: `tools.run_source_closed_project_handoff` → source-owned `QuantityEvidence` and `CommercialTakeoffSourceTrace` → `pb_source_closed_run_export.seal_source_closed_quantity/_build_sealed_run` → `pb_customer_output_verification.verify_sealed_customer_output` → `tools.report_gpt3_four_project_evidence.build_four_project_evidence_ledger` → unchanged frozen `evaluate_suite_v2`. V1 fingerprints use `pb_migration_contracts.canonical_contract_json` and `stable_contract_id`.
- The original source PDF hash, page count and byte size were calculated by the owner's launcher and checked against manifests; GPT3 **independently compared the persisted signed preflight values to the unchanged manifest**. It did not independently possess or SHA-read the original ten PDF bytes, so this review does not overstate that authority.

## Thirty completed independent receipt/release-gate checks

Each result below names an actual separately tested guard or an inspected source-derived receipt, not a claim that thirty production features shipped.

| # | Gate / evidence examined | Result |
|---:|---|---|
| 1 | Current repository context and main head | Source ref inspected; baseline branch `821372b4` |
| 2 | Frozen suite project count | Exactly 4 |
| 3 | Frozen denominator by project | 27 / 63 / 24 / 6 = 120 |
| 4 | Frozen source-manifest publication state | All 4 `INCOMPLETE`; no score |
| 5 | Lot16 architectural original source receipt | SHA/size/page/role exactly matches frozen source manifest |
| 6 | Lot16 structural original source receipt | SHA/size/page/role exactly matches frozen source manifest |
| 7 | 3Laurel original source receipt | SHA/size/page/role exactly matches frozen source manifest |
| 8 | Maryborough original source receipt | SHA/size/page/role exactly matches frozen source manifest |
| 9 | Q5446 standard plans original source receipt | SHA/size/page/role exactly matches frozen source manifest |
| 10 | Q5446 siting original source receipt | SHA/size/page/role exactly matches frozen source manifest |
| 11 | Q5446 inclusions original source receipt | SHA/size/page/role exactly matches frozen source manifest |
| 12 | Q5446 specification original source receipt | SHA/size/page/role exactly matches frozen source manifest |
| 13 | Q5446 colour boards original source receipt | SHA/size/page/role exactly matches frozen source manifest |
| 14 | Q5446 sales advice original source receipt | SHA/size/page/role exactly matches frozen source manifest |
| 15 | Owner-run receipt root SHA-256 | `RUN_RECEIPT.json` recomputed and matches `SHA256SUMS` |
| 16 | Owner-run manifest-digest file | Independent SHA-256 `317f93cce0fbbee07b4a629fd42db5d1b3375e9a4fb235cf6f5e6bbb0b338995` |
| 17 | All share-safe derived artifacts | 28/28 SHA-256 and byte count checks pass; 4 empty stack dump files verified empty |
| 18 | Lot16 archived eight-source-run schema | V1 `1.0.0` retained |
| 19 | Lot16 original archived row fingerprints | Independently recomputed 8/8 valid |
| 20 | Lot16 fresh machine-run row fingerprints | Independently recomputed 8/8 valid |
| 21 | Lot16 historical complete-run fingerprint | Recomputed and equal to `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb` |
| 22 | Lot16 fresh complete-run fingerprint | Recomputed and equal to `2e8333c7ee2642d8b0a6f533e5153d8642e595b554f04de5550fc4394b7e9a5f` |
| 23 | Historical and fresh deterministic run IDs | Both independently recompute correctly |
| 24 | Cross-run source physical identity and quantity set | Exact 8/8 quantity IDs + physical object refs, source SHA/page/viewport, family, unit, value retained |
| 25 | Cross-run evidence version integrity | 8/8 host binding receipt IDs changed; 5/8 frame receipt IDs changed; all 8 fingerprints therefore differ |
| 26 | Historical archived customer output ID bijection | Exactly 8 unique customer quantity IDs matching archived sealed run; no duplicate/foreign ID |
| 27 | Commercial inclusion status of those archived rows | 8/8 `PROVISIONAL` / `To review`; NOT commercial approval |
| 28 | Owner machine's fresh Lot16 customer proof | `customer_rows_file=null`, `customer_rows_verified=false`; new projection NOT EXECUTED |
| 29 | Source-first production status differentiation | Lot16 completed/sealed; 3Laurel no sealable quantities; Maryborough stopped by MEMORY_LIMIT; Q5446 blocked by unchanged 20,000-source-primitive bound |
| 30 | Official unchanged frozen V2 publication preconditions | Not met: no complete four-project verified source/customer/identity-map reconciliation and all frozen source manifests still `INCOMPLETE`; `coverage_accuracy=null`, `precision_adjusted_accuracy=null` |

Independent SHA implementation was checked against known SHA-256 test vector `sha256("abc") = ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad`. The source seal digest algorithm and deterministic run ID were independently recomputed from actual committed JSON with Python's canonical JSON semantics (including float confidence representation); checks are **integrity** checks, not proof of physical geometry.

## Independently checked snapshot-scoped rekey compatibility (follow-up)

A later read-only GPT3 pass traced the existing `tools/source_report_scoped_equality.py`: `mask_snapshot_scoped_ids` → `equal_modulo_snapshot_scoped_ids`, and `evidence_swap_matches`. **All eight** actual Lot16 archived-vs-owner-run sealed quantity bodies pass *structural* equality after masking **only** the allowlisted snapshot-scoped receipt prefixes and excluding the derived `fingerprint`. **All eight** pass the comparator's stricter receipt-set rule: at most one replaced `opening_host_binding_v3` and at most one `opening_host_frame_v2` in each of `evidence_ids` and `trace_evidence_ids`, no source observation/other evidence added or lost. Five rows rekey one host and one frame, and three rekey one host only.

The same check was deliberately tested against four synthetic negative mutations of the genuine untrusted *comparands*: changed measured value, changed physical object identity, altered original source observation receipt, and a second added host receipt. All four comparisons **reject** the mutation. These are independently executed read-only comparisons, **not newly merged CI tests or approval**.

**Scope of this result:** the two snapshots have compatible quantity-body **shapes**, not proven issuer/host geometry equivalence. The masked string comparator does not reissue original wall membership, frame ancestry or decision scope; it is unsafe to project customer rows, combine old/new V1 receipts, or claim new scores based on masking. Require old/new original producer-issued source records and positive same-physical/source-owner checks before a versioned lineage attestation.

**Integrity vocabulary:** the V1 "signed" and "sealed" quantities use public, **unkeyed SHA-256 content fingerprints** and deterministic content-derived IDs, as directly observed in `pb_source_closed_run_export.py`; they are not an asymmetric digital signature, cryptographic authentication of the producer, or proof that a third party did not construct another self-consistent envelope. Recomputing the fingerprints detects edits against a **separately trusted pinned digest**; source authentication requires the original-PDF reissue/authority gates. Here "signed" follows the repository's historical API names and must not imply stronger security properties.

## Original owner-machine production outcomes

| Project | Eligible | Machine process status | Authenticated handoff observation | First score/customer gate |
|---|---:|---|---|---|
| `au_qld_lot16_power` | 27 | `COMPLETED` | 8 sealed `opening_area`, 13 more detected physical openings unsigned; architecture primary PDF is only the handoff input | Eight fresh V1 signatures valid but *no verified new customer rows*; full two-source document closure and postseal identity check missing |
| `au_qld_3laurel` | 63 | `COMPLETED` | `no_sealable_quantities`, `live_canonical_wall_frame_conflict`; host equivalence unresolved | No signed quantities/customer; physical first gate for any specific frozen item not established |
| `au_qld_maryborough_service_station` | 24 | `MEMORY_LIMIT` at 12,428.6 MB peak private | `source_attempt_recorded_unsealed`, not a completed source calculation | Full production **not executed to completion**, not zero correct out of 24; three separate historical `floor_area` receipts remain valid but don't match `floor_finish_area` |
| `au_qld_q5446_armstrong32_harlequin` | 6 | `COMPLETED` | `source_complexity_blocked` at `physical_wall_candidate_scope_complexity_exceeded` | No signed/customer project rows, not zero correct out of 6 |
| **Full suite** | **120** | 3 processes completed, 1 resource-stopped | Partial original production only | **`UNPUBLISHED`**, official accuracy **NULL** |

Historical selected-project development observation (from prior independently signed project checkpoints): Lot16 8/27, Maryborough 0/24, combined 8/51 = 15.69%. Those are **not** a full-four-project accuracy figure. The immutable original Lot16 eight signed opening areas are `0.54, 0.90, 1.26, 1.80, 1.80, 2.16, 2.16, 10.08 m2`; no signed 5.67 m² STACKER is permitted. Maryborough retains separately documented Food Prep 13.270425 m², Office 9.05352 m², Cold Room 25.37875 m² **plain floor_area** receipts; no coercion to material finish.

## First failing source authority and owner

1. **GPT MAX / Claude (source issuer):** exact original producer replay old vs fresh host/frame IDs for the same eight Lot16 opening identities. For each changed record demand positive same-source `snapshot_id`, `decision_scope_id`, original structural wall members and competing source alternatives before any versioned scope attestation or reuse of customer output. Do not infer from equal value or label.
2. **Claude/Cursor runner (#2844):** reject failed `git fetch --ref` rather than falling back to stale HEAD; escape or separate valid Windows path contents when bootstrapping Python; rerun original fresh source without uploading source PDFs to public GitHub. Maryborough needs memory-safe source observation pipeline or a genuinely larger-memory runner with a reproducible source-root.
3. **GPT2 / GPT1:** original Maryborough A140 FT3 and A120 material/physical occurrence closure, true PWD wall-face dimension ownership and page7 correspondence, then new independently authentic FIRM `QuantityEvidence`. Existing three floor_area signatures do not grant finish quantities.
4. **GPT MAX / GPT1:** original Lot16 physical opening host/frame/kind/independent ordered dimension gates; do not default door height, count=1, or transfer a neighbour host. 3Laurel wall geometry/text authority and Q5446 outlined lettering/typed negatives remain shadow until independently reviewed source-positive promotion.
5. **GPT3:** signed V1 bytes remain immutable. The existing `pb_source_scope_sidecar_v2_preview` checksum is an unauthenticated integrity digest, **not producer source-scope signature**; add versioned source-issued attestation only after #2297's authority review, customer bijection/security tests, exact source replay, exact-head CI and explicit owner approval. Untrusted or extra customer projection is ABSTAIN, not a score.
6. **Frozen publication:** both four-project reconciliation and frozen manifest `status=VERIFIED` are required by the unchanged evaluator. Changing benchmark truth, eligibility, tolerance, manifest or scorer to force publication is forbidden; request separately governed source-closure validation if the original benchmark ever becomes fully verified.

## No-action / retention proof

This change is **documentation only**; no original PDF, benchmark file, signed fixture, customer receipt, production module, evaluation input, scoring rule, 20,000 cap, geometry snap tolerance, or V1 signed fingerprint has been modified. A source-publication PR containing a client structural PDF (#2782) remains HELD pending explicit redistribution permission. Formal independent GitHub approval is still unavailable under the shared login; this report and review comments must not be called independent release approval.

For an item-granular **diagnostic** inventory enumerating all 120 frozen eligible item IDs without inventing physical-first gates, see #2004 comment 6210306574. Complete audit text and producer source handoff are tracked in #2004 comment 6219762567 and #2297 comment 6219774175.
