import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { readFile, mkdtemp, rm } from "node:fs/promises";
import { resolve, sep } from "node:path";
import { tmpdir } from "node:os";
import { setTimeout as sleep } from "node:timers/promises";

const dist = resolve("dist");
const mime = { html: "text/html", js: "text/javascript", css: "text/css", json: "application/json" };
const server = createServer(async (request, response) => {
  try {
    const path = new URL(request.url, "http://localhost").pathname;
    const file = resolve(dist, "." + (path === "/" ? "/index.html" : path));
    if (!file.startsWith(dist + sep)) throw new Error("Outside build");
    response.writeHead(200, { "Content-Type": mime[file.split(".").at(-1)] ?? "application/octet-stream" });
    response.end(await readFile(file));
  } catch {
    if (!response.headersSent) response.writeHead(404);
    response.end();
  }
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));

const profile = await mkdtemp(resolve(tmpdir(), "planreader-test-"));
const chrome = spawn(process.env.CHROME_PATH || "google-chrome", [
  "--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-background-networking",
  "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--remote-debugging-pipe",
  "--window-size=1280,900", "--user-data-dir=" + profile,
], { stdio: ["ignore", "ignore", "ignore", "pipe", "pipe"] });
const responses = new Map();
const exceptions = [];
let failure;
let nextId = 0;
let buffer = "";
chrome.stdio[4].setEncoding("utf8");
chrome.stdio[4].on("data", fragment => {
  buffer += fragment;
  let end;
  while ((end = buffer.indexOf("\0")) !== -1) {
    const event = JSON.parse(buffer.slice(0, end));
    buffer = buffer.slice(end + 1);
    if (event.method === "Runtime.exceptionThrown") exceptions.push(event.params.exceptionDetails.text);
    const pending = responses.get(event.id);
    if (!pending) continue;
    responses.delete(event.id);
    clearTimeout(pending.timer);
    if (event.error) pending.reject(new Error(event.error.message));
    else pending.resolve(event.result);
  }
});
function stop(error) {
  failure = error;
  for (const pending of responses.values()) {
    clearTimeout(pending.timer);
    pending.reject(error);
  }
  responses.clear();
}
chrome.on("error", stop);
chrome.on("exit", code => stop(new Error("Chrome exited with code " + code)));
chrome.stdio[3].on("error", stop);
let sessionId;
function send(method, params = {}, browser = false) {
  if (failure) return Promise.reject(failure);
  const id = ++nextId;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      responses.delete(id);
      reject(new Error("Timed out calling " + method));
    }, 12000);
    responses.set(id, { resolve, reject, timer });
    chrome.stdio[3].write(JSON.stringify({ id, method, params, ...(browser ? {} : { sessionId }) }) + "\0");
  });
}
async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description ?? result.exceptionDetails.text);
  return result.result.value;
}
async function waitFor(test, message) {
  for (let i = 0; i < 100; i++) {
    if (await evaluate("Boolean(" + test + ")")) return;
    await sleep(100);
  }
  throw new Error(message);
}
function click(text, container = "body") {
  return evaluate(`(() => {
    const button = [...document.querySelectorAll(${JSON.stringify(container)} + ' button')]
      .find(button => button.textContent.trim() === ${JSON.stringify(text)} && button.offsetWidth);
    if (!button || button.disabled) throw Error('Unavailable button ' + ${JSON.stringify(text)});
    button.click();
  })()`);
}
function input(selector, value) {
  return evaluate(`(() => {
    const field = document.querySelector(${JSON.stringify(selector)});
    const prop = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(field), 'value');
    prop.set.call(field, ${JSON.stringify(value)});
    field.dispatchEvent(new Event(field.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
  })()`);
}
function key(key, options = {}) {
  return evaluate(`document.querySelector('.scene-canvas canvas').dispatchEvent(new KeyboardEvent('keydown', {
    key: ${JSON.stringify(key)}, bubbles: true, ...${JSON.stringify(options)}
  }))`);
}

try {
  const { targetId } = await send("Target.createTarget", { url: "about:blank" }, true);
  ({ sessionId } = await send("Target.attachToTarget", { targetId, flatten: true }, true));
  await send("Runtime.enable");
  await send("Page.navigate", { url: "http://127.0.0.1:" + server.address().port });
  await waitFor("document.querySelector('.demo-button')", "Example plan entry point is missing");
  await click("Open example");
  await waitFor("document.querySelector('.viewport canvas')", "The example did not start a WebGL canvas");
  assert.equal(await evaluate(`(window.testCanvas = document.querySelector('.viewport canvas')).offsetHeight >= 315 &&
    document.querySelector('.build-tools').getBoundingClientRect().bottom <= testCanvas.getBoundingClientRect().top + 1`), true,
  "The editing toolbar must leave the canvas clear");

  await click("Plan", ".view-toolbar");
  await click("Wall", ".build-tools");
  await evaluate("new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))))");
  const points = await evaluate(`(() => { const box = testCanvas.getBoundingClientRect();
    return [0.40, 0.56].map(part => ({ x: Math.round(box.left + box.width * part), y: Math.round(box.top + box.height * 0.50) }));
  })()`);
  for (const point of points) {
    await send("Input.dispatchMouseEvent", { type: "mouseMoved", ...point });
    await send("Input.dispatchMouseEvent", { type: "mousePressed", ...point, button: "left", clickCount: 1 });
    await send("Input.dispatchMouseEvent", { type: "mouseReleased", ...point, button: "left", clickCount: 1 });
    await sleep(110);
  }
  await waitFor("document.querySelector('.build-options').textContent.includes('Draft walls (1)')", "Wall was not added through the canvas");
  await key("z", { ctrlKey: true });
  await waitFor("!document.querySelector('.build-options').textContent.includes('Draft walls (1)')", "Undo did not remove the wall");
  await key("z", { ctrlKey: true, shiftKey: true });
  await waitFor("document.querySelector('.build-options').textContent.includes('Draft walls (1)')", "Redo did not restore the wall");

  await click("Items", ".build-tools");
  await input("#item-catalogue input[type=search]", "sliding door");
  await waitFor("document.querySelector('#item-catalogue .catalogue-results').textContent.toLowerCase().includes('sliding door')",
    "The catalogue did not show the search results");
  await evaluate("document.querySelector('#item-catalogue .catalogue-results button').click()");
  await waitFor("document.querySelector('.catalogue-instructions') && !document.querySelector('.build-tool[aria-pressed=true]')",
    "Arming an item left the wall tool active");
  await key("Escape");
  await waitFor("!document.querySelector('.catalogue-instructions')", "Escape did not finish item placement");

  await click("Review", ".inspector-nav");
  await input("#review-status", "verified");
  await waitFor("document.querySelector('#panel-review').textContent.includes('No objects match')", "The source filter did not apply");
  assert.equal(await evaluate("testCanvas === document.querySelector('.viewport canvas') && testCanvas.isConnected"), true,
    "Source filters must preserve the existing canvas");
  await click("Clear filters", "#panel-review");

  await click("Resize footprint", ".view-toolbar");
  const width = await evaluate("Number(document.querySelector('.footprint-tools input[name=width]').value)");
  await input(".footprint-tools input[name=width]", width + 1000);
  await click("Resize", ".footprint-tools");
  await waitFor("document.querySelector('.draft-notice')", "The resized footprint was not displayed");
  await key("z", { ctrlKey: true });
  await waitFor("!document.querySelector('.draft-notice')", "Undo did not restore the source-sized footprint");
  await key("z", { ctrlKey: true, shiftKey: true });
  await waitFor("document.querySelector('.draft-notice')", "Redo did not restore the footprint draft");
  await click("Done", ".footprint-tools");
  await click("Return to source size", ".draft-notice");

  await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: false });
  await waitFor("innerWidth === 390 && document.documentElement.scrollWidth <= 391", "The layout overflows a narrow browser");
  assert.equal(await evaluate(`document.querySelector('.build-tools').getBoundingClientRect().bottom <=
    testCanvas.getBoundingClientRect().top + 1`), true, "The toolbar obscures the narrow-view canvas");
  assert.deepEqual(exceptions, [], "Browser runtime exceptions");
  console.log("Browser checks passed: plan opening, tool switching, drawing, undo/redo, filtering, footprint resize and narrow layout.");
} finally {
  chrome.kill();
  server.closeAllConnections();
  server.close();
  await rm(profile, { recursive: true, force: true, maxRetries: 3, retryDelay: 120 }).catch(() => undefined);
}
