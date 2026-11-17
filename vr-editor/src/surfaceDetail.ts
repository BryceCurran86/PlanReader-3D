/** Source-safe presentation helpers: never create walls, sizes or measured finishes. */
export type SurfaceDetail = "smooth" | "subtle";
export function isSurfaceDetail(value: unknown): value is SurfaceDetail {
  return value === "smooth" || value === "subtle";
}
/** Two triangles spanning an EXISTING source-derived wall face.
 * UVs describe only renderer texture repeat; they cannot authorize a wall finish.
 */
export function sourceWallUV(lengthM: number, heightM: number): Float32Array | null {
  if (!Number.isFinite(lengthM) || !Number.isFinite(heightM) ||
      lengthM <= 0 || heightM <= 0 || lengthM > 10000 || heightM > 1000)
    return null;
  // 2 repeats per presented metre makes microvariation independent of wall span.
  const u = lengthM * 2, v = heightM * 2;
  return new Float32Array([0, 0, u, 0, u, v, 0, 0, u, v, 0, v]);
}
/** Draw only bounded, deterministic micro-roughness. No external texture data or material schedules. */
export function createPresentationRoughnessTile(): Uint8ClampedArray {
  const size = 64;
  const output = new Uint8ClampedArray(size * size * 4);
  let seed = 0x624b92bd;
  for (let i = 0; i < size * size; i++) {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    const grey = 231 + (seed % 17);
    const p = i * 4;
    output[p] = grey; output[p+1] = grey; output[p+2] = grey; output[p+3] = 255;
  }
  return output;
}
