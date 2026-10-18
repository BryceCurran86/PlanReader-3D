# GPT3 source-only V1 snapshot identity audit

Use this only when you have **two independently signed original-source V1
runs** but the old customer output was not archived. It does not pretend to
have a customer bijection or to authenticate a new original producer scope.

Example, with a public checkout and *private* owner archival paths:

```powershell
python -m tools.diag_gpt3_original_v1_source_only_transition `
  --historical-v1 "D:\Historical\lot16-original.sealed.json" `
  --candidate-v1 "D:\Candidate\lot16-source.sealed.json" `
  --output "D:\Reports\lot16-snapshot-drift-new.json"
```

The command validates every V1 run and quantity fingerprint using the
existing canonical loader, enforces canonical frozen project/source SHA
membership, compares exact quantity identity and signed proposition,
and categorizes shared rekeyed receipts plus historical quantities that
disappeared and new candidate quantities that appeared. It *never* joins
an old door and new window by equal area, proximity or printed label.

Result always says `SOURCE_ONLY_SNAPSHOT_IDENTITY_HOLD`, returns exit
code 2, sets `official_four_project_accuracy: null`, sets customer/
source issuer attestations false, and grants **zero** FIRM quantities.
Output is created exclusively, never overwriting source or old reports.

This does **not** replace the existing customer-verified
`tools.gpt3_signed_v1_replay_drift`: use that when the historical
customer rows **actually exist**, and independently verify new customer
rows against their own new seal.

For the private Oct 2026 historical source evidence, one independently
verified earlier Lot16 V1 run had a 5.67m² door not in the later
source run, and the latter had a newly issued 1.80m² window. Seven
shared quantity IDs retained their values but changed signed receipt
fingerprints. Do not equate these two eight-row runs. The public
20261015->20261016 pair instead retains the same eight quantity IDs
but changes all eight signed source receipts. Both are explicit
**source-producer decision-scope issuer** blockers.

Frozen V2 truth, 120-item denominator, the 20,000-raster cap, original
PDFs and archived V1/customer signatures remain unchanged.
