# PlanReader edit → related-page drawing revision

**Implementation:** `pb_plan_edit_revision_bundle.py`, `pb_plan_edit_related_page_resolver.py`, `pb_plan_edit_revision_store.py`, `pb_plan_edit_revision_wsgi.py` plus the VR editor Save and Revision History panels.

## What is saved

For a source-verified correction to a PlanReader editable wall/surface, the opt-in revision service:

1. Authenticates the actor with an explicit **revision-save grant**, stronger than ordinary viewing or correction preview.
2. Verifies the exact original drawing document, source bytes SHA-256, source snapshot, object revision and physical/canonical ownership using the existing typed command preview.
3. Requires a server-owned, complete universe of *related pages*. For cross-sheet pages, `CrossSheetRegistrationAuthority` must have a producer-corroborated source callout and unique target physical object. Guessing from the same room name, wall label or drawing title is not allowed.
4. Builds a new PDF without overwriting the original. Each verified affected page gets a visible `PR-R0001` etc review annotation and, **only if an original-source location was independently proved**, a region outline. Every unrelated page remains unchanged.
5. Atomically saves the existing `editable_3d_correction_events` event, the `editable_3d_object_state` current object, a new immutable PDF blob, a per-page provenance/coordination manifest, and the new revision head using a single SQLite transaction.
6. Exposes tenant-checked revision history and a private downloadable PDF. The next correction gets `PR-R0002` based on the prior revisioned PDF, preserving prior page notes.

Saved copies are **review/coordination drawings**; the PDF vector lines and dimensions on the original elevation/section have **NOT** been automatically redrawn. This is deliberate: the current correction has a 3D measurement, but not automatically the local 2D native vector on every corroborating elevation or section. A false visual redraw would be unsafe. Original PDFs are preserved by SHA; every saved edited PDF is separately hashed and versioned.

## Wiring to the production PlanReader application

This is an **opt-in WSGI endpoint factory**. The eight callbacks below are integration interfaces, not already deployed functions:

```python
from pb_plan_edit_revision_wsgi import make_plan_edit_revision_wsgi_app
from pb_plan_edit_revision_store import install_plan_edit_revision_schema

# Run once as part of an authorized application DB migration:
install_plan_edit_revision_schema(application_sqlite_connection)

app = make_plan_edit_revision_wsgi_app(
    authenticate_session=production_session_verifier,
    load_authorized_workspace=tenant_scoped_workspace_and_original_lineage_loader,
    load_authorized_ledger=editable_3d_event_replay_and_quantity_loader,
    verify_csrf=production_csrf_verifier,
    get_revision_db_connection=tenant_scoped_fresh_sqlite_connection,
    load_original_pdf_bytes=protected_original_document_blob_loader,
    resolve_verified_related_pages=complete_cross_sheet_source_page_resolver,
    resolve_workspace_database_id=trusted_integer_workspace_db_id_loader,
)
```

**None** of the above illustrative callback names is an implemented app provider. The user-provided browser command must not provide file paths, page lists, physical receipts, rate fields, geometry authority, target page indices, or a `complete` flag.

The server resolver should construct `RelatedPageCoverage`, optionally through `corroborated_related_page_coverage()` with a complete producer-owned candidate-page census and `CrossSheetRegistrationAuthority`. If a related page is missing, ambiguous, cross-project, stale, or uncorroborated, the revision refuses to save; it does NOT silently issue a partially updated drawing set. The original page source witness must be exact. This implementation supports every related page **within a single original PDF**. Cross-document links in separate PDFs require a multi-document transaction and an independently verified source-SHA mapping for each PDF before claiming the entire uploaded plan set was revised.

The production workspace loader must replay the persisted editable-3D correction events, surface the new object revision, and increment `modelRevision` from the `plan_edit_revision_heads` row on the next load. Never reuse the prior head as an accepted new edit. The source SHA and original PDF revision remain the original immutable provenance; `PR-Rxxxx` is a **working-plan revision ID**, not a fabricated source-architect revision.

The current Streamlit `pb_editable_3d_inspector_panel.py` uses its existing standalone correction pathway; it is **not automatically wired to this revision service**. To make every existing Streamlit edit use these transactions, deploy the same service in that panel with genuine original-source and cross-sheet loaders, replacing rather than duplicating its `_save_correction()` call. Do not enable write grants for unsupported workspaces or silently create a PDF from an unverified source.

## Endpoints

- `POST /api/editor/workspaces/{id}/revisions` — existing typed edit command, CSRF + authenticated `allowed_revision_workspace_ids`; returns saved `revisionId`, `revisionLabel`, per-page evidence, and private download URL. Requires all source and page checks, no rate/pricing/publish fields.
- `GET /api/editor/workspaces/{id}/revisions` — read-only private revision history, sorted newest first.
- `GET /api/editor/workspaces/{id}/revisions/{revisionId}/pdf` — private immutable revised PDF download; no unauthenticated source file URLs.
- Existing `GET .../manifest` and `POST .../commands/preview` are passed through unchanged.

An editor user must explicitly choose **Save new plan revision and linked pages** after a successful correction preview. The app shows the sheet list, saves the model-event history in the same transaction, and provides the PDF link. The History section permits retrieving older versions.

## Guardrails and remaining engineering

- Revision is not approval: existing takeoff/quote/JobHub publication gates remain independent. Each correction clears prior geometry approval.
- The new PDF does not magically redraw wall lengths, openings, ceiling heights, or finishes on every elevation. To render actual revised 2D geometry, a future producer must provide source-page-specific native primitives, calibrated transforms and verified, reversible update operations.
- Stored PDF BLOBs are intended for an authorized private SQLite-backed deployment. Plan retention, encryption at rest, backup/restore, size quotas, signed PDFs and XFA forms need the host's operational policy.
- The existing Streamlit app and external VR server require production callback wiring; tests use explicit authenticated fixtures, **never** production source PDFs. The frozen 120-item evaluator and Lot16 signed opening areas are untouched.
- Revision history belongs to the original document/source snapshot. Cross-source PDF bundles, full commercial remeasurement and multi-object transactions need additional work.

### Focused tests

```bash
python -m pytest -q tests/editable_3d/test_plan_edit_revision_store.py tests/editable_3d/test_plan_edit_revision_wsgi.py
cd vr-editor && npm ci && npm test && npm run build
```

## Independently source-verified 2D vector revision overlays

When *all* independently discovered related pages contain a producer-confirmed
source PDF native stroke, a page-specific calibrated new vector, and a source
correction receipt for the current command, PlanReader can add an actual new
PDF vector line to each related sheet. The original native line stays intact
as a reversible reference; the new line is highlighted **PROPOSED VECTOR
(REVIEW)**. This is not a destructive original CAD rewrite or an architect's
signed revised drawing.

Use `RelatedPageCoverage.vector_overlays` only from the protected
source/vector registration provider, with
`vector_projection_complete=True` **only** if every related page is
independently verified. Missing/mismatched page geometry, ambiguous original
PDF line, rotated page without calibrated transform, orphan command receipt,
or a repeated geometry stroke aborts the entire save transaction. The
client cannot submit these vector overlays in the HTTP request.

The returned `pagesRevised[]` now contains `vectorGeometryOverlayDrawn` and
`vectorOverlayKind`; the saved revision summary contains
`sourceVerifiedVectorOverlayComplete`. `geometryRedrawn` remains false
because the original architectural drafting is preserved and the overlay
has not replaced the native source. This is an explicit step toward
cross-sheet geometric coordination, not a claim of full BIM re-projection.
