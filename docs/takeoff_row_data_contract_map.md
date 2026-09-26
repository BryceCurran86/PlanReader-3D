# Take-off row data contract map

Producer → transformers → database → consumers for `takeoff_rows`, and the
3D records keyed by take-off or mass ids. Everything below is **OBSERVED** in
current functions (2026-09-26, main `c3cdea5`) unless marked otherwise. Where a
defect was found, the fixing PR is named; decisions still open are listed at
the end.

## 1. Canonical layouts

`pb_takeoff_row_contract` (#903) is the single source of field order:

| layout | fields |
|---|---|
| `core` (21) | `workspace_id` + 17 editable fields + `row_role`, `created_at`, `updated_at` |
| `commercial` (26) | `core` + 5 `commercial_authority_*` before the stamps |
| `commercial_provenance` (30) | `commercial` + `ai_baseline_quantity`, `pre_map_quantity`, `pre_map_quantity_status`, `origin` before the stamps |

Every literal `INSERT INTO takeoff_rows` (21 sites, 13 modules) uses one of
these layouts. The drift tests in #903 enforce this, together with the widths
of inline and positional tuples. `TAKEOFF_UNITS` (#909) is the estimator's
unit set, and `save_schedule()` (#911) is the identity-preserving schedule
writer.

## 2. Producers

| producer (module · function) | trigger | layout / builder | owner key and replacement | transaction | identity across re-runs/saves |
|---|---|---|---|---|---|
| auto geometry · `analyse_workspace` → `_replace_auto_rows` | upload/process, *Re-run automatic geometry*, autopilot | core, positional `_takeoff_row()` (keyword-only builder) | `PB Auto Geometry v1.2.19%`, workspace-scoped | rows only (main); rows + envelope + report (#904) | new ids every run (open decision A) |
| ↳ unit rows, facades | `_build_unit_rows`, `_build_facade_rows` | same | nested under the auto prefix | — | — |
| ↳ context floor area (v1.2.24), selected-evidence floor (v1.2.26), room faces (`PB RoomFace v2`) | wrappers of `_build_unit_rows` | same; room faces mapped by name (#902) | nested under the auto prefix | — | — |
| no-AI · `replace_no_ai_rows` | *Build / Refresh take-off from measurements* | commercial, named dicts | `PB No-AI v1.2.16%` | one | new ids every refresh |
| no-AI · `save_schedule_batched` | *Save no-AI take-off schedule* (default route) | commercial or +provenance | whole workspace schedule | one | new ids every save → kept (#911) |
| app · `subscription_takeoff_page` save | *Save take-off schedule* (AI route) | commercial+provenance | whole workspace schedule | per-row commits after a committed DELETE → one (#911) | new ids every save → kept (#911) |
| commercial · `sync_pb_generated_rows` | after every analysis (`refresh_pb_takeoff`) | core, positional `_takeoff_values` | `PB Commercial Takeoff v1.2.25%` | one | new ids every run |
| 3D surfaces · `replace_surface_rows_batched` | *Save provisional 3D surfaces for take-off review* | commercial | `PB 3D Surface Editor v1.2.12%` | one | new ids every save |
| Takeoff Studio · `replace_studio_rows_batched` | Studio save per page | commercial | `PB Takeoff Studio v1.2.11 · page:N ·%` | one | new ids per page save |
| floor mapper · `_replace_generated_rows` | floor mapper per page | core | `PB floor mapper v1.2.7 · page:N ·%` | committed DELETE, then per-row commits (a failure leaves the page partial until the next refresh) | new ids per page save |
| unified building · `sync_rows` | reconstruction sync | core | `PB Unified Building v1.3.9%` | one | new ids per sync |
| review · `merge_rows` | *Merge* in review | commercial | `PB Merge v1.2.26 · rows:…`; inputs recorded for cleanup | one | relinks measurement lines to the merged row |
| AI · `import_ai_result` | *Import this AI draft* | core (+ provenance via `pb_takeoff_accuracy_v125.import_ai`) | none: appends | per-row commits | appends a new set per import (open decision D) |
| mapper · `_ensure_mapper_row` / `mapper_row` | Plan Mapper draw target | core | keyed by (section, element, location, unit) | per-row | idempotent |
| copy to level · `copy_takeoff_rows_to_level` | *Copy rows to another level* | core | skips rows that already exist | per-row | idempotent |
| JobHub · `pull_takeoff_from_jobhub` | JobHub import | core | `source_page='JobHub import'`, workspace-scoped | — | replaced per import |
| CSV/XLSX · `takeoff_import_panel` | file import | core | appends | per-row | appends |
| editable 3D · `_perform_commercial_sync` | approved 3D quantity sync | commercial+provenance | inserts the approved quantity row plus an `editable_3d_commercial_sync_events` audit row referencing it (`ON DELETE CASCADE`) | — | — |

Seeds (*Add standard rows*) and *Clear take-off data* are explicit estimator
actions.

## 3. Transformers

- **Automatic rows:**
  - `_build_unit_rows` is wrapped in startup order: v1.2.19 guard (manual floor precedence), unit gate, context floor area, selected-evidence floor, room face (manual floor precedence #902).
  - `_build_facade_rows` is wrapped by the guard (manual external pages).
- **Validation:**
  - main checks row length and the auto prefix before any DELETE.
  - #909 adds named per-field checks on new automatic rows: workspace, text, finite non-negative numbers, `TAKEOFF_UNITS`, automatic roles and inclusion.
- **`analyse_workspace` wrappers,** inner → outer: memory, unit floor area, material schedule, autopilot (3D model; mass identity #905), commercial refresh, elevation regions, review cleanup of merged inputs (#912), legend register, plan-read engine.
- **Mapped quantities:** `pb_takeoff_accuracy_v125.save_lines` → `recompute` writes the sum of linked lines into the row (`quantity_status='Mapped'`).
- **Migrations at startup:**
  - `_ensure_takeoff_columns` adds every newer column.
  - Units are normalised to `m²`/`lm`.
  - Legacy auto-detected floor rows get `row_role='floor_area'`.
  - The composed app runs init once per process (`pb_db_init_guard_v1215`).

## 4. Database

- **Row owners** (#913): every `DELETE FROM takeoff_rows` is scoped to one workspace. No owner prefix is a case-insensitive prefix of another or contains a LIKE wildcard.
- **Records keyed by `takeoff_rows.id`:**
  - `measurement_lines.takeoff_row_id` has **no foreign key**, so it dangles if the row is re-inserted;
  - `editable_3d_commercial_sync_events.takeoff_row_id` is `ON DELETE CASCADE`, so the audit row is deleted with the row.
- **Records keyed by `model_masses.id`:**
  - `model_openings.mass_id` (`ON DELETE SET NULL`);
  - 3D surface edits `mass:{id}:{face}` in `workspace_settings`;
  - editable-3D corrections and approvals `MASS-{id}`.

  Mass writers keep ids: autopilot #905, Building masses editor #906, Quick 3D #907.
- **Indexes:** `takeoff_rows(workspace_id,id)` and `(workspace_id,row_role,id)`, `measurement_lines(takeoff_row_id)`, `model_masses(workspace_id,id)` and `model_openings(workspace_id,mass_id,id)` cover the replacement and link paths. No new index is indicated.

## 5. Consumers

- Review dataframe `dataframe_for_takeoff` and the per-level summary. `floor_area` rows drive floor-m² pricing and are not priced themselves.
- Take-off QA (`pb_takeoff_accuracy_v125.issues`): non-`UNIT_OPTIONS` units are *Critical*.
- Plan Mapper targets (`takeoff_rows_for_mapper`) offer **every** m²/lm row, automatic rows included.
- Commercial review, export preflight and JobHub (`pb_commercial_review_v161`, `pb_commercial_export_preflight_v163`).
- Canonical 3D diagnostics match v1.3.9 registered-wall rows by the literal prefix `PB Unified Building v1.3.9 · ` (guarded by #908).
- Manual-precedence readers: `_manual_floor_keys`, `_manual_external_pages` (by name), and the guard's positional `row[3]` (location) and `row[9]` (source_page) on builder tuples, which match the `core` layout.

Reads are tolerant of legacy NULLs and units (#915).

## 6. Open decisions (reported, not changed)

- **A. Estimator-mapped generated rows.**
  - **Behaviour (reproduced):** tracing an automatic row in the Plan Mapper makes it `Mapped`, but the next automatic re-run deletes it, republishes the automatic quantity under a new id and leaves the traced lines dangling. Every prefix-replacing generator in §2 behaves the same way.
  - **Options:** mapped rows become estimator-owned and are skipped on re-run, or generated rows keep ids through a keyed update and the mapped quantity is re-applied. Both change commercial rows after a re-run and need an authority review.
- **B. Render "replace" mode.** `apply_render_to_model(mode="replace")`, the Quick 3D default, deletes every non-Measured/Verified mass with its openings, not only AI-assumed masses as its docstring says.
- **C. Overlapping floor-area families.** The page-level fallback floor area and room-face floor areas can both publish `floor_area` rows for the same page. Choosing which wins is floor-area authority.
- **D. AI draft import.** Each import appends a full set of rows.
- **E. Empty quantities.** The schedule save stores an empty quantity as `0` (`_num`).
- **F. Dangling measurement lines.** Lines orphaned by schedule saves before #911 remain in existing databases, and no reliable key exists to relink them.
