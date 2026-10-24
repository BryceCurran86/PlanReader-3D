# Optional AI code reviews with one GitHub account — PlanReader-3D

**Status:** optional review guidance for the owner's single-account workflow, governed by current `AGENTS.md` on main (2026-10-24). The owner **removed mandatory independent-review restrictions**, including a separate GitHub account, formal approved vote, cross-agent sign-off or a stop awaiting architecture approval. GPT1/GPT2/GPT3/GPT MAX/Cursor/AntiGravity may implement, validate and merge already authorized work without waiting for a reviewer. Extra AI reviews are useful, **not a gate**. No automatic merging is configured by these instructions.

## Unchanged engineering acceptance requirements

Keep mandatory exact-head applicable CI and Python3.13/3.14, source SHA/page/viewport/revision/snapshot/identity evidence, production issuer/customer wiring, original-source replay where required, signed customer/retention, frozen Full Plan V2 120-object truth/evaluator, correct ABSTAIN/CONFLICT and geometric safety 20,000 cap / W2 2.5pt snap. Do not upload owner-private original PDFs or secrets to this PUBLIC repo. Code author's own final diff inspection and full required validation are sufficient; additional code review is optional. The original source, not an AI reviewer, authenticates measured construction facts. The owner retains task/release authority.

## How to turn on automatic GitHub Copilot Code Review (account-side action)

GitHub Code Review can automatically review your own PRs without a different personal account. It requires an eligible GitHub Copilot license and can consume review credits; **check your quota and billing before enabling reviews on all pushes**.

1. GitHub profile picture → **Copilot settings → Code review**.
2. Enable **Automatic Copilot code review**. Optionally enable **Review draft pull requests** and **Review new pushes** once you are comfortable with usage; many PlanReader-3D drafts will otherwise be skipped.
3. For deep Python/security/authority review choose **Balanced** effort if available. Monitor credit use, as repeated review on many pushes can cost more.
4. To request an **initial** review on an existing PR, open the PR → **Reviewers → Copilot → Request**. Official REST API reviewer login is `copilot-pull-request-reviewer[bot]`; if entitlement is absent, the request can fail.
5. Optionally: repo Settings → Copilot → Code review → use custom instructions; this repository supplies `.github/copilot-instructions.md` and root `AGENTS.md`. According to GitHub, Copilot reads instructions from the PR **head branch**, allowing tests before merge. Preserve current owner policy if older PR branches contain contradictory instructions.
6. **Copilot approvals** are separate public preview toggles, disabled by default. They are unnecessary under the owner's new engineering policy; do not enable just to satisfy an artificial gate. If actual GitHub branch protection does require them, an eligible Copilot approval can count when enabled and allowed by the repo. Do not assume it is enabled.

Official GitHub setup: https://docs.github.com/en/copilot/how-tos/copilot-on-github/set-up-copilot/configure-code-review

Official API reviewer identity: https://docs.github.com/en/copilot/how-tos/copilot-on-github/use-copilot-agents/copilot-code-review

## Alternative Claude review

Claude managed Code Review requires eligible Team/Enterprise setup and per-review billing; do not claim it is connected unless the owner has configured it. Where unavailable, Claude can review source and PRs using the owner's existing Claude environment, recording labelled technical comments. Same-account comments are advisory and cannot be presented as distinct-user GitHub approval. Never add an API key to a public PR job or run untrusted PR-supplied code with secrets.

## Optional review procedure

An AI reviewer (Claude or Copilot) should inspect current main and head, actual diff, production callers, test/CI receipts, original source proof when available, signed/customer/frozen impact and security; use root `REVIEW.md` for an evidence-based TECHNICAL PASS / CHANGES REQUIRED / SOURCE BLOCKED report. A failed review is useful defect evidence and should be fixed, but a missing additional reviewer is not a release blocker. Implementer may complete the same required validation before merging owner-authorized work. A changed head needs new CI/source evidence; optionally request a new AI review.

All agents continue reading and updating PR #3462 after substantive work; keep that hub **OPEN and DRAFT**. Never merge obsolete/overlapping PRs or change frozen truth to inflate accuracy. Source-specific architecture drafts (#3839) are not production quantities or score improvements.

## Status at creation

Review documentation and instructions only: no GitHub account settings were changed, no service subscribed, no paid reviews automatically scheduled, no source secrets provisioned, no new FIRM quantities or V2 scorer runs. Connected GitHub App has read-only information on rulesets but may fail branch-protection GET; verify actual settings in GitHub UI rather than claiming enforcement changes.
