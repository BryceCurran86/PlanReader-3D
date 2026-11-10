# Door-height owner decision memo (2026-11-02)

**Status.** Decided 2026-11-02: Option A, keep abstaining (section 7). Docs only; no code, test, workflow or truth change. It grants no authority, implements no default and is not an input to any producer. It follows candidate 1 of `claude_accuracy_gate_census_report_20261102.md` and the open decision in section 4 of `ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`.

## 1. The question

Several Lot16 openings have no source-stated second axis. Either keep abstaining on them, or approve a height under the existing `USER_APPROVED` authority as an explicit, reviewable record (source, scope, approver), never an inferred or AI default.

## 2. What the repository already has (observed)

- `AuthorityStatus.USER_APPROVED` and `MeasurementAuthorityType.USER_APPROVED` (`pb_geometry_takeoff_model.py`). JobHub refuses a `USER_APPROVED` row without a named approver (`pb_jobhub_publishing_contract.py:395`).
- A per-opening approval pattern that already works for **width**: `_build_approved_single_width_review` in `pb_nominal_opening_canonical_shadow.py`. It requires an existing `MeasurementRecord` whose `approved_by` is non-empty, `approved_at` is a timezone-aware timestamp, `geometry_ref` equals the physical opening id, the page and the source owners (document, revision, sha256, snapshot) match, the value equals the printed label, and it refuses to override a schedule or a resolved source width. The result keeps `takeoff_eligible=False`, `deduction_authority=False`, `height_resolved=False`.
- `pb_door_height_owner_gate_shadow.py` (70 lines): takes a bare `user_approved_height: bool` and a float. It carries no approver, no scope and no source binding, so a caller can assert approval with a flag. It is shadow-only and publishes nothing, but it is the weak link if a height approval is ever consumed.

## 3. What the census says about the value of deciding now (observed, Lot16 on `main` `86c0193c1`)

Of the 13 unsigned openings, only **1** is blocked first by the second axis. The other 12 fail an earlier gate: 6 have no authenticated host, 3 have a host and no whole-wall frame, 3 have a frame and an unproven door/window kind. So a height approval moves one opening now, and the rest only after host, frame and kind are resolved by their owners. It is the last gate for most of them, not the first.

## 4. Options

| | Option | What the owner records | Risk |
|---|---|---|---|
| A | Keep abstaining (status quo) | nothing | no new door areas |
| B | Approve a height **per opening** | one `MeasurementRecord` per opening: `axis="height"`, value in mm, `approved_by`, timezone-aware `approved_at`, `geometry_ref` = physical opening id, source owners, basis text | one approval per door; slow, but each is exact and auditable |
| C | Approve **one project-scoped** height for a named list of opening ids | one approval event that expands into explicit per-opening records for the listed ids only | a convention applied to ids the owner has not individually looked at; acceptable only if the list is explicit and the basis is written |

Never acceptable: a global or inferred default (`2100`, `2400`, `2.8 m`), a height read from a datum label, or any record with no approver.

## 5. Recommendation

Option A for now, with Option B recorded as the allowed path. Reason: section 3 shows a decision moves one opening today, so it should wait until a host, frame or kind gate releases more of them, and it should then be made per opening so every approval is exact. If the owner prefers Option B or C now, the next work is design-only: a height analogue of the width approval above (same record shape, `axis="height"`), plus replacing the bare flag in `pb_door_height_owner_gate_shadow.py` with a record check. Neither would publish a quantity.

## 6. Not decided here

Distinct reviewer identities (B1 in the levers document), any opening-count or frame claim, and any change to a signed output.

## 7. Owner decision (2026-11-02)

**Option A: keep abstaining.** The owner chose this in chat on 2026-11-02. Consequences:

- No door-height approval record is created, and no height is supplied by default, convention or datum label.
- `pb_door_height_owner_gate_shadow.py` stays as it is (shadow-only, publishes nothing). Its bare `user_approved_height` flag is not consumed by any producer, so nothing changes.
- Option B (per-opening approval) stays the allowed path. Revisit it when host, frame and kind gates release more openings (section 3); it needs a fresh owner decision then, not this one.
- No code, test, workflow, threshold or truth change follows from this decision.
