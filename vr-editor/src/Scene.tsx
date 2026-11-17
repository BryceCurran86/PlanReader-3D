import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { VRButton } from "three/addons/webxr/VRButton.js";
import type { EditorObject, SceneManifest } from "./types";
import { studyColor } from "./finishStudy";
import type { FinishStudy } from "./finishStudy";

type Props = {
  manifest: SceneManifest;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  finishStudy: FinishStudy | null;
  onCycleStudy: (objectId: string) => void;
};

function point2(value: unknown): value is [number, number] {
  return Array.isArray(value) && value.length === 2 &&
    value.every((v) => typeof v === "number" && Number.isFinite(v));
}

function displayObject(row: EditorObject): THREE.Object3D | null {
  const shape = row.geometry;
  if (!shape || !point2(shape.start) || !point2(shape.end)) return null;
  const a = new THREE.Vector3(shape.start[0], 0, shape.start[1]);
  const b = new THREE.Vector3(shape.end[0], 0, shape.end[1]);
  if (a.distanceTo(b) <= 1e-8) return null;
  const trustworthy = row.renderState === "verified" &&
    row.unresolvedIssues.length === 0;
  const color = trustworthy ? 0x48b8a6 : 0xe3ad58;
  const name = row.objectId;
  if (shape.kind === "wallFace" && Number.isFinite(shape.heightM) &&
      shape.heightM > 0 && shape.heightM < 1000) {
    const h = shape.heightM;
    const data = new Float32Array([
      a.x, 0, a.z, b.x, 0, b.z, b.x, h, b.z,
      a.x, 0, a.z, b.x, h, b.z, a.x, h, a.z,
    ]);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(data, 3));
    geometry.computeVertexNormals();
    const material = new THREE.MeshStandardMaterial({
      color,
      transparent: !trustworthy,
      opacity: trustworthy ? 0.92 : 0.4,
      side: THREE.DoubleSide,
      roughness: 0.8,
      metalness: 0,
      depthWrite: trustworthy,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.userData.objectId = name;
    return mesh;
  }
  // Unverified height is shown ONLY as source XY linework, never an extruded
  // "default 2.7m" wall or a user-billable surface.
  const lineGeometry = new THREE.BufferGeometry().setFromPoints([
    a.clone().add(new THREE.Vector3(0, 0.015, 0)),
    b.clone().add(new THREE.Vector3(0, 0.015, 0)),
  ]);
  const line = new THREE.Line(
    lineGeometry, new THREE.LineBasicMaterial({ color: 0xefb35d })
  );
  line.userData.objectId = name;
  return line;
}

function labelSprite(value: string): THREE.Sprite {
  const canvas = document.createElement("canvas");
  canvas.width = 640;
  canvas.height = 128;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.fillStyle = "rgba(16, 25, 32, 0.93)";
    ctx.fillRect(0, 0, 640, 128);
    ctx.strokeStyle = "#40c4b5";
    ctx.lineWidth = 4;
    ctx.strokeRect(2, 2, 636, 124);
    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 28px sans-serif";
    ctx.fillText(value.slice(0, 36), 22, 74);
  }
  const texture = new THREE.CanvasTexture(canvas);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
    map: texture, depthTest: false,
  }));
  sprite.scale.set(2.9, 0.58, 1);
  return sprite;
}

export function SceneView({ manifest, selectedId, onSelect, finishStudy, onCycleStudy }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const callback = useRef(onSelect);
  callback.current = onSelect;
  const cycleCallback = useRef(onCycleStudy);
  cycleCallback.current = onCycleStudy;
  const picked = useRef(selectedId);
  picked.current = selectedId;
  const currentStudy = useRef(finishStudy);
  currentStudy.current = finishStudy;

  useEffect(() => {
    const parent = host.current;
    if (!parent) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x101920);
    scene.add(new THREE.HemisphereLight(0xdceef5, 0x2e3340, 2));
    const sunlight = new THREE.DirectionalLight(0xffffff, 1.4);
    sunlight.position.set(8, 16, 7);
    scene.add(sunlight);
    const grid = new THREE.GridHelper(50, 50, 0x36515a, 0x283842);
    scene.add(grid);

    const camera = new THREE.PerspectiveCamera(65, 1, 0.01, 2500);
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    } catch {
      setRenderError("WebGL is unavailable. The source evidence inspector remains usable without 3D.");
      return;
    }
    setRenderError(null);
    renderer.domElement.tabIndex = 0;
    renderer.domElement.setAttribute(
      "aria-label", "Read-only building scene. Use Escape to clear selection."
    );
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.xr.enabled = true;
    renderer.xr.setReferenceSpaceType("local-floor");
    parent.append(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.minDistance = 0.15;
    controls.maxDistance = 2000;

    const physical = new THREE.Group();
    scene.add(physical);
    const pickables: THREE.Object3D[] = [];
    const sourceById = new Map(manifest.objects.map(row => [row.objectId, row]));
    for (const row of manifest.objects) {
      const item = displayObject(row);
      if (!item) continue;
      physical.add(item);
      pickables.push(item);
      // Keep the original review material as the fallback after any study clears.
      if (item instanceof THREE.Mesh && item.material instanceof THREE.MeshStandardMaterial)
        item.userData.originalReviewColor = item.material.color.getHex();
    }
    const bbox = new THREE.Box3().setFromObject(physical);
    if (!bbox.isEmpty()) {
      const center = bbox.getCenter(new THREE.Vector3());
      const radius = Math.max(bbox.getSize(new THREE.Vector3()).length(), 4);
      controls.target.copy(center);
      camera.position.set(center.x + radius, center.y + radius * 0.7,
        center.z + radius);
      camera.near = Math.max(0.01, radius / 5000);
      camera.far = Math.max(300, radius * 50);
      camera.updateProjectionMatrix();
    } else {
      camera.position.set(8, 6, 8);
      controls.target.set(0, 0, 0);
    }
    controls.update();

    const raycaster = new THREE.Raycaster();
    raycaster.params.Line = { threshold: 0.2 };
    const mouse = new THREE.Vector2();
    const select = (id: string | null) => callback.current(id);
    function pick() {
      const hits = raycaster.intersectObjects(pickables, false);
      const hit = hits[0];
      select(typeof hit?.object.userData.objectId === "string"
        ? hit.object.userData.objectId : null);
    }
    let startPointer: { id: number; x: number; y: number } | null = null;
    function pointerDown(e: PointerEvent) {
      if (renderer.xr.isPresenting) return;
      startPointer = { id: e.pointerId, x: e.clientX, y: e.clientY };
    }
    function pointerUp(e: PointerEvent) {
      const start = startPointer;
      startPointer = null;
      if (renderer.xr.isPresenting || !start || start.id !== e.pointerId) return;
      // Orbiting the camera must not silently select a different wall.
      if (Math.hypot(e.clientX - start.x, e.clientY - start.y) > 6) return;
      const rect = renderer.domElement.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      mouse.set(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1
      );
      raycaster.setFromCamera(mouse, camera);
      pick();
    }
    function keyDown(e: KeyboardEvent) {
      if (e.key === "Escape") select(null);
    }
    renderer.domElement.addEventListener("pointerdown", pointerDown);
    renderer.domElement.addEventListener("pointerup", pointerUp);
    renderer.domElement.addEventListener("keydown", keyDown);

    // Controller selection uses exactly the same pickables and canonical
    // object IDs as desktop. No headset state changes any building geometry.
    const tempMatrix = new THREE.Matrix4();
    const controllers = [renderer.xr.getController(0), renderer.xr.getController(1)];
    function xrPick(controller: THREE.Group) {
      tempMatrix.identity().extractRotation(controller.matrixWorld);
      raycaster.ray.origin.setFromMatrixPosition(controller.matrixWorld);
      raycaster.ray.direction.set(0, 0, -1).applyMatrix4(tempMatrix);
      pick();
    }
    const select0 = () => xrPick(controllers[0]);
    const select1 = () => xrPick(controllers[1]);
    // Grip/squeeze cycles a cosmetic colour on the currently selected wall.
    // Trigger selection remains independent. No source command is generated.
    const squeeze = () => {
      const id = picked.current;
      if (id && sourceById.has(id)) cycleCallback.current(id);
    };
    controllers[0].addEventListener("squeeze", squeeze);
    controllers[1].addEventListener("squeeze", squeeze);
    controllers[0].addEventListener("select", select0);
    controllers[1].addEventListener("select", select1);
    for (const controller of controllers) {
      const pointer = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 0, -2)
        ]),
        new THREE.LineBasicMaterial({ color: 0x45c6b4 })
      );
      controller.add(pointer);
      scene.add(controller);
    }

    const vrButton = VRButton.createButton(renderer);
    vrButton.setAttribute("aria-label", "Enter or exit VR");
    parent.append(vrButton);

    function onResize() {
      const width = Math.max(parent?.clientWidth || 1, 1);
      const height = Math.max(parent?.clientHeight || 1, 1);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    }
    const resizeObserver = new ResizeObserver(onResize);
    resizeObserver.observe(parent);
    onResize();

    let selectedLabel: THREE.Sprite | null = null;
    let lastLabelId: string | null = null;
    renderer.setAnimationLoop(() => {
      // Only the existing rendered mesh tint changes. No scene DTO/geometry/
      // ledger mutation, and no new mesh or billable wall is ever created.
      for (const item of pickables) {
        if (!(item instanceof THREE.Mesh) || !(item.material instanceof THREE.MeshStandardMaterial)) continue;
        const row = sourceById.get(item.userData.objectId as string);
        if (!row) continue;
        const swatch = studyColor(row, currentStudy.current);
        const fallback = item.userData.originalReviewColor as number;
        const colour = swatch ?? fallback;
        if (item.material.color.getHex() !== colour) item.material.color.setHex(colour);
      }
      if (picked.current !== lastLabelId) {
        if (selectedLabel) {
          scene.remove(selectedLabel);
          selectedLabel.material.map?.dispose();
          selectedLabel.material.dispose();
          selectedLabel = null;
        }
        lastLabelId = picked.current;
        if (lastLabelId) {
          const sourceObject = pickables.find(x => x.userData.objectId === lastLabelId);
          if (sourceObject) {
            selectedLabel = labelSprite(lastLabelId);
            const bounds = new THREE.Box3().setFromObject(sourceObject);
            selectedLabel.position.copy(bounds.getCenter(new THREE.Vector3()));
            selectedLabel.position.y += 1.2;
            scene.add(selectedLabel);
          }
        }
      }
      controls.update();
      renderer.render(scene, camera);
    });

    return () => {
      renderer.setAnimationLoop(null);
      resizeObserver.disconnect();
      renderer.domElement.removeEventListener("pointerdown", pointerDown);
      renderer.domElement.removeEventListener("pointerup", pointerUp);
      renderer.domElement.removeEventListener("keydown", keyDown);
      controllers[0].removeEventListener("squeeze", squeeze);
      controllers[1].removeEventListener("squeeze", squeeze);
      controllers[0].removeEventListener("select", select0);
      controllers[1].removeEventListener("select", select1);
      controls.dispose();
      if (selectedLabel) {
        scene.remove(selectedLabel);
        selectedLabel.material.map?.dispose();
        selectedLabel.material.dispose();
      }
      scene.traverse((o) => {
        if (o instanceof THREE.Mesh || o instanceof THREE.Line) {
          o.geometry.dispose();
          const materials = Array.isArray(o.material) ? o.material : [o.material];
          materials.forEach(m => m.dispose());
        }
      });
      renderer.dispose();
      vrButton.remove();
      renderer.domElement.remove();
    };
  }, [manifest]);

  return <div className="scene-canvas" ref={host}
    aria-label="Read-only 3D building scene; click or point to select an object">
    {renderError && <div className="scene-loading" role="alert">{renderError}</div>}
  </div>;
}
