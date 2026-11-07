# GPT3 source-worker process-group cleanup — 2026-11-06

## Observed repository behavior (not an accuracy result)

Read `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, current `tools/gpt3_owner_all_source_role_handoff.py`, `tools/run_source_closed_project_handoff.py`, `tools/four_job_windows_launcher.py`, `tests/test_four_job_windows_launcher.py` and current original-run safe status.

Real source-to-seal runtime path: `produce_all_source_roles` iterates each SHA-verified original document and calls `run_logged` in `four_job_windows_launcher`; it starts `tools.run_source_closed_project_handoff`, which invokes `collect_live_physical_net_wall_claim`, then proceeds to sealed/customer verification only after the child reports success. At resource abort `run_logged` calls `kill_tree`.

**First demonstrated defective code path:** before this patch, `kill_tree` used `proc.kill()` on POSIX. `sample_memory_kb` deliberately measures descendant processes, but the cleanup killed only their parent. A producer that launches OCR/PDF subprocesses could therefore leave live descendants after a `MEMORY_LIMIT` or `TIMEOUT` decision.

Private original Maryborough run 42059298510 is a **confirmed RESOURCE FAILURE** (`MEMORY_LIMIT`) after original source hashes and dependencies passed. It has **not** been demonstrated that orphan descendants caused its initial allocation overrun. Repairing cleanup is not evidence that the memory limit itself is solved.

## Inferred impact

An orphan may retain memory / CPU and interfere with subsequent source-role attempts even though its parent failed and the caller correctly did not issue signed quantities. This is a process lifecycle problem, independent of physical/measurement authority.

## Proposed and implemented bounded repair

- On POSIX, launch each `run_logged` child with `start_new_session=True`, placing its child processes in a newly isolated process group.
- On resource abort/timeout use `os.killpg` with `SIGKILL` **only when** the target process group's ID is its recorded worker PID and differs from the caller's group. For an ungrouped supplied process, only kill that process; never signal the caller's group. Reap the parent with `proc.wait()`.
- Preserve existing Windows `taskkill /T /F`, return codes, resource thresholds, SHA verification, score/frozen contracts, and private log paths.
- Source-neutral positive/negative tests spawn a descendant and prove it dies under both TIMEOUT and deterministic MEMORY_LIMIT; a separately created unrelated group must survive.

## Explicit nonclaims and untouched boundaries

**No claim** of reduced peak memory, completed Maryborough original producer, new Q5446/Lot16 quantities, signed/customer count increase, or official frozen 120 accuracy. No modifications to `pb_source_observation_authority.py` (GPT1 #4220 active claim), source original PDFs, V2 scorer or target truth, quantity issuers, W2/W4, 20,000 primitive cap or 2.5pt snap. An original run at the next changed producer head is still needed to determine the real Maryborough memory allocation blocker.
