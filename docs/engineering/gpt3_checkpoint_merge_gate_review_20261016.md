# GPT3 partial-checkpoint release architecture review

Reviewed against main ef6ca359f35e1b6187c568f0413eb6cdaaa1e94f on 2026-10-16.

The existing partial Full Plan V2 checkpoint workflow restricts pull-request execution to a list of paths. Changes in transitive producer, signer, customer-verifier or dependency modules can therefore bypass this checkpoint. The workflow also explicitly checks out the pull-request head rather than the proposed merge result, so passing CI may not reflect integration with main.

Proposed fail-closed change: remove the pull-request paths filter, retain main-branch scoping and manual dispatch, use the default pull-request merge checkout, and run adversarial workflow-invariant tests in the same job. Preserve SHA-pinned eight-row signed V1 fixture, its run fingerprint, customer receipts, unchanged frozen four-project evaluator, the 20,000 raster-primitive cap, and the partial score's NULL full-development accuracy. Never infer a complete four-project score from 8/27 or 8/120.

Independent review and successful exact-head Actions checks are required before merging. This document grants no publication authority and changes no production quantity.
