# Remaining public PR source jobs — cleanup architecture

## Observed

The ceiling checksum workflow's original-partial-source job executes tools/run_source_closed_project_handoff.py on a private 3Laurel original from pull-request-controlled code, then uploads its source-derived directory. The final-material RCP workflow's maryborough-material job ingests the private original through SourceVisibilityProducer and SourceMaterialSemanticProducer, tees recovered source words into public logs, and uploads them. The 22-candidate cleanup run reproduced the missing-source ceiling failure (job 123029187680). Public focused synthetic tests are separate jobs in both workflows.

## Inference and change

Public PR validation cannot authenticate an unavailable private original, and provisioning it to PR code would expose the owner's drawings. Keep every original-positive assertion and consumer verification in a manual job restricted to the repository owner, initiating owner, and immutable main SHA. Use the existing SHA-verifying provision action. Capture original commands in ephemeral private logs, remove artifact uploads, and always remove original files, derived files and private logs. Public focused checks retain their existing commands with read-only credentials. A skipped original job is never an original-positive pass.

## Validation and boundaries

Run the existing dynamic token-boundary, original-log/privacy and signed-output path-coverage guards, focused ceiling/material tests, YAML structure checks, frozen truth integrity and production/gold isolation. Full exact-head Python 3.13/3.14 remains required. These workflow changes issue no quantity or source authority and do not modify producers, original PDFs, archived signed/customer rows, frozen truth, 20,000 primitive cap or 2.5pt snap. The private original assertions remain release requirements for production changes.
