import test from "node:test";
import assert from "node:assert/strict";
import {
  checkPcVrCapability,
  inspectPcVrController,
  standardSqueezePressed,
  PcVrSqueezeTracker,
} from "../src/pcVr2Support.ts";

test("SteamVR/PS VR2 readiness checks WebXR immersive-vr, not fake adapter identity", async () => {
  let calls = 0;
  const result = await checkPcVrCapability({
    secureContext:true,
    xr:{isSessionSupported:async mode => {
      assert.equal(mode,"immersive-vr");
      calls++;
      return true;
    }},
  });
  assert.equal(calls,1);
  assert.equal(result.status,"available");
  assert.equal(result.canAttemptImmersiveVr,true);
  assert.match(result.message,/browser supports immersive VR/i);
  assert.doesNotMatch(result.message,/PS VR2 connected/i);
});

test("insecure browser, missing WebXR, unsupported device and rejected probe are actionable", async () => {
  const noHttps = await checkPcVrCapability({
    secureContext:false,
    xr:{isSessionSupported:async()=>{throw Error("Must not probe in insecure context");}},
  });
  assert.equal(noHttps.status,"insecure-context");
  assert.match(noHttps.message,/HTTPS/);

  const noXR = await checkPcVrCapability({secureContext:true,xr:null});
  assert.equal(noXR.status,"webxr-missing");
  assert.equal(noXR.canAttemptImmersiveVr,false);

  const unsupported = await checkPcVrCapability({
    secureContext:true,xr:{isSessionSupported:async()=>false},
  });
  assert.equal(unsupported.status,"immersive-vr-unavailable");
  assert.match(unsupported.message,/SteamVR/);

  const broken = await checkPcVrCapability({
    secureContext:true,xr:{isSessionSupported:async()=>{throw Error("driver offline");}},
  });
  assert.equal(broken.status,"probe-failed");
  assert.doesNotMatch(broken.message,/driver offline/);
});

test("Sony controller profiles are informative only; generic SteamVR input remains usable", () => {
  const input={
    handedness:"left",profiles:["sony-interactive-entertainment-vr2-sense",
      "generic-trigger-squeeze-thumbstick"],
    targetRayMode:"tracked-pointer",
    gripSpace:{},
    gamepad:{mapping:"xr-standard",buttons:[
      {pressed:false},{pressed:true},{pressed:false}
    ]},
  };
  const info=inspectPcVrController(input);
  assert.equal(info?.hand,"left");
  assert.equal(info?.trackedPointer,true);
  assert.equal(info?.gripTracked,true);
  assert.equal(info?.xrStandardSqueeze,true);
  assert.equal(standardSqueezePressed(input),true);
  const generic=inspectPcVrController({
    handedness:"right",profiles:[],
    targetRayMode:"tracked-pointer",gripSpace:null,
    gamepad:{mapping:"",buttons:[{pressed:false},{pressed:true}]},
  });
  assert.equal(generic?.profile,"generic WebXR controller");
  assert.equal(generic?.gripTracked,false);
  assert.equal(standardSqueezePressed({gamepad:{mapping:"",buttons:[null,{pressed:true}]}}),null);
  assert.equal(standardSqueezePressed({gamepad:null}),null);
  assert.equal(inspectPcVrController(null),null);
});

test("generic controller squeeze fires once on grip release, never on each frame", () => {
  const state=new PcVrSqueezeTracker();
  assert.equal(state.poll("0",false),false);
  assert.equal(state.poll("0",true),false);
  assert.equal(state.poll("0",true),false);
  assert.equal(state.poll("0",false),true);
  assert.equal(state.poll("0",false),false);
  assert.equal(state.poll("0",true),false);
  assert.equal(state.poll("0",false),true);
  // Separate left and right hand states are independent.
  assert.equal(state.poll("1",true),false);
  assert.equal(state.poll("1",false),true);
});

test("native WebXR squeeze events take precedence over Gamepad fallback", () => {
  const state=new PcVrSqueezeTracker();
  state.onNativeStart("left");
  assert.equal(state.poll("left",true),false);
  assert.equal(state.poll("left",false),false);
  assert.equal(state.onNativeSqueeze("left"),true);
  assert.equal(state.poll("left",true),false);
  assert.equal(state.poll("left",false),false);
  assert.equal(state.onNativeSqueeze("left"),true);
  state.clear("left");
  assert.equal(state.poll("left",true),false);
  assert.equal(state.poll("left",false),true);
  // A subsequent native event for the same release cannot double-apply.
  assert.equal(state.onNativeSqueeze("left"),false);
});

test("unsupported raw gamepad mappings never run arbitrary buttons as grip edits", () => {
  const state=new PcVrSqueezeTracker();
  const source={gamepad:{mapping:"unknown",buttons:[{pressed:true},{pressed:true}]}};
  assert.equal(standardSqueezePressed(source),null);
  assert.equal(state.poll("left",standardSqueezePressed(source)),false);
  assert.equal(standardSqueezePressed({gamepad:{mapping:"xr-standard",buttons:[
    {pressed:false},{pressed:undefined,value:.9}
  ]}}),true);
  assert.equal(standardSqueezePressed({gamepad:{mapping:"xr-standard",buttons:[
    {pressed:false},{pressed:undefined,value:.2}
  ]}}),false);
  state.clear();
  assert.equal(state.poll("left",false),false);
});
