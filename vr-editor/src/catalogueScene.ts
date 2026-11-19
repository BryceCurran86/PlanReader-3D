import * as THREE from "three";
import { openingFits, planLength } from "./buildPlacement.ts";
import type { PlanPoint, WallVisual } from "./buildPlacement.ts";
import { getCatalogueItem } from "./itemCatalogue.ts";
import type { CatalogueItem, ItemTarget } from "./itemCatalogue.ts";
import { makeItemHostId, openingHostId, worktopId } from "./itemPlacement.ts";
import type { ItemHit, PlacedItem, Vector } from "./itemPlacement.ts";
import { createCatalogueFixture } from "./catalogueFixtures.ts";
import { finishMesh, trimRun } from "./catalogueGeometry.ts";

type WallRun = { start: PlanPoint; end: PlanPoint; gaps: [number, number][] };
type Opening = { start: PlanPoint; end: PlanPoint; bottom: number; top: number; leaf: boolean };
export type CatalogueHost = {
  id: string;
  target: ItemTarget;
  mesh: THREE.Mesh;
  run?: WallRun;
  opening?: Opening;
};

export function catalogueWallHost(id: string, mesh: THREE.Mesh, start: PlanPoint, end: PlanPoint): CatalogueHost {
  return { id: makeItemHostId("wall", id), target: "wall", mesh, run: { start, end, gaps: [] } };
}

function xy(point: PlanPoint, y = 0) {
  return new THREE.Vector3(point[0], y, point[1]);
}

export function draftCatalogueHosts(wall: WallVisual, group: THREE.Group): CatalogueHost[] {
  const hosts: CatalogueHost[] = [];
  const face = group.children.find(child => child.userData.catalogueWallFace);
  const floorGaps: [number, number][] = [];
  const start = xy(wall.start), end = xy(wall.end);
  const tangent = end.clone().sub(start).normalize();
  const openings = (wall.openings ?? []).filter(opening => openingFits(wall, opening))
    .sort((a, b) => a.offsetM - b.offsetM);
  let lastEnd = 0;
  for (const opening of openings) {
    if (opening.offsetM < lastEnd - 0.000001) continue;
    lastEnd = opening.offsetM + opening.widthM;
    if (opening.sillHeightM < 0.001) floorGaps.push([opening.offsetM, lastEnd]);
    if (opening.openingKind === "window") continue;
    const a = start.clone().addScaledVector(tangent, opening.offsetM);
    const b = start.clone().addScaledVector(tangent, lastEnd);
    const floor = opening.sillHeightM, top = floor + opening.heightM;
    const outline: Opening = { start: [a.x, a.z], end: [b.x, b.z], bottom: floor,
      top, leaf: opening.openingKind === "door" };
    const points = [xy(outline.start, floor), xy(outline.end, floor), xy(outline.end, top),
      xy(outline.start, floor), xy(outline.end, top), xy(outline.start, top)];
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    geometry.computeVertexNormals();
    const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ side: THREE.DoubleSide, visible: false }));
    group.add(mesh);
    hosts.push({ id: openingHostId(wall.proposalId, opening.openingId), target: "opening", mesh, opening: outline });
  }
  if (face instanceof THREE.Mesh) {
    hosts.push({ id: makeItemHostId("draft-wall", wall.proposalId), target: "wall", mesh: face,
      run: { start: wall.start, end: wall.end, gaps: floorGaps } });
  }
  return hosts;
}

/** Only the built-in demo asks for these planes. They cannot become evidence or teleport targets. */
export function demoCatalogueHosts(scene: THREE.Scene): CatalogueHost[] {
  const hosts: CatalogueHost[] = [];
  for (const [room, from, to] of [["west", 0, 4], ["east", 4, 9]] as const) {
    for (const target of ["floor", "ceiling"] as const) {
      const floor = target === "floor";
      const plane = new THREE.PlaneGeometry(to - from, 7)
        .rotateX(floor ? -Math.PI / 2 : Math.PI / 2)
        .translate((to + from) * 0.5, floor ? 0 : 2.4, 3.5);
      const mesh = new THREE.Mesh(plane, new THREE.MeshStandardMaterial({
        color: floor ? 0xb9a78d : 0xd7d3c7, roughness: 0.89,
      }));
      mesh.receiveShadow = true;
      scene.add(mesh);
      hosts.push({ id: makeItemHostId(target, "demo-" + room), target, mesh });
    }
  }
  return hosts;
}

function trimMount(host: CatalogueHost, item: CatalogueItem, normal: THREE.Vector3) {
  const group = new THREE.Group();
  const spec = item.visual;
  if (spec.kind !== "trim") return group;
  const vertical = new THREE.Vector3(0, 1, 0);
  const add = (a: THREE.Vector3, b: THREE.Vector3, across: THREE.Vector3) => {
    const mesh = trimRun(a, b, across, normal, spec);
    if (mesh) group.add(mesh);
  };
  if (host.run) {
    const { start, end, gaps } = host.run;
    const length = planLength(start, end);
    const origin = xy(start);
    const along = xy(end).sub(origin).normalize();
    const at = (distance: number) => origin.clone().addScaledVector(along, distance);
    let left = 0;
    for (const [from, until] of gaps) {
      add(at(left), at(from), vertical);
      left = until;
    }
    add(at(left), at(length), vertical);
  }
  if (host.opening) {
    const { start, end, bottom, top } = host.opening;
    const left = xy(start, top), right = xy(end, top);
    const across = right.clone().sub(left).normalize();
    add(xy(start, bottom), left, across.clone().negate());
    add(xy(end, bottom), right, across);
    add(left.addScaledVector(across, -spec.widthM), right.addScaledVector(across, spec.widthM), vertical);
  }
  return group;
}

function dispose(root: THREE.Object3D) {
  const materials = new Set<THREE.Material>();
  root.traverse(object => {
    if (!(object instanceof THREE.Mesh)) return;
    object.geometry.dispose();
    const faces = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of faces) materials.add(material);
  });
  for (const material of materials) {
    if (material instanceof THREE.MeshStandardMaterial) material.map?.dispose();
    material.dispose();
  }
}

function surfaceKey(entry: PlacedItem) {
  return JSON.stringify([entry.hostId, entry.target === "wall" || entry.target === "opening" ? entry.side : 1]);
}

export function createCatalogueScene(scene: THREE.Scene) {
  const mounts: THREE.Object3D[] = [];
  const hosts = new Map<THREE.Object3D, CatalogueHost>();
  let meshes: THREE.Object3D[] = [];
  let sourceKey: readonly CatalogueHost[] | null = null;
  let draftKey: readonly CatalogueHost[] | null = null;
  let itemKey: readonly PlacedItem[] | null = null;
  const marker = new THREE.Mesh(new THREE.RingGeometry(0.036, 0.047, 22),
    new THREE.MeshBasicMaterial({ color: 0x78ffe1, side: THREE.DoubleSide, depthWrite: false }));
  marker.visible = false;
  scene.add(marker);
  const up = new THREE.Vector3(0, 1, 0);
  const front = new THREE.Vector3(0, 0, 1);

  function clear() {
    for (const root of mounts) root.removeFromParent();
    for (const root of mounts) dispose(root);
    mounts.length = 0;
    hosts.clear();
    meshes = [];
    sourceKey = draftKey = itemKey = null;
  }

  function sync(source: readonly CatalogueHost[], drafts: readonly CatalogueHost[], items: readonly PlacedItem[]) {
    if (sourceKey === source && draftKey === drafts && itemKey === items) return;
    clear();
    sourceKey = source;
    draftKey = drafts;
    itemKey = items;
    const byId = new Map<string, CatalogueHost>();
    function addHost(host: CatalogueHost) {
      hosts.set(host.mesh, host);
      byId.set(host.id, host);
    }
    for (const host of [...source, ...drafts]) addHost(host);
    const visibleFinishes = new Set(items.filter(placement => {
      const visual = getCatalogueItem(placement.itemId)?.visual;
      return visual?.kind === "surface" && visual.slot === "finish";
    }).map(surfaceKey));
    for (const placement of items) {
      const item = getCatalogueItem(placement.itemId);
      const host = byId.get(placement.hostId);
      if (!item || !host || host.target !== placement.target) continue;
      const normal = new THREE.Vector3(...placement.normal);
      const { visual } = item;
      let node: THREE.Object3D;
      if (visual.kind === "surface") {
        if (item.group === "doors" && !host.opening?.leaf) continue;
        if (visual.slot === "lining" && visibleFinishes.has(surfaceKey(placement))) continue;
        node = finishMesh(host.mesh, visual, host.target, normal, placement.side);
      } else if (visual.kind === "trim") {
        node = trimMount(host, item, normal);
      } else {
        const { group, worktop } = createCatalogueFixture(visual, host.target);
        group.position.set(...placement.point).addScaledVector(normal, 0.001);
        const useUp = host.target === "floor" || host.target === "worktop";
        group.quaternion.setFromUnitVectors(useUp ? up : front, normal);
        group.quaternion.multiply(new THREE.Quaternion().setFromAxisAngle(useUp ? up : front, placement.turn * Math.PI / 2));
        if (worktop) addHost({ id: worktopId(placement.id), target: "worktop", mesh: worktop });
        node = group;
      }
      host.mesh.add(node);
      node.updateWorldMatrix(true, true);
      mounts.push(node);
    }
    meshes = [...hosts.keys()];
  }

  function target(raycaster: THREE.Raycaster, item: CatalogueItem): ItemHit | null {
    for (const hit of raycaster.intersectObjects(meshes, false)) {
      const host = hosts.get(hit.object);
      if (!host || !hit.face) continue;
      // The hidden target inside a rough opening does not intercept ordinary finishes or fixtures.
      if (host.target === "opening" && !item.targets.includes("opening")) continue;
      if (!item.targets.includes(host.target) || (item.group === "doors" && !host.opening?.leaf)) return null;
      const local = host.mesh.worldToLocal(hit.point.clone());
      const normal = hit.face.normal.clone().normalize();
      const worldNormal = normal.clone().applyNormalMatrix(new THREE.Matrix3().getNormalMatrix(host.mesh.matrixWorld));
      const side = worldNormal.dot(raycaster.ray.direction) > 0 ? -1 : 1;
      if (host.target === "worktop" && (normal.y < 0.9 || side < 0)) return null;
      return { hostId: host.id, target: host.target, point: local.toArray() as Vector,
        normal: normal.multiplyScalar(side).toArray() as Vector, side };
    }
    return null;
  }

  function aim(hit: ItemHit | null) {
    marker.visible = false;
    if (!hit) return;
    const host = [...hosts.values()].find(entry => entry.id === hit.hostId);
    if (!host) return;
    const normal = new THREE.Vector3(...hit.normal).applyNormalMatrix(new THREE.Matrix3().getNormalMatrix(host.mesh.matrixWorld));
    marker.position.copy(host.mesh.localToWorld(new THREE.Vector3(...hit.point))).addScaledVector(normal, 0.015);
    marker.quaternion.setFromUnitVectors(front, normal);
    marker.visible = true;
  }

  return { sync, clear, target, aim };
}
