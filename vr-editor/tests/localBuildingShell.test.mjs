import test from "node:test";
import assert from "node:assert/strict";
import {localBuildingShell} from "../src/connectedDraftShell.ts";
import {defaultWallAssembly} from "../src/wallProfiles.ts";
const w=(id,start,end,external=true)=>({proposalId:id,scopeKey:"scope",levelId:"ground",start,end,heightM:2.4,openings:[],assembly:defaultWallAssembly(external?"external-timber":"internal-timber")});
const boundary=[w("a",[0,0],[8,0]),w("b",[8,0],[8,6]),w("c",[8,6],[0,6]),w("d",[0,6],[0,0])];
const partition=w("p",[4,0],[4,6],false);
const ceiling={proposalId:"ceiling",scopeKey:"scope",levelId:"ground",start:[0,0],end:[4,6],heightM:2.4};
const settings={roof:"gable",pitchDeg:22.5,slabMm:100};
test("explicit exterior perimeter generates shell despite internal partitions and explicit ceilings",()=>{
 const walls=[...boundary,partition];
 const shell=localBuildingShell(walls,[ceiling],settings);
 assert.equal(shell.floorM2,48);
 assert.ok(Math.abs(shell.slabM3-4.8)<1e-9);
 assert.deepEqual(shell.surfaces.map(x=>x.kind),["floor","roof"]);
 assert.deepEqual(localBuildingShell(walls,[],settings).surfaces.map(x=>x.kind),["floor","ceiling","roof"]);
 const expanded=[w("a",[0,0],[10,0]),w("b",[10,0],[10,6]),w("c",[10,6],[0,6]),boundary[3],partition];
 assert.equal(localBuildingShell(expanded,[ceiling],settings).floorM2,60);
});
test("does not replace missing exterior walls with internal partitions or other levels",()=>{
 assert.equal(localBuildingShell([...boundary.slice(0,3),partition],[ceiling],settings),null);
 assert.equal(localBuildingShell([...boundary,{...partition,levelId:"upper"}],[],settings),null);
 assert.equal(localBuildingShell(boundary,[{...ceiling,scopeKey:"foreign"}],settings),null);
});
test("unclassified local ring retains existing closed-ring operation",()=>{
 const walls=boundary.map(x=>({...x,assembly:defaultWallAssembly("internal-timber")}));
 assert.equal(localBuildingShell(walls,[],settings).floorM2,48);
});
