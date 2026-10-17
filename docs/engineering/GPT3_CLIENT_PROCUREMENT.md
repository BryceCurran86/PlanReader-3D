# GPT3 customer procurement, vendor offers and purchase-order drafts

This is a **real two-stage executable customer procurement workflow** built
on the original signed-quantity client estimator (#3021, merged).

**Critical distinction:** original drawn opening/floor/wall quantities and
verified customer rows are reused only for source references. There is
no scientifically justified mapping from e.g. 1.8 m² opening area to
how many manufactured frames, fasteners or paint tins must be ordered.
Every *purchase* description, quantity, unit and budget is separately entered
by a client. It is **never** a newly measured construction takeoff.

The tools are local/owner controlled and create new output files without
overwriting the original sealed run, customer rows, original drawings or frozen
benchmark. Neither tool can transmit a purchase order or make a bank payment.

## 1. Client procurement and competing vendor bids

    python -m tools.gpt3_client_procurement_awards \
      --quote /secure/project/priced_quote.json \
      --sealed-run /secure/project/source_sealed_run.json \
      --customers /secure/project/verified_customer_rows.json \
      --procurement-book /secure/project/supplier_procurement.json \
      --output /secure/project/procurement_awards.json --format json

Format: gpt3-client-procurement-v1, with project_id and the exact existing
quote_fingerprint, explicit matching currency, as_of date, suppliers,
requisitions, supplier_offers and client_awards.

- Supplier rows require supplier_id, supplier_name, same quote currency,
  explicit eligible_for_award boolean, integer payment_terms_days.
- Requisitions require unique requisition_id, purchased description and unit,
  independently client-entered positive requested_purchase_quantity,
  at least one *existing* signed source quantity ID, delivery location,
  need-by date and optional maximum_approved_gross.
- Supplier offers require unique offer_id, matching requisition_id/supplier_id,
  matching purchase_unit, ex-tax unit price, ex-tax freight,
  minimum_order_quantity, pack_multiple, 0-365 integer lead_days,
  explicit tax_pct, valid_through date.
- The engine rounds ordered quantities up to whole supplier packs and
  captures any overbuy separately (a **client procurement effect**, not a
  signed takeoff quantity).
- Supplier rankings expose quote price and speed; expired, late, ineligible
  and over-budget offers cannot be selected. This cannot implicitly select
  the cheapest supplier.
- Each award must explicitly name requisition_id, offer_id, approved_by,
  approval_reference and approved_on. Award date equals the evaluation
  as_of date, so quotes cannot be approved from stale eligibility tests.
- Awarded quotes produce grouped **unsent** vendor purchase-order drafts.
  Their approval references are customer declarations, not cryptographic
  e-signatures or an actual supplier transmission.
- Unawarded material requisitions stay clearly visible, not free or omitted.
- Optional exports: --format rfq-csv for customer purchase requirements and
  --format po-csv for explicit unsent supplier order lines.
- Quote material-cost totals are shown separately from tax-inclusive vendor
  commitments; they are **not like-for-like** construction margin analysis.

## 2. Customer-recorded fulfillment and supplier payable ledger

    python -m tools.gpt3_client_procurement_receipts \
      --procurement /secure/project/procurement_awards.json \
      --events /secure/project/supplier_events.json \
      --output /secure/project/supplier_ledger.json --format json

Events are client-entered, chronological, append-only objects bound to the
**exact procurement_fingerprint**:

- RECORD_PO_SENT — recorded_by, reference, date, draft PO ID.
- SHIPMENT_NOTICE — requisition ID, shipped_quantity and reference.
- RECEIVE_DELIVERY — requisition ID, unique receipt_id, accepted_quantity,
  rejected_quantity and client reference.
- RETURN_ACCEPTED — requisition ID, unique return_id, returned_quantity,
  and client reference.
- SUPPLIER_INVOICE — requisition ID, unique invoice_id and exact-cent
  gross_amount for a line with net accepted physical purchases.
- RECORD_SUPPLIER_PAYMENT — unique payment_id, invoice_id, client
  recorded amount and remittance reference.

Each event also requires event, po_draft_id, recorded_on and reference.
Shipment/delivery/invoice records require a previously CLIENT-recorded PO
sent event; this tool never sends anything. Duplicate event receipts, over
ordered deliveries, returns beyond accepted stock, invoice gross exceeding
authorised order value, payments exceeding invoiced balances and
chronological rewrites are rejected.

The ledger reports ordered purchase units, accepted/rejected/returned units,
outstanding stock, partial/complete/unissued order statuses, supplier
invoiced/paid gross and outstanding payables. Optional --format csv emits a
purchase-line reconciliation with source quantity IDs.

Cash/payment and receipt events are supplied by the user, **not verified by a
bank or courier**. The hash chain is tamper-evident, **not** a legal
signature or third-party confirmation.

## No private PDFs or benchmark contamination

The real archived source-neutral regression uses Lot16's existing eight
signed source/customer areas, and synthetic supplier, quote, budget,
delivery and cash events. It does not access a customer's original PDF.
Procurement planning cannot change construction quantities, source
identity, revision, issuer, eight signed opening amounts, 20,000 raster cap
or 120-item frozen truth/evaluator.

Both report official_four_project_accuracy = null. Nothing is marked as
bank-verified, delivered by this tool, a FIRM takeoff or an official
published four-job benchmark score.
