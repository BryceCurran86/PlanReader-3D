// CC0 presentation assets. Fetch only during the build; verify provider size and checksum.
import {mkdir,readFile,writeFile,rename} from "node:fs/promises";
import {createHash} from "node:crypto";
import {fileURLToPath} from "node:url";
import {join} from "node:path";
const dir=fileURLToPath(new URL("../public/architectural-assets/",import.meta.url));
const plan=[
 ["wood_floor","Diffuse","1k","jpg","wood-colour.jpg"],
 ["wood_floor","nor_gl","1k","jpg","wood-normal.jpg"],
 ["wood_floor","Rough","1k","jpg","wood-rough.jpg"],
 ["white_plaster_02","nor_gl","1k","jpg","plaster-normal.jpg"],
 ["white_plaster_02","Rough","1k","jpg","plaster-rough.jpg"],
 ["leafy_grass","Diffuse","1k","jpg","grass-colour.jpg"],
 ["suburban_field_02","hdri","2k","hdr","outdoor.hdr"]
];
const hash=(algorithm,bytes)=>createHash(algorithm).update(bytes).digest("hex");
const get=(obj,key)=>Object.entries(obj??{}).find(([k])=>k.toLowerCase()===key.toLowerCase())?.[1];
const max=12*1024*1024;
async function request(url){
 const response=await fetch(url,{headers:{"User-Agent":"PlanReader-VR-AssetBuild/1.0"},signal:AbortSignal.timeout(90000)});
 if(!response.ok)throw Error("Asset request failed: "+response.status+" "+url);
 return response;
}
async function valid(entry,file){
 try{const bytes=await readFile(file);return entry&&bytes.length===entry.size&&hash("sha256",bytes)===entry.sha256;}catch{return false;}
}
await mkdir(dir,{recursive:true});
let previous={};
try{previous=JSON.parse(await readFile(join(dir,"manifest.json"),"utf8")).files??{};}catch{}
const files={},metadata=new Map();
for(const [id,map,res,format,name] of plan){
 const target=join(dir,name),old=previous[name];
 if(old?.id===id&&old?.map===map&&old?.resolution===res&&old?.format===format&&await valid(old,target)){files[name]=old;continue;}
 if(!metadata.has(id))metadata.set(id,await (await request("https://api.polyhaven.com/files/"+id)).json());
 const info=get(get(get(metadata.get(id),map),res),format);
 if(!info||!Number.isInteger(info.size)||info.size<=0||info.size>max||!(/^[a-f0-9]{32}$/i.test(info.md5)))throw Error("Missing or oversized asset metadata: "+id+" "+map);
 const url=new URL(info.url);
 if(url.protocol!=="https:"||url.hostname!=="dl.polyhaven.org")throw Error("Unexpected asset origin: "+url.hostname);
 const response=await request(url);
 const bytes=Buffer.from(await response.arrayBuffer());
 if(bytes.length!==info.size||hash("md5",bytes)!==info.md5.toLowerCase())throw Error("Asset checksum mismatch: "+name);
 if(format==="jpg"&&(bytes[0]!==255||bytes[1]!==216)||format==="hdr"&&!bytes.subarray(0,32).toString("ascii").includes("#?"))throw Error("Unexpected asset format: "+name);
 await writeFile(target+".tmp",bytes);await rename(target+".tmp",target);
 files[name]={id,map,resolution:res,format,url:String(url),size:bytes.length,md5:info.md5,sha256:hash("sha256",bytes),license:"CC0-1.0",source:"https://polyhaven.com/a/"+id};
 console.log("Prepared",name,bytes.length);
}
await writeFile(join(dir,"manifest.json"),JSON.stringify({schema:1,files},null,2)+"\n");
console.log("Architectural assets verified:",Object.keys(files).length,"files",Object.values(files).reduce((n,x)=>n+x.size,0),"bytes");
