# Owner rule — external-door height when not specifically stated (9 November 2026)

Bryce's instruction: **assume 2100 mm for an authenticated external door if the plans do not specifically state another height**. This is an owner-authorized *estimating assumption*, not a measured/source-authenticated fact.

## Order of use

1. Resolve the height from a uniquely door-linked source schedule. If a specific height is stated, use it.
2. Otherwise resolve a specifically identified external-door elevation/plan height for that same door. If a different height is stated, use it.
3. If neither specifically identifies the door's height and there is no unresolved specific exception, use **2100 mm as a provisional review estimate** for that authenticated external door only. Show “Assumed 2100 mm — verify on site.”
4. Conflicting schedule/elevation evidence, another stated but unverified height, an unbound general joinery-height note, an unproven door identity, a window/internal door, or an unresolved exception: do not silently treat 2100 as measured. Stop for review or use the explicit owner-approved measurement route for review with its own provenance.

## Authority and implementation

Source-authenticated figured height and an owner assumption are different authority classes. A default may support a *labelled provisional costing line with review provenance* ("Assumed 2100 mm — verify on site"), but it never by itself creates FIRM `QuantityEvidence`, a source-closed signed measurement or a frozen120 score. It also cannot manufacture a missing opening host, frame, typed door kind or width.

Policy helper: `pb_external_door_height_estimate_policy.resolve_external_door_height_estimate`. The helper stays read-only. The live opening issuer may consume the assumption case as a labelled provisional customer quantity once the door, unique EXTERNAL host and printed width are already authenticated.

The default does not apply to internal doors, windows, garage panels or generic joinery elements. Existing signed Lot16 eight and Maryborough three and the immutable 2.5-point snap / 20,000 primitive limits remain unchanged.
