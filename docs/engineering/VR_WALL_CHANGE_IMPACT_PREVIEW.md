# VR added wall — scoped construction cost and related-sheet preview

## Integration in original PlanReader

The original `pb_vr_wall_assembly_wsgi.make_wall_addition_scope_wsgi_app`
still performs authenticated session/CSRF/snapshot checks, looks up a
server-owned project wall assembly specification and verifies service routes.
It now optionally accepts:

- `load_proposed_wall_rate_book(principal, workspace, assembly_profile_id)`,
  returning a typed `ProposedWallRateBook` for the **logged-in tenant**
  and exact workspace/profile. The server owns rate identifiers, currencies,
  revision IDs and unit costs. Do not take price amounts from browser commands.
- `load_related_page_census(principal, workspace, wall)`, returning a typed
  `ProposedRelatedPageCensus` for the **exact original PDF SHA** with
  independently verified same-document sheet registrations. An incomplete
  census must declare `complete=False` and never fabricate affected sheets.

The wall scope calculator emits explicit opening, bracing, framing, lining,
skirting, electrical and hydraulic holds when designs are not specified.
The `impactPreview` response adds exact-cent pricing for the **known**
construction lines, an explicit `unpricedLines` list, a `pricedComplete`
flag, and the verified related page register. The VR editor displays the
preliminary subtotal, incomplete scopes and document coordination list.
Opt-in live mode re-runs this on edits after a 700 ms pause without adding
those transient edits to the local multi-wall batch.

## Deliberately not a production wall-create or drawing-issue endpoint

The endpoint is `POST /api/editor/workspaces/{id}/walls/add/preview`.
Every response is `reviewOnly=True`, `wallCreated=False`,
`relatedPagesRevised=False`, `persisted=False`, and
`commercialPublicationAllowed=False`. Its quantity receipts are not
original-source dimensional authority and cannot be used to bypass
the quantity, quoting or JobHub approval gates. `pricedSubtotalOnly` is
a **direct cost subtotal**, not the full tender/quote: it excludes
unpriced lines, overhead, gross margin, contingency, tax and additional
coordination work.

For a complete production feature, engineering must still provide a
server-authenticated wall-create transaction with stable canonical wall
identity, host/room topology validation, clash checks and audit/idempotency;
a revision transaction that reprojects the new geometry across each
independently registered floor plan, elevation, RCP, section and schedule
without overwriting original drawings; and an approved company costing
policy with waste, labour, overhead, margin, tax, subcontract and review
gates. A rate book alone never authorizes those operations. Cross-PDF
relationships require a multi-document, all-or-nothing transaction.

**No provider callback is implemented by these examples.** Production must
install real tenant-scoped loaders and fail closed for missing or stale data.

## Validation

```bash
python -m pytest -q tests/editable_3d/test_vr_wall_assembly_dependencies.py tests/editable_3d/test_vr_wall_assembly_wsgi.py tests/editable_3d/test_vr_wall_change_impact.py
cd vr-editor && npm ci && npm test && npm run build
```

The focused two-version Python matrix lives in
`.github/workflows/vr-wall-assembly.yml`; the VR editor build has a
separate TypeScript workflow. Do not merge while either is red or unverified.
