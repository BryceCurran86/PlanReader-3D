# Original PlanReader — VR wall creation and related-page working revisions

Implemented in `pb_vr_wall_create_revision_store.py` and
`pb_vr_wall_create_revision_wsgi.py`, with the VR editor save action.

## What is actually implemented

- Strictly **authenticated working-design wall creation**, with stable
  `vr-wall:<sha>` identity, tenant/source/snapshot scope, explicit
  idempotency keys and optimistic revision comparison.
- One SQLite transaction writes wall geometry, documented assembly scope,
  derived trade work package, a new immutable PDF, independently registered
  affected-page evidence and a new model-revision head. If any page fails
  projection or the PDF is malformed, all changes roll back.
- New user-created segments reject overlapping and mid-wall intersecting\n  previously saved user-created walls on the same level; verified shared\n  endpoints remain possible junctions. Existing source-wall clashes still\n  require the production host's separate topology provider.\n- Each independently verified affected page receives a **blue dashed
  proposed-wall vector** and `PR-W0001` review annotation. Related pages
  missing from the producer's complete census block the entire save.
- Subsequent wall revisions use the prior revised PDF as their parent;
  private per-tenant PDF GET returns immutable historical versions.
- A source-scoped working-wall ledger can be hydrated in the editor's read-only
  scene through `load_created_working_walls`. Every user-authored wall stays
  `renderState: review`, never a false original source witness. Reload the
  workspace after saving so model revision and wall objects are refreshed.
- All default routes preserve original source PDFs and commercial takeoff
  authority. No source-detected wall, job benchmark or approved quote is changed.

## Production integration (mandatory; nothing here deploys itself)

Call `install_wall_creation_schema(connection)` through a trusted application
migration before activating the service. Wire nine **real** server callbacks:

```python
make_wall_create_revision_wsgi_app(
    authenticate_session=authenticated_session_provider,
    load_authorized_workspace=tenant_scoped_source_and_latest_model_loader,
    verify_csrf=csrf_verifier,
    load_project_assembly_profile=project_owned_assembly_loader,
    load_verified_service_routes=trusted_service_route_census,
    load_verified_wall_sheet_coverage=complete_sheet_projection_provider,
    load_original_pdf_bytes=protected_source_pdf_loader,
    get_wall_create_db_connection=tenant_scoped_sqlite_connection,
    verify_unified_document_head=shared_document_head_lock_and_compare,
)
```

These names are **integration placeholders**, not implemented providers.
`verify_unified_document_head` MUST acquire/retain a shared document lock
through the creation transaction and compare other revision streams, the
original source, current working head and source snapshot. Without that
external host-level mechanism, do not expose the write endpoint.

For scene reload, call `make_editor_readonly_wsgi_app(...,
load_created_working_walls=trusted_wall_ledger_loader)`, where the loader
returns `list_created_walls(db, principal, workspace)` under matching grants,
and updates `workspace.scope.model_revision` to include the persisted head.

## API endpoints

- POST `/api/editor/workspaces/{id}/walls/add/commit` — typed wall request
  from `/walls/add/preview` plus `idempotencyKey`. No page coordinates,
  PDF bytes, rate values, source witnesses, approval fields or page names
  are accepted from browser commands.
- GET `/api/editor/workspaces/{id}/walls/created` — private created-wall
  model records for authorized workspace reads.
- GET `/api/editor/workspaces/{id}/walls/revisions/{sha40}/pdf` —
  versioned private working PDF download.

## Essential engineering boundaries before issuing drawings

- This supports **verified new-wall vector proposals** on each page, not
  complete architect/CAD/BIM drafting. An elevation/section registration must
  provide its own independently calibrated PDF vector; the server never
  projects 2D plan segments blindly to other views. The renderer draws a
  single new wall reference line. Full wall width, height, junctions, openings,
  dimension strings, construction details, RCP updates and schedule entries
  still need their own authenticated page-specific producers.
- Working-design walls are separate from original source-extracted canonical
  physical walls and existing corrected-object ledgers. A production host must
  unify **all** model revision streams, coordinate room/topology/MEP and
  invalidate any affected takeoff, approval and quotation. The write service
  deliberately does not publish construction quantities.
- `verify_unified_document_head` is a required integration callback, **not
  evidence that the host already has a locking provider**. The host must
  serialize all competing writers and use a consistent source/working snapshot.
- This service revises a **single original PDF**. An entire multi-PDF drawing
  set needs a cross-document, all-or-nothing transaction. Never label the
  current output an architect-signed or authority-approved revised plan.
- Retention, DB migration rollout, backups, secrets, encrypted storage,
  tenancy indexes, rate approval, audit monitoring and headset regression
  still require production operations validation.

## Tests

```bash
python -m pytest -q \
  tests/editable_3d/test_vr_wall_assembly_dependencies.py \
  tests/editable_3d/test_vr_wall_assembly_wsgi.py \
  tests/editable_3d/test_vr_wall_change_impact.py \
  tests/editable_3d/test_vr_wall_create_revision_store.py
cd vr-editor && npm ci && npm test && npm run build
```

CI: `.github/workflows/vr-wall-assembly.yml` and VR Editor TypeScript.
The frozen PlanReader measurement benchmark and issued output authority must
remain unchanged. Do not activate new write routes before real host callbacks,
shared document lock, authorization regression and pilot plan-set validation.
