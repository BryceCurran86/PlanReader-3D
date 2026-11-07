# 3Laurel: source-owned room wet/dry classification for the finished-face gate (shadow, 2026-11-08)

Assignment (MAX, #4135 comment 6712588972): "a bounded, default-off SOURCE-OWNED room wet/dry classification using the existing room semantic/label authority where possible. A unique authenticated room label and explicit source-scoped rule must own each classification; absence of a wet label cannot itself prove dry, unresolved/conflicting labels ABSTAIN. This classification grants no wall layer/jamb/finish/metric permission and must not undo the finished-face gate." Claim: #4135 comment 6712843876. Counts, sheet ids and reason codes only; no drawing text or measurement.

## 1. Observed repository behavior (main `63700875`)
- The authenticated internal-wall build-up statement can carry a wet-area lining variant. `pb_layered_wall_face_identity_shadow._classify_edges` then adds `room_wet_area_status_not_established` unless its caller passes `room_is_wet_area=False`.
- The only caller, `pb_live_physical_net_wall_integration._finished_face_receipts`, never passed it. On the 3Laurel original every ring receipt therefore carries that reason (#4135 comment 6712408666).
- Every `LiveCanonicalRoomObject` already carries `room_label`, set only when the source label authority proves one unique corroborated label for that exact face (`_unique_source_room_labels_by_face`, `_verified_source_room_label_for_face`). It also carries the label binding record id, the label evidence ids and `source_room_face_record_id`, which ties it to the gated ring face.
- No existing module decides wet/dry status. The wet-area modules in the repository are candidate-only shadows.

## 2. What was built (all default-off)
- `pb_room_wet_dry_classification_shadow.py`. `classify_room_wet_dry(rooms)` produces one frozen noncommercial record per room:
  - **Input:** it consumes only the already-verified room label and never reads words itself.
  - **Rule:** one explicit, versioned rule table `WET_DRY_ROOM_LABEL_RULES`, matched on the whole phrase after one normalization (upper case, punctuation to spaces, trailing room numbers removed). There is no substring, prefix, fuzzy or nearest match.
  - **Dry:** needs a listed dry phrase. Kitchens, garages and outdoor areas are deliberately not listed.
  - **Abstain:** an unlisted phrase, an unlabelled room, a label without binding lineage or an incomplete room scope.
  - **Table safety:** a phrase listed under two rules, or an unnormalized phrase, stops the table from loading.
  - **Lineage:** each record binds the room's document, revision, source SHA, snapshot, page, decision scope and face record, the label binding record id, the label evidence ids, and the rule id and version.
- `wet_area_status_by_face_record(classifications, records)` applies a CORROBORATED record to a sealed face record only when every scope field equals the record's own. Two applicable records that disagree leave the status unestablished.
- `pb_live_physical_net_wall_integration`:
  - adds the explicit-boolean keyword `room_wet_dry_classification` on `_collect_live_physical_net_wall_claim` and `collect_live_physical_net_wall_claim`. It requires `layered_finished_face_gate`.
  - `_finished_face_receipts` receives the per-record status.
  - the claim carries `room_wet_dry_classifications` (diagnostic).
  - with the flag off, behaviour is byte-identical.
- **What it changes and what it doesn't.** The only effect is that a dry room's receipt no longer carries `room_wet_area_status_not_established`. A wet room keeps the reason, because no wet-variant lining is applied. The gate, the refused documented route and the withheld scaled route are unchanged, so even a fully resolved receipt stays noncommercial (no finished-polygon applier exists).

## 3. Tests
`tests/test_room_wet_dry_classification_shadow_v1.py` has 41 tests:
- normalization, and table integrity (duplicate phrase, unnormalized phrase, unknown class);
- each listed class through its rule;
- unlisted phrases abstain (absence of wet never proves dry);
- unauthenticated or unbound labels abstain;
- incomplete scope abstains;
- replay and order invariance, and no mutation;
- consumer lineage: wrong room, revision, source, document, snapshot, page or scope gets no status; conflicting, abstained or forged records leave it unestablished;
- the receipt helper rejects a malformed mapping;
- keyword typing and the parent requirement on both entry points;
- with the flag off, the claim is unchanged;
- end to end on a synthetic plan:
  - a dry label settles only the wet-area reason and still issues no room, floor, finish or ceiling quantity, and the receipt joins to its classification;
  - a wet or unlisted label keeps the reason;
  - without a wet-area variant, the classification changes no receipt.

`tests/test_layered_finished_face_gate_v1.py`: its fixture gains an optional label (default unchanged).

## 4. Validation (local)
- **Mutation:** 11 of 11 mutants killed. They covered the scope-equality guard, the CORROBORATED filter, the conflict rule, number stripping, the lineage guard, the scope guard, the duplicate-phrase guard, whole-phrase matching, the parent-keyword guard, the per-record application and the flag gate.
- **Related suites:** 105 files (ring, wiring, partition, gate, room face, room area, floor area, same view, labels, customer output, handoff), 2417 passed and 8 skipped.
- **Static checks:** compileall and Ruff F821/F823 pass, as do the V2 truth-separation and provider-isolation checks. `check_full_plan_v2_integrity` fails identically on an unchanged checkout on this Windows machine, because autocrlf rewrites 9 frozen JSON files.
- **Historical signed outputs, local:**
  - Lot16: the eight regenerate byte-identically to the archive (`ef58f8ae...`).
  - Maryborough: see section 5.
  - The protected replay is MAX's.

## 5. Result on the original
Run: SHA-authenticated original (`014e9f68...`), plan sheet A0.3 with the build-up statement on A0.7, every control on, glyph-ledger trust, RapidOCR, `room_wet_dry_classification=True`, `PYTHONHASHSEED=0`, local Windows CPython 3.13.15. Wall time 3245 s under heavy machine load; a repeat finished in 2949 s with identical output. Counts and codes only; no drawing text or measurement is recorded here.

| Item | Result |
|---|---|
| Ring faces gated | 2 |
| Rooms carrying an authenticated unique label (existing label authority, `source_room_label_scope_resolved`) | 2 of 2 |
| Wet/dry classifications | 2, both `dry_area`, `CORROBORATED`, reason `room_wet_dry_classified_by_label_rule`, two different listed dry rules |
| Receipt verdicts | 2 `unresolved` (unchanged) |
| `room_wet_area_status_not_established` on a receipt | 0 of 2 (it was on 2 of 2 on main) |
| Remaining receipt reasons | `internal_strip_thickness_not_the_stated_frame` x2, `wall_fill_not_classified` x2, `external_wall_internal_lining_not_stated` x1 |
| Same-view first-failure codes | `same_view_layered_ring_finished_face_not_established`, `same_view_trusted_label_ambiguous` (unchanged) |
| Room, floor, finish or ceiling quantity issued | 0 |

So the classification removes exactly one blocker from a dry room's receipt and no other. The two missing facts MAX named (the strip thickness is not the stated frame, and the wall fill is unclassified) and the unstated external lining are untouched, and nothing becomes a quantity.

Retention (flag off, local):
- Lot16: `source_sealed_run.json` and `verified_customer_rows.json` are byte-identical to the main-generated files; sealed fingerprint `ef58f8ae...`, eight quantities.
- Maryborough: see section 6.

## 6. Not proven here
- The protected original-source replay and the dual-Python CI are MAX's.
- Maryborough three: the flag-off regeneration of the signed floor run on this code, compared with the main-generated baseline, was still running when this head was published. Its result follows in a PR comment; until then it is NOT proven.
- No finished-polygon applier exists, so no quantity can follow from this change.
- The label table covers only the phrases it lists; every other label abstains by design.
