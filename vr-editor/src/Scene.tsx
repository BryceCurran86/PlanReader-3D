import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { VRButton } from "three/addons/webxr/VRButton.js";
import type { EditorObject, SceneManifest } from "./types";
import { studyColor } from "./finishStudy";
import { safeDrafts } from "./reviewDraft";
import type { DraftHistory, WallDraft } from "./reviewDraft";
import { maxRenderPixelRatio, mayRenderWallFace, shadowMapSize, VISUAL_PRESETS } from "./visualRealism";
import type { LightingMood, RenderQuality } from "./visualRealism";

type Props = {
  manifest: SceneManifest;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  draftState: DraftHistory | null;
  onCycleStudy: (objectId: string) => void;
  mood: LightingMood;
  quality: RenderQuality;
};

function point2(value: unknown): value is [number, number] {
  return Array.isArray(value) && value.length === 2 &&
    value.every((v) => typeof v === "number" && Number.isFinite(v));
}

function displayObject(row: EditorObject, roughness: number): THREE.Object3D | null {
  const shape = row.geometry;
  if (!shape || !point2(shape.start) || !point2(shape.end)) return null;
  const a = new THREE.Vector3(shape.start[0], 0, shape.start[1]);
  const b = new THREE.Vector3(shape.end[0], 0, shape.end[1]);
  if (a.distanceTo(b) <= 1e-8) return null;
  const trustworthy = row.renderState === "verified" &&
    row.unresolvedIssues.length === 0;
  const color = trustworthy ? 0x48b8a6 : 0xe3ad58;
  const name = row.objectId;
  if (shape.kind === "wallFace" && mayRenderWallFace(shape.kind, shape.heightM)) {
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
      roughness,
      metalness: 0,
      depthWrite: trustworthy,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.userData.objectId = name;
    mesh.castShadow = true;
    mesh.receiveShadow = true;
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

export function SceneView({ manifest, selectedId, onSelect, draftState, onCycleStudy, mood, quality }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const callback = useRef(onSelect);
  callback.current = onSelect;
  const cycleCallback = useRef(onCycleStudy);
  cycleCallback.current = onCycleStudy;
  const visualSettings = useRef({ mood, quality });
  visualSettings.current = { mood, quality };
  const picked = useRef(selectedId);
  picked.current = selectedId;
  const draftMap = useRef<Map<string, WallDraft>>(new Map());
  draftMap.current = new Map((draftState ? safeDrafts(draftState, manifest) : [])
    .map(d => [d.objectId, d]));

  useEffect(() => {
    const parent = host.current;
    if (!parent) return;

    const scene = new THREE.Scene();
    const initialPreset = VISUAL_PRESETS[visualSettings.current.mood];
    scene.background = new THREE.Color(initialPreset.background);
    const ambient = new THREE.HemisphereLight(
      initialPreset.ambientSky, initialPreset.ambientGround, initialPreset.ambientIntensity,
    );
    scene.add(ambient);
    const sunlight = new THREE.DirectionalLight(initialPreset.sunColor, initialPreset.sunIntensity);
    sunlight.position.set(...initialPreset.sunPosition);
    sunlight.castShadow = true;
    sunlight.shadow.mapSize.set(shadowMapSize(visualSettings.current.quality),
      shadowMapSize(visualSettings.current.quality));
    sunlight.shadow.bias = -0.0001;
    sunlight.shadow.normalBias = 0.03;
    sunlight.shadow.radius = 2;
    scene.add(sunlight);
    const grid = new THREE.GridHelper(50, 50, 0x72919f, 0x91a9b0);
    grid.position.y = 0.005;
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
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1,
      maxRenderPixelRatio(visualSettings.current.quality, false)));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = initialPreset.exposure;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
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
      const item = displayObject(row, initialPreset.materialRoughness);
      if (!item) continue;
      physical.add(item);
      pickables.push(item);
      // Keep the original review material as the fallback after any study clears.
      if (item instanceof THREE.Mesh && item.material instanceof THREE.MeshStandardMaterial) {
        item.userData.originalReviewColor = item.material.color.getHex();
        item.userData.originalOpacity = item.material.opacity;
        const geometry = row.geometry;
        if (geometry?.kind === "wallFace") item.userData.originalHeight = geometry.heightM;
      }
    }
    // Presentation-only shadow-catching floor; never a sourced slab, floor finish or quantity.
    // It exists solely below existing linework and cannot be selected.
    const presentationFloor = new THREE.Mesh(
      new THREE.PlaneGeometry(1, 1),
      new THREE.ShadowMaterial({ color: 0x293440, opacity: 0.15 }),
    );
    presentationFloor.rotation.x = -Math.PI / 2;
    presentationFloor.position.y = -0.01;
    presentationFloor.receiveShadow = true;
    scene.add(presentationFloor);
    const bbox = new THREE.Box3().setFromObject(physical);
    if (!bbox.isEmpty()) {
      const center = bbox.getCenter(new THREE.Vector3());
      const radius = Math.max(bbox.getSize(new THREE.Vector3()).length(), 4);
      controls.target.copy(center);
      const size = bbox.getSize(new THREE.Vector3());
      const shadowExtent = Math.min(150, Math.max(12, size.x, size.z) * 1.4);
      sunlight.shadow.camera.left = -shadowExtent;
      sunlight.shadow.camera.right = shadowExtent;
      sunlight.shadow.camera.top = shadowExtent;
      sunlight.shadow.camera.bottom = -shadowExtent;
      sunlight.shadow.camera.near = 0.5;
      sunlight.shadow.camera.far = 180;
      sunlight.shadow.camera.updateProjectionMatrix();
      presentationFloor.scale.set(Math.min(300, Math.max(20, size.x * 1.5)),
        Math.min(300, Math.max(20, size.z * 1.5)), 1);
      presentationFloor.position.x = center.x;
      presentationFloor.position.z = center.z;
      sunlight.target.position.copy(center);
      sunlight.position.add(center);
      scene.add(sunlight.target);
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
    let lastMood: LightingMood | null = null;
    let lastQuality: RenderQuality | null = null;
    renderer.setAnimationLoop(() => {
      const { mood: activeMood, quality: activeQuality } = visualSettings.current;
      if (lastMood !== activeMood) {
        const preset = VISUAL_PRESETS[activeMood];
        scene.background = new THREE.Color(preset.background);
        ambient.color.setHex(preset.ambientSky);
        ambient.groundColor.setHex(preset.ambientGround);
        ambient.intensity = preset.ambientIntensity;
        sunlight.color.setHex(preset.sunColor);
        sunlight.intensity = preset.sunIntensity;
        sunlight.position.set(...preset.sunPosition);
        renderer.toneMappingExposure = preset.exposure;
        for (const item of pickables) {
          if (item instanceof THREE.Mesh && item.material instanceof THREE.MeshStandardMaterial) {
            item.material.roughness = preset.materialRoughness;
          }
        }
        lastMood = activeMood;
      }
      if (lastQuality !== activeQuality) {
        const size = shadowMapSize(activeQuality);
        sunlight.shadow.mapSize.set(size, size);
        sunlight.shadow.map?.dispose();
        sunlight.shadow.map = null;
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1,
          maxRenderPixelRatio(activeQuality, renderer.xr.isPresenting)));
        onResize();
        lastQuality = activeQuality;
      }
      // Render-only proposals; underlying source geometry and manifest are untouched.
      // Ghost heights may only modify an EXISTING display wall-face mesh.
      for (const item of pickables) {
        if (!(item instanceof THREE.Mesh) || !(item.material instanceof THREE.MeshStandardMaterial)) continue;
        const id = item.userData.objectId as string;
        const row = sourceById.get(id);
        if (!row) continue;
        const draft = draftMap.current.get(id);
        const swatch = studyColor(row, draft?.swatch ? { objectId: id, swatch: draft.swatch } : null);
        const originalHeight = item.userData.originalHeight as number | undefined;
        const ghostHeight = draft?.heightM;
        const ghost = ghostHeight !== null && ghostHeight !== undefined &&
          originalHeight !== undefined;
        const colour = swatch ?? (ghost ? 0xb899de : item.userData.originalReviewColor as number);
        if (item.material.color.getHex() !== colour) item.material.color.setHex(colour);
        const originalOpacity = item.userData.originalOpacity as number;
        item.material.opacity = ghost ? 0.30 : originalOpacity;
        item.material.transparent = ghost || originalOpacity < 1;
        item.material.depthWrite = !ghost && originalOpacity >= 0.9;
        if (originalHeight !== undefined) {
          const height = ghost ? ghostHeight : originalHeight;
          const position = item.geometry.getAttribute("position");
          if (position instanceof THREE.BufferAttribute && position.getY(2) !== height) {
            // Triangle vertices 2, 4 and 5 are the upper face vertices.
            position.setY(2, height); position.setY(4, height); position.setY(5, height);
            position.needsUpdate = true;
            item.geometry.computeVertexNormals();
          }
        }
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
      presentationFloor.geometry.dispose();
      presentationFloor.material.dispose();
      sunlight.shadow.dispose();
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
