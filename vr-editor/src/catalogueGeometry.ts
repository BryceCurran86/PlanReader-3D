import * as THREE from "three";
import type { ItemTarget, ItemVisual, Pattern, TrimProfile } from "./itemCatalogue";

type FinishSpec = Extract<ItemVisual, { kind: "surface" }>;
type TrimSpec = Extract<ItemVisual, { kind: "trim" }>;

function makePattern(pattern: Exclude<Pattern, "solid">) {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 128;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.fillStyle = "#f9f9f9";
  ctx.fillRect(0, 0, 128, 128);
  let seed = 7;
  const random = () => {
    seed = (1664525 * seed + 1013904223) >>> 0;
    return seed / 0x100000000;
  };
  if (pattern === "grain" || pattern === "plank") {
    for (let index = 0; index < 92; index++) {
      const x = random() * 128;
      ctx.beginPath();
      ctx.strokeStyle = index % 3 ? "#a99f9636" : "#7f746639";
      ctx.moveTo(x, 0);
      ctx.bezierCurveTo(x + random() * 7, 42, x - random() * 7, 87, x, 128);
      ctx.stroke();
    }
    if (pattern === "plank") {
      ctx.fillStyle = "#8e847b";
      ctx.fillRect(0, 0, 2, 128);
      ctx.fillRect(0, 0, 128, 1.5);
    }
  }
  if (pattern === "tile" || pattern === "fleck" || pattern === "woven") {
    const spots = pattern === "woven" ? 1200 : pattern === "fleck" ? 260 : 66;
    for (let index = 0; index < spots; index++) {
      ctx.fillStyle = index % 3 ? "#a09a9040" : "#76706a63";
      const scale = pattern === "fleck" ? 1.8 : 1;
      ctx.fillRect(random() * 128, random() * 128, 0.6 + random() * scale, 0.7 + random() * scale);
    }
    if (pattern === "tile") {
      ctx.fillStyle = "#818181";
      ctx.fillRect(0, 0, 2, 128);
      ctx.fillRect(0, 0, 128, 2);
    }
  }
  if (pattern === "rib") {
    const shade = ctx.createLinearGradient(0, 0, 128, 0);
    shade.addColorStop(0, "#64605c");
    shade.addColorStop(0.15, "#dad6cf");
    shade.addColorStop(0.27, "#faf7ed");
    shade.addColorStop(0.78, "#f5f0e6");
    shade.addColorStop(1, "#7f796e");
    ctx.fillStyle = shade;
    ctx.fillRect(0, 0, 128, 128);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.anisotropy = 4;
  return texture;
}

export function finishMesh(
  host: THREE.Mesh, spec: FinishSpec, target: ItemTarget, normal: THREE.Vector3, side: number,
) {
  const geometry = host.geometry.clone();
  const verts = geometry.getAttribute("position");
  const nx = normal.x, nz = normal.z;
  const [repeatX, repeatY] = spec.repeatM ?? [0.12, 0.12];
  const uv = new Float32Array(verts.count * 2);
  const vertical = target === "wall" || target === "opening";
  for (let index = 0; index < verts.count; index++) {
    uv[index * 2] = (vertical ? verts.getX(index) * nz - verts.getZ(index) * nx : verts.getX(index)) / repeatX;
    uv[index * 2 + 1] = (vertical ? verts.getY(index) : verts.getZ(index)) / repeatY;
  }
  geometry.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
  const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({
    color: spec.color, roughness: spec.roughness,
    side: vertical ? (side === 1 ? THREE.FrontSide : THREE.BackSide) : host.material instanceof THREE.Material ? host.material.side : THREE.DoubleSide,
    map: spec.pattern === "solid" ? null : makePattern(spec.pattern),
    polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -1,
  }));
  mesh.position.copy(normal).multiplyScalar(0.0008);
  mesh.receiveShadow = true;
  return mesh;
}

// Profile cross sections use fractions of the visible height and projection.
const sections: Record<TrimProfile, [number, number][]> = {
  square: [[1, 1]],
  pencil: [[1, 0.23], [0.97, 0.67], [0.91, 1]],
  bullnose: [[1, 0.05], [0.97, 0.59], [0.89, 0.87], [0.76, 1]],
  splay: [[1, 0.24], [0.72, 1]],
  step: [[1, 0.36], [0.86, 0.36], [0.86, 0.67], [0.71, 0.67], [0.71, 1]],
  ogee: [[1, 0.15], [0.93, 0.19], [0.86, 0.33], [0.78, 0.66], [0.69, 0.89], [0.56, 1]],
  colonial: [[1, 0.12], [0.95, 0.47], [0.83, 0.61], [0.81, 0.37], [0.74, 0.52], [0.65, 0.92], [0.51, 1]],
  lamb: [[1, 0.14], [0.94, 0.24], [0.86, 0.32], [0.77, 0.67], [0.71, 0.91], [0.54, 1]],
};
export function trimRun(
  start: THREE.Vector3, end: THREE.Vector3, across: THREE.Vector3, normal: THREE.Vector3, spec: TrimSpec,
) {
  const run = end.clone().sub(start);
  const length = run.length();
  if (length <= 0.001) return null;
  const outline = new THREE.Shape();
  outline.moveTo(0, 0);
  outline.lineTo(spec.widthM, 0);
  for (const [width, depth] of sections[spec.profile]) outline.lineTo(width * spec.widthM, depth * spec.depthM);
  outline.lineTo(0, spec.depthM);
  outline.closePath();
  const geometry = new THREE.ExtrudeGeometry(outline, { depth: length, bevelEnabled: false });
  geometry.applyMatrix4(new THREE.Matrix4().makeBasis(across, normal, run.normalize()).setPosition(start));
  const mesh = new THREE.Mesh(geometry,
    new THREE.MeshStandardMaterial({ color: spec.color, roughness: 0.56, side: THREE.DoubleSide }));
  mesh.receiveShadow = true;
  return mesh;
}
