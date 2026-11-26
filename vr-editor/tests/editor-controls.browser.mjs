import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { resolve, sep } from "node:path";
import { chromium } from "playwright";

const dist = resolve("dist");
const mime = { html: "text/html", js: "text/javascript", css: "text/css", json: "application/json", jpg: "image/jpeg", hdr: "application/octet-stream" };
const server = createServer(async (request, response) => {
  try {
    const path = new URL(request.url, "http://localhost").pathname;
    const file = resolve(dist, "." + (path === "/" ? "/index.html" : path));
    if (!file.startsWith(dist + sep)) throw new Error("Outside build");
    const content = await readFile(file);
    response.writeHead(200, { "Content-Type": mime[file.split(".").at(-1)] ?? "application/octet-stream" });
    response.end(content);
  } catch {
    response.writeHead(404).end();
  }
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));

let browser;
try {
  browser = await chromium.launch({
    channel: "chrome", headless: true,
    args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  page.setDefaultTimeout(12000);
  const errors = [],assetErrors=[],externalRequests=[];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message=>{if(message.type()==="error"&&/Local architectural HDR unavailable|Missing local photographic asset|Local photographic map unavailable/.test(message.text()))assetErrors.push(message.text());});
  page.on("request", request=>{if(/^https?:/.test(request.url())&&!request.url().startsWith("http://127.0.0.1:"))externalRequests.push(request.url());});
  await page.goto("http://127.0.0.1:" + server.address().port);
  const canvas = page.locator(".viewport canvas");
  await page.locator(".header-state").getByText("Editable starter house", {exact:true}).waitFor();
  await canvas.waitFor();
  await page.waitForFunction(()=>document.querySelector(".viewport canvas")?.dataset.architecturalEnvironment==="loaded",{},{timeout:30000});
  const photoFiles=await page.evaluate(async()=>{
    const manifest=await (await fetch("/architectural-assets/manifest.json")).json();
    const files=Object.entries(manifest.files);const decoded=[];
    for(const [name,info] of files){if(name.endsWith(".jpg")){const image=new Image();image.src="/architectural-assets/"+name;await image.decode();decoded.push({name,width:image.naturalWidth,height:image.naturalHeight});}}
    return {count:files.length,decoded};
  });
  assert.equal(photoFiles.count,7);assert.equal(photoFiles.decoded.length,6);
  // Verify the real renderer's material loader consumed the photos, not merely that URLs decode.
  await page.waitForFunction(()=>["wood-colour","wood-normal","wood-rough","plaster-normal","plaster-rough","grass-colour"].every(name=>document.documentElement.getAttribute("data-photo-"+name)==="loaded"),undefined,{timeout:30000});
  assert.ok(photoFiles.decoded.every(f=>f.width>=512&&f.height>=512),"Photographic maps must decode at useful resolution");
  await page.locator(".build-tools").getByText("Draft walls (7)",{exact:true}).waitFor();
  const selection=page.locator("#selected-draft-object");
  assert.equal(await selection.locator("option").count(),12,"Seven editable walls and four editable ceilings");
  await selection.selectOption("living-ceiling");
  await page.getByLabel("Selected ceiling height (mm)",{exact:true}).fill("2600");
  await page.getByLabel("Selected ceiling height (mm)",{exact:true}).press("Tab");
  await selection.selectOption("");
  await selection.selectOption("living-ceiling");
  assert.equal(await page.getByLabel("Selected ceiling height (mm)",{exact:true}).inputValue(),"2600","Ceiling height must persist when reselected");
  await canvas.evaluate(element=>{window.starterCanvas=element;});
  await page.getByRole("button", { name: "Open example", exact: true }).click();
  await page.locator(".header-state").getByText("Example plan",{exact:true}).waitFor();
  await page.waitForFunction(()=>!window.starterCanvas.isConnected);
  await canvas.waitFor();
  const layoutClear = () => page.evaluate(() => {
    const canvas = document.querySelector(".viewport canvas");
    const bar = document.querySelector(".build-tools");
    return canvas.offsetHeight >= 315 &&
      bar.getBoundingClientRect().bottom <= canvas.getBoundingClientRect().top + 1;
  });
  assert.equal(await layoutClear(), true, "The editing toolbar must leave the canvas clear");
  await canvas.evaluate(element => { window.testCanvas = element; });

  const view = page.locator(".view-toolbar");
  const tools = page.locator(".build-tools");
  const button = (area, name) => area.getByRole("button", { name, exact: true });
  await button(view, "Top 3D").click();
  await button(tools, "Wall").click();
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  await canvas.scrollIntoViewIfNeeded();
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const box = await canvas.boundingBox();
  for (const part of [0.40, 0.56]) await page.mouse.click(box.x + box.width * part, box.y + box.height / 2);
  const walls = tools.getByText("Draft walls (1)", { exact: true });
  await walls.waitFor();
  await page.keyboard.press("Control+z");
  await walls.waitFor({ state: "hidden" });
  await page.keyboard.press("Control+Shift+z");
  await walls.waitFor();
  await button(tools,"Done").click();
  await page.getByLabel("Pick",{exact:true}).selectOption("walls");
  const wallId=await selection.locator("option").nth(1).getAttribute("value");
  await selection.selectOption(wallId);
  const position=page.getByLabel("Selected draft position",{exact:true});
  const originalPosition=await position.textContent();
  await canvas.scrollIntoViewIfNeeded();
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  const directBox=await canvas.boundingBox();
  await page.mouse.move(directBox.x+directBox.width*.48,directBox.y+directBox.height*.5);
  await page.mouse.down();
  await page.mouse.move(directBox.x+directBox.width*.48,directBox.y+directBox.height*.5+35,{steps:8});
  await page.mouse.up();
  await page.waitForFunction(({id,before})=>document.querySelector("#selected-draft-object")?.value===id&&document.querySelector('output[aria-label="Selected draft position"]')?.textContent!==before,{id:wallId,before:originalPosition});
  const movedPosition=await position.textContent();
  assert.notEqual(movedPosition,originalPosition,"Direct drag changes geometry, not just selection or camera");
  await canvas.focus();
  await page.keyboard.press("Control+z");
  await page.waitForFunction(before=>document.querySelector('output[aria-label="Selected draft position"]')?.textContent===before,originalPosition);
  await walls.waitFor();
  await page.keyboard.press("Control+Shift+z");
  await page.waitForFunction(after=>document.querySelector('output[aria-label="Selected draft position"]')?.textContent===after,movedPosition);
  await walls.waitFor();

  await button(tools, "Items").click();
  const catalogue = page.locator("#item-catalogue");
  await catalogue.getByRole("searchbox").fill("sliding door");
  const results = catalogue.locator(".catalogue-results button");
  await results.filter({ hasText: /sliding door/i }).first().click();
  await page.locator(".catalogue-instructions").waitFor();
  assert.equal(await tools.locator(".build-tool[aria-pressed=true]").count(), 0);
  await page.keyboard.press("Escape");
  await page.locator(".catalogue-instructions").waitFor({ state: "hidden" });

  await button(page.locator(".inspector-nav"), "Review").click();
  const review = page.locator("#panel-review");
  await review.locator("#review-status").selectOption("verified");
  await review.getByText("No objects match the current filters.").waitFor();
  assert.equal(await canvas.evaluate(element => window.testCanvas === element && element.isConnected), true,
    "Source filters must preserve the existing canvas");
  await button(review, "Clear filters").click();

  await button(view, "Resize footprint").click();
  const footprint = page.locator(".footprint-tools");
  const width = footprint.locator("input[name=width]");
  await width.fill(String(Number(await width.inputValue()) + 1000));
  await button(footprint, "Resize").click();
  const notice = page.locator(".draft-notice");
  await notice.waitFor();
  await page.keyboard.press("Control+z");
  await notice.waitFor({ state: "hidden" });
  await page.keyboard.press("Control+Shift+z");
  await notice.waitFor();
  await button(footprint, "Done").click();
  await button(notice, "Return to source size").click();

  const stage=view.locator(".stage-select select");
  const board=view.getByLabel("Preview board");
  for(const value of ["framing","rough-in","lock-up","insulation","sheeted","set","sanded","undercoat","finished"]){
    await stage.selectOption(value);
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    assert.equal(await canvas.evaluate(element=>window.testCanvas===element&&element.isConnected),true,"Construction stages must preserve the existing 3D renderer");
  }
  await stage.selectOption("set");
  for(const value of ["wet-area","fire-rated","standard"]){
    await board.selectOption(value);
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    assert.equal(await board.inputValue(),value);
  }
  await stage.selectOption("finished");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForFunction(() => innerWidth === 390 && document.documentElement.scrollWidth <= 391);
  assert.equal(await layoutClear(), true, "The toolbar obscures the narrow-view canvas");
  await page.setViewportSize({width:1280,height:900});
  await button(view,"Architectural plan (2D)").click();
  const plan=page.getByRole("region",{name:"Architectural plan preview"});
  await plan.waitFor();
  const image=plan.locator("canvas");
  await image.waitFor();
  await page.waitForFunction(()=>{
    const canvas=document.querySelector('canvas[aria-label="2D architectural plan drawing"]');
    return canvas?.getContext("2d")?.getImageData(0,0,1,1).data[3]===255;
  });
  await button(view,"Return to 3D").click();
  await plan.waitFor({state:"hidden"});
  await canvas.waitFor();
  assert.deepEqual(errors, [], "Browser runtime exceptions");
  assert.deepEqual(assetErrors, [], "Photographic assets must load without decoder errors");
  assert.deepEqual(externalRequests, [], "Runtime must not contact an external asset provider");
  console.log("Browser checks passed: plan opening, tool switching, drawing, undo/redo, filtering, footprint resize, construction stage/board switching, architectural plan and narrow layout.");
} finally {
  await browser?.close();
  server.closeAllConnections();
  server.close();
}
