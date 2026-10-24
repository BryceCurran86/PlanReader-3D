# AI technical reviews with a single owner GitHub account

**Status:** proposed docs-only workflow; does not override `AGENTS.md`, protected branch settings or #3462 until reviewed and adopted. Repository `BryceCurran86/PlanReader-3D` stays PUBLIC. Never upload owner/client original PDFs, private font files or secrets to public GitHub.

## Roles and release policy

- GPT1/GPT2/GPT3/GPT MAX/Cursor/AntiGravity implement changes and tests on their own existing PRs; separate coding agents do not self-approve.
- GitHub Copilot Code Review or Claude checks each PR's exact head and comments with technical findings per root `REVIEW.md`, `CLAUDE.md` and `.github/copilot-instructions.md`.
- **An AI technical verdict is not automatically independent original construction source authority.** GitHub’s requirements can only be satisfied by actual eligible GitHub approval; a PR comment under author login `BryceCurran86` is not a qualifying approval. GitHub Copilot's approval public-preview feature may provide a qualifying bot approval if it is separately enabled and the repository allows it; verify its actual review state and branch protection rather than assuming.
- The owner makes a *per-exact-SHA* release decision **after** source, security, test and review gates. A new head requires re-review and new owner decision.
- Do not enable auto-merge or bypass required protections. Keep coordination PR #3462 open and draft.

## Simplest activation: GitHub Copilot automatic code reviews

1. Confirm a Copilot plan with code-review entitlement. In GitHub profile menu choose **Copilot settings → Code review**.
2. Enable **Automatic Copilot code review**, **Review draft pull requests** and **Review new pushes**. Set review effort to **Balanced** where available. These settings cause Copilot to check your own PRs without needing a second account.
3. Optionally in repo **Settings → Rules → Rulesets**, set an explicit review policy for main; do not enable a new unverified bypass. GitHub's **Copilot approvals** is a separate public-preview switch, disabled by default. Only enable after verifying the exact repo and your accountability requirements.
4. Request a review on one existing draft PR using its **Reviewers → Copilot → Request** control; check it actually posts review findings. Before requesting all, inspect your plan's usage/billing quota. Review existing draft PRs individually if automatic review does not retroactively trigger.
5. A Copilot review by itself cannot run the owner-private original PDF pipeline in untrusted public PR CI. Keep trusted owner-original replay in a separate secure environment, independently verified.

Documentation: https://docs.github.com/en/copilot/how-tos/copilot-on-github/set-up-copilot/configure-code-review

## Alternative: Claude AI code review

Claude's managed Code Review requires an eligible Team/Enterprise organization and bills separately per review; owner must configure its GitHub App and repository in Claude admin. It may not work on existing draft PRs until they are ready for review. Do not mass-enable expensive per-push reviews without a cost cap. Where the managed service is unavailable, Claude Code GitHub Action can be configured with the official GitHub App and a protected `ANTHROPIC_API_KEY` or authenticated OAuth secret; do not run arbitrary PR-supplied code under those secrets. No Claude credentials are configured or claimed by this policy.

Docs: https://support.claude.com/en/articles/14233555-set-up-code-review-for-claude-code and https://github.com/anthropics/claude-code-action/blob/main/docs/setup.md

## PR review and release checklist

For each PR, require:
1. Exact main/base/head SHA and full authored diff; no overlapping author's unreviewed changes.
2. Architecture-first observation/inference/proposal, first failing source/quantity gate, negative tests and genuine production consumer.
3. Exact-head Python 3.13/3.14 and specialist tests. Original source tests marked **NOT RUN/BLOCKED** when PDFs or token unavailable, never green by omission.
4. Exact original PDF SHA/page/viewport/revision, producer snapshot, physical identity, material, dimensional and semantic receipts when claiming source/metric/quantity authority.
5. No change to signed original eight Lot16 opening areas, Maryborough original three plain floor areas, commercial/customer rows and frozen four-project 120-item truth/evaluator/tolerances.
6. AI reviewer posts findings, implementation author repairs, second review on new head, any required *eligible* formal GitHub approval exists, owner explicitly authorizes exact SHA.
7. Merge only at that exact authorized SHA; report verified scorer numerator/denominator **or NOT RUN**. Keep unsupported evidence ABSTAIN.
8. Close a predecessor only after patch equivalence and successful successor merge; don't treat backlog closures as 99%-accuracy milestones.

### Suggested owner comment, **only after real evidence passes**
```
[OWNER RELEASE AUTHORIZATION]
PR #:
Exact head SHA:
AI reviewer verdict, reviewer and link:
Exact-head CI runs:
Trusted-original SHA/page/snapshot replay (or explain why genuinely inapplicable):
Signed/customer/frozen retention:
Remaining blockers: NONE

I authorize merging only this exact reviewed commit, provided all applicable
repository and GitHub-required gates are actually satisfied. Any new commit
revokes this authorization.
```

## Known blockers at adoption time
Current #3796 integrates signed V1/customer/floor review but requires private-source replay, duplicate-key parser review and real eligibility; do not auto-approve. #3839 is architecture-only; its source p3 says dimensions must not be obtained by scaling, while CID font / F07 role authority is still unresolved. Neither may be promoted to FIRM or called a frozen score improvement based on an AI comment.

**Repository permission visibility:** The connected GitHub integration may read repository rulesets but currently cannot inspect branch-protection settings (403). Owner must check the GitHub UI. This policy adds no workflow, source token, private attachment or automatic merge action.
