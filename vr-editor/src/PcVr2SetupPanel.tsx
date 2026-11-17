import { useEffect, useState } from "react";
import {
  checkPcVrCapability,
} from "./pcVr2Support";
import type {
  PcVrCapability, PcVrControllerInfo, PcVrProbe,
} from "./pcVr2Support";

export interface PcVrSessionReport {
  presenting: boolean;
  controllers: PcVrControllerInfo[];
}

type Props = {
  session: PcVrSessionReport;
};

export function PcVr2SetupPanel({session}: Props) {
  const [probe, setProbe] = useState<PcVrCapability | null>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setProbe(null);
    const xr = (navigator as Navigator & {xr?: PcVrProbe["xr"]}).xr;
    void checkPcVrCapability({
      secureContext: window.isSecureContext,
      xr,
    }).then(next => {
      if (!cancelled) setProbe(next);
    });
    return () => { cancelled = true; };
  }, [retry]);

  const status = session.presenting
    ? "Headset immersive session active"
    : probe?.canAttemptImmersiveVr
      ? "Browser ready to attempt VR"
      : probe === null
        ? "Checking browser headset support…"
        : "VR not ready";

  return <section className="pcvr2-panel" aria-label="PlayStation VR2 PC adapter compatibility">
    <span className="eyebrow">PLAYSTATION VR2 · PC ADAPTER</span>
    <p className="muted">
      Run this VR editor in a compatible Windows desktop browser through
      SteamVR/OpenXR. A successful WebXR check means the browser can attempt
      immersive VR, not that the Sony headset or adapter has been identified.
    </p>
    <p className="pcvr2-status" role="status">
      <strong>{status}</strong>
      <span>{probe?.message ?? "Checking immersive-vr support…"}</span>
    </p>
    <button type="button" disabled={probe === null}
      onClick={() => setRetry(previous => previous + 1)}>
      Check VR availability again
    </button>
    <p className="muted">
      PS VR2 PC: connect the adapter directly to USB 3, connect DisplayPort 1.4
      to the graphics card, pair both Sense controllers over Bluetooth, and
      complete initial setup in SteamVR and PlayStation VR2 App.
    </p>
    {session.presenting && <div className="pcvr2-controllers">
      <strong>Live WebXR controller inputs</strong>
      {session.controllers.length === 0
        ? <p className="muted">No tracked controller inputs reported. Check
            Sense-controller Bluetooth pairing and SteamVR tracking.</p>
        : <ul>{session.controllers.map((input,index) =>
          <li key={input.hand + ":" + index}>
            <strong>{input.hand === "none" ? "Unassigned" : input.hand} controller</strong>
            <span>Profile: {input.profile}</span>
            <span>{input.trackedPointer ? "Tracked pointer" : "No tracked ray"}
              {" · "}{input.gripTracked ? "Grip tracked" : "No grip pose"}
              {" · "}{input.xrStandardSqueeze ? "Generic grip mapping" : "WebXR actions only"}
            </span>
          </li>)}</ul>}
    </div>}
    <p className="muted">In the headset: L2/R2 trigger selects a wall.
      The squeeze/grip action cycles temporary finish colours in inspection
      mode. SteamVR dashboard controls stay managed by SteamVR.
      Desktop mouse and keyboard remain available if immersive VR fails.</p>
    <p className="muted">
      Basic VR support does not require eye tracking, adaptive triggers or HDR.
      Real PS VR2-on-PC acceptance testing is still required.
    </p>
    <p className="pcvr2-links">
      <a href="https://www.playstation.com/en-au/support/hardware/pc-ps-vr2-set-up/"
        target="_blank" rel="noopener noreferrer">Official PC setup instructions</a>
      <a href="https://store.steampowered.com/app/2580190/PlayStationVR2_App/"
        target="_blank" rel="noopener noreferrer">PlayStation VR2 App on Steam</a>
    </p>
  </section>;
}
