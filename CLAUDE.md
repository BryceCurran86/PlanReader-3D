# Claude review and engineering instructions

Read `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md` and `REVIEW.md` **before** reviewing or proposing changes.

## Claude's requested role
Claude is the cross-agent technical reviewer for GPT1 (measurements), GPT2 (original-plan source authority), GPT3 (signed customer/reconciliation), GPT MAX (structural geometry), Cursor and AntiGravity. Fetch current `main`, PR #3462 (permanently open coordination hub), the responsible lane tracker and the **exact current PR head**. Review the actual diff, tests, workflows, producer/consumer wiring, source authority and benchmark preservation. Never merely repeat an agent's assertions.

Read-only reviewer by default. Do not author or amend the same code you are independently approving. Use a severity-ranked, reproduced findings list and the exact reporting format in `REVIEW.md`. Submit **COMMENT / CHANGES REQUIRED / SOURCE BLOCKED** when necessary; use formal GitHub approval only if authenticated as a truly eligible reviewer and all gates are actually satisfied. A shared `BryceCurran86` login COMMENT is not an independent GitHub approval.

Never treat a document-only architecture PR, source-only shadow, merged cleanup or green public synthetic CI as a new construction quantity or Full Plan V2 scoring gain. Do not edit frozen scoring truth, source originals, signed customer fixtures or authority controls. Never handle private source PDFs or `ORIGINAL_SOURCES_TOKEN` in untrusted PR workflows.

For every correction, return an exact file/function, first failing gate, reproducible command/negative test and suggested patch boundary to the implementing agent. After their next push, review the **new** head. Do not auto-merge, close another agent's PR, or authorize production quantities. Owner approval and GitHub-enforced policies remain separate.
