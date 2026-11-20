import * as THREE from "three";
import type { RoofComponentVisual } from "./itemCatalogue.ts";
import type { RoofEdge } from "./roofComponents.ts";

export function roofComponentMesh(edge: RoofEdge, spec: RoofComponentVisual) {
  const group = new THREE.Group();
  const from = new THREE.Vector3(...edge.from), to = new THREE.Vector3(...edge.to);
  const run = to.clone().sub(from).normalize();
  const up = new THREE.Vector3(0, 1, 0).addScaledVector(run, -run.y).normalize();
  const across = run.clone().cross(up).normalize();
  group.position.copy(from).lerp(to, 0.5);
  if (new THREE.Vector3(...edge.interior).sub(group.position).dot(across) > 0) {
    across.negate();
    run.negate(); // Keep a right-handed orientation after pointing across away from the roof.
  }
  group.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(run, up, across));
  const length = from.distanceTo(to);
  const material = new THREE.MeshStandardMaterial({ color: spec.color, roughness: 0.55, metalness: 0.24 });
  function strip(height: number, width: number, y: number, z: number, angle = 0) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(length, height, width), material);
    mesh.position.set(0, y, z);
    mesh.rotation.x = angle;
    group.add(mesh);
  }
  if (spec.component === "fascia") {
    strip(0.17, 0.032, -0.083, 0.018);
  } else if (spec.component === "gutter") {
    if (spec.profile === "half-round") {
      const geometry = new THREE.CylinderGeometry(0.071, 0.071, length, 16, 1, true, Math.PI, Math.PI);
      const curve = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({
        color: spec.color, roughness: 0.55, metalness: 0.24, side: THREE.DoubleSide,
      }));
      material.dispose();
      curve.rotation.z = Math.PI / 2;
      curve.position.set(0, -0.049, 0.078);
      group.add(curve);
    } else {
      strip(0.013, 0.131, -0.12, 0.083);
      strip(0.083, 0.012, -0.078, 0.019);
      strip(0.083, 0.012, -0.078, 0.146, spec.profile === "quad" ? 0.26 : 0);
    }
  } else if (spec.profile === "ridge" || spec.profile === "valley") {
    const angle = spec.profile === "ridge" ? 0.22 : -0.12;
    strip(0.011, 0.15, 0.035, -0.071, -angle);
    strip(0.011, 0.15, 0.035, 0.071, angle);
  } else {
    strip(0.012, 0.13, 0.024, -0.059);
    strip(0.085, 0.014, -0.016, 0.009);
  }
  return group;
}
