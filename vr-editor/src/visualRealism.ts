/** Render-only photometric controls for source-bound wall evidence.
 * These settings NEVER alter metres, geometry, source authority or quantities.
 * Ground/sky are deliberately marked as presentation context, not source BIM.
 */
export type LightingMood = "daylight" | "studio" | "dusk";
export type RenderQuality = "balanced" | "high";
export interface VisualPreset {
  label: string;
  background: number;
  ambientSky: number;
  ambientGround: number;
  ambientIntensity: number;
  sunColor: number;
  sunIntensity: number;
  sunPosition: readonly [number, number, number];
  exposure: number;
  materialRoughness: number;
}
export const VISUAL_PRESETS: Readonly<Record<LightingMood, Readonly<VisualPreset>>> = {
  daylight: {
    label: "Architectural daylight (illustrative)",
    background: 0xc6d9e5, ambientSky: 0xf0f7ff, ambientGround: 0x83918e,
    ambientIntensity: 2.0, sunColor: 0xfff2da, sunIntensity: 3.0,
    sunPosition: [9, 18, 7], exposure: 0.88, materialRoughness: 0.89,
  },
  studio: {
    label: "Neutral model studio (illustrative)",
    background: 0x182934, ambientSky: 0xd9ebf7, ambientGround: 0x667782,
    ambientIntensity: 2.3, sunColor: 0xf7fbff, sunIntensity: 2.0,
    sunPosition: [-8, 17, 11], exposure: 0.92, materialRoughness: 0.83,
  },
  dusk: {
    label: "Warm evening light (illustrative)",
    background: 0x354358, ambientSky: 0x849ac1, ambientGround: 0x574d48,
    ambientIntensity: 1.5, sunColor: 0xffc18c, sunIntensity: 2.2,
    sunPosition: [16, 9, 5], exposure: 0.91, materialRoughness: 0.91,
  },
};

export function isLightingMood(v: unknown): v is LightingMood {
  return typeof v === "string" && Object.hasOwn(VISUAL_PRESETS, v);
}
export function isRenderQuality(v: unknown): v is RenderQuality {
  return v === "balanced" || v === "high";
}
export function maxRenderPixelRatio(quality: RenderQuality, isXR: boolean): number {
  // Headset compositor controls its own size; don't add an expensive desktop multiplier.
  return isXR ? 1 : quality === "high" ? 2 : 1.5;
}
export function shadowMapSize(quality: RenderQuality): number {
  return quality === "high" ? 2048 : 1024;
}
/** Only authentic existing wall faces with stated heights may be lit as surfaces. */
export function mayRenderWallFace(
  kind: string | null | undefined, heightM: number | null | undefined,
): boolean {
  return kind === "wallFace" && typeof heightM === "number" &&
    Number.isFinite(heightM) && heightM > 0 && heightM < 1000;
}
