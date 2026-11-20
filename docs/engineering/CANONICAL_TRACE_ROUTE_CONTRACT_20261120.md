# Canonical original PlanReader trace route — mandatory agent contract

**Owner directive, 20 November 2026.** Do not mistake a supplementary diagnostic
for the original app's source-native tracing, or declare earlier work regressed
without comparing the same producer on the same original PDF.

## Approved production-app source-native preview

- UI entry: `pb_planreader_3d_app.plan_mapper_page`
- Actual preview: `pb_new_source_trace_preview.source_native_trace_preview`
- Exterior stage: `pb_new_exterior_wall_preflight.attempt_source_native_outer_wall_first`
- Native wall/ring stage: `pb_layered_wall_doorway_room_ring_shadow.build_layered_wall_doorway_room_rings`

These are SUPPLEMENTARY diagnostics, not the full user-visible preview:
- `pb_external_footprint_first_trace.trace_external_footprint_first`
- `pb_external_footprint_inside_face_runtime.run_inside_face_footprint_runtime_stage`
- `tools/run_original_footprint_first.py`

A candidate outline is never authenticated commercial wall/floor geometry.
Results from those substage calls may not be compared against previous full-app
preview results as if both executions were equivalent.

## Exact-head private source execution

Run from a full checked-out repository using SHA-pinned private PDFs:

```bash
python tools/run_canonical_source_native_preview.py \
  --pdf "$PRIVATE_SOURCE_PDF" \
  --page-index 2 \
  --source-sha256 "$EXPECTED_PDF_SHA256" \
  --expected-head-sha "$EXACT_40_CHAR_GIT_COMMIT" \
  --out-dir "$PRIVATE_RESULTS_DIRECTORY" \
  --purpose preview
```

The command fails closed for wrong code revision, source, page, producer,
legacy envelope fallback or commercial authority. It writes a private PNG
and receipt with canonical route, source SHA, head SHA and actual status/reason.
Do not copy private PDF bytes, unredacted customer details or generated private
overlays into the public repository, workflows, PRs or coordination hub.

## Mandatory regression comparison

1. Identify earlier known-good PR and exact commit plus PDF SHA and page.
2. Run the SAME canonical function on known-good and current exact commits
   against the SAME original PDF bytes. Do not substitute a raster or inside-face
   diagnostic even if it is newer and reports closed contours.
3. Compare actual source-native outside-wall path owners, party wall role,
   garage/opening/window bridges, outside walk, room rings, status and runtime.
4. Only if identical-route evidence shows regression, bisect the actual changed
   commits. Preserve existing working original-engine code; do not rebuild it.
5. Run protected original source -> physical/metric -> issuer/customer/seal and
   unchanged frozen120 scorer separately for actual four-job accuracy. Acacia
   remains a held-out separate test. No preview may claim official score.

If checkout/private source is unavailable, report BLOCKED, never invent a run.

## Continuous CI check

The existing required CI job runs `scripts/check_canonical_trace_route.py`
and the public regression suite includes `tests/test_canonical_trace_route_guard.py`.
These block unexpected app/runner route substitution and wrong-producer receipts.
Public CI alone cannot certify protected drawing accuracy.
## Reuse the owner's already-uploaded private sources

The private 18-file ZIP and SHA-256 manifest already exist in the owner's ChatGPT Library. First look in conversation attachments and Library; materialize if not mounted. **Do not ask for another upload of the originals.**

Use the all-in-one source preflight and real source-native preview:

    python tools/run_verified_planreader_sources.py --check-only
    python tools/run_verified_planreader_sources.py --project 3Laurel

Without --project, the launcher covers the five source projects (official four plus held-out Acacia) and configured original plan pages. It discovers the mounted full 18-file archive, rejects incomplete or tampered files, pins the current exact Git HEAD, invokes only the already-approved canonical source-native preview, and writes private per-project PNG/JSON plus a summary.

The optional PLANREADER_PRIVATE_SOURCE_BUNDLE environment variable selects the materialized private archive. Never add private PDF bytes, contract data, or source images to public CI or GitHub. If the source preflight passes but the full checkout is absent, report **original code checkout unavailable**, not missing owner drawings. Preflight is not a completed app run and preview is not frozen120 scoring.

