import * as THREE from "three";
import { nearestRoofEdge } from "./roofComponents.ts";
import type { RoofEdge } from "./roofComponents.ts";
import { roofComponentMesh } from "./roofComponentGeometry.ts";
import { showConstructionSurface } from "./constructionStages.ts";
import type { ConstructionStage } from "./constructionStages.ts";
import {itemLayerVisible,EMPTY_LAYERS} from "./constructionLayers.ts";
import type {LayerOverrides} from "./constructionLayers.ts";
import type { CeilingDraft } from "./buildPlacement.ts";
import { openingFits, planLength } from "./buildPlacement.ts";
import type { PlanPoint, WallVisual } from "./buildPlacement.ts";
import { getCatalogueItem,ITEM_CATALOGUE } from "./itemCatalogue.ts";
import type {FinishContext} from "./contextFinishes.ts";
import type { CatalogueItem, ItemTarget, ItemVisual } from "./itemCatalogue.ts";
import { makeItemHostId, openingFitMessage, openingHostId, timberFitsWall, worktopId } from "./itemPlacement.ts";
import type { ItemHit, OpeningSize, PlacedItem, Vector, WallSection } from "./itemPlacement.ts";
import { createCatalogueFixture } from "./catalogueFixtures.ts";
import { finishMesh, trimRun } from "./catalogueGeometry.ts";
import {architraveMitres} from "./architraveMitres.ts";
import {skirtingEndCuts,applySkirtingCuts} from "./skirtingMitres.ts";
import type {WallCornerJoins} from "./wallCornerJoin.ts";
import { createEntryAssembly, createTimberSection } from "./exteriorGeometry.ts";
import { createDesignAssembly, createOpeningStyle } from "./extensionGeometry.ts";
import { SITE_HOST_ID } from "./itemPlacement.ts";
import {wallAssembly} from "./wallProfiles.ts";

type WallRun = WallSection & { gaps: [number, number][] };
type Opening = { start: PlanPoint; end: PlanPoint; bottom: number; top: number; size: OpeningSize;
  reviewLeaf?: THREE.Mesh };
type OpeningFinish = Extract<ItemVisual, { kind: "surface" }>;
export type CatalogueHost = {
  id: string;
  target: ItemTarget;
  mesh: THREE.Mesh;
  run?: WallRun;
  opening?: Opening;
  roofEdges?: RoofEdge[];
  ceilingDraft?: CeilingDraft;
  halfThickness?:number;
  cornerJoins?:WallCornerJoins;
  finishFaces?:{left:THREE.Mesh;right:THREE.Mesh};
};

export function catalogueWallHost(id: string, mesh: THREE.Mesh, start: PlanPoint, end: PlanPoint, heightM: number): CatalogueHost {
  return { id: makeItemHostId("wall", id), target: "wall", mesh, run: { start, end, heightM, gaps: [], apertures: [] } };
}

function xy(point: PlanPoint, y = 0) {
  return new THREE.Vector3(point[0], y, point[1]);
}

export function draftCatalogueHosts(wall: WallVisual, group: THREE.Group,cornerJoins?:WallCornerJoins): CatalogueHost[] {
  const hosts: CatalogueHost[] = [];
  const face = group.children.find(child=>child.userData.catalogueMountFace) ?? group.children.find(child => child.userData.catalogueWallFace);
  const floorGaps: [number, number][] = [];
  const apertures: WallSection["apertures"] = [];
  const leaves = new Map(group.children.flatMap(child => child instanceof THREE.Mesh &&
    typeof child.userData.catalogueDoorLeaf === "string"
    ? [[child.userData.catalogueDoorLeaf as string, child] as const] : []));
  const start = xy(wall.start), end = xy(wall.end);
  const tangent = end.clone().sub(start).normalize();
  const openings = (wall.openings ?? []).filter(opening => openingFits(wall, opening))
    .sort((a, b) => a.offsetM - b.offsetM);
  let lastEnd = 0;
  for (const opening of openings) {
    if (opening.offsetM < lastEnd - 0.000001) continue;
    lastEnd = opening.offsetM + opening.widthM;
    const bottom = opening.sillHeightM, top = bottom + opening.heightM;
    apertures.push({ from: opening.offsetM, to: lastEnd, bottom, top });
    if (bottom < 0.001) floorGaps.push([opening.offsetM, lastEnd]);
    const a = start.clone().addScaledVector(tangent, opening.offsetM);
    const b = start.clone().addScaledVector(tangent, lastEnd);
    const outline: Opening = { start: [a.x, a.z], end: [b.x, b.z], bottom, top,
      size: { widthM: opening.widthM, heightM: opening.heightM, door: opening.openingKind === "door",
         window: opening.openingKind === "window" },
      reviewLeaf: leaves.get(opening.openingId) };
    const points = [xy(outline.start, bottom), xy(outline.end, bottom), xy(outline.end, top),
      xy(outline.start, bottom), xy(outline.end, top), xy(outline.start, top)];
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    geometry.computeVertexNormals();
    const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ side: THREE.DoubleSide, visible: false }));
    group.add(mesh);
    hosts.push({ id: openingHostId(wall.proposalId, opening.openingId), target: "opening", mesh, opening: outline });
  }
  if (face instanceof THREE.Mesh) {
    const left=group.children.find(c=>c.userData.draftFinishFace==="left"),right=group.children.find(c=>c.userData.draftFinishFace==="right");
    const finishFaces=left instanceof THREE.Mesh&&right instanceof THREE.Mesh?{left,right}:undefined;
    hosts.push({ id: makeItemHostId("draft-wall", wall.proposalId), target: "wall", mesh: face, finishFaces,cornerJoins,halfThickness:wallAssembly(wall.assembly).thicknessMm/2000,
      run: { start: wall.start, end: wall.end, heightM: wall.heightM, gaps: floorGaps, apertures } });
  }
  return hosts;
}

export function draftSiteHost(scene: THREE.Scene): CatalogueHost {
  const geometry = new THREE.PlaneGeometry(20000, 20000).rotateX(-Math.PI / 2).translate(0, -0.025, 0);
  const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ visible: false }));
  scene.add(mesh);
  return { id: SITE_HOST_ID, target: "site", mesh };
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
  if (host.run) {
    const { start, end, gaps } = host.run;
    const length = planLength(start, end);
    const origin = xy(start);
    const along = xy(end).sub(origin).normalize();
    const at = (distance: number) => origin.clone().addScaledVector(along, distance);
    const cuts=host.halfThickness?skirtingEndCuts(start,end,host.halfThickness,normal,host.cornerJoins):null;
    const segment=(from:number,to:number)=>{const a=at(from),b=at(to),mesh=trimRun(a,b,vertical,normal,spec);if(!mesh)return;applySkirtingCuts(mesh,a,b,normal,spec.depthM,cuts,from===0,to===length);group.add(mesh);};
    let left = 0;
    for (const [from, until] of gaps) {
      segment(left,from);
      left = until;
    }
    segment(left,length);
  }
  if (host.opening) {
    const { start, end, bottom, top } = host.opening;
    const left = xy(start, top), right = xy(end, top);
    const mitres=architraveMitres(left,right,bottom,normal,spec);
    group.add(...mitres.children.slice());
  }
  return group;
}

function dispose(root: THREE.Object3D) {
  const materials = new Set<THREE.Material>();
  const textures = new Set<THREE.Texture>();
  root.traverse(object => {
    if (!(object instanceof THREE.Mesh)) return;
    object.geometry.dispose();
    const faces = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of faces) materials.add(material);
  });
  for (const material of materials) {
    if (material instanceof THREE.MeshStandardMaterial) for(const texture of [material.map,material.bumpMap,material.roughnessMap])if(texture)textures.add(texture);
    material.dispose();
  }
  for(const texture of textures)texture.dispose();
}

function surfaceKey(entry: PlacedItem) {
  return JSON.stringify([entry.hostId, entry.target === "wall" || entry.target === "opening" ? entry.side : 1]);
}

import {MAX_PREVIEW_LIGHTS,nearestPreviewLights,previewLightingRole} from "./lightingPreview.ts";

export function createCatalogueScene(scene: THREE.Scene) {
  const mounts: THREE.Object3D[] = [];
  const mountedEntries=new Map<THREE.Object3D,PlacedItem>();
  const previewFixtures: {id:string;node:THREE.Object3D}[]=[];
  const previewSwitches: THREE.Object3D[]=[];
  const previewPool=Array.from({length:MAX_PREVIEW_LIGHTS},()=>{
    const light=new THREE.PointLight(0xffe5c4,0,8,2);light.castShadow=false;scene.add(light);return light;
  });
  const previewPoint=new THREE.Vector3();
  function visibleInScene(node:THREE.Object3D){for(let p:THREE.Object3D|null=node;p;p=p.parent)if(!p.visible)return false;return !!node.parent;}
  function updatePreviewLights(enabled:boolean,eye:THREE.Vector3){
    const fixtures=enabled?previewFixtures.filter(f=>visibleInScene(f.node)).map(f=>{f.node.getWorldPosition(previewPoint);return {id:f.id,position:previewPoint.toArray()};}):[];
    const nearest=nearestPreviewLights(fixtures,eye.toArray());
    previewPool.forEach((light,i)=>{const f=nearest[i];light.intensity=f?18:0;if(f)light.position.set(...f.position);});
  }
  function previewSwitchDistance(ray:THREE.Raycaster){
    const hit=ray.intersectObjects(previewSwitches.filter(visibleInScene),true)[0];return hit?.distance??Infinity;
  }
  const coveredLeaves = new Map<THREE.Mesh, boolean>();
  const hosts = new Map<THREE.Object3D, CatalogueHost>();
  let meshes: THREE.Object3D[] = [];
  let sourceKey: readonly CatalogueHost[] | null = null;
  let draftKey: readonly CatalogueHost[] | null = null;
  let itemKey: readonly PlacedItem[] | null = null;
  let stageKey: ConstructionStage = "finished";
  let layersKey:LayerOverrides=EMPTY_LAYERS;
  let cutawayKey=false;
  const marker = new THREE.Mesh(new THREE.RingGeometry(0.036, 0.047, 22),
    new THREE.MeshBasicMaterial({ color: 0x78ffe1, side: THREE.DoubleSide, depthWrite: false }));
  marker.visible = false;
  scene.add(marker);
  const up = new THREE.Vector3(0, 1, 0);
  const front = new THREE.Vector3(0, 0, 1);

  function clear() {
    for (const [leaf, visible] of coveredLeaves) leaf.visible = visible;
    coveredLeaves.clear();
    for (const root of mounts) root.removeFromParent();
    for (const root of mounts) dispose(root);
    mounts.length = 0;mountedEntries.clear();previewFixtures.length=0;previewSwitches.length=0;
    for(const light of previewPool)light.intensity=0;
    hosts.clear();
    meshes = [];
    sourceKey = draftKey = itemKey = null;
  }

  function sync(source: readonly CatalogueHost[], drafts: readonly CatalogueHost[], items: readonly PlacedItem[],
    stage: ConstructionStage = "finished",layers:LayerOverrides=EMPTY_LAYERS,cutaway=false) {
    if (sourceKey === source && draftKey === drafts && itemKey === items && stageKey === stage&&layersKey===layers&&cutawayKey===cutaway) return;
    clear();
    sourceKey = source;
    draftKey = drafts;
    itemKey = items;
    stageKey = stage;layersKey=layers;cutawayKey=cutaway;
    items = items.filter(placement => {
      const item = getCatalogueItem(placement.itemId);
      return !!item && itemLayerVisible(stage,item,layers)&&!(cutaway&&(placement.target==="roof"||placement.target==="ceiling"));
    });
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
    const designedDoors = new Set<string>();
    const doorFinishes = new Map<string, OpeningFinish>();
    for (const placement of items) {
      const item = getCatalogueItem(placement.itemId);
      const opening = byId.get(placement.hostId)?.opening;
      if (!item || !opening || openingFitMessage(item, opening.size)) continue;
      if (item.visual.kind === "entry" || (item.visual.kind === "opening-style" && item.visual.type === "door"))
        designedDoors.add(placement.hostId);
      if (item.group === "doors" && item.visual.kind === "surface") doorFinishes.set(surfaceKey(placement), item.visual);
    }
    for (const placement of items) {
      const item = getCatalogueItem(placement.itemId);
      const host = byId.get(placement.hostId);
      if (!item || !host || host.target !== placement.target) continue;
      const normal = new THREE.Vector3(...placement.normal);
      const point = new THREE.Vector3(...placement.point);
      const { visual } = item;
      if (host.target === "opening" && openingFitMessage(item, host.opening?.size)) continue;
      let node: THREE.Object3D;
      let actualFinishFace=false;
      if (visual.kind === "roof-component") {
        const edge = host.roofEdges?.find(row => row.key === placement.roofEdgeKey);
        if (!edge) continue;
        node = roofComponentMesh(edge, visual);
      } else if (visual.kind === "surface") {
        if (item.group === "doors" && designedDoors.has(host.id)) continue;
        if (visual.slot === "lining" && visibleFinishes.has(surfaceKey(placement))) continue;
        const face=host.finishFaces&&host.run?((host.run.end[0]-host.run.start[0])*normal.z-(host.run.end[1]-host.run.start[1])*normal.x>0?host.finishFaces.left:host.finishFaces.right):null;
        actualFinishFace=!!face;
        node = finishMesh(face??host.mesh, visual, host.target, normal, face?1:placement.side);
      } else if (visual.kind === "trim") {
        node = trimMount(host, item, normal);
      } else if (visual.kind === "entry" || visual.kind === "opening-style") {
        const opening = host.opening;
        if (!opening) continue;
        const { widthM, heightM } = opening.size;
        const entryFront = xy(opening.end).sub(xy(opening.start)).normalize()
          .cross(up).multiplyScalar(placement.side);
        const frontFinish = doorFinishes.get(surfaceKey(placement));
        const rearFinish = doorFinishes.get(surfaceKey({ ...placement, side: placement.side === 1 ? -1 : 1 }));
        const assembly = visual.kind === "entry" ? createEntryAssembly(visual, widthM, heightM, frontFinish, rearFinish) :
          createOpeningStyle(visual, widthM, heightM, visual.type === "door" ? frontFinish?.color : undefined);
        assembly.position.copy(xy(opening.start, opening.bottom).lerp(xy(opening.end, opening.bottom), 0.5));
        assembly.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(
          up.clone().cross(entryFront), up, entryFront,
        ));
        if (opening.reviewLeaf) {
          coveredLeaves.set(opening.reviewLeaf, opening.reviewLeaf.visible);
          opening.reviewLeaf.visible = false;
        }
        node = assembly;
      } else if (visual.kind === "timber") {
        if (!timberFitsWall(visual, placement.point, placement.turn, host.run)) continue;
        const section = createTimberSection(visual);
        const axis = visual.mount === "post" ? up : front;
        section.quaternion.setFromUnitVectors(axis, normal);
        section.quaternion.multiply(new THREE.Quaternion().setFromAxisAngle(axis, placement.turn * Math.PI / 2));
        section.position.copy(point).addScaledVector(normal, 0.001);
        node = section;
      } else if (visual.kind === "design-assembly") {
        node = createDesignAssembly(visual);
        if (host.target === "wall") {
          // Flyovers project out from the selected wall face and travel with that wall.
          node.position.set(point.x, 0, point.z).addScaledVector(normal, visual.depthM / 2);
          node.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(up.clone().cross(normal), up, normal));
        } else {
          node.position.copy(point).addScaledVector(normal, 0.002);
          node.quaternion.setFromUnitVectors(up, normal);
          node.quaternion.multiply(new THREE.Quaternion().setFromAxisAngle(up, placement.turn * Math.PI / 2));
        }
      } else {
        const { group, worktop } = createCatalogueFixture(visual, host.target);
        group.position.set(...placement.point).addScaledVector(normal, 0.001);
        const useUp = host.target === "floor" || host.target === "worktop";
        group.quaternion.setFromUnitVectors(useUp ? up : front, normal);
        group.quaternion.multiply(new THREE.Quaternion().setFromAxisAngle(useUp ? up : front, placement.turn * Math.PI / 2));
        if (worktop) addHost({ id: worktopId(placement.id), target: "worktop", mesh: worktop });
        node = group;
      }
      // Stored wall anchors remain on the design centreline. Mount to the selected physical face.
      if(host.target==="wall"&&host.halfThickness&&!actualFinishFace)node.position.addScaledVector(normal,host.halfThickness);
      // A local leaf finish must follow its swing/slide/overhead transform.
      const parent=visual.kind==="surface"&&item.group==="doors"&&host.opening?.reviewLeaf&&!designedDoors.has(host.id)?host.opening.reviewLeaf:host.mesh;
      if(parent.userData.nominalDoorSlab&&visual.kind==="surface")node.position.addScaledVector(normal,.019);
      parent.add(node);
      node.updateWorldMatrix(true, true);
      mounts.push(node);mountedEntries.set(node,placement);
      const lightingRole=previewLightingRole(item);
      if(lightingRole==="light")previewFixtures.push({id:placement.id,node});
      if(lightingRole==="switch")previewSwitches.push(node);
    }
    meshes = [...hosts.keys()];
  }

  function candidate(raycaster: THREE.Raycaster, item: CatalogueItem, turn = 0, selectedHit?:THREE.Intersection): { hit: ItemHit | null; reason?: string } {
    for (const hit of selectedHit?[selectedHit]:raycaster.intersectObjects(meshes, false)) {
      const host = hosts.get(hit.object);
      if (!host || !hit.face) continue;
      // Keep floor and interior placement available under roof finishes and behind opening targets.
      if ((host.target === "opening" || host.target === "roof" || host.target === "site" ||
          (host.target === "ceiling" && !showConstructionSurface(stageKey, "ceiling")) ||
          item.targets.includes("site")) && !item.targets.includes(host.target)) continue;
      if (!item.targets.includes(host.target)) return { hit: null };
      if (host.target === "opening") {
        const reason = openingFitMessage(item, host.opening?.size);
        if (reason) return { hit: null, reason };
      }
      const local = host.mesh.worldToLocal(hit.point.clone());
      if (item.visual.kind === "timber" && !timberFitsWall(item.visual, local.toArray() as Vector, turn, host.run)) {
        return { hit: null, reason: "Move the timber clear of the wall edge or opening, or rotate it." };
      }
      const normal = hit.face.normal.clone().normalize();
      const worldNormal = normal.clone().applyNormalMatrix(new THREE.Matrix3().getNormalMatrix(host.mesh.matrixWorld));
      const side = worldNormal.dot(raycaster.ray.direction) > 0 ? -1 : 1;
      if (host.target === "roof" && worldNormal.y * side <= 0.001) {
        return { hit: null, reason: "Aim at the top of the roof face." };
      }
      if (host.target === "worktop" && (normal.y < 0.9 || side < 0)) return { hit: null };
      const point = local.toArray() as Vector;
      const edge = item.visual.kind === "roof-component"
        ? nearestRoofEdge(host.roofEdges ?? [], item.visual, point) : undefined;
      if (item.visual.kind === "roof-component" && !edge) return { hit: null, reason: "Aim closer to a matching roof edge." };
      const hitValue: ItemHit = { hostId: host.id, target: host.target, point,
        normal: normal.multiplyScalar(side).toArray() as Vector, side, opening: host.opening?.size,
        roofEdgeKey: edge?.key };
      if (host.id.startsWith("draft-wall:") && host.run && !host.opening) {
        const { start, end } = host.run;
        const length = Math.hypot(end[0] - start[0], end[1] - start[1]);
        const along = ((point[0] - start[0]) * (end[0] - start[0]) +
          (point[2] - start[1]) * (end[1] - start[1])) / length;
        hitValue.anchor = { kind: "wall", offsetM: Math.max(0, Math.min(length, along)) };
      }
      if (host.ceilingDraft) {
        const { start, end } = host.ceilingDraft;
        hitValue.anchor = { kind: "ceiling",
          xFraction: THREE.MathUtils.clamp((point[0] - Math.min(start[0], end[0])) / Math.abs(end[0] - start[0]), 0, 1),
          zFraction: THREE.MathUtils.clamp((point[2] - Math.min(start[1], end[1])) / Math.abs(end[1] - start[1]), 0, 1) };
      }
      return { hit: hitValue };
    }
    return { hit: null };
  }

  function contextAt(ray:THREE.Raycaster):FinishContext|null{
    // One explicit controller action, never per-frame catalogue traversal.
    const hostHits=ray.intersectObjects(meshes,false).filter(h=>{
      const host=hosts.get(h.object);
      if(!host||host.target==="site"||!visibleInScene(h.object))return false;
      if(host.target==="ceiling"||host.target==="roof")return !cutawayKey&&showConstructionSurface(stageKey,host.target);
      if(host.target==="floor")return showConstructionSurface(stageKey,"floor");
      return stageKey!=="slab";
    });
    const picked=ray.intersectObjects(mounts.filter(visibleInScene),true).find(h=>visibleInScene(h.object)&&h.distance<=4);
    if(picked&&picked.distance<=(hostHits[0]?.distance??Infinity)+.10){
      for(let p:THREE.Object3D|null=picked.object;p;p=p.parent){
        const entry=mountedEntries.get(p);
        if(entry)return {hit:entry,entry,worldPoint:picked.point.toArray() as Vector};
      }
    }
    const first=hostHits[0];
    if(!first||first.distance>4)return null;
    const host=hosts.get(first.object)!;
    const probe=ITEM_CATALOGUE.find(i=>i.targets.includes(host.target)&&
      (host.target==="opening"?i.group===(host.opening?.size.door?"doors":"windows"):
        host.target==="wall"||host.target==="ceiling"?i.group==="paint":
        host.target==="floor"?i.group==="floors":host.target==="roof"?i.group==="roofing":i.group==="tapware"));
    if(!probe)return null;
    // Reuse the exact visible intersection chosen above. A second unfiltered
    // raycast can hit a hidden roof or an unrelated host before this surface.
    const result=candidate(ray,probe,0,first);
    return result.hit&&result.hit.hostId===host.id?{hit:result.hit,worldPoint:first.point.toArray() as Vector}:null;
  }

  function aim(hit: ItemHit | null) {
    marker.visible = false;
    if (!hit) return;
    const host = [...hosts.values()].find(entry => entry.id === hit.hostId);
    if (!host) return;
    const normal = new THREE.Vector3(...hit.normal).applyNormalMatrix(new THREE.Matrix3().getNormalMatrix(host.mesh.matrixWorld));
    marker.position.copy(host.mesh.localToWorld(new THREE.Vector3(...hit.point))).addScaledVector(normal, 0.015+(host.halfThickness??0));
    marker.quaternion.setFromUnitVectors(front, normal);
    marker.visible = true;
  }

  return { sync, clear, candidate, aim, contextAt, updatePreviewLights, previewSwitchDistance };
}
