# OFFICE FT3 floor finish: where the p11 mark meets the p7 floor (architecture report, 2026-11-07)

Owner handover 2026-11-06; MAX file ownership [#4135 comment 6693817568](https://github.com/BryceCurran86/PlanReader-3D/issues/4135#issuecomment-6693817568); my claim [#4135 comment 6694023764](https://github.com/BryceCurran86/PlanReader-3D/issues/4135#issuecomment-6694023764). Base: MAX's integration head #4224 (`4caa71a92`, contains the accepted F07 binding). Docs only: no code, no quantity, no customer row, no score claim.

## Observed repository behavior

- `CrossViewFloorFinishProducer.publish` (`pb_cross_view_floor_finish_authority.py`) issues a FIRM `floor_finish_area` (authority `DOCUMENTED_DIMENSION`, formula `authenticated_cross_view_room_area_with_source_finish`) whose value is the documented figured-dimension room area, for a physical floor and one source finish occurrence found inside that area's dimension box. The binding predicate is therefore also the commercial gate.
- In the source-owned plan-view mode (`for_source_owned_plan_view_shadow`, driven by the material producer's F07 plan views) `_source_owned_mark_eligible_for_existing_physical_floor` returns `floor.page_id == occurrence.page_id` and nothing else. A p11 FT3 mark can never bind to a p7 canonical floor. Its docstring states the missing input: an independently issued cross-sheet structural correspondence receipt. Same-view and default-mode behavior is unchanged.
- The only typed producer of such a receipt is `SourceCrossViewFloorCorrespondenceProducer` (`pb_source_cross_view_floor_correspondence_shadow.py`). Its records are `CANDIDATE` with `commercial_projection_allowed=False`, `takeoff_eligible=False` and the standing blockers `support_page_has_no_source_owned_room_face_or_label_authority` and `no_physical_wall_equivalence_authority_for_box_sides`.
- Measured today (`tools/diag_ft3_p11_p7_floor_correspondence.py`, SHA-original Maryborough, current head, local run, counts and statuses only): the p11 to p7 registration is unique (identity, scale 1, translation -78 pt in x, wall-derived; 3.66 times the strongest competitor). Of the three measured rooms, **one** is a geometric candidate and two abstain:
  - OFFICE: `candidate`, reason `floor_geometrically_owned_equivalence_not_authenticated` (the box is wall-bounded on both sheets, exactly one FT3 mark inside, no other finish code).
  - FOOD PREP: `abstained`, `box_not_wall_bounded_on_both_sheets`.
  - COLD ROOM: `abstained`, `wall_evidence_differs_between_sheets` and `box_owned_by_other_finish_code`.
- The accepted F07 scope on p11 (MAX: 1 CORROBORATED complete scope, 52 records, 0 unresolved words) supplies the FT3 occurrence and the plan-view ownership; it does not supply equivalence.

## Inference

- OFFICE is exactly one authority short of a bound FT3 floor: *the box sides on p11 and p7 are the same physical walls* (`no_physical_wall_equivalence_authority_for_box_sides`, here surfaced as `floor_geometrically_owned_equivalence_not_authenticated`). That is W4 SAME/DISTINCT identity (AntiGravity and MAX), together with the finished-face ring and the D15 threshold transition the handover requires. It cannot be produced by the issuer.
- The first blocker (`support_page_has_no_source_owned_room_face_or_label_authority`) is plausibly narrowed by the accepted F07 plan view and trusted label words, which is in my lane; but closing it alone leaves the floor `CANDIDATE`.
- A consumer seam in the issuer that accepts a correspondence record would, today, accept nothing: every record is `CANDIDATE` with blockers. Building it first would define what a promoted record looks like (which fields, which status, who sets `takeoff_eligible`), and that is an authority-promotion decision, not an issuer detail.

## Addendum 2026-11-07: material authority is closed, equivalence is the only gap

- Counts from the accepted F07 scope (`SourceMaterialSemanticProducer.for_physical_plan_view_shadow` on p11 with `source_native_finish_text_shadow=True`, SHA-original, local run under a minute, counts only): 1 plan viewport, 1 CORROBORATED complete scope, 52 records: FT1 x2, FT2 x8, FT3 x5, WA02 x1, WA03 x14, WA04 x16, WA05 x2, WA09 x4. The definitions of FT1, FT2, FT3 (tile), WA02 (roofing) and WA03/04/05/09 (plasterboard) are all CORROBORATED. The earlier diagnostic's "material authority still required" (it ran without the F07 supplier: 0 material occurrences) therefore no longer applies; what remains is the authenticated equivalence.
- The existing typed equivalence record, `PhysicalWallEquivalenceResolution` (`pb_physical_wall_identity.py`), is scoped to ONE viewport (`scope_viewport_id`) and classifies wall candidates within it. No existing record binds wall candidates of one sheet to wall candidates of another under a registration. The correspondence shadow derives that geometrically (unique registration, per-side kinds, identical wall evidence on both sheets) but, by design, only as a CANDIDATE. The record AntiGravity and MAX would have to supply is therefore a cross-sheet one: for each of the four OFFICE box sides, the p7 wall candidate ids and the p11 wall candidate ids that are the same physical wall under the unique registration, each side's per-sheet identity taken from `PhysicalWallEquivalenceResolution`, ambiguity retained.

## Proposed (nothing built in this change)

1. Do not add the consumer seam until a typed equivalence record exists. When it does, the seam is a single default-off predicate in `_source_owned_mark_eligible_for_existing_physical_floor` that accepts a correspondence record only if: exact document, revision, source hash and snapshot; unique match on canonical floor, physical room, source room-face record, support page, target page and the occurrence's material code; status CORROBORATED and no authority blockers; no rival record for the same floor or code; the occurrence box inside the record's support dimension box. With today's CANDIDATE output the behavior is byte-identical.
2. Ask AntiGravity and MAX for the typed record that carries *physical equivalence of the box sides across p11 and p7* (candidate home: the existing W4 identity/equivalence records), plus the OFFICE finished-face ring and D15 threshold records, through existing typed producers. My issuer consumes them; it does not mint them.
3. In my lane meanwhile: measure blocker 1 on the original (does the accepted F07 plan view plus trusted OFFICE and FT3 words satisfy a source-owned label authority for the support page?) and report counts; any resulting producer change goes through a precise claim first.

## Not changed / not claimed

No finished-face proof, threshold or D15/D13 proof, FT2/FT3 quantity, ceiling zone, customer row, or change to the provisional 9/120 count. Existing signed Office room area is not an FT3 quantity.

## Benchmark observations that must not influence implementation

Which rooms abstain, the signed room areas and the item counts are observations of failure modes only. No threshold or rule is derived from them; the proposed rule is an exact identity test on typed records.

## Tests the eventual seam needs

Synthetic positive with a fully qualified record; look-alike negatives (CANDIDATE status, remaining blockers, wrong floor, wrong code, wrong page pair, stale snapshot, forged ids); ambiguity (two matching records, one rival record); input-order invariance; translation, rotation and scale metamorphic variants of the underlying geometry upstream; no mutation; deterministic replay; proof that default-mode and same-view quantities are byte-identical.
