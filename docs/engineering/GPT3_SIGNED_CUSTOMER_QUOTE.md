# GPT3 verified customer estimates (signed V1 source only)

A source-closed signed takeoff is not itself a customer price. The client supplies
their own rates and tax/markup policy; GPT3 preserves exactly the sealed
physical quantities and source identities while building an itemized estimate.
**This cannot generate Full Plan V2 matches or publish a benchmark accuracy.**
The rate book is intentionally external to the frozen benchmark and should
remain customer-private.

```sh
python -m tools.gpt3_verified_customer_quote \
  --sealed-run /secure/project/source_sealed_run.json \
  --customers /secure/project/verified_customer_rows.json \
  --client-rates /secure/project/client_rates.json \
  --output /secure/project/estimate.json --format json
```

For machine-importable item rows use `--format csv` with a new .csv output.
Neither format contains the original drawings or entire nested customer
provenance notes.

## Client rate book schema

```json
{
  "schema_version": "gpt3-client-rates-v1",
  "project_id": "au_qld_lot16_power",
  "currency": "AUD",
  "issued_on": "2026-10-17",
  "expires_on": "2026-11-17",
  "include_manual_allowances": false,
  "manual_allowances": [
    {"id": "option-01", "description": "Optional manual scope", "amount": "250.00"}
  ],
  "rates": [
    {
      "scope": "family", "key": "opening_area", "unit": "m2",
      "material": "100.00", "labour": "60.00", "plant": "10.00",
      "subcontract": "0", "labour_hours_per_unit": "0.5",
      "waste_pct": "5", "markup_pct": "20"
    }
  ],
  "adjustments": {
    "overhead_pct": "8",
    "contingency_pct": "5",
    "discount_pct": "0",
    "tax_pct": "10"
  }
}
```

The numbers are illustrative client-entered prices **not source measurements**.
The engine has no built-in rates or tax defaults. Clients must confirm all
commercial settings; GST here is only the explicit example tax percentage,
not a statement of a project's legal tax treatment.

## Functionality

1. Independently authenticate the existing signed-run/customer-row bijection.
2. Lock rate books to the exact project and issuer quantities.
3. Maintain all physical values in the sealed source units.
4. Family-wide client-supplied rate cards.
5. Source-semantic specific rate cards.
6. Exact signed quantity-ID rate overrides (override > semantic > family).
7. Materials cost per physical unit.
8. Labour cost per physical unit.
9. Plant cost per physical unit.
10. Subcontract cost per physical unit.
11. Labour hours per billable unit.
12. Separately disclosed *commercial pricing-only* waste (no physical-area edit).
13. Per-card selling markup.
14. Client-selected project overhead.
15. Client-selected contingency.
16. Client-selected discount.
17. Client-selected tax; never presume a tax rate.
18. Optional, source-distinct manually priced allowances.
19. Item-level precise physical/source-page/revision lineage.
20. Family-and-unit breakdown with disjoint units.
21. Source-page costing breakdown without original PDF data.
22. Unpriced items produce an incomplete estimate, **never a false zero total**.
23. Deterministic full quote fingerprint.
24. Source-neutral machine CSV and structured JSON exports.
25. Distinguish rate-only price changes from changes to signed physical quantities.
26. Atomic new-only output that cannot overwrite source or frozen benchmark data.
27. Currency recorded explicitly per client.
28. Expiry and issue-date contract.

### Explicit limitations

The source run is V1 signed and customer-projected; this tool does not
rehash original PDFs or independently execute four-job V2 reconciliation.
Original source authentication and first-party customer approval must still
occur upstream before public/commercial release.

All inputs and outputs should remain client-controlled/private where they
contain customer information. Never commit a real client's rate book into
the public repository. A manual allowance is **not** a signed physical
quantity and does not create a frozen benchmark identity. Using `--format csv`
cannot substitute for retaining the signed JSON source run and full verifier
receipts. Quote comparisons use signed fingerprints; a different fingerprint
requires independent issuer adjudication rather than being treated as new work.
