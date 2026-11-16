# Shared building envelope vs multiple dwellings — source-native tracing contract
**PlanReader original tracing, 16 November 2026.**

## Correct hierarchy (general rule, not per-room hardcoding)

1. **Building footprint / external envelope:** The complete outside-facing boundary of the ONE connected building, including all attached dwellings and enclosed garage sections. Exclude explicitly exterior ALFRESCO, PORCH, open carport and freestanding posts.
2. **Dwelling zones:** One building can contain two or more separately occupied dwellings. Trace each dwelling's inside faces as *subregions*, not as alternative outside building envelopes.
3. **Party / inter-tenancy / demising wall:** A physical wall between those dwellings is a **real shared wall**; it counts once in the physical inventory and may bound both dwelling subregions. It is NOT part of the external building perimeter merely because it is continuous and closes a clockwise/left-turn inside-face walk.
4. **Room loops:** Enclosed rooms within each dwelling; boundaries cross source-authenticated windows and close real door thresholds, but clear door apertures are not opaque wall or billable floor under a wall.

**Do not assume** the drawing layer `Enclosure_WallExternal` proves external envelope role. Source CAD categories describe a graphic family, not necessarily an *outside-facing wall*. Likewise, a leftmost-turn walk returning to its start proves only a planar cycle, not its semantic role.

## Generic source role evidence

`pb_source_shared_dwelling_envelope_shadow.py` locates original `PARTY WALL` annotation word(s) from one native source block, nearby long, dark-painted, named CAD wall bar(s), and source room labels on **both opposite sides**. It preserves the actual annotation word IDs, painted wall path IDs and adjoining role labels. It does not infer a party wall from thickness, a user-coloured screenshot, a disconnected note or a left-only closed ring. It does not promote a role into `pb_wall_role_authority.WallRoleClassification.PARTY` without that sealed authority's separate source evidence.

`closed_loop_uses_interior_dwelling_divider` compares a candidate loop to the real wall's **long faces**, and vetoes when the loop traverses at least 55% of a shared wall face. Touching the party wall at its two external endpoints is allowed: the **correct full building envelope** passes those junctions while leaving the separating wall inside. All positive cycles still require independently authenticated full external wall/door/window continuity; this role check is a VETO, not an inferred hull or geometry snap.

The original `pb_new_exterior_wall_preflight.attempt_source_native_outer_wall_first` now produces separate read-only `shared_dwelling_divider_candidates` and a party-wall-specific ABSTAIN reason if it encounters a closed-but-wrong unit envelope. It retains any real unjoined source walls beyond that candidate. The `pb_new_source_trace_preview` displays the proposed party wall in purple and the candidate dwelling zones in JSON. No commercial quantities, old signed areas, benchmark truths or private PDF bytes are changed.

## Verified original 3Laurel p3 source

The original construction plan labels **C.S.R TIMBER PARTY WALL SYSTEM — 220mm STUD TO STUD (260 TOTAL)** in the note by the long shared vertical wall near PDF x354–360 y192–457. Exact native annotation words: **733 'PARTY'** and **734 'WALL'**, and original source-painted wall paths **1139, 1027, 1029, 1031**. The physical divider is classified under the original `Enclosure_WallExternal` CAD layer despite lying **inside** the combined building. Actual named rooms exist to its left and right. User explicitly confirmed **TWO separate dwellings under ONE building footprint**, and clarified the divider is NOT the exterior boundary.

The existing left-hand Bed5/Living contour is a *dwelling candidate*, not the complete connected building exterior. Its early closure must not reject the real right-hand bedrooms, Media or Garage as outside. ALFRESCO and PORCH are excluded; timber post 4102 is not a physical external wall. On original source replay, the initial outer trace still ABSTAINS because 130 actual structural wall bars remain outside the current wall-body candidate and no full verified shared external polygon exists. No wall/ceiling/floor quantities are authorized by this change.

## Safety and acceptance

- Unit tests: one building with two subregions, party note + original dark physical wall, negative annotation/white floor/unknown source/outdoor labels, wrong-side room labels and no wall, partial unit loop rejection vs legitimate whole-building loop *not* rejected, invalid geometry.
- Original p3 replay must identify one candidate party divider, keep its original source IDs, reject partial unit loop, retain original unrelated 130 outside wall bands, and return `measurement_authorized=False`.
- Single-dwelling plans without original supported party evidence must keep existing tracing behavior.
- Existing full source owner, frozen 120 development benchmark and real customer issuer remain unchanged.

**Next step:** classify outside-facing wall graph by unbounded external region adjacency, with the party edge belonging to two enclosed dwelling zones rather than the outside face. Run exact original source replay before approving any new building perimeter. Do NOT invent a hull or draw a wall from a label.
