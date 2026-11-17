# Cursor execution handoff — owner wall/room fix #4443

**Current owner assignment: Cursor, superseding the prior AntiGravity handoff.**

Open this repository in Cursor. Read `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, `.cursor/rules/planreader-wall-closure-4443.mdc`, and the source-specific details in `docs/engineering/ANTIGRAVITY_RUN_WALL_CLOSURE_4443.md` (legacy document name retained for link continuity). Coordinate on [#4135](https://github.com/BryceCurran86/PlanReader-3D/issues/4135) and track [#4443](https://github.com/BryceCurran86/PlanReader-3D/issues/4443).

Use this Cursor terminal command from the repository root, substituting the actual private original PDF path and a private output folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run_cursor_wall_closure.ps1 `
  -Pdf "C:\PRIVATE\original_acacia.pdf" `
  -PageIndex 1 `
  -OutDir "C:\PRIVATE\cursor_wall_closure" `
  -ExpectedSha256 "435a6b610fea904f2b27dc330667d92a25919ada3368e5905e58ff92e047f37a"
```

This runs the existing read-only original-source footprint, edge ownership, and room diagnostics, plus focused public regression tests. It requires local access to the actual PDF and Python 3.13 dependencies. The source and generated overlays stay outside Git.

**Definition of done:** Two fabricated boxes removed without smoothing genuine recesses; source-paint-preserved continuous walls; real hosted openings and threshold-only virtual closures; closed, valid, non-overlapping room rings for the owner-highlighted BED5/WIR/BATH/LIVING portions wherever source supports them; living/kitchen open plan not fabricated into separate rooms; no customer area without authenticated physical/metric/finish lineage; exact-head tests green, original overlay visually reviewed, protected source/signed/frozen120 checks intact; code pushed and merged. Unproved gaps remain explicitly ABSTAIN.

PR #4445 is the existing wall/opening shadow arbitration; PRs #4423/#4436/#4437 relate to Acacia native exterior paths. PR #4450 provides this runner/handoff. Merge nothing blindly; inspect up-to-date branches and approvals/checks. Posting these instructions does **not** launch Cursor automatically.
