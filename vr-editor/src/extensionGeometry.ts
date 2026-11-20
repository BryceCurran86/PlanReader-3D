import * as THREE from "three";
import type { DesignAssembly, OpeningStyle } from "./itemCatalogue.ts";

export function createOpeningStyle(spec: OpeningStyle, width: number, height: number, finishColor?: number) {
  const group = new THREE.Group();
  const material = new THREE.MeshStandardMaterial({ color: finishColor ?? spec.color, roughness: 0.62 });
  const glass = new THREE.MeshStandardMaterial({ color: 0xaecddc, metalness: 0.14, roughness: 0.24,
    transparent: true, opacity: 0.34, depthWrite: false, side: THREE.DoubleSide });
  const bar = Math.min(0.044, width * 0.075, height * 0.075);
  function box(w: number, h: number, d: number, x: number, y: number, z: number, surface = material) {
    const part = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), surface);
    part.position.set(x, y, z);
    group.add(part);
    return part;
  }
  if (spec.type === "covering") {
    glass.dispose();
    const depth = 0.10;
    const w = width + 0.14, h = height + 0.12;
    box(w + 0.05, 0.025, 0.035, 0, h + 0.01, depth);
    if (spec.style === "curtain" || spec.style === "sheer") {
      material.transparent = spec.style === "sheer";
      material.opacity = spec.style === "sheer" ? 0.49 : 1;
      material.depthWrite = !material.transparent;
      for (let index = 0; index < 22; index++) {
        const mesh = box(w / 22 * 1.22, h, 0.022, -w / 2 + (index + 0.5) * w / 22,
          h / 2, depth + 0.02 * Math.cos(index * Math.PI / 2));
        mesh.rotation.y = 0.24 * Math.sin(index * Math.PI / 2);
      }
    } else if (spec.style === "vertical") {
      for (let index = 0; index < 14; index++)
        box(w / 14 * 0.8, h, 0.01, -w / 2 + (index + 0.5) * w / 14, h / 2, depth);
    } else if (spec.style === "roller") {
      box(w, h * 0.84, 0.014, 0, h * 0.58, depth);
    } else {
      const slats = spec.style === "roman" ? 6 : spec.style === "shutter" ? 10 : 18;
      for (let index = 0; index < slats; index++) {
        const mesh = box(w, (h / slats) * 0.83, 0.018, 0, (index + 0.5) * h / slats, depth);
        mesh.rotation.x = spec.style === "venetian" ? -0.42 : 0;
      }
    }
    return group;
  }
  box(width, bar, 0.062, 0, bar / 2, 0);
  box(width, bar, 0.062, 0, height - bar / 2, 0);
  box(bar, height, 0.062, -(width - bar) / 2, height / 2, 0);
  box(bar, height, 0.062, (width - bar) / 2, height / 2, 0);
  const panels = spec.style === "wide-stacker" || spec.style === "bifold" ? 4 :
    spec.style === "stacker" ? 3 :
    ["slider", "lift-slide", "casement", "bypass"].includes(spec.style) ? 2 : 1;
  const inner = width - bar * 2;
  const panelWidth = inner / panels;
  const opaque = ["cavity", "barn", "bypass"].includes(spec.style);
  if (opaque) glass.dispose();
  for (let index = 0; index < panels; index++) {
    const x = -inner / 2 + (index + 0.5) * panelWidth;
    const track = spec.type === "door" && index % 2 ? 0.023 : 0;
    box(panelWidth, height - bar * 2, opaque ? 0.044 : 0.012, x, height / 2, track, opaque ? material : glass);
    if (index) box(bar, height - bar * 2, 0.046, x - panelWidth / 2, height / 2, track);
    if (spec.type === "door") box(bar * 0.38, height * 0.11, 0.046, x + panelWidth * 0.35, height * 0.45, track + 0.03);
  }
  if (spec.style === "double-hung" || spec.style === "awning")
    box(inner, bar, 0.052, 0, height * (spec.style === "awning" ? 0.66 : 0.50), 0.015);
  if (spec.style === "louvre") for (let i = 1; i < 8; i++)
    box(inner, bar / 4, 0.075, 0, height * i / 8, 0.02).rotation.x = -0.24;
  if (spec.style === "barn") box(width, bar / 2, 0.06, 0, height + 0.05, 0.045);
  return group;
}

export function createDesignAssembly(spec: DesignAssembly) {
  const group = new THREE.Group();
  const { widthM: w, heightM: h, depthM: d, shape } = spec;
  const primary = new THREE.MeshStandardMaterial({ color: spec.color, roughness: 0.72 });
  function coloured(color: number, opacity = 1) {
    return new THREE.MeshStandardMaterial({ color, roughness: 0.69, transparent: opacity < 1,
      opacity, depthWrite: opacity === 1, side: THREE.DoubleSide });
  }
  function mount(geometry: THREE.BufferGeometry, x: number, y: number, z: number, material = primary) {
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(x, y, z);
    mesh.receiveShadow = true;
    group.add(mesh);
    return mesh;
  }
  function box(width: number, height: number, depth: number, x: number, y: number, z: number, material = primary) {
    return mount(new THREE.BoxGeometry(width, height, depth), x, y, z, material);
  }
  const steps = Math.max(3, Math.round(h / 0.19));
  if (shape === "spiral-stair") {
    mount(new THREE.CylinderGeometry(0.058, 0.058, h, 12), 0, h / 2, 0);
    for (let index = 0; index < steps; index++) {
      const angle = index / steps * Math.PI * 2 * 0.86;
      box(w * 0.46, 0.045, w * 0.22, Math.cos(angle) * w * 0.25,
        (index + 1) * h / steps, Math.sin(angle) * w * 0.25).rotation.y = -angle;
    }
  } else if (shape.endsWith("-stair")) {
    const half = Math.ceil(steps / 2);
    for (let index = 0; index < steps; index++) {
      const y = (index + 1) * h / steps;
      if (shape === "straight-stair") {
        box(w, 0.055, d / steps * 1.03, 0, y, -d / 2 + (index + 0.5) * d / steps);
      } else if (index < half) {
        box(w, 0.055, d / half * 1.03, -w / 2, y, -d / 2 + (index + 0.5) * d / half);
      } else if (shape === "u-stair") {
        box(w, 0.055, d / (steps - half) * 1.03, w / 2 + 0.04, y,
          d / 2 - (index - half + 0.5) * d / (steps - half));
      } else {
        box(d / (steps - half), 0.055, w, (index - half + 0.5) * d / (steps - half), y, d / 2 + w / 2);
      }
    }
    if (shape !== "straight-stair") box(w * (shape === "u-stair" ? 2.04 : 1), 0.055, w,
      shape === "u-stair" ? 0 : -w / 2, half * h / steps, d / 2 + w / 2);
  } else if (shape.endsWith("-rail")) {
    for (const x of [-w / 2, 0, w / 2]) box(0.046, h, d, x, h / 2, 0);
    if (shape === "glass-rail") box(w, h * 0.83, 0.014, 0, h * 0.50, 0, coloured(0xa6cad4, 0.38));
    else {
      box(w, 0.046, d * 0.75, 0, h - 0.02, 0);
      if (shape === "wire-rail") for (let i = 1; i < 8; i++) box(w, 0.009, 0.009, 0, i * h / 8, 0);
      if (shape === "picket-rail") {
        const count = Math.ceil(w / 0.12);
        for (let i = 1; i < count; i++) box(0.022, h * 0.90, d * 0.32, -w / 2 + i * w / count, h / 2, 0);
      }
    }
  } else if (shape === "skillion" || shape === "gable" || shape === "insulated") {
    for (const x of [-w * 0.45, w * 0.45]) for (const z of [-d * 0.44, d * 0.44]) {
      const postHeight = shape === "gable" ? h - 0.23 : h - z * 0.11;
      box(0.095, postHeight, 0.095, x, postHeight / 2, z);
    }
    if (shape === "gable") {
      box(w * 0.52, 0.075, d, -w * 0.25, h, 0).rotation.z = 0.18;
      box(w * 0.52, 0.075, d, w * 0.25, h, 0).rotation.z = -0.18;
    } else box(w, shape === "insulated" ? 0.13 : 0.052, d, 0, h, 0).rotation.x = 0.11;
  } else if (shape.endsWith("-pool")) {
    const trim = coloured(0xd8d5c8);
    if (shape === "rounded-pool") {
      mount(new THREE.CylinderGeometry(1, 1, h, 36), 0, h / 2, 0, trim).scale.set(w / 2, 1, d / 2);
      mount(new THREE.CircleGeometry(1, 36).rotateX(-Math.PI / 2), 0, h + 0.002, 0).scale.set(w * 0.46, 1, d * 0.46);
    } else {
      box(w, h, d, 0, h / 2, 0, trim);
      box(w - 0.24, 0.016, d - 0.24, 0, h + 0.01, 0);
    }
  } else if (shape === "garden") {
    box(w, h, d, 0, h / 2, 0);
    box(w - 0.14, 0.025, d - 0.14, 0, h + 0.002, 0, coloured(0x6f6046));
  } else if (shape === "tree" || shape === "hedge") {
    if (shape === "tree") {
      mount(new THREE.CylinderGeometry(0.08, 0.12, h * 0.73, 12), 0, h * 0.365, 0, coloured(0x7e644c));
      mount(new THREE.IcosahedronGeometry(1, 2), 0, h * 0.73, 0).scale.set(w / 2, h * 0.34, d / 2);
    } else for (let index = 0; index < 6; index++)
      mount(new THREE.IcosahedronGeometry(1, 1), -w / 2 + (index + 0.5) * w / 6, h * 0.46, 0)
        .scale.set(w * 0.12, h * 0.54, d / 2);
  } else if (shape === "stepping") {
    for (let index = 0; index < 6; index++) box(w, h, d / 8, (index % 2 ? -1 : 1) * w * 0.07,
      h / 2, -d / 2 + (index + 0.5) * d / 6).rotation.y = (index % 2 ? 1 : -1) * 0.05;
  } else box(w, h, d, 0, h / 2, 0);
  return group;
}
