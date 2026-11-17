/** Windows PS VR2 PC-adapter / SteamVR compatibility utilities.
 *
 * Browser WebXR cannot prove the Sony adapter's identity or invoke its USB
 * driver. We use standard immersive-vr + xr-standard inputs exposed by the
 * active OpenXR runtime, without device-specific guessed button indexes.
 * All helpers are pure or accept an explicitly injected browser capability.
 */

export type PcVrCapabilityStatus =
  | "available"
  | "insecure-context"
  | "webxr-missing"
  | "immersive-vr-unavailable"
  | "probe-failed";

export interface PcVrCapability {
  status: PcVrCapabilityStatus;
  message: string;
  canAttemptImmersiveVr: boolean;
}

export interface PcVrProbe {
  secureContext: boolean;
  xr?: {
    isSessionSupported: (mode: "immersive-vr") => Promise<boolean>;
  } | null;
}

export async function checkPcVrCapability(probe: PcVrProbe): Promise<PcVrCapability> {
  if (!probe.secureContext) {
    return {
      status: "insecure-context", canAttemptImmersiveVr: false,
      message: "Open PlanReader over HTTPS or localhost to allow WebXR.",
    };
  }
  if (!probe.xr || typeof probe.xr.isSessionSupported !== "function") {
    return {
      status: "webxr-missing", canAttemptImmersiveVr: false,
      message: "This browser does not expose WebXR. Try an up-to-date Windows Chrome or Edge browser with SteamVR running.",
    };
  }
  try {
    if (await probe.xr.isSessionSupported("immersive-vr")) {
      return {
        status: "available", canAttemptImmersiveVr: true,
        message: "This browser supports immersive VR. Use Enter VR in the viewer to test the connected PC headset.",
      };
    }
    return {
      status: "immersive-vr-unavailable", canAttemptImmersiveVr: false,
      message: "Immersive VR is unavailable in this browser/runtime. Check SteamVR, its OpenXR runtime setting and the headset connection.",
    };
  } catch {
    return {
      status: "probe-failed", canAttemptImmersiveVr: false,
      message: "Browser VR capability check failed. Verify SteamVR/OpenXR and retry. Desktop review remains available.",
    };
  }
}

export type VrHandedness = "left" | "right" | "none";
export interface PcVrInputSource {
  handedness?: string;
  profiles?: readonly string[];
  targetRayMode?: string;
  gripSpace?: unknown | null;
  gamepad?: {
    mapping?: string;
    buttons?: ReadonlyArray<{pressed?: boolean; value?: number} | null>;
  } | null;
}
export interface PcVrControllerInfo {
  hand: VrHandedness;
  profile: string;
  trackedPointer: boolean;
  gripTracked: boolean;
  xrStandardSqueeze: boolean;
}

export function inspectPcVrController(source: PcVrInputSource | null | undefined): PcVrControllerInfo | null {
  if (!source) return null;
  const hand: VrHandedness =
    source.handedness === "left" || source.handedness === "right"
      ? source.handedness : "none";
  const named = Array.isArray(source.profiles)
    ? source.profiles.find(p => typeof p === "string" && !!p && p.length <= 100)
    : undefined;
  return {
    hand,
    // A generic profile is not proof this is a Sony controller.
    profile: named ?? "generic WebXR controller",
    trackedPointer: source.targetRayMode === "tracked-pointer",
    gripTracked: source.gripSpace !== null && source.gripSpace !== undefined,
    xrStandardSqueeze: source.gamepad?.mapping === "xr-standard" &&
      !!source.gamepad?.buttons?.[1],
  };
}

/** The xr-standard gamepad button #1 is a GENERIC squeeze/grip fallback.
 * It is not a claimed proprietary PS VR2 hardware mapping.
 */
export function standardSqueezePressed(source: PcVrInputSource | null | undefined): boolean | null {
  if (source?.gamepad?.mapping !== "xr-standard") return null;
  const button = source.gamepad.buttons?.[1];
  if (!button) return null;
  if (typeof button.pressed === "boolean") return button.pressed;
  if (typeof button.value === "number" && Number.isFinite(button.value)) {
    return button.value > 0.65;
  }
  return null;
}

/** Native WebXR squeeze events take priority; gamepad polling only fills gaps.
 * If both report one squeeze, run the edit action exactly once. Action fires
 * on release, just as the standard WebXR 'squeeze' event does.
 */
export class PcVrSqueezeTracker {
  private readonly state = new Map<string, {
    previousPressed: boolean;
    nativeSeen: boolean;
    fallbackFired: boolean;
  }>();

  private get(key: string) {
    let state = this.state.get(key);
    if (!state) {
      state = {previousPressed: false, nativeSeen: false, fallbackFired: false};
      this.state.set(key, state);
    }
    return state;
  }

  onNativeStart(key: string): void {
    this.get(key).nativeSeen = true;
  }

  onNativeSqueeze(key: string): boolean {
    const state = this.get(key);
    state.nativeSeen = true;
    state.previousPressed = false;
    if (state.fallbackFired) {
      state.fallbackFired = false;
      return false;
    }
    return true;
  }

  poll(key: string, pressed: boolean | null): boolean {
    const state = this.get(key);
    if (pressed === null) {
      state.previousPressed = false;
      return false;
    }
    if (state.nativeSeen) {
      state.previousPressed = pressed;
      return false;
    }
    if (pressed) {
      if (!state.previousPressed) state.fallbackFired = false;
      state.previousPressed = true;
      return false;
    }
    const fire = state.previousPressed && !state.fallbackFired;
    state.previousPressed = false;
    if (fire) state.fallbackFired = true;
    return fire;
  }

  clear(key?: string): void {
    if (key === undefined) this.state.clear();
    else this.state.delete(key);
  }
}
