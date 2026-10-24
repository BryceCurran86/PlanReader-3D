# PlanReader-3D — independent AI pull-request review rules

These instructions apply to Claude Code Review and any other reviewer that reads `REVIEW.md`. `AGENTS.md` is the controlling engineering contract. A technical review does **not** replace original-source verification, GitHub branch protection, a distinct required approval, or explicit repository-owner release authorization.

## Independence
- Reviewer must not have authored, co-authored, or edited the specific PR diff under review. Recuse and request another independent reviewer if it has.
- Identify the model/system performing the review, current PR number, exact head SHA, base SHA and date. The shared `BryceCurran86` GitHub login is not a distinct human or GitHub approval; never describe a same-login COMMENT as formal independent approval.
- Inspect the *actual changed files and affected production callers*, not only a PR description, synthetic claims or earlier comments.
- For each new commit, re-review the exact new head. Do not trust older green runs.

## Hard release blockers
Mark **BLOCKED** or **CHANGES REQUIRED**, not approved, if any applicable item is absent:
- Original plan source SHA-256, page, revision, viewport and physical identity receipts; producer snapshot and decision scope; authentic metric/finish/host/count evidence. Unknown, conflicting, unsupported or stale evidence stays ABSTAINED.
- Real producer -> canonical physical entity -> `QuantityEvidence` -> signed source-closed V1 -> customer row -> original frozen Full Plan V2 evaluator, with exact-source reproduction for a claimed scoring gain. A synthetic pass or candidate does not certify a quantity.
- CI for the **exact HEAD** on applicable Python 3.13 and 3.14 workflows, focused negatives, conflicts, metamorphic/determinism and owner-private source replay where needed. Missing private PDFs or credentials mean NOT VERIFIED, never PASSED.
- No loss or reshaping of the historical eight source-sealed Lot16 opening areas or three genuinely sealed Maryborough plain room areas; no silent customer or physical-ID remapping, no duplicate quantity, no fabricated count=1.
- No edits to immutable full-plan V2 120-object truth, evaluator, tolerances, denominators or source originals to chase a score. Preserve 20,000 raster-primitive cap and 2.5 pt W2 snap.
- No source/customer credential exposure. Reject original private PDF upload, token logging, artifact leaks or untrusted pull-request code running with the `ORIGINAL_SOURCES_TOKEN` secret.
- Source policy restrictions such as original 3Laurel page 3 “Dimensions shall not be obtained by scaling” must never be silently overridden by a graphic scale-bar match. CID decoded labels, DERIVED viewport, shadow graph and proximity joins grant no firm geometry authority.
- Avoid lossily parsing duplicated nested JSON keys, bypassing commit receipt verification, silent identity conflicts, partial opening universe counts, stale signed receipts or cross-project authority.
- No merge of a draft, coordinated hub #3462 or overlapping ancestor merely to clean up backlog. Close superseded branches only with proven patch equivalence and successor merge.

## Review output on the PR
```
[INDEPENDENT AI TECHNICAL REVIEW — NOT OWNER RELEASE]
PR:
Reviewer/model:
Exact head SHA / base SHA:
Files and production paths inspected:
Tests actually run (command, interpreter, result):
GitHub Actions verified (run IDs, conclusion; failures classified):
Original-source proof (SHA/page/viewport/snapshot/identity; or NOT VERIFIED):
Signed/customer/frozen parity (proof or NOT VERIFIED):
Findings (severity, file:line, repro, required correction):
Verdict: TECHNICAL PASS / CHANGES REQUIRED / SOURCE BLOCKED / NOT REVIEWED
Score delta: independently measured exact frozen numerator/denominator, or NOT RUN
Formal GitHub approving review: YES ONLY IF ACTUALLY SUBMITTED BY AN ELIGIBLE DISTINCT REVIEWER; otherwise NO
Owner release authorization: YES ONLY IF OWNER ACTUALLY POSTED FOR THIS EXACT HEAD; otherwise NO
```
Review comments must distinguish **observed**, **inferred**, and **proposed**. Flag unverifiable statements without guessing. A TECHNICAL PASS is advisory and must never automatically merge a PR.
