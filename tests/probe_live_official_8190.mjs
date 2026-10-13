/** Real 8190 official-workflow persistence test, no RH cloud requests.
 * Uses WorkspaceKit's already-installed Playwright package; no installs.
 * Creates uniquely named RH-only fixtures, then moves them to test trash.
 * Never submits a ComfyUI /prompt; never touches 8188 user files.
 */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const existingPlaywright = createRequire(path.resolve(root, "..", "ComfyUI-WorkspaceKit", "package.json"));
const { chromium } = existingPlaywright("playwright");
const BASE = "http://127.0.0.1:8190/";
const names = [
  "__WK_TEST__/rh-official-new-" + Date.now() + ".json",
  "__WK_TEST__/rh-official-legacy-" + Date.now() + ".json",
];
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const page = await ctx.newPage();
const created = [];
const checks = [];
let passed = false;

async function api(url, payload) {
  return await page.evaluate(async ({ url, payload }) => {
    const response = await fetch(url, payload === undefined ? undefined : {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || data?.ok === false) {
      throw new Error("Local ComfyUI test endpoint failed: " + url + " status=" + response.status);
    }
    return data;
  }, { url, payload });
}

async function ready() {
  await page.waitForFunction(() => Boolean(
    window.app?.rootGraph &&
    window.app?.extensionManager?.workflow &&
    window.Workspace2CanvasGroups?.initialized &&
    window.LiteGraph?.registered_node_types?.RH_Execute &&
    window.LiteGraph?.registered_node_types?.RH_WorkflowInspect
  ), null, { timeout: 60000, polling: 250 });
}

async function openFixture(relative) {
  await page.evaluate(async () => window.app.extensionManager.workflow.syncWorkflows?.());
  const toggle = page.locator('[aria-label="WorkspaceKit"], .workspace2-tab-button').first();
  await toggle.waitFor({ state: "visible", timeout: 35000 });
  if (!(await toggle.evaluate(el => el.classList.contains("side-bar-button-selected")))) await toggle.click();
  await page.locator('[data-workspace2-module-id="workflows"]').click();
  const parent = page.locator('[data-workspace2-item-path="__WK_TEST__"]');
  if (await parent.count()) {
    const arrow = parent.locator(".workspace2-disclosure");
    if (await arrow.count() && !(await arrow.evaluate(x => x.classList.contains("is-open")))) await arrow.click();
  }
  const target = page.locator('[data-workspace2-item-path="' + relative + '"]');
  await target.waitFor({ state: "visible", timeout: 25000 });
  await target.click();
  await page.waitForFunction(
    rel => window.app?.extensionManager?.workflow?.activeWorkflow?.path === "workflows/" + rel,
    relative, { timeout: 35000, polling: 150 });
  await page.waitForFunction(() => window.LiteGraph?.registered_node_types?.RH_Execute &&
    window.app?.rootGraph?._nodes?.some(n => n.type === "RH_Execute"),
    null, { timeout: 20000 });
}

async function readState() {
  return await page.evaluate(() => {
    const graph = window.app.rootGraph;
    const execute = graph._nodes.find(n => n.type === "RH_Execute");
    const inspect = graph._nodes.find(n => n.type === "RH_WorkflowInspect");
    const download = graph._nodes.find(n => n.type === "RH_Download");
    const get = (node, name) => node?.widgets?.find(w => w.name === name)?.value;
    return {
      executePresent: Boolean(execute),
      inspectorPresent: Boolean(inspect),
      downloadPresent: Boolean(download),
      instance: get(execute, "instance_type"),
      frameMode: get(execute, "video_frame_mode"),
      timeout: get(execute, "timeout"),
      prefix: get(execute, "output_prefix"),
      downloadMode: get(download, "video_frame_mode"),
      schemaConnected: execute?.inputs?.find(i => i.name === "workflow_schema")?.link != null,
      errorNodes: graph._nodes.filter(n => n.type === "RH_MigrationRequired").length,
      active: window.app.extensionManager.workflow.activeWorkflow?.path,
    };
  });
}

try {
  await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 35000 });
  await ready();
  const baseline = await page.evaluate(() => {
    // Build a disconnected in-memory graph. No user workflow is replaced
    // by fixture construction; the official Open path loads the saved graph.
    const graph = new LiteGraph.LGraph();
    const create = (type, x) => {
      const n = LiteGraph.createNode(type);
      if (!n) throw new Error("RH node not registered: " + type);
      graph.add(n);
      n.pos = [x, 150];
      return n;
    };
    const run = create("RH_Execute", 120);
    const inspect = create("RH_WorkflowInspect", 560);
    const download = create("RH_Download", 1080);
    const widget = (node, name, value) => {
      const v = node.widgets?.find(w => w.name === name);
      if (!v) throw new Error("Missing widget " + name);
      v.value = value;
      v.callback?.call(v, value, window.app.canvas, node);
    };
    widget(run, "instance_type", "plus");
    widget(run, "video_frame_mode", "disabled");
    widget(run, "output_prefix", "RH_INTEGRATION");
    widget(download, "video_frame_mode", "preview_only");
    const slot = run.inputs.findIndex(i => i.name === "workflow_schema");
    if (slot < 0 || !inspect.connect(0, run, slot)) throw new Error("Could not connect inspector to Execute");
    const saved = structuredClone(graph.serialize());
    saved.extra ||= {};
    saved.extra.xzgGroups = {};
    return saved;
  });
  assert.equal(baseline.nodes.length, 3);
  await api("/workspace2/workflow/save", { path: names[0], workflow: baseline });
  created.push(names[0]);
  await openFixture(names[0]);

  let state = await readState();
  assert.deepEqual(
    [state.instance, state.frameMode, state.downloadMode, state.schemaConnected, state.errorNodes],
    ["plus", "disabled", "preview_only", true, 0],
    "New RH fixture must open with all widget values and links intact");
  checks.push("Official Open restores RH instance, frame policies and inspector link");

  await page.evaluate(async () => {
    const app = window.app;
    const run = app.rootGraph._nodes.find(n => n.type === "RH_Execute");
    const widget = run.widgets.find(w => w.name === "instance_type");
    widget.value = "ultra";
    widget.callback?.call(widget, "ultra", app.canvas, run);
    app.rootGraph.change?.();
    const tracker = app.extensionManager.workflow.activeWorkflow?.changeTracker;
    if (!tracker?.captureCanvasState) {
      throw new Error("Official ChangeTracker.captureCanvasState is unavailable");
    }
    await tracker.captureCanvasState();
  });
  await page.waitForFunction(
    () => Boolean(window.app.extensionManager.workflow.activeWorkflow?.isModified),
    null, { timeout: 15000 });
  const save = page.locator(".workspacekit-topbar-save-button");
  await save.waitFor({ state: "visible", timeout: 20000 });
  await save.click();
  await page.waitForFunction(
    () => !window.app.extensionManager.workflow.activeWorkflow?.isModified,
    null, { timeout: 20000 });
  const stored = await api("/workspace2/workflow/read?path=" + encodeURIComponent(names[0]));
  assert.ok(stored.workflow?.nodes?.some(n => n.type === "RH_Execute"), "Official Save lost RH node");
  checks.push("Official top-bar Save persisted modified RH Execute");

  await page.reload({ waitUntil: "domcontentloaded", timeout: 35000 });
  await ready();
  await openFixture(names[0]);
  state = await readState();
  assert.deepEqual(
    [state.instance, state.frameMode, state.downloadMode, state.schemaConnected, state.errorNodes],
    ["ultra", "disabled", "preview_only", true, 0],
    "F5 + official Open lost RH values or inspector connection");
  checks.push("F5 then official Open preserves RH saved values and links");

  // Build an old Boolean Execute fixture without changing the source
  // saved graph. This exercises beforeConfigureGraph on a real Open.
  const legacy = structuredClone(baseline);
  const old = legacy.nodes.find(n => n.type === "RH_Execute");
  old.widgets_values = [777, true, true, "LEGACY_RH"];
  delete old.widgets_values_named;
  delete old.widget_values;
  if (old.properties) delete old.properties.rh_instance_type_version;
  const oldInput = old.inputs?.find(x => x.name === "instance_type");
  if (oldInput) {
    oldInput.name = "use_high_performance";
    oldInput.type = "BOOLEAN";
    if (oldInput.widget) oldInput.widget.name = "use_high_performance";
  }
  await api("/workspace2/workflow/save", { path: names[1], workflow: legacy });
  created.push(names[1]);
  await openFixture(names[1]);
  state = await readState();
  assert.deepEqual(
    [state.instance, state.frameMode, state.timeout, state.prefix, state.schemaConnected, state.errorNodes],
    ["plus", "all_frames", 777, "LEGACY_RH", true, 0],
    "Official Open of old Boolean RH graph failed its value/link migration");
  checks.push("Official Open migrates legacy Boolean true to Plus, retaining timeout/prefix/link");

  passed = true;
  console.log(JSON.stringify({ result: "PASS", tests: checks, testPaths: names }, null, 2));
} catch (error) {
  console.error("RH 8190 official Save/Open/F5 test FAILED:", String(error));
  console.error("Fixtures retained for inspection:", JSON.stringify(created));
  process.exitCode = 1;
} finally {
  // The fixture endpoints are scoped to the isolated :8190 ComfyUI package.
  if (passed) {
    for (const name of created) {
      try {
        const res = await api("/workspace2/trash/move", { path: name });
        console.log("Moved isolated RH fixture to test trash:", name, Boolean(res?.ok));
      } catch (err) {
        console.warn("Could not move test fixture to test trash:", name, String(err));
      }
    }
  }
  await ctx.close();
  await browser.close();
}
