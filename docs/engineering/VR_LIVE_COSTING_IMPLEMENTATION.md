# PlanReader VR live costing — source-checked preview contract

**Status:** Implementation of an opt-in server price-preview engine and VR
what-if display. It is NOT a deployed customer quoting or rate-editing service.
Deployment must connect the five production providers described below.

## What is reused

- Existing protected, tenant-scoped **typed correction** and original-source
  witness validation in `pb_vr_editor_command_preview.py`.
- Deep-copy correction ledger replay and supported quantity recalculation in
  `pb_editable_3d_quantity_recalculation.py`.
- Company-owned `CanonicalCompanyRate`, quantity unit normalisation and the
  exact-cent **gross-margin-on-selling-price** ordering of
  `price_canonical_quantities` in `pb_builder_edition_architecture.py`.
- Existing approved commercial takeoff and JobHub publication gates remain
  entirely separate. This module publishes NOTHING.

The browser POSTs the existing typed correction request, NOT a quantity
override, tax selection, rate, quote status or margin. The server proves the
current object revision, document SHA, snapshot and canonical ownership,
recalculates on a copy, then loads a rate book from the authenticated tenant.

### Exact formula sequence (all currency values rounded half up to cents)

Given source-checked previous or proposed quantity `Q` and server-owned
rates/percentages:

1. `material = cents(Q × material_cost_per_unit)`
2. `waste = cents((Q × material_cost_per_unit) × waste_pct / 100)`
3. `labour = cents(Q × labour_cost_per_unit)`
4. `subcontract = cents(Q × subcontract_cost_per_unit)`
5. `plant = cents(Q × plant_cost_per_unit)`
6. `direct = material + waste + labour + subcontract + plant`
7. `overhead = cents(direct × overhead_pct / 100)`
8. `contingency = cents((direct + overhead) × contingency_pct / 100)`
9. `cost_before_margin = direct + overhead + contingency`
10. `sell_ex_tax = cents(cost_before_margin / (1 - gross_margin_pct / 100))`
11. `margin = sell_ex_tax - cost_before_margin`
12. `tax = cents(sell_ex_tax × tax_pct / 100)`
13. `sell_inc_tax = sell_ex_tax + tax`
14. `change = after - before` calculated separately on rounded values.

Tax and contingency are **mandatory explicit tenant policy inputs**, even if
zero. There is no inferred Australian GST percentage, no default company
rates or exchange conversion. When contingency and tax are zero, the
sell-price, direct-cost and margin formulae match the canonical costing engine.
A true 20% gross margin is `cost / 0.80`, **not** a 20% cost markup.

### Test example (illustrative client rates only, NOT market prices)

For an actual protected-source wall changing height from 2.4 to 3.0 m on a
4.0 m length, the independently recalculated gross areas are 9.6 to 12 m².
Using a *test company rate* AUD per m² of materials 12, labour 8, plant 1,
material waste 5%, overhead 10%, true margin 20%, contingency 0%, and
explicit tax 10%:

- Before: direct 207.36; overhead 20.74; sell ex-tax 285.13;
  tax 28.51; sell incl tax 313.64 AUD.
- After: direct 259.20; overhead 25.92; sell ex-tax 356.40;
  tax 35.64; sell incl tax 392.04 AUD.
- The **impact on this single priced gross-area line** is +78.40 AUD inc tax.
  Wall net area and any other recalculated target are still **UNPRICED** until
  independently bound to appropriate company rates. These partial totals
  must NOT be called the total job price.

### Required production integration

```python
from pb_vr_live_costing_wsgi import make_vr_live_costing_wsgi_app

app = make_vr_live_costing_wsgi_app(
    authenticate_session=production_session_auth,
    load_authorized_workspace=tenant_pinned_original_source_workspace_loader,
    load_authorized_ledger=tenant_pinned_correction_ledger_loader,
    verify_csrf=production_csrf_verifier,
    load_authorized_cost_book=tenant_source_snapshot_rate_book_loader,
)
```

This is a **contract**, not preexisting deployed provider names. The application
must supply these five real callbacks, configured for logged-in staff with
`allowed_preview_workspace_ids`. The cost book loader must return immutable
`LiveCostBook` with tenant/workspace/source SHA/snapshot/revision, explicit
currency, tax and contingency, and explicit `LiveRateBinding` entries whose
rate keys and binding provenance are supplied by the server. Missing evidence
or rate entries cannot be converted into free work.

`POST /api/editor/workspaces/{workspace}/costing/preview` returns
`quantityPreview` (existing source-checked response) and `costingPreview`
(cent-exact subtotal/delta and every unpriced target). Denied source commands
return 409/422 with NO costing result. Unauthorized callers are denied before
workspace or rates can be fetched. No rates are accepted from browser JSON.
The endpoint is same-origin, no-store, CSP-bound, CSRF-protected and has a
32 KB body cap. All money is represented as exact **decimal strings** over
the wire.

The browser retains the existing **Preview quantity only** path. A second
**Recalculate live costs** button calls the new server endpoint and validates
component footing, rate/source snapshot identity and all affected quantity
targets before displaying any money. Changing a field aborts/invalidates
stale results. All responses always report `quoteReady=false`,
`requiresApproval=true`, `persisted=false`,
`commercialPublicationAllowed=false`.

### Versioned company rate book adapter (optional SQLite)

The additional `pb_vr_live_ratebook_store.py` implements opt-in rate-book
persistence for teams using SQLite. It is **not** an anonymous rate editor.

- Run `install_rate_book_schema(connection)` only in deployment migration.
- Real role-aware admin code calls `activate_rate_book(connection, principal=...,
  workspace=..., book=..., authorize_rate_manager=...)`. The last callback must
  independently confirm the user's company financial administration permission.
- The rate revision is immutable; changing any price requires a NEW revision.
  Historical revisions remain stored; the active revision pointer changes
  only by explicit authorized action.
- Only canonical objects that match the protected original-source witness
  may receive bound rates in the stored book.
- For read/preview, connect
  `load_authorized_cost_book(connection, principal, workspace)` through the
  production repository callback. It refuses missing, corrupt, cross-tenant
  or stale-source snapshots and never creates default prices.
- A source SHA/snapshot change requires re-attesting a rate book to the new
  source. Do NOT expose its SQLite DB or any raw rate-book file through a
  public repository, CDN or unauthenticated endpoint.

This adapter provides local/server storage semantics, **not** a hosted
company-admin management interface, supplier live pricing connector,
deployment migration of existing user data, or verified customer quote.

### Release gates not completed by the formula code

- Connect tested production tenant rate-book storage and a versioned rate
  management UI with real company material/labour/subcontract/plant prices.
- Verify source-complete wall faces, finishes, floors, openings, ceilings and
  quantity-to-trade-rate bindings from the original protected drawings.
- Publish only via existing commercial approval and JobHub signoff, not this
  preview. A cumulative multi-edit quote needs independent transaction and
  duplicate-quantity reconciliation.
- End-to-end tenant session/CSRF deployment, VAT/GST jurisdiction configuration,
  review by a licensed estimator, and real headset acceptance.
- Frozen four-project 120-item denominator and signed Lot16 opening areas
  remain untouched. The test rates above must **never** be used as defaults.

To run focused tests:

```bash
python -m pytest -q tests/editable_3d/test_vr_live_costing.py tests/editable_3d/test_vr_live_costing_wsgi.py tests/editable_3d/test_vr_live_ratebook_store.py
cd vr-editor && npm ci && npm test && npm run build
```

### Interactive live refresh

The pricing panel also offers opt-in **Live update after changes**, off by
default. Once an authenticated canonical object, complete positive correction
value and an evidence reason of at least eight characters are supplied, it
waits 650 ms after the latest change and POSTs a fresh source-checked preview.
Changing a field aborts prior in-flight requests, invalidates old figures and
rejects stale receipts. The client never calculates sell prices from its own
inputs. When **zero lines** can be priced, the display says UNPRICED rather
than showing a misleading 0.00 job cost.
