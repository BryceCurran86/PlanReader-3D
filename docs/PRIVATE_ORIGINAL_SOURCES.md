# Local original construction source package

The four owner-provided original construction PDFs must **not** be committed
to this public GitHub repository. Their names, exact sizes and immutable
SHA-256 digests remain in the existing **frozen source manifests**, which must
never be edited to make a missing input pass.

## For authorized local production and benchmarks

1. Obtain the originals directly from the rightful owner via a private channel.
2. Create `documents/sources/` in the local checkout (this directory is now
   Git-ignored).
3. Place each original PDF under its expected exact filename from the frozen
   manifest. If a source is missing or wrong, **ABSTAIN/INCOMPLETE**; do not
   silently synthesize or substitute another PDF.
4. Run the repository's existing `tools/diag_gpt1_source_pdf_package_preflight`
   to verify original bytes, SHA-256, page count and size before production.
5. Keep diagnostic output, PDF renders, page vectors, material descriptions,
   client locations and the original raw pages on an authorized private disk.

The production scorer still requires the ten original source documents for
the four-job suite, including companion files not included in this repository.
GitHub Actions cannot run original-source tests requiring missing private
inputs unless they are supplied to an authorized, isolated runner. **Do not
"fix" red source tests by changing frozen truth, removing required targets, or
assuming missing sources are a zero score.**

## Git history and residual exposure

Removing these files from the tip of `main` **does not** erase the PDFs from
Git history, previous PR commits, forks or caches. Actual confidentiality
requires history and ref remediation under owner control (usually after making
the repository private), followed by credential rotation if secrets were
present. GitHub repository privacy settings are not automatically changed by
this cleanup.
