# GPT3 source-linked client contracts, variations and progress claims

These are **three executable commercial workflows**, not diagnostic-only code,
and are stacked on the GPT3 signed customer quote PR #3021.

They operate on the unchanged original **signed V1 quantities**, verified
commercial customer rows and a client-entered price schedule. They do not
read original private PDF bytes, grant new FIRM quantities, certify installation,
authenticate a client e-signature, or publish the frozen four-project V2 score.

## A. Create a source-linked contract

    python -m tools.gpt3_verified_contract_delivery --sealed-run /secure/source_sealed_run.json --customers /secure/verified_customer_rows.json --quote /secure/quote.json --policy /secure/contract_policy.json --output /secure/contract.json

The policy must have schema_version gpt3-contract-policy-v1, the exact
source project_id, client contract_id/client_reference, explicit
payment_terms_days and retention_pct, inclusions and exclusions arrays,
package_assignments mapping **each actual signed quantity ID** to one client
package_id, package_descriptions of those IDs, milestones and acceptance.

Milestones are objects with id, description, due_on (ISO date), share_pct
(client percentage as decimal string), and must total **exactly 100%**.
Payment amounts split the actual quote gross in cents with final-stage
rounding residual. These are scheduled amounts, not certified earnings.
Source physical quantities roll up within work packages by **unit**, without
combining metres, metres squared and counts.

The acceptance object uses status DRAFT, SUBMITTED, ACCEPTED or REJECTED,
quote_fingerprint, and (for accepted/rejected) actor, reference and
recorded_on. Expired quotes cannot acquire later acceptance by
backdating. Client-supplied approval references are **not e-signatures**.

## B. Reprice the same physical quantities in quote revisions

    python -m tools.gpt3_verified_contract_delivery --sealed-run /secure/source_sealed_run.json --customers /secure/verified_customer_rows.json --revisions /secure/quote_revisions.json --output /secure/quote_history.json

Quote revisions JSON is an object with a revisions array. Each row contains
positive increasing integer version, canonical effective_on date and the
**complete generated quote object**, not a placeholder. Every quote is
independently rebound to the *same original* signed V1 issuer and customer
bijection; the output reports price changes and changed item IDs without
inventing any physical quantity, different project or benchmark match.

## C. Propose, decide and price client variations

    python -m tools.gpt3_customer_change_orders --contract /secure/contract.json --quote /secure/quote.json --events /secure/client_variation_events.json --output /secure/variation_register.json --format json

Events input is an object with schema_version gpt3-client-variations-v1,
contract_id, the **exact contract_fingerprint**, currency and events array.
To propose, specify event PROPOSE, unique variation_id, recorded_on,
scope_type ADDED_SCOPE/REMOVED_SCOPE/CLIENT_OPTION, description,
net_ex_tax (signed exact cent decimal), explicit tax_pct, and optional
related_signed_quantity_ids (only genuine signed IDs).

For later decisions append event APPROVE, REJECT or WITHDRAW with that
variation_id, recorded_on, actor and external reference. No second
proposal/decision for one variation is allowed. Only approved variations
alter committed client gross. Pending, rejected and withdrawn options
remain visible but excluded from the price baseline. A removal is an
explicit negative credit; all other categories require positive price.
This cannot change any signed measurement or produce a source quantity.

Change registers contain an ordered content-fingerprint event chain,
outstanding pending values, approved gross changes and committed price.
These hashes are **not client digital signatures**. Use --format csv for
a human-importable change-order schedule.

## D. Customer-reported cumulative progress and payments

    python -m tools.gpt3_client_progress_claims --contract /secure/contract.json --quote /secure/quote.json --variations /secure/variation_register.json --sealed-run /secure/source_sealed_run.json --customers /secure/verified_customer_rows.json --previous-claims /secure/previous_claims.json --current-claim /secure/current_claim.json --output /secure/progress_claim.json --format json

An empty JSON list is the previous-claims input for the first claim.
Subsequent calls provide the original ordered immutable prior claim
objects, and claim_number increments by exactly one.

The current input contains schema_version gpt3-client-progress-input-v1,
contract_id, claim_number, claim_reference, claim_date, three explicit
ID-to-percentage maps, deposit_credit_applied, new_receipts,
release_retention and (if releasing) release_retention_reference.

- milestone_completion_pct contains exactly the client contract milestone IDs
- source_line_progress_pct contains **every signed quantity ID**, reported by client
- variation_completion_pct contains exactly the **approved** variation IDs
- each receipt has receipt_id, received_on, amount and private remittance reference

Financial earnings are derived from scheduled milestone gross and approved
variation gross against **client-reported completion percentages**, not from
plan geometry. Source-line quantity-equivalents are informational, labelled
client-reported, and never become newly sealed or remeasured quantities.
The prices already include client-specified tax; progress does not apply
the quote GST percentage a second time.

The output calculates claim-period and cumulative earnings, amounts due,
withheld retention, guarded final retention release, deposit credits,
agreed payment-term due dates, recorded receipts and receivables with
current/1-30/31-60/61+ overdue aging. Receipts are allocated oldest-first.
Payment overclaims, repeated receipt IDs, rolled-back percentages, changed
prior claims and rewritten variation event histories are rejected.

New approved variations **may be added after the first claim**, but only
through an append-only extension of the earlier variation event ledger.
Pending work never earns a change-order progress claim. --format csv
exports source-line, milestone, manual variation and financial summary rows.

## Commercial and security boundaries

All figures, schedules, approvals, stage-completion percentages and receipts
are client-provided records. They are not bank verification, legal e-signature,
licensed construction certification or proof of completed physical work.

These tools return official_four_project_accuracy = null. Never use a
commercial claim as a PlanReader measured result. Keep all private
rate books, client notes, documents and remittances OUT of public GitHub.
