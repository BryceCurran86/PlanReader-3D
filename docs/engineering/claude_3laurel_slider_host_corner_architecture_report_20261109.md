# Claude: 3Laurel two-figure sliding door `b5091e15` and the three external doors. Architecture report (no code change)

Date: 2026-11-09. Base `origin/main` `22ebd4e3c`. Branch `claude/3laurel-slider-host-corner-report-20261109`. **Docs only. No production module, test, benchmark-defining file, identity map, signed fixture, snap (2.5 pt) or primitive cap (20 000) is changed.** Ids are short suffixes, counts and point coordinates only. No private drawing text, names or addresses are repeated. This is the report `AGENTS.md` requires before a change. **Stop for review.**

## 0. Compliance block (AGENTS.md)

- **Read this session:** `AGENTS.md`; MAX instruction block of 9 Nov (pasted by the owner); the shared-pier and door-audit reports of the same day. `docs/AI_ENGINEERING_PLAYBOOK.md` was **not** re-read in this session.
- **Traced (real call path, 3Laurel page 3, original read in place, RapidOCR environment):** `recover_source_opening_areas` → `compose_live_wall_opening_authority` → `PhysicalOpeningAuthority.prove_existence` → `OpeningHostBindingProducer.publish` (`_local_boundary_clean_host_scope`, `_resolve_two_face_lineage_host`, `_resolve_two_face_reveal_stub_flank_lineage_host_from_records`, `_resolve_host_bands`, raster fallbacks) → `compose_live_physical_opening_voids` (`OpeningLabelDimensionProducer.publish_scope`, `_canonical_opening_area`) → `publish_live_opening_area_quantities` (`_opening_quantity`).
- **Authority boundaries crossed:** none changed. Every seam was only called, through read-only wrappers that log and return the original value.
- **Untouched (and will stay untouched until review):** every `pb_*.py`, `tools/`, `benchmarks/frozen_holdout/full_plan_v2/`, `documents/sources/`, both identity maps, the signed Lot16-eight and Maryborough-three baselines, `takeoff_eligible=False` on W10.

## 1. Observed repository behaviour (3Laurel original `014e9f68…`, page 3, `22ebd4e3c`)

| Fact | Observation |
|---|---|
| Physical opening existence | **All 23 mapped ids exist** in the current run (180 existence records, all `jamb_bounded_two_face_interruption`). Physical identity is stable; 19 of the 23 reach a sealed quantity, 4 do not |
| `b5091e15` existence | `CORROBORATED`, 6 source lines: 4 wall-face reveal stubs and 2 jamb lines, gap 42.8 pt |
| `b5091e15` label | `OpeningLabelDimensionProducer` resolves the printed two-figure label with a door token: area **3.15 m²**, basis `figured_opening_label`, kind `door`, label record present. **The label is not the blocker** |
| `b5091e15` host | `OpeningHostBindingProducer.publish` returns `ABSTAINED`, reason `no_authenticated_host_wall_band`. `host_wall_id`, `host_binding_record_id`, `host_frame_record_id` are all null |
| Why no quantity | `_opening_quantity` (`pb_live_opening_area_quantity_publication.py`) returns `None` unless `host_wall_id` and a host binding/frame record are present. The sealed run therefore has no row for it |
| Local host scope | `_local_boundary_clean_host_scope` keeps **2** candidates for the slider (hosted controls: 4 and 5) |
| Lineage | `_resolve_two_face_lineage_host_from_records` needs each of the 4 face lines to be owned by a W4 candidate. Owners for the slider: north-left stub `e11d3ff5` (a chain whose overall direction is not parallel to the opening axis, so `_candidate_locally_participates_in_two_face_band` excludes it), south-left stub `2950cdad`, **north-right stub: none, south-right stub: none** |
| Right flank | The two right stubs are 4.68 pt and 2.13 pt long and end at the faces of a perpendicular wall (the corner with the wall that hosts the neighbouring garage personnel door). No collinear wall face continues past either stub |
| Existing stub resolver | `_resolve_two_face_reveal_stub_flank_lineage_host_from_records` is built for reveal stubs between two **collinear** flanking walls. It requires a flanking face primitive continuing past each stub's outer end on both flanks, so it abstains (`opening_two_face_wall_lineage_unmapped`) at a corner |
| Remaining fallbacks | `_resolve_host_bands`, whole-wall, split-centerline and raster-primitive all return `CORROBORATED` with zero bands. `_resolve_raster_source_band_host` is gated on `scope_complete is True`, which is false for this page |
| Class size | 93 of 180 page-3 openings are `no_authenticated_host_wall_band`; 21 of them have exactly 2 of 4 face lines unowned (the slider's profile). This is a general wall-candidate coverage gap, not a slider special case |

### External doors `22e7e155`, `be1e67bf`, `9d4dc1b3` (item 2)

- Each carries one printed width only, no door token; canonical `opening_kind` is `None` and `area_m2` is `None` for all three. `22e7e155` and `be1e67bf` are also hostless (`no_authenticated_host_wall_band`); `9d4dc1b3` is hosted.
- **Door height in the original (all 18 sheets scanned for text, read in place):** there is **no door or joinery schedule**. The plan labels print width only. Two elevation sheets print a **general note giving a default joinery head height unless noted otherwise** and a height chain beside the façade. Neither is a per-door height, and the note's exception clause means it cannot be bound door by door without a plan-to-elevation identity that no existing authority supplies. The core run executes page 3 only, so even a printed elevation dimension would not be in scope.
- **Decision on evidence:** the source does not establish a height for these three doors. They stay ABSTAIN. The precise missing evidence is a per-door height (schedule row, elevation dimension bound to that door, or an owner-approved record under `--owner-door-height-approvals`). Whether a printed general joinery note may ever count as that evidence is an authority-promotion question for MAX, not something this report assumes.

## 2. Inference

1. The slider's quantity is blocked at exactly one gate: **host binding**, caused by a **corner**: its right flank is a short reveal stub running into a perpendicular wall, so no right-flank owner exists and every existing host path needs one.
2. The earlier audit line "cause inferred from the removed uniform-height shadow" was only right for the three single-figure doors; it was wrong for the slider, which is two-figure and never depended on a height.
3. A repair that adds right-flank owners by changing W4 candidate assembly would move 93 hostless openings and every wall topology result. That is the wrong blast radius.

## 3. Proposed change (shadow only; nothing below is implemented)

A new opt-in, default-off host rule **`corner_terminated_two_face_reveal_stub_host_shadow`**, reusing `EvidenceResolutionStatus`, the existing `_HostBand` and equivalence helpers; no second vocabulary:

1. Existing proof stays: two positive-gap face pairs plus two jambs.
2. One flank maps through the existing stub-flank lineage rule, on **both** faces, to **one** unambiguous equivalence group.
3. The opposite flank's two reveal stubs each end on a face line of an authenticated **perpendicular** W4 candidate (usable, source-lineaged), and the two stub-to-wall offsets equal that wall's thickness.
4. No collinear face primitive continues past either stub (otherwise the existing path applies).
5. Anything else (ambiguous equivalence, two possible left owners, a free-standing stub, no terminator) abstains. All plausible owners are retained, never nearest, first or smallest.
6. Output is a shadow host band with a distinct reason code. It does not set `takeoff_eligible`, does not enter `publish`'s default result and does not change any sealed or customer row.

**Rejected alternatives:** retaining short stubs in W4 globally (blast radius above); waiving the host requirement for figured-label quantities (changes quantity authority semantics, MAX's call); nearest-wall binding (forbidden).

## 4. Proof plan (synthetic first, then shadow replay)

Positives: corner-terminated reveal stub on each of 4 orientations and both handednesses. Look-alikes that must abstain: stub into a free-standing pier, stub into a wall of the wrong thickness, stub with a collinear continuation, stub into a perpendicular wall that is itself ambiguous. Metamorphic: translation, rotation, uniform scale, mirror. Invariance: input order, segment splitting, unrelated content, viewport expansion. Deterministic replay, stable ids, no input mutation. Live-prediction proof: with the flag off the 3Laurel claim, Lot16 signed eight and Maryborough signed three are byte-identical; with the flag on, every newly hosted opening is listed with its first remaining gate, and no signed row changes.

## 5. Benchmark observations that must not influence implementation

Item ids were read only to compare which production ids the existing identity map already binds. No expected quantity, tolerance or BOQ value was read. The 3.15 m² above is the printed two-figure product the producer already issues, not a target. The rule in section 3 is defined from drawing geometry alone.

## 6. Not proven

Protected-environment (Tesseract) behaviour; Python 3.14 (public CI only); that the corner rule is sufficient for any other opening in the 21-opening class; that a host binding from this rule would be accepted by authority review. No quantity, score or authority is claimed. No benchmark item is newly eligible.
