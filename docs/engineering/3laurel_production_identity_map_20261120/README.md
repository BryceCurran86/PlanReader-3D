# 3Laurel independent 22-finish identity reconciliation — 20 Nov 2026

This is benchmark-side identity mapping ONLY, not a production issuer or a frozen truth change. The source is the original 3Laurel Rev3 PDF with SHA-256 014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e.

The original 23 opening identity bindings in the 20261106 file are preserved exactly. The new map adds 22 unique physical object bindings: 3 vinyl floors, 4 wet tiled floors, 8 wall tile faces, 7 ceiling finishes. Binding is by independently source-owned physical object ID and quantity family, never by room-label similarity or matching expected values.

On the authenticated original PDF, the existing source issuer returned 22 FIRM_SOURCE_CUSTOMER_TO_REVIEW sealed quantities and 22 verified customer review rows. The unchanged frozen project evaluator independently found 22/63 exact development matches, 41 absent items from the isolated finish run, 0 unsupported extra and 0 lineage conflicts. Protected original-positive regression validates this. Public CI can explicitly skip the source test when the PDF is absent; that skip is NOT source acceptance.

The previous saved 17/63 3Laurel development matches were opening_area quantities, disjoint from these 22 finish targets. If a NEW combined sealed/project source run retains those 17 matches, 3Laurel may reach 39/63; if the other projects' previous 15 matches also survive, the four-project development score could reach 54/120 = 45%. **These figures are conditional, not freshly scored or published.** The frozen project manifests still report INCOMPLETE, so the official score remains UNPUBLISHED.

To run the original four-project scorer, copy this identity_map.json to the private scorer's identity-map directory as au_qld_3laurel.identity_map.json, and supply the exact-source combined sealed/customer-verified production output. Do not copy private drawings or customer data into GitHub; do not modify frozen reference_takeoff.json, source_manifest.json or evaluator.py.

Run test: python -m pytest -q tests/test_gpt1_3laurel_finish22_frozen_reconciliation.py. With the actual original PDF, set PLANREADER_3LAUREL_ORIGINAL_PDF to its authorized private file path.
