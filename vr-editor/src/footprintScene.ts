import * as THREE from "three";
import { FOOTPRINT_CORNERS, footprintCorner, footprintDepth, footprintWidth, projectVertex, sameFootprint } from "./footprintResize.ts";
import type { FootprintBounds, FootprintCorner, FootprintProjection } from "./footprintResize.ts";
import type { CatalogueHost } from "./catalogueScene.ts";

type SourceMesh = THREE.Mesh | THREE.Line;

export function footprintGeometry(objects: readonly THREE.Object3D[]) {
  return objects.flatMap(object => {
    if (!(object instanceof THREE.Mesh || object instanceof THREE.Line)) return [];
    const positions = object.geometry.getAttribute("position");
    if (!positions) return [];
    const original = new Float64Array(positions.count * 2);
    for (let i = 0; i < positions.count; i++) {
      original[i * 2] = positions.getX(i);
      original[i * 2 + 1] = positions.getZ(i);
    }
    return [{ object: object as SourceMesh, original }];
  });
}

export function renderFootprintGeometry(source: ReturnType<typeof footprintGeometry>, projection: FootprintProjection | null) {
  for (const { object, original } of source) {
    const position = object.geometry.getAttribute("position");
    for (let i = 0; i < position.count; i++) {
      const x = original[i * 2], z = original[i * 2 + 1];
      position.setX(i, projection ? projection.draft.minX + (x - projection.original.minX) * projection.scaleX : x);
      position.setZ(i, projection ? projection.draft.minZ + (z - projection.original.minZ) * projection.scaleZ : z);
    }
    position.needsUpdate = true;
    if (object instanceof THREE.Mesh) object.geometry.computeVertexNormals();
    object.geometry.computeBoundingBox();
    object.geometry.computeBoundingSphere();
  }
}

export function projectSourceHost(host: CatalogueHost, projection: FootprintProjection): CatalogueHost {
  const run = host.run && { ...host.run,
    start: plan(host.run.start), end: plan(host.run.end) };
  const roofEdges = host.roofEdges?.map(edge => ({
    ...edge, from: projectVertex(edge.from, projection), to: projectVertex(edge.to, projection),
    interior: projectVertex(edge.interior, projection),
  }));
  function plan([x, z]: [number, number]): [number, number] {
    const point = projectVertex([x, 0, z], projection);
    return [point[0], point[2]];
  }
  return { ...host, run, roofEdges };
}

export function createFootprintGizmo(scene: THREE.Scene) {
  const root = new THREE.Group();
  root.name = "Draft footprint handles";
  root.visible = false;
  scene.add(root);
  const positions = new THREE.Float32BufferAttribute(new Float32Array(15), 3);
  const geometry = new THREE.BufferGeometry().setAttribute("position", positions);
  const outline = new THREE.Line(geometry, new THREE.LineBasicMaterial({color: 0x77efca, depthTest: false}));
  outline.frustumCulled = false;
  outline.renderOrder = 16;
  root.add(outline);
  const handles = FOOTPRINT_CORNERS.map(corner => {
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(1, 16, 10),
      new THREE.MeshBasicMaterial({ color: 0x77efca, depthTest: false }));
    mesh.renderOrder = 17;
    root.add(mesh);
    return { corner, mesh };
  });
  let last: FootprintBounds | null = null;
  function show(bounds: FootprintBounds | null) {
    root.visible = !!bounds;
    if (!bounds || (last && sameFootprint(bounds, last))) return;
    last = bounds;
    const size = Math.max(0.12, Math.min(0.42, Math.min(footprintWidth(bounds), footprintDepth(bounds)) * 0.045));
    for (const row of handles) {
      const [x, z] = footprintCorner(bounds, row.corner);
      row.mesh.position.set(x, 0.06, z);
      row.mesh.scale.setScalar(size);
    }
    for (const [index, handle] of [0, 1, 3, 2, 0].entries()) {
      const { x, y, z } = handles[handle].mesh.position;
      positions.setXYZ(index, x, y, z);
    }
    positions.needsUpdate = true;
    root.updateWorldMatrix(true, true);
  }
  function pick(ray: THREE.Raycaster): FootprintCorner | null {
    if (!root.visible) return null;
    const hit = ray.intersectObjects(handles.map(row => row.mesh), false)[0];
    return handles.find(row => row.mesh === hit?.object)?.corner ?? null;
  }
  return { show, pick };
}
