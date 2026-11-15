# Owner rule — door height when no page of the plans states one (16 November 2026)

Bryce's instruction: **if no page of the plans states a height for that door — schedule, elevations or floor plans — use the standard door height of 2100 mm for authenticated hinged doors, including internal doors. If the app cannot find the door height, the line needs user review.** This is an owner-authorized *estimating assumption*, not a measured/source-authenticated fact.

## Order of use

1. Resolve the height from a uniquely door-linked source schedule on any page. If a specific height is stated, use it.
2. Otherwise resolve a specifically identified door elevation or floor-plan height for that same door on any page. If a different height is stated, use it.
3. If no page states that door's height and there is no unresolved specific exception, use **2100 mm as a provisional review estimate** for that authenticated hinged door, whether its unique host is EXTERNAL or INTERNAL. Show “Assumed 2100 mm — verify on site” and keep the customer line on user review.
4. Conflicting schedule/elevation evidence, another stated but unverified height, an unbound general joinery-height note, an unproven door identity, a window, garage panel, sliding/stacker, cased opening, joinery, or an unresolved exception: do not silently treat 2100 as measured. Stop for review or use the explicit owner-approved measurement route for review with its own provenance.

## Authority and implementation

Source-authenticated figured height and an owner assumption are different authority classes. A default may support a *labelled provisional costing line with review provenance* ("Assumed 2100 mm — verify on site"), but it never by itself creates FIRM `QuantityEvidence`, a source-closed signed measurement or a frozen120 score. It also cannot manufacture a missing opening host, frame, typed door kind or width.

Policy helper: `pb_external_door_height_estimate_policy.resolve_external_door_height_estimate`. The helper stays read-only. The live opening issuer may consume the assumption case as a labelled provisional customer quantity once the door, unique EXTERNAL or INTERNAL host and printed width are already authenticated.

The default does not apply to windows, garage panels, sliding/stacker, cased openings or generic joinery. Existing signed Lot16 eight and Maryborough three and the immutable 2.5-point snap / 20,000 primitive limits remain unchanged.
