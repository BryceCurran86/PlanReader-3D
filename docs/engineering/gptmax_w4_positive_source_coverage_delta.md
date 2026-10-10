# GPT MAX — source-positive W4 assembly coverage delta

Compare **two independently produced original-source reports**, not the frozen benchmark answer data.

Source fixture: Lot16 original PDF SHA `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`, PR #2161 run 38068100685, artifact 11675407730.

Usage:

```bash
PYTHONPATH=. python tools/gptmax_w4_positive_source_coverage_delta.py \
  --baseline original-source-before.json \
  --candidate original-source-after.json \
  --output w4-positive-source-coverage-delta.json
```

This **read-only** diagnostic compares source-owned W4 edge coverage only when the PDF SHA, page scope, physical opening identity, primitive safety cap (20,000), authenticated W4 scopes and original producer-owned positive primitive IDs agree. It measures missing coverage in the **original PDF point coordinate system** by matching genuine source primitive IDs and collinear overlap, independently of transient W2 split_N and node address changes.

Important original-source examples:

- Opening `2c31ccb...`, primitive suffix `:1585`: W4 membership after compact/T loses x=410.25, y=341.50–342.72 (**1.22 PDF points**).
- Opening `661fc5e6...`, primitive suffix `:324`: W4 membership loses y=531.25, x=582.60–584.50 (**1.90 PDF points**).
- Opening `38c03575...`, source `:1567`: original y=336.75–338.75 **unpainted gap** must remain unproven. Resplitting y=338.75–342.72 and y=342.72–349.00 does not itself lose positive source coverage despite changing W4 wall member identity.

The diagnostic **does not establish physical wall loss, physical equivalence, source gap closure, host receipt retention, opening count, source-complete candidate universe, QuantityEvidence, metric takeoff or benchmark accuracy**. Unresolved candidate hosts are ABSTAIN rather than assumed lost geometry. Any structural source edit still requires independent source authority and the strict physical host/frame retention gate. This PR does not alter W2/W4 graph production, raster detector, source PDF, 20k cap, frozen V2 holdout or commercial quantities.
