"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const source=fs.readFileSync(path.join(__dirname,"../sparkle_coder/ui/app.js"),"utf8");
const addressSource=source.slice(source.indexOf("function engineAddress("),source.indexOf("const isHosted="));
const engineAddress=new Function(addressSource+";return engineAddress;")();
assert.equal(engineAddress("http://127.0.0.1:43123/"),"http://127.0.0.1:43123");
for(const value of ["https://attacker.example","http://192.168.1.2:1234","http://localhost.attacker.example:1234",
  "http://user:password@127.0.0.1:1234","http://127.0.0.1:1234/api","http://localhost:1234/?token=oops"])
  assert.throws(()=>engineAddress(value));
const cloudSource=source.slice(source.indexOf("function cloudAccessUrl("),source.indexOf("const icons"));
const cloudAccessUrl=new Function(cloudSource+";return cloudAccessUrl;")();
assert.equal(cloudAccessUrl("https://changed-gateway.example/v1"),"https://changed-gateway.example/request");

async function check(){
  const calls=[];
  const fetch=async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>({connected:true}),blob:async()=>"file bytes"};};
  const helpers=source.slice(source.indexOf("async function engineRequest("),source.indexOf("function toast("));
  const {api,engineRequest}=new Function("fetch","accessToken","engineOrigin","isHosted",helpers+";return {api,engineRequest};")(
    fetch,"paired-test-token","http://127.0.0.1:43123",true);
  assert.equal((await api("/state")).connected,true);
  await api("/projects",{name:"New project"});
  assert.equal(await (await engineRequest("/projects/example/download?path=file.txt")).blob(),"file bytes");
  for(const call of calls){
    assert.ok(call.url.startsWith("http://127.0.0.1:43123/api/"));
    assert.equal(call.options.headers["X-Sparkle-Token"],"paired-test-token");
    assert.equal(call.options.credentials,"omit");assert.equal(call.options.redirect,"error");
  }
  const noEngine=new Function("fetch","accessToken","engineOrigin","isHosted",helpers+";return api;")(fetch,"secret","",true);
  await assert.rejects(noEngine("/state"),/Connect website/);
  assert.equal(calls.length,3,"An unpaired website must not make an API request");
  console.log("Hosted UI: loopback-only routing, authenticated downloads, gateway links and unpaired state passed.");
}
check().catch(error=>{console.error(error);process.exitCode=1;});
