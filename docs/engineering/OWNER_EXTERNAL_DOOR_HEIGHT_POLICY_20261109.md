# Owner rule — standard external-door height when unstated (25 November 2026)

Bryce's instruction is to **assume 2040 mm for an authenticated standard external door if the plans do not state a height**. Use it as a provisional estimate.

## Order of use

1. Resolve the height from a uniquely door-linked source schedule. If a specific height is stated, use it.
2. Otherwise resolve a specifically identified external-door elevation/plan height for that same door. If a different height is stated, use it.
3. If neither source states a height and there is no unresolved specific exception, use **2040 mm as a provisional review estimate** for the authenticated standard external door. A width-only schedule row can qualify. Show “Assumed 2040 mm — verify on site.”
4. Send conflicting or unverified height claims, unbound joinery-height notes, unproven door identities and unresolved exceptions to review.

## Authority and implementation

The default supports a labelled provisional costing line with review provenance (“Assumed 2040 mm — verify on site”). Source evidence is required for a firm quantity, signed measurement or benchmark credit, and for the opening's host, frame, kind and width.

Policy helper: `pb_external_door_height_estimate_policy.resolve_external_door_height_estimate`. The helper stays read-only. The live opening issuer may consume the assumption case as a labelled provisional customer quantity once the door, unique EXTERNAL host and printed width are already authenticated.

The default does not apply to internal doors, windows, garage panels or generic joinery elements. Existing signed Lot16 eight and Maryborough three and the immutable 2.5-point snap / 20,000 primitive limits remain unchanged.
