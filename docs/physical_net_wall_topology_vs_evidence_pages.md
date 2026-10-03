# Physical net-wall chain: topology pages versus evidence pages

Status: DRAFT authority transition, customer path only. Not active, not mergeable, until GPT Max explicitly reviews this customer-output transition (normal CI does not count). Base: `origin/main` a703af84.
Labels: OBSERVED = executed or traced here. INFERENCE = derived. CONTROL = compared with V2 truth read-only; never an input.

## 1. Observed repository behaviour
- `pb_auto_geometry_v1219._try_physical_net_wall_rows` sends every selected sheet of a source to `collect_live_physical_net_wall_claim` as `pages=`. For the real Lot16 plan set that is 11 of 13 pages (cover, site, plan, four elevations, roof, section, two detail sheets).
- `collect_live_physical_net_wall_claim` passes that one page set to `compose_live_wall_opening_authority(page_ids=...)`, so walls, openings, host binding, completeness, canonical walls/rooms/floors and the customer coverage registry are all composed for every selected sheet.
- `compose_live_gross_wall_geometry` requires every page in `wall_opening_composition.page_ids` to have a CORROBORATED, `scope_complete` wall scope, else the whole claim is blocked (`live_gross_wall_geometry_wall_coverage_incomplete`). The same function registers each plan wall to every other decoded page, and `CrossSheetRegistrationProducer.publish` returns `cross_sheet_registration_target_page_unresolved` unless the TARGET page's wall scope is corroborated with records.
- The extractor (`pb_planreader_pdf_extractor._is_physical_floor_plan_page`) passes only source-classified floor-plan pages. INFERENCE: that leaves no elevation target in the decoded universe, so cross-sheet wall height cannot register there.
- INFERENCE: neither path can publish a net-wall claim on a real multi-sheet set. The customer path is blocked by the coverage firewall on non-plan sheets; the extractor path starves height registration. The chain has no first-class evidence-only page.
- OBSERVED, real Lot16 customer run (13-page plan set, 11 selected): 740 canonical objects (577 walls, 163 openings). Per-page census of the 163: elevations and sections each carry 9-21 "openings" and some even get host bindings. Only the floor plan sheet carries 28.

## 2. Proposed change (customer path only)
1. `pb_source_floor_plan_page_scope.py` (new): classifies selected pages from source evidence only. A page is a floor-plan page when the page-title authority binds an explicit drawing title that classifies as a floor plan (multi-view titles that include a floor plan count), or, with no bound title, F.07 has a floor-plan viewport. A page is positively another drawing only when it has a bound title that does not classify as a floor plan. No filename, page number, coordinate, project name or database page label is read.
2. `compose_live_wall_opening_authority(..., evidence_page_ids=())` (additive): topology `page_ids` keep exactly today's treatment; `evidence_page_ids` get their wall-candidate scope materialized (so registration and height proof can resolve targets) but no opening enumeration, host binding, completeness, canonical objects or coverage obligation. Default: none, so every existing caller is unchanged.
3. `collect_live_physical_net_wall_claim(..., topology_pages=None)` (additive): `pages` remains the decoded evidence universe; `topology_pages` is the subset that is composed as topology. Empty or non-subset values raise; they are never widened.
4. The customer bridge passes `topology_pages` only when the classifier has positive evidence on both sides (at least one floor-plan page and at least one page positively titled as another drawing). Unreadable sources, sources without a positive floor plan, and pages with no title evidence are never narrowed: the call is exactly today's call. The classification is recorded on the coverage `source_report["page_scope"]` for audit.

## 3. Authority transition that needs sign-off
Customer wall output can change only through which sheets feed the physical chain: (a) canonical walls/openings/rooms/floors and coverage-registry objects from sheets positively titled as another drawing stop entering the customer object universe; (b) the wall-scope completeness firewall applies to topology pages, not to evidence sheets; (c) evidence sheets still supply cross-sheet registration and height proof. It does NOT change: the extractor, JobHub payload, firm-authority seams, W10 flags, `QuantityEvidence` schema, any V2 truth, or the chain's own abstention rules on topology pages.

## 4. Measurements (real Lot16 plan set, same worktree base, sequential runs)
| | main a703af84 | topology scope |
|---|---|---|
| `analyse_workspace` | 1,492.5 s | 299.8 s (and 291.3 s on the previous code revision) |
| coverage-registry DETECTED objects | 740 (577 walls + 163 openings) | 28 (0 walls + 28 openings) |
| customer takeoff rows | 6 | 6, identical elements and quantities |
Timing caveat: other work shared the machine during the baseline run; the same run at main 7566be79 took 690.6 s. The object counts and rows are deterministic; treat the ratio as an order of magnitude, not a benchmark. No accuracy claim: official Lot16 stays 0/27.

## 5. Reviewer checklist and known risks
- A floor-plan sheet with an unconventional bound title (for example only "PLAN") is positively "another drawing" when another sheet is positively a floor plan, and becomes evidence-only. Review whether that is acceptable or whether unclassified titles should be left in topology scope.
- Pages with no title evidence stay in topology scope, so untitled elevations still contaminate. This is deliberate: absent evidence never removes a page.
- Evidence sheets still pay wall-candidate materialization (their scope is needed for registration); the runtime saving comes from skipping opening/G17 work and canonicalization there.
- Multi-storey sets with several positively titled floor plans keep all of them as topology (cross-floor mixing is unchanged by this PR).
- The extractor still passes floor-plan pages only; adopting the topology/evidence split there is a separate decision.
- Merge conflicts are likely with the open opening performance stack that touches `pb_live_wall_opening_authority_composition.py`.

## 6. Tests
`tests/test_source_floor_plan_page_scope.py` (24): classification positives and look-alike negatives, multi-view titles, unproven pages never removed, order/duplicate invariance, file-name independence, unreadable source, no mutation, additive and rejecting `topology_pages`, evidence pages keep a corroborated wall scope but receive no openings or obligations, customer routing with mocked claims (narrowed, not narrowed, failing classifier). Existing customer, chain and opening suites are unchanged and pass.
