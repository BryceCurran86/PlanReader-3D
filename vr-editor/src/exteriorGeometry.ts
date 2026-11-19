import * as THREE from "three";
import { makePattern } from "./catalogueGeometry.ts";
import type { EntryVisual, ItemVisual, TimberProfile, TimberVisual } from "./itemCatalogue.ts";

type FaceFinish = Extract<ItemVisual, { kind: "surface" }>;

const profiles: Record<TimberProfile, readonly (readonly [number, number])[]> = {
  square: [[0, 0], [1, 0], [1, 1], [0, 1]],
  eased: [[0.04, 0], [0.96, 0], [1, 0.13], [1, 0.86], [0.96, 1], [0.04, 1], [0, 0.86], [0, 0.13]],
  bullnose: [[0, 0], [1, 0], [1, 0.33], [0.94, 0.75], [0.82, 1], [0, 1]],
  chamfer: [[0, 0], [1, 0], [1, 0.55], [0.87, 1], [0.13, 1], [0, 0.55]],
  rebate: [[0, 0], [1, 0], [1, 0.48], [0.76, 0.48], [0.76, 1], [0, 1]],
  shiplap: [[0, 0], [0.82, 0], [0.82, 0.48], [1, 0.48], [1, 1], [0.18, 1], [0.18, 0.54], [0, 0.54]],
  "v-joint": [[0, 0], [1, 0], [1, 0.5], [0.92, 1], [0.08, 1], [0, 0.5]],
  bevelback: [[0, 0], [1, 0], [1, 1], [0, 0.2]],
  "half-round": Array.from({ length: 13 }, (_, i) => [
    (1 - Math.cos(i * Math.PI / 12)) / 2, Math.sin(i * Math.PI / 12),
  ] as const),
};

function timberMaterial(color: number, grain: number | null, roughness = 0.58) {
  return new THREE.MeshStandardMaterial({ color, roughness,
    map: grain === null ? null : makePattern("grain", grain) });
}

export function createTimberSection(spec: TimberVisual) {
  const { widthM: width, depthM: depth, lengthM: length } = spec;
  const outline = new THREE.Shape(profiles[spec.profile].map(([x, y]) =>
    new THREE.Vector2((x - 0.5) * width, y * depth)));
  const geometry = new THREE.ExtrudeGeometry(outline, { depth: length, bevelEnabled: false });
  geometry.rotateX(-Math.PI / 2);
  if (spec.mount === "face") {
    geometry.rotateY(Math.PI);
    geometry.translate(0, -length / 2, 0);
  } else {
    geometry.translate(0, 0, depth / 2);
  }
  const positions = geometry.getAttribute("position");
  const uv = new Float32Array(positions.count * 2);
  for (let i = 0; i < positions.count; i++) {
    uv[i * 2] = (positions.getX(i) + positions.getZ(i) * 0.6) / Math.max(width, 0.08);
    uv[i * 2 + 1] = positions.getY(i) / 1.3;
  }
  geometry.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
  const mesh = new THREE.Mesh(geometry, timberMaterial(spec.color, spec.grain));
  mesh.receiveShadow = true;
  return mesh;
}

type Pane = { x: number; y: number; width: number; height: number; arched?: boolean };
function rectangle(x: number, y: number, width: number, height: number) {
  return new THREE.Shape([new THREE.Vector2(x, y), new THREE.Vector2(x + width, y),
    new THREE.Vector2(x + width, y + height), new THREE.Vector2(x, y + height)]);
}
function paneShape(pane: Pane) {
  const { x, y, width, height } = pane;
  if (!pane.arched) return rectangle(x, y, width, height);
  const rise = Math.min(height / 3, width / 2);
  const spring = y + height - rise;
  const path = new THREE.Shape();
  path.moveTo(x, y);
  path.lineTo(x + width, y);
  path.lineTo(x + width, spring);
  path.absellipse(x + width / 2, spring, width / 2, rise, 0, Math.PI, false, 0);
  path.lineTo(x, y);
  return path;
}

export function createEntryAssembly(
  spec: EntryVisual, width: number, height: number, frontFinish?: FaceFinish, backFinish?: FaceFinish,
) {
  const group = new THREE.Group();
  const timber = timberMaterial(spec.color, spec.grain);
  const hardware = new THREE.MeshStandardMaterial({ color: 0x424649, roughness: 0.39, metalness: 0.58 });
  const glass = new THREE.MeshStandardMaterial({ color: 0x82acb2, roughness: 0.22, transparent: true,
    opacity: 0.42, depthWrite: false, side: THREE.DoubleSide });
  const appliedFinish = (finish?: FaceFinish) => finish ?
    timberMaterial(finish.color, finish.pattern === "grain" ? 1 : null, finish.roughness) : timber;
  const front = appliedFinish(frontFinish), back = appliedFinish(backFinish);
  const edge = Math.min(0.044, width / 19), gap = 0.005;
  const thickness = spec.style === "pivot" ? 0.058 : 0.043;

  function box(w: number, h: number, d: number, x: number, y: number, z: number,
    material: THREE.MeshStandardMaterial) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material);
    mesh.position.set(x, y, z);
    group.add(mesh);
  }
  box(edge, height, 0.09, -width / 2 + edge / 2, height / 2, 0, timber);
  box(edge, height, 0.09, width / 2 - edge / 2, height / 2, 0, timber);
  box(width - 2 * edge, edge, 0.09, 0, height - edge / 2, 0, timber);
  box(width - 2 * edge, 0.014, 0.07, 0, 0.007, 0, hardware);

  const bottom = 0.015, leafHeight = height - edge - gap - bottom;
  function leaf(left: number, span: number, style: EntryVisual["style"], pulls: "left" | "right" | "none") {
    const outer = rectangle(left, bottom, span, leafHeight);
    const pane = (x: number, y: number, w: number, h: number, arched = false): Pane => ({
      x: left + x * span, y: bottom + y * leafHeight, width: w * span, height: h * leafHeight, arched,
    });
    let glazing: Pane[] = [];
    if (style === "craftsman") glazing = [0.13, 0.385, 0.64].map(x => pane(x, 0.69, 0.23, 0.22));
    if (style === "vertical-lite") glazing = [pane(0.18, 0.15, 0.25, 0.71)];
    if (style === "strip-lite") glazing = [0.29, 0.49, 0.69].map(y => pane(0.14, y, 0.72, 0.12));
    if (style === "full-lite") glazing = [pane(0.13, 0.12, 0.74, 0.8)];
    if (style === "arched-lite") glazing = [pane(0.16, 0.36, 0.68, 0.55, true)];
    if (pulls === "none") glazing = [pane(0.16, 0.11, 0.68, 0.80)];
    for (const cutout of glazing) {
      const opening = paneShape(cutout);
      outer.holes.push(opening);
      const pane = new THREE.Mesh(new THREE.ShapeGeometry(opening), glass);
      pane.name = "Door glazing";
      group.add(pane);
    }

    const geometry = new THREE.ExtrudeGeometry(outer, { depth: thickness, bevelEnabled: false });
    geometry.translate(0, 0, -thickness / 2);
    geometry.clearGroups();
    const normals = geometry.getAttribute("normal");
    const position = geometry.getAttribute("position");
    const uv = new Float32Array(position.count * 2);
    let materialIndex = -1, start = 0;
    for (let index = 0; index < normals.count; index += 3) {
      const nz = normals.getZ(index);
      const next = nz > 0.9 ? 1 : nz < -0.9 ? 2 : 0;
      if (next !== materialIndex) {
        if (materialIndex >= 0) geometry.addGroup(start, index - start, materialIndex);
        start = index;
        materialIndex = next;
      }
    }
    geometry.addGroup(start, normals.count - start, materialIndex);
    for (let index = 0; index < position.count; index++) {
      uv[index * 2] = position.getX(index) / 0.32;
      uv[index * 2 + 1] = position.getY(index) / 1.4;
    }
    geometry.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
    const slab = new THREE.Mesh(geometry, [timber, front, back]);
    slab.name = "Entry door leaf";
    group.add(slab);
    const face = thickness / 2;
    const centre = left + span / 2;
    if (style === "shaker" || style === "double") {
      for (const [fraction, panelHeight] of [[0.31, 0.31], [0.72, 0.36]]) {
        box(span * 0.67, leafHeight * panelHeight, 0.014, centre, bottom + leafHeight * fraction, face, front);
      }
    }
    if (style === "batten" || style === "pivot") for (let index = 0; index < 7; index++) {
      const x = left + span * (0.12 + index * 0.116);
      box(span * 0.042, leafHeight * 0.92, 0.012, x, bottom + leafHeight * 0.5, face, front);
    }
    if (pulls === "none") return;
    const x = left + span * (pulls === "right" ? 0.88 : 0.12);
    const y = bottom + leafHeight * 0.48;
    const pullHeight = style === "pivot" ? 0.58 : style === "flush" || style === "batten" ? 0.31 : 0.075;
    const pullWidth = pullHeight > 0.1 ? 0.024 : 0.072;
    for (const sign of [-1, 1]) {
      box(0.048, Math.max(0.074, pullHeight * 0.85), 0.022, x, y, sign * (face + 0.01), hardware);
      box(pullWidth, pullHeight, 0.032, x, y, sign * (face + 0.03), hardware);
    }
  }

  const inside = width - 2 * edge - 2 * gap;
  const left = -width / 2 + edge + gap;
  if (spec.style === "double") {
    const half = (inside - gap) / 2;
    leaf(left, half, "double", "right");
    leaf(left + half + gap, half, "double", "left");
  } else if (spec.style === "sidelight") {
    const light = Math.min(0.38, inside * 0.26);
    const panel = inside - light - edge;
    leaf(left, panel, "craftsman", "right");
    box(edge, leafHeight, 0.075, left + panel + edge / 2, bottom + leafHeight / 2, 0, timber);
    leaf(left + panel + edge, light, "full-lite", "none");
  } else {
    leaf(left, inside, spec.style, "right");
  }
  if (!group.children.some(child => child instanceof THREE.Mesh && child.material === glass)) glass.dispose();
  return group;
}
