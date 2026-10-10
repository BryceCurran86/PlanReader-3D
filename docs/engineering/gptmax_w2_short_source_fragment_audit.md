# GPT MAX — W2 real original-source short fragment retention audit

Original Lot16 PDF source SHA: `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`. The unfinished capture+W2 experiment (draft PR #2161) demonstrates 23 physical openings, 18 hosts and nine frames, compared with retained production 23/14/9. The experiment **must not be merged yet** because old host/frame receipt identities change, including two physical W4 wall candidate path/provenance changes near independent supplemental T intersections.

Source-first unresolved fragment examples:
- Original raster source primitive suffix `:1585` (opening `2c31ccb...`) has a short authentic source fragment x=410.25, y=341.50..342.72, 1.22 PDF points. Supplemental source T changes the locally assembled W4 wall start to y=342.72; continuity/identity is not automatically proved.
- Original raster source primitive suffix `:324` (opening `661fc5e6...`) has short authentic source fragment at y=531.25, x=582.60..584.50, 1.90 PDF points. Shortened W4 source-owned extent cannot be assumed equivalent to old identity.
- Ordinary source primitive suffix `:1567` in the positive Lot16 T has a **separate unproven y=336.75..338.75 gap**. No short-fragment audit may convert that into a wall connection.

## New read-only audit

`pb_wall_room_topology_short_fragment_audit.audit_short_source_fragments` compares the genuine W2 pre-snap split-fragment inventory to the W2 post-snap edges and post-collinear-merge leaf lineage, using the original producer-positive single source primitive and its page-coordinate coverage for each fragment.

It distinguishes `RETAINED_RAW_EDGE`, `COLLINEAR_MERGED`, `SNAP_COLLAPSED` and `UNRESOLVED_MERGE_ANCESTRY`; records original PDF-point geometry and maximum raw endpoint displacement from final snapped W2 nodes, without modifying any geometry, merging wall identities, manufacturing host owners or closing unproven gaps.

By default nothing changes in W2 output. Only when `GPTMAX_W2_SHORT_SOURCE_AUDIT=1` is present does W2 attach the read-only `short_source_fragment_retention_audit` sidecar to its graph. The audit's threshold is precisely the **existing W2 snap tolerance**, used only to select short fragments for observation. Neither the 2.5pt tolerance nor any primitive geometry is modified. The report explicitly forbids host/count/metric quantity publication and contains no benchmark accuracy figure.

Validation includes positive authenticated source fragments, snap collapse, retained merge leaf lineage, source endpoint displacement, source-lacking/different parent, invalid source, duplicated raw IDs, nonfinite geometry, integrity, and a production-output parity check showing graph authority unchanged by opt-in. The pull request must pass full CI, performance checks and any required original Lot16 and Maryborough source jobs before merge.

Next production repair, not included: preserve source-owner mapping of the two changed W4 physical candidate regions using original child-fragment observations. A physical equivalence claim needs independent full source coverage; this diagnostic alone does not authorize it.
