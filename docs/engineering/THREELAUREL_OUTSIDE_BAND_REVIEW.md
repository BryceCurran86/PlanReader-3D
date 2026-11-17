# 3Laurel — unresolved exterior source-band review (noncommercial)

Owner original: `3LAUREL - Construction Plan Set Rev3 08.05.26.pdf`, page 3 (0-based index **2**). Verify SHA-256:

`014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e`

**Never copy the PDF or resulting native geometry/overlay receipts into the public Git checkout, PR comments or CI artifacts.** The original is held privately by the owner.

From the project root in Cursor's authorized local Python 3.13 environment:

```powershell
py -3.13 tools/run_source_outside_residual_owner_review.py `
  --pdf "C:\PRIVATE\3LAUREL - Construction Plan Set Rev3 08.05.26.pdf" `
  --expected-sha256 014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e `
  --page-index 2 `
  --private-output "C:\PRIVATE\3laurel_replay\unresolved_outside_bands.json"
```

## What the receipt establishes

- The **canonical existing** source-native preflight status and reason; the tool does not draw or infer missing geometry.
- Number of two-dwelling source-closed interior zones (previous accepted candidate: two).
- Every unresolved exterior band (up to a bounded 32-band review sample), exact native PDF point bounding box and its *locally intersecting* original path IDs, not unrelated members of huge vector composites.
- A fixed prohibition on commercial quantity, wall-authentication and score promotion.
- When `all_unresolved_bands_in_sample=false`, investigate further; the sample is incomplete.

The latest source audit found 148 outside-looking bands, 137 authenticated nonwalls and 11 still unresolved WallExternal-bearing bands. These counts are an **observed checkpoint**, not a hardcoded correct quantity. Determine the current live replay result.

For each unresolved path group, examine the original source-native layer, fill, line/stroke, adjacent wall ends, host relationship, contact with the exterior face versus the PARTY divider, and viewport/figure ownership. Distinguish real external walls, internal/party walls, posts, alfresco/porch structure, and annotation/service paths **only when independently proven**. Do not label the 11 as nonwalls merely to reach zero.

A safe end state requires no unidentified outside structural bands, verified source-painted connected exterior and genuine hosted openings, valid two-dwelling topological boundary, full exact-head CI, source privacy and independent physical wall/metric authority. A closed preview still has `building_footprint_authenticated=false` and `measurement_authorized=false` until those authority gates pass.

Original p3 negative example: paths 10847 and 10853 are vertical unfilled `Annotation_FloorPlan` dimension extension lines and must not create protruding external walls. Genuine PARTY/host paths 1027/1029/1031/1139/1708/1709 are black-filled `Enclosure_WallExternal` and must not be erased.

Relevant PRs: main-integrated #4442 and #4448, bounded new diagnostics #4456, Cursor source-backed detour correction #4452. Historical stacked #4440 was closed as superseded; do not reinstate its `structural_outside=[]` polygon-equality shortcut.
