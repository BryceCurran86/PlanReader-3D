# Shared Agent Coordination Hub — 20 October 2026

**Status: DRAFT discussion-only PR. This is a cross-agent handoff protocol, NOT production code, measurement evidence, source authority, an automated runner, or an approval to merge. Keep this hub PR open as a draft. Do not merge it merely to close the task.**

**Repository:** BryceCurran86/PlanReader-3D  
**Shared chat/PR home:** the Conversation comments on the PR introducing this file (link in PR description).  
**Historical cross-PR integration evidence:** issue #2608 (reference only; not an active lane or coordination mailbox).  
**Lane trackers:** GPT1 #2017; GPT2 #2843 (historical #2009 closed); GPT3 #2004 and #2297; GPT MAX #2396.  

## 1. Governance and limits

**Owner update — 2026-10-24:** mandatory independent review is removed. Older PR descriptions/comments requiring a separate reviewer, separate GitHub account, formal approval or architecture-review pause are superseded. Original-source verification, required tests/CI, signed/customer retention, frozen truth separation and existing safety limits remain required.

- **Source-of-truth precedence:** explicit current owner instructions > AGENTS.md > docs/AI_ENGINEERING_PLAYBOOK.md > docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md > this handoff protocol > historical PR notes. The owner's 2026-10-24 instruction removes independent-review restrictions and supersedes older reviewer gates.
- New changes obey AGENTS.md: inspect real files/functions, record the architecture report, then trace → propose → synthetic proof → shadow run → source-authority validation. The implementing agent may validate and proceed within owner-authorized scope. Independent human/AI review is optional; no separate person/account, formal APPROVED vote, cross-agent sign-off, or review pause is required.
- The GitHub PR is **not a scheduler**. A comment cannot awaken another agent, guarantee independent review, or keep a closed chat running. Agents execute while their authorized sessions/tools are active. An explicit scheduled automation is separate.
- Every agent must read the current hub conversation *and* the relevant PR/issue evidence, not trust a stale chat recap. Comments must say which SHA and evidence was actually verified. An agent with no GitHub connection must say so rather than claim a check.
- Merge within owner-authorized scope only after applicable checks and source/evidence requirements pass. Missing reviewer approval is not a blocker and does not require another owner confirmation. Do not force-push or overwrite another lane's work; coordinate ownership before taking over a PR. Preserve immutable originals. Source, FIRM, customer and benchmark authority still require the actual producer/issuer/evaluator contracts; a procedural waiver is not evidence.
- Never claim that merged code, green synthetic tests, reopened workflows, or a marked-up plan automatically increase the frozen V2 score. Only genuine source-verified signed new quantities plus independently proven physical-to-frozen binding and the unchanged evaluator do.
- Do not manipulate or feed frozen gold values, project labels/filenames, expected quantities or scores into prediction logic. Do not change the frozen V2 truth/evaluator/tolerances, original PDF bytes, signed historical rows, 20,000 raster-primitive cap or the existing 2.5pt snap rule. Maintain source hash/revision/page/viewport/physical identity/producer snapshot/decision-scope lineage. Unknown and ambiguous evidence ABSTAINS.
- Do not upload private original PDFs to public GitHub to make CI green. Use only an authorized SHA-verified source path/package.
- **Accuracy objective:** improve authentic verified coverage, not count PRs, tests, prose, tiny refactors or failed runs as major engineering developments.

## 2. Mandatory check-and-update protocol (EVERY AGENT)

**At session start, and before choosing a task:**
1. Read AGENTS.md, playbook and this exact PR's current description, file at its PR HEAD and **all new Conversation comments since your last read** (follow pagination), plus your tracker and the latest main/related PR statuses. The file is on a draft PR branch, not necessarily on main.
2. Post one **[JOIN]** comment with: lane, current UTC timestamp, exact main SHA, your working branch + head SHA (or NONE), tracker, the specific unblocked first-failing gate chosen, and which source, validation or tool gates remain blocked.
3. Do not work on a task actively claimed by another lane. If claims appear stale, comment a **[CONFLICT]** and coordinate; never overwrite someone else's branch/worktree or assume their unmerged PR is on main.

**Before each substantive new development:** post **[CLAIM]** in this hub with one specific source-first-failure, lane, exact object/authority boundary (without benchmark gold as decision input), branch name, expected positive/negative tests, and next independent fallback. Then record the AGENTS.md architecture report and proceed with the authorized implementation and validation; do not wait for reviewer sign-off.

**After EACH substantive completed task, even if it fails or is blocked:**
1. Re-read this hub's newest comments and linked PR updates *before starting the next task*.
2. Post a **[RESULT]** or **[BLOCKED]** hub comment (template below) with exact PR/commit/CI evidence, real original-source coverage, source state, protected signed rows, newly published quantity count, exact evaluator result if run, first remaining gate, owner, and next unblocked task.
3. Update the originating lane tracker and the actual engineering PR where evidence belongs; link back to this hub. A hub comment does not replace reviewable code, a lane issue, or substantive PR evidence.
4. Check hub again after CI completes, after a peer handoff, before touching shared modules, before proposing a merge, and before your active session ends. If new work is unblocked, continue into the next task in your lane **without asking the user after each task**.
5. Work in bounded transactions: complete implementation, relevant positive/negative/metamorphic tests, reproducibility and original-source verification wherever available. If unable to complete, honestly label it incomplete and switch to an independent task; never count a partial as done. Respect execution/time/tool limits and report them.

**To request another agent's input:** post **[HANDOFF]** with FROM lane → TO lane, blocking first authority gate, precise required file/function/source evidence, exact producer/head SHA, acceptance test, and safe independent next step. Other agents should accept with **[CLAIM]**; no vague “please help.”

**To propose an integration:** post **[INTEGRATION]** listing component exact HEAD SHAs, stacking/overlap order, exact combined-tree CI status, immutable signed-run preservation comparison, original-source preflight status, owner-authorized scope. Leave a combined trial as draft/test-only until its required validation passes. No agent should claim an unmerged component is on main.

## 3. Required hub comment templates

**[JOIN]**
- LANE / UTC / TRACKER:
- READ: AGENTS.md + playbook + hub newest comment timestamp, related PRs:
- BASE main SHA / BRANCH / HEAD SHA:
- OWNED next first-failing gate and why it is independent:
- OTHER CLAIMS seen / blockers:
- READINESS: ACTIVE, SOURCE_BLOCKED, VALIDATION_BLOCKED, or TOOL_BLOCKED. Missing independent review is never a blocker.

**[CLAIM]**
- LANE + unique TASK ID (lane/date/object; no shared IDs):
- FIRST FAILED AUTHORITY (exact source receipt/gate, not a guessed score):
- FILES + FUNCTIONS traced / unchanged authority boundaries:
- WORKING BRANCH and source snapshot / intended PR:
- POSITIVE + NEGATIVE + original-source test plan:
- FALLBACK independent task if source/validation/tool blocked:

**[RESULT] / [BLOCKED]**
- LANE + TASK ID / STATUS (DONE only for fully implemented, tested and reviewable work; VALIDATION_BLOCKED, SOURCE_BLOCKED, TOOL_BLOCKED, FAILED or SUPERSEDED otherwise):
- EXACT HEAD, PR and CI RUN IDs + results:
- Original source PDF SHA/revision, page/viewport/snapshot/decision scope evidence actually verified:
- New FIRM quantity IDs / signed retention compared / customer projection verified (or NONE):
- Frozen exact V2 result only if actually run; denominator and project IDs; else NOT RUN / UNCHANGED NOT RECHECKED:
- First remaining gate, responsible lane and [HANDOFF] link:
- Next independent unclaimed task:

**[HANDOFF]**
- FROM → TO / TASK ID / linked PR and head:
- Exactly what source proof is missing:
- Producer file/function and reproducible first failure:
- Tests and acceptance to unblock:
- What must remain ABSTAIN / unmodified:
- Fallback if blocker persists:

## 4. Explicit lane ownership and highest-value current queues

**GPT1 — measurement and true quantities (tracker #2017):** Turn authenticated boundaries, finishes, ceilings, spans, openings and surfaces into source-closed FIRM metric measurements and customer-sealed rows. Start from original Maryborough FT2/FT3 floor/ceiling finish authority and Lot16 missing opening axis/kind/host-supported measurement, then wall/ceiling surfaces. Never convert source candidates or assumed door heights into FIRM; floor finishes end at internal wall faces and at door/threshold finish transitions as actually supported. Handoff only signed source receipts with canonical physical identity and complete evidence to GPT3.

**GPT2 — Maryborough drawing/source authority (tracker #2843):** Prove source page and viewport, room boundary and doorway-threshold ownership, page-7 ↔ page-11 FT2/FT3 occurrences, page-9 RCP IPF1/grid/WFPB ceiling attribution, physical room labels and original wall/face/cross-view evidence. Prioritize FREEZER, WASH UP, FOOD SERVICE/POS COUNTER, OFFICE, LAUNDRY, AIRLOCK and M-/F-AMB where first gate fails. Do not invent a closed room, nearest finish label, 2D cross-sheet registration or default metric area. Supply producer-owned proof to GPT1, with unresolved alternatives retained.

**GPT MAX — Lot16 physical opening topology (tracker #2396):** Prove structural host, full physical parent and frame identity, G17 dual-ended/single-pier competitors, STACKER 2127 and 1215 SGW original source ancestry, opening-universe completeness and count authority. Preserve existing historical eight Lot16 signed 0.54/0.90/1.26/1.80/2.16/2.16/5.67/10.08 m² rows; 1215 1.80 m² is historically signed, not a ninth new score. No inferred count=1, source-title alias, proximity match, snap-cap increase or false frame grant. Send authenticated source receipts to GPT1.

**GPT3 — source sealing, commercial output, reconciliation, safe release (trackers #2004, #2297):** Verify exact source physical identity → QuantityEvidence → sealed V1 or separately authenticated lineage supplement → customer rows → independently established physical-to-frozen identity binding → unchanged Full Plan V2 evaluator. Reject wrong trade/material mappings (tile versus vinyl/epoxy; windows versus doors), duplicate or forged scope, unproved count, missing family/units, incomplete signed customer parity. Integrate draft protection PRs without overwriting atomic activation receipts or regressing historical eight. Maintain exact-head CI ledger; original private source failure must be recorded as SOURCE_BLOCKED not production test success.

**Cursor — active implementation and cross-lane integration engineer (own cursor/ branches):** Own independent source-safe implementation, regression repair, typed positive/negative tests, source-authenticated producer-to-consumer integration and exact-head CI coordination for specifically claimed unblocked tasks. At the start of each active session, read this hub's current PR comments and lane trackers; post [JOIN] and [CLAIM]. Trace exact production functions and first failing authority, produce the required architecture report, then implement and validate without waiting for another reviewer. For each task, commit a reviewable PR, verify exact head with both Python versions and original-source receipt where accessible, and check historic signed source/customer output parity. After every substantive task, re-read the hub, post [RESULT] or [BLOCKED], and start the next independent unclaimed Cursor-suitable item. For upstream source evidence handoffs, tag the receiving GPT1/GPT2/GPT MAX/GPT3 lane with exact acceptance gates. Coordinate other agents' branches before integration. FIRM promotion, commercial activation and merge must remain within owner-authorized scope and pass required source, issuer, customer and CI checks; separate reviewer approval is not required.

**Anti Gravity — active original-source extraction, geometry and adversarial-test engineer (own antigravity/ branches):** Own explicitly claimed independent source-first-failure diagnosis and code/proof for PDF native/raster visibility, W2/W3/W4 wall topology, room/ceiling/finish source correspondence, opening host/frame ancestry, metamorphic/adversarial validation and bounded producer performance. Select the highest-impact unclaimed source gate from GPT2/GPT MAX/GPT1 handoffs; do not duplicate an already claimed investigation or assume an unmerged PR is on main. At each active session start read hub/trackers, post [JOIN] and [CLAIM], trace real sources/functions and record the required first architecture report. Implement on a separate branch, exercise source and negative tests, and make a source-backed PR without waiting for independent review. Re-read hub and post [RESULT] or [BLOCKED] after every substantive task, handing source-owned receipts to its measurement/identity lane; then continue on an independent unclaimed task. Never infer FIRM quantities or default area/count, or change original source/benchmark constraints. Implement and merge within owner-authorized scope only after required validation; independent review is optional.

**Copilot — optional research assistant, not an active coordination lane:** May investigate clearly assigned code/source questions and return exact file/function evidence to the requesting active lane. It must not create unsupervised source, FIRM, score or merge claims.

## 5. Known checkpoint to VERIFY, never assume current

Historical last independently verified **Lot16 8/27; Maryborough 0/24; combined 8/51 = 15.69%** (two-project subset, not 120-point completion). The unchanged exact evaluator and fresh producer runs are the only authority for a later result.

As of the 20 October GPT3 review, integrated draft #3445 source-signature/identity activation checks and focused Python3.13/3.14 checks passed, but two original-source workflows failed SHA preflight because exact original PDFs were absent from CI: Lot16 run 39369273043, Maryborough run 39369273052. This is **missing original input**, not proof of a code regression and not a new benchmark match. Secure source provisioning and exact-head rerun remain required.

## 6. Session exit / next-entry guarantee

Before ending an active session, post **[SESSION EXIT]** with completed work (not checks), open PRs, exact SHA, source gaps, outstanding validation and three ranked independent next tasks. At the next session, resume from GitHub hub + lane tracker, not the model's memory. Agents cannot be kept alive by phrasing alone; if they are not running or authorized, nothing is polling. The owner may separately create scheduled checks.