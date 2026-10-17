# Full Plan V2 public code checkout transfer (sources not included)

This public workflow previously required **Maryborough original client PDF**
inside a `git archive` of the public tracked checkout. That can never work
after PR #2920 correctly removed original client drawings from current Git.

The replacement preserves the **workflow filename and job name**, with a
source-neutral build of the public tracked CODE repository, then checks:

- Frozen Full Plan V2 four-project suite manifest and all four original SHA
  manifest files are present inside the archive.
- The ten actual original PDF **filenames** and SHA declarations are present
  **as metadata only**; no PDF payload, `.env`, credentials, original client
  folder or symlink enters the downloadable archive.
- Every archive member is audited before uploading. A failing or missing
  original SHA manifest is a **hard failure**, never an unverified score.
- An immutable code `HEAD` SHA, archive SHA-256 and transparent
  `CODE_ONLY_SOURCE_FREE` receipt accompany the downloadable **public
  code archive only** (3-day retention). No access tokens are used.
- Exact original client source files remain private and must be SHA-provisioned
  on a trusted owner machine separately (see
  `docs/engineering/ORIGINAL_SOURCE_PROVISIONING.md`). The frozen
  120-item evaluation is **NOT** executed in this workflow.

The standard `CI / test` source-neutral/public security gate remains
unchanged; the public checkout is **not an official production test pass**,
not a complete customer source handoff and not a method to obtain the
private client PDFs. It does not erase historical Git exposure, which
requires separate GitHub account-level history remediation.
