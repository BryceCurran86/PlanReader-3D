# Original Lot16 signed output: the eight opening-area quantities (fixture)

Source-positive production output of the original Lot 16 architectural PDF
(SHA-256 `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`), produced by GitHub Actions run
38636511093 at producer head `4e5aedf085cf63f92dac0935132b1e1c1dbaa178` and kept here so that no check depends on an
expiring Actions artifact (artifact `11929406140`, ZIP SHA-256 `950e1074d270e6b1d4558b165e5345cf49b2ac0c962a3cc8edf420f11f67bd91`,
deleted by GitHub retention on 2026-11-13).

| file | what it is |
|---|---|
| `production/source_sealed_run.json` | the sealed run, fingerprint `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`, eight `opening_area` quantities (0.54, 0.9, 1.26, 1.8, 1.8, 2.16, 2.16, 10.08 m2) |
| `production/verified_customer_rows.json` | the eight customer rows, one per sealed quantity |
| `identity_map_with_1215.json` | benchmark-side binding of those eight to the frozen objects (read only by the development checkpoint) |
| `exact_project_report.json` | the exact 27-object reconciliation of that run (8 matched within tolerance) |
| `producer_head_sha.txt` | producer head of the run |
| `SHA256SUMS` | SHA-256 of every file above; `.gitattributes` sets `* -text` so no checkout rewrites line endings |

This is production output of the original PDF, **not benchmark truth**, and it is not edited by any pull request: the
files are byte-identical to the signed originals that are compared after every owner merge that touches a production
module. Verification: `sha256sum --check SHA256SUMS`, `tests/test_lot16_signed_eight_row_fixture.py` (runs in the
ordinary CI), and `.github/workflows/diag-gpt3-full-v2-current-development-checkpoint.yml`.
