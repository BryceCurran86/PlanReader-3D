/** Local JSON is NEVER the authenticated original-source surface producer.
 * Strip verified mesh payloads before any renderer sees imported data.
 */
import type { SceneManifest } from "./types";
export function downgradeLocalManifest(source: SceneManifest): SceneManifest {
  const { sourceSurfaces: untrustedSourceSurfaces, ...scene } = source;
  void untrustedSourceSurfaces;
  return {
    ...scene,
    objects: scene.objects.map(object => ({
      ...object,
      renderState: "review" as const,
      unresolvedIssues: [...new Set([
        ...object.unresolvedIssues, "local_manifest_not_authenticated",
      ])],
    })),
  };
}
