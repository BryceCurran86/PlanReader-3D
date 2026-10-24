# Antigravity Pipeline Partial Failure Recovery and Graceful Degradation Report (v1)

## Compliance & Context

### Files Actually Read
- `AGENTS.md`
- `docs/AI_ENGINEERING_PLAYBOOK.md`
- `pb_source_memory_efficient_plan_processing_shadow.py`
- `pb_source_geometry_engine_shadow.py`
- PR #3462 (shared coordination hub)

### Exact Functions Traced
- `pb_source_memory_efficient_plan_processing_shadow.StreamingPagePlanProcessor.process_plan_stream`: Streaming page lifecycle
- `pb_source_geometry_engine_shadow.SourceGeometryEngine.compile_plan_geometry`: Plan compilation

### Authority Boundaries Crossed
- Subsystem fault isolation, error quarantine, and partial plan geometry preservation.
- Strictly non-publishing shadow authority (`status = CANDIDATE`, `commercial_projection_allowed = False`, `takeoff_eligible = False`).

### Expected Abstentions Before Any Tests
- Any subsystem experiencing an unhandled exception, syntax error, or timeout is quarantined with `SubsystemStatus.QUARANTINED` and abstains.
- Downstream commercial projection and takeoff eligibility remain strictly `False` for quarantined subsystems.
- Surviving subsystems retain authenticated candidate geometry without contamination.
- Customer retention baseline preserved byte-for-byte.

### Files That Will Remain Untouched
- All benchmark gold and holdout definitions (`benchmarks/**`).
- Production extractors and commercial writers.
- 20,000 primitive safety cap and 2.5 pt snap tolerance.

---

## 1. Observed Repository Behavior

Complex multi-page architectural plan sets contain diverse subsystems: structural wall systems, physical openings, room boundaries, floor finishes, reflected ceiling plans, and schedules. Under existing monolithic execution paths, if one subsystem or page encounters a localized failure (such as an unsupported font program, a corrupted vector stream, or a processing timeout), the entire document extraction is aborted, discarding all valid geometry on preceding and succeeding sheets.

---

## 2. Inference

A resilient pipeline requires:
1. Subsystem boundary isolation (`SubsystemKind`):
   - `WALLS`, `OPENINGS`, `ROOMS`, `FINISHES`, `CEILINGS`, `SCHEDULES`, `LEVELS`.
2. Fault quarantine:
   - When a subsystem fails, it is quarantined with `SubsystemStatus.QUARANTINED`, preserving the error code and diagnostic notes.
   - Healthy subsystems continue execution independently.
3. Partial recovery compilation:
   - Compiles a `PartialPlanRecoveryReport` detailing healthy vs quarantined subsystems, ensuring downstream consumers receive valid partial geometry with explicit boundary flags rather than a hard crash.

---

## 3. Proposed Change

Implement `pb_source_pipeline_failure_recovery_shadow.py` with:
- `SubsystemKind` and `SubsystemStatus` enums.
- `SubsystemRecoveryResult` and `PartialPlanRecoveryReport` dataclasses.
- `PipelineFailureRecoveryShadowAuthority`:
  - `execute_guarded_subsystem(subsystem_kind, callable_fn, *args, **kwargs) -> SubsystemRecoveryResult`
  - `compile_recovery_report(document_id, revision_id, source_sha256, page_count) -> PartialPlanRecoveryReport`
- Invariants:
  - Candidate status only.
  - Quarantined subsystems never publish or project commercially.
  - Zero benchmark gold dependencies.

---

## 4. Benchmark Observations That Must Not Influence Implementation

- No specific project names or benchmark metrics are referenced.
- Purely generic error handling, exception sanitization, and fault quarantine.
