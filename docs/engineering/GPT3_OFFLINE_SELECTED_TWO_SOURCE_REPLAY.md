# GPT3 offline original-source replay — no private GitHub repository

The main repository remains **public**. A private companion repository or paid
hosted runner is **not required** for this development-only two-project replay.
Original construction PDFs stay on the owner's computer; do not commit or upload
them to public Actions artifacts. The existing [four-project evaluator](../../tools/report_gpt3_four_project_evidence.py)
remains the only permitted publisher of a complete **120-item** official score.

## Offline inputs

Save the unchanged, previously signed **derived** artifacts from the public
GitHub Actions archive and obtain the two original PDFs locally.

| Input | Previously pinned artifact / validation |
|---|---|
| Lot16 signed producer archive ZIP | Actions artifact `11929406140`, ZIP SHA-256 `950e1074d270e6b1d4558b165e5345cf49b2ac0c962a3cc8edf420f11f67bd91` |
| Maryborough signed producer archive ZIP | Actions artifact `11928069961`, ZIP SHA-256 `df0b3e42bf3b2b3aace43f155b7feec087dbfa5e55559ec7f16714577ef5e7b0` |
| Owner's original Lot16 architectural PDF | `1. Construction Plans - Lot 16 Power (REV E).pdf` |
| Owner's original Maryborough drawing PDF | `Arch_Combined_Maryborough_Service_Station.pdf` |

The input archive ZIPs may expire from GitHub Actions retention; use a
previously downloaded **byte-identical** copy if available. Do not substitute
a newly produced archive under the old SHA. The original PDFs can be stored
either directly under `--source-dir` or beneath a subdirectory matching each
frozen project ID. If both copies exist, their bytes must agree.

From a checkout of the public repository on the same computer, run:

```powershell
python -m tools.run_gpt3_selected_two_offline_replay `
  --source-dir "D:\PrivatePlanSources" `
  --lot16-archive "D:\SignedArtifacts\lot16-source.zip" `
  --maryborough-archive "D:\SignedArtifacts\maryborough-source.zip" `
  --output "D:\PrivateReports\selected-two-development-only.json"
```

This command never downloads PDFs, requests cloud credentials, uploads
artifacts or sends anything to GitHub. It verifies the two ZIP digests,
safely extracts derived receipts into a temporary directory, finds the
original local PDFs, and calls the existing independent signed/customer
reconciliation and **unchanged frozen exact project** evaluator. The original
PDF sizes and SHA-256 values must match the frozen source manifests. A
conflict, unverified producer, changed mapping, invalid customer seal or
unavailable byte blocks the run. The output path must be new and outside the
originals, ZIPs and frozen benchmark.

## What the result does and does not claim

A successful run produces a `SELECTED_PROJECT_DEVELOPMENT_ONLY` report,
with exactly 51 frozen eligible items (27 Lot16 + 24 Maryborough) and the
currently archived signed supplier/customer producer result. It expressly
sets `official_four_project_accuracy: null` and disallows full-suite
publication. An archive of only the Lot16 *architectural* original cannot
establish that the second frozen structural PDF was also processed; its
source-document-universe completeness is reported independently.

For the **official full four-project benchmark**, all ten original PDFs,
all four complete source producer executions, signed canonical quantities,
independent identity maps and verified customer projections must be present,
byte-authenticated and reconciled together using
`tools/report_gpt3_four_project_evidence.py`. Selected-project scores
cannot be rebranded as a 120-item percentage.

The script makes no unmeasured construction quantities, no new room
identities and no changes to the frozen V2 manifest, tolerance, raster cap,
source signatures or customer prices.
