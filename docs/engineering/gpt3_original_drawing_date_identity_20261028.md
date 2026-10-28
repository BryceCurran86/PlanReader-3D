# GPT3 — Original drawing date must not be inferred from publish time (2026-10-28)

## Observed current-main behaviour
- `pb_jobhub_publishing_pipeline.build_publishing_package_from_workspace` reads `workspaces.drawing_issue`, document SHA-256 digests and page count, then creates `DrawingRevisionPayload(drawing_date=datetime.date.today().isoformat())`. This is the **publisher's wall-clock date**, not a source-drawing issue date.
- `pb_jobhub_publishing_contract.PublishingPackagePayload.compute_payload_hash` seals `drawing_revision.to_dict()`, including that wall-clock date. Two unchanged source/quantity packages built on consecutive days therefore have different seals.
- `pb_jobhub_publishing_pipeline.execute_jobhub_publishing` validates the seal and detects duplicates by matching that hash in the JobHub package notes under the destination transaction. A new wall-clock date can evade the duplicate match even when source PDF bytes, quantity rows and pricing are unchanged.
- `tests/publishing/test_publishing_pipeline_e2e.py` exercises real in-memory PlanReader and JobHub SQLite schemas and the final publisher. The workspace fixture has `drawing_issue` but **no original-drawing date field**.

## Inference, not source authority
The current workspace schema does not prove the drawing's printed issue date. Today's date cannot substitute for an original page/title-block receipt. Even a SHA-256 digest does not disclose a drawing date. This repair does **not** authenticate a source date or add new FIRM quantities.

## Proposed narrow production change
Set `DrawingRevisionPayload.drawing_date=""` for the workspace builder until a source-owned, independently authenticated original drawing-date field is available. This is explicit unknown/abstention, not a new source date. Keep the already source-digest-derived `source_files_hash`, sheet count, drawing issue, customer gate, final payload SHA, transaction and duplicate detection unchanged.

## Expected negative/positive outcomes before tests
- An unchanged workspace with identical SHA-256 original source digests, row identities, rates and approval fields yields a byte-identical full-evidence payload hash even when a test-controlled wall clock moves across dates.
- The actual SQLite JobHub publisher accepts the first approved package and rejects the second unchanged package as a duplicate, leaving exactly one package and its lines.
- Changing the source document SHA-256 changes the revision hash and the full-evidence payload hash; distinct revisions are not accidentally deduplicated.
- No original drawing date is claimed; empty date is retained as unknown, not promoted. Missing original SHA remains blocked by existing commercial source gate. Invalid commercial quantities and approval remain blocked as before.

## Boundaries and untouched paths
Source PDF/viewport/snapshot/decision-scope authority is unchanged; this is a publisher metadata integrity repair only. No source files, private PDFs, credentials, original source receipts, signed/customer archives, frozen V2 120-object evaluator/denominators, other agents' branches, 20,000-primitive cap, or 2.5pt snap are touched. No benchmark project names, expected quantities, or truth are consulted by production code.

## Validation
Dedicated real SQLite regression tests, complete final three-file diff review, exact-head Python 3.13 and 3.14 full CI, signed/customer retention and raster/performance companions. Public CI cannot prove private original source or authorize #3796, new FIRM quantities or a frozen V2 score increase.
