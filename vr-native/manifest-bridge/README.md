# Native Unity 6 / PC VR JSON scene handoff — review only

The original PlanReader app remains the sole source of dimensions, walls,
source evidence, edits and commercial quantities. The existing Python
`pb_vr_editor_scene_manifest.compile_editor_scene` produces a versioned,
source-bound, READ-ONLY scene for the React/Three.js browser viewer.

This isolated .NET 8 console bridge is the **first native consumer-side gate**
for a future Unity 6/SteamVR/OpenXR application. It is NOT a Unity player,
does not run in Unity yet and does not detect a PS VR2 headset. It has no
network dependency, login/tenant authority, native building detector or
edit/quantity output. Future Unity integration must implement actual meshes
and headset interaction separately and must not bypass this local trust boundary.

The bridge reads a single **local** UTF-8 manifest (max 16 MiB, 20,000
objects, strict JSON, max nesting 32) and emits a pared-down JSON
`walls` preview packet to standard output. The `scope` carries exact
workspace/project/document/revision/snapshot, original source SHA-256 and
model revision; coordinates are metres with no unknown transform.
Surfaces and unsupported geometry are rejected.

Every local source object is forcibly downgraded to `review`; all
`measurementAuthorized`, `locallyAuthenticated`, `canEdit` and
`commercialQuantityPublicationAllowed` flags are always false. Claims
of `firm` or `verified` from an imported file are never authoritative.

## Build and smoke

```powershell
dotnet build .\vr-native\manifest-bridge\PlanReader.ManifestBridge.csproj -c Release
dotnet run --project .\vr-native\manifest-bridge\PlanReader.ManifestBridge.csproj -- .\vr-native\manifest-bridge\tests\valid-review-scene.json
```

On Windows GitHub Actions, `Test-ManifestBridge.ps1` compiles the native
package and checks valid, forged source hash, forbidden publication, stale
model revision, forged surfaces and duplicate IDs. This validates the
consumer contract, not a real Unity6 player or the original-source PDF.

Private source PDFs, signed/customer output, frozen120 and the original
production measurement engine stay untouched. No Unity 6 binaries are
asserted or fabricated.
