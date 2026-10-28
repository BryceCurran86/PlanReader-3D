# GPT3 — Exact source workspace identity at actual package builder (2026-10-29)

## Observed first production gate

On source-neutral main `98ce4bd77488894e7d13e4153b34197ef3205f58`, `build_publishing_package_from_workspace(conn, workspace_id: int)` opens SQLite and queries `workspaces WHERE id=?` without validating runtime type. SQLite INTEGER primary keys equate untrusted caller values `True`, `1.0` and `"1"` with real workspace `1`; the returned project/docs/pages/quantities become a new `PublishingPackagePayload` with caller-supplied alias in `workspace_id`, sealed by `compute_payload_hash`. Existing target JobHub job ID validation guards a different field *after* source selection and cannot prove the original selected workspace. This is a real PlanReader source identity discrepancy feeding the actual downstream JobHub writer.

## Change and downstream verification

Require `type(workspace_id) is int and workspace_id > 0` before database metadata/cursor/query. Never coerce Boolean, float, text, or truthy alias into project/source identity. Preserve current exact positive integer source selection, original document hash, quantity and approval evidence, revisions, client rate, pricing, unchanged full source hash and true customer publishing path. Real SQLite tests probe both commercial and draft modes; invalid aliases fail BEFORE any SQL trace and JobHub package/line writes; valid canonical ID 1 reaches validated/hashed real JobHub customer transaction in both modes with unchanged quantities.

## Safety and authority

No change to historical signed eight/full customer archives, four-project frozen V2 120/evaluator, original PDF/token, benchmark mapping, source scale/geometry cap/snap, GPT1/2/MAX/AntiGravity/Claude code, or #3796 trusted owner original8+9 pending replay. Synthetic source rows prove downstream exact identity gate mechanics only; do NOT promote original FIRM quantities or claim a new V2 score. Release requires complete exact-head Python3.13/3.14 CI, signed/customer/raster/performance companions, and final patch review.
