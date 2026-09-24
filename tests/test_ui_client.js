// Exercise the actual browser API helper without a browser or third-party packages.
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const source = fs.readFileSync(path.join(__dirname, "../sparkle_coder/ui/app.js"), "utf8");
const helper = source.slice(source.indexOf("async function engineRequest("), source.indexOf("function toast("));

async function check() {
  let response = {ok: true, data: {id: "saved-run", status: "needs_input", error: "Model disconnected"}};
  const requests = [];
  const fetch = async (url, options) => {
    requests.push({url, options});
    return {ok: response.ok, json: async () => response.data};
  };
  const api = new Function("fetch", "accessToken", "engineOrigin", "isHosted", helper + "\nreturn api;")(fetch, "test-launch-token", "", false);
  assert.equal((await api("/runs/saved-run?after=1")).status, "needs_input");
  assert.equal((await api("/runs", {goal: "Build"})).error, "Model disconnected");
  assert.equal(requests[0].options.headers["X-Sparkle-Token"], "test-launch-token");
  assert.equal(requests[1].options.method, "POST");
  response = {ok: false, data: {error: "Reopen the launcher"}};
  await assert.rejects(api("/runs/saved-run"), /Reopen the launcher/);
  response = {ok: true, data: {error: "Folder chooser unavailable"}};
  await assert.rejects(api("/select-folder", {}), /Folder chooser unavailable/);
  console.log("Browser API helper: saved run errors remain resumable; transport and action errors still surface.");
}
check().catch(error => {console.error(error); process.exitCode = 1;});
