# Local original construction source package

The owner-provided construction PDFs stay on the local computer. Their names, exact sizes and immutable
SHA-256 digests remain in the existing **frozen source manifests**, which must
never be edited to make a missing input pass.

## Run the official benchmark locally

The Windows app launcher uses the existing original producer and frozen scorer.
Configure the originals, the four independent identity maps and a private
results directory with `.planreader-benchmark.local.json` beside the launcher.
This file is Git-ignored.

```json
{
  "source_dir": "D:/PlanReader/Originals",
  "identity_map_dir": "D:/PlanReader/IdentityMaps",
  "run_root": "D:/PlanReader/BenchmarkRuns"
}
```

Use a clean checkout and install the normal app dependencies before extraction.
Check the setup with:

```powershell
.\RUN_PLANREADER_WINDOWS.bat benchmark --check-only
```

This verifies the unchanged ten-PDF roster by SHA-256, size and page count
and checks that all four maps are present. For a fresh run, disconnect the
computer's network connections for the duration of extraction and execute:

```powershell
.\RUN_PLANREADER_WINDOWS.bat benchmark
```

The benchmark checks the local network state and Git head before starting each
project and before scoring. It writes a new run directory with the four-project
status and the existing `frozen120_score.json` evaluator result. The signed
quantities and customer records stay in that private directory. An incomplete
source, issuer or customer record leaves the official result unpublished.

The same module accepts explicit `--source-dir`, `--identity-map-dir` and
`--output-dir` arguments. Use `--saved-run-dir` to verify archived signed
evidence locally. A saved run verifies the archived output.

GitHub Actions runs public code and synthetic checks. Original PDF replay,
scoring and signed customer verification use the local benchmark path.

## Git history and residual exposure

Removing these files from the tip of `main` **does not** erase the PDFs from
Git history, previous PR commits, forks or caches. Actual confidentiality
requires history and ref remediation under owner control (usually after making
the repository private), followed by credential rotation if secrets were
present. GitHub repository privacy settings are not automatically changed by
this cleanup.
