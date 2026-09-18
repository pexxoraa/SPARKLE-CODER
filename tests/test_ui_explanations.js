// Exercise the actual rendering functions with a small DOM double. This tests
// behavior and visibility, not browser layout or native OS dialogs.
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const source = fs.readFileSync(path.join(__dirname, "../sparkle_coder/ui/app.js"), "utf8");
const functions = source.slice(source.indexOf("function renderRecovery("), source.indexOf("async function loadChanges("));
class Element {
  constructor(tag, className="", text="") {this.tag=tag;this.className=className;this.text=text;this.children=[];this.open=false;this.hidden=false;this.value="";}
  append(...items) {this.children.push(...items);}
  prepend(...items) {this.children.unshift(...items);}
  replaceChildren(...items) {this.children=items;}
}
const node = (...args) => new Element(...args);
const elements = new Map();
const id = name => {if(!elements.has(name))elements.set(name,node("div"));return elements.get(name);};
const descendants = element => [element, ...element.children.flatMap(descendants)];
const visibleText = element => element.hidden ? "" : element.text + " " + (element.tag==="details"&&!element.open ? element.children.filter(x=>x.tag==="summary") : element.children).map(visibleText).join(" ");
let working=false, submissions=0, settingsOpened=0;
id("taskForm").requestSubmit=()=>submissions++;
const ui = new Function("id","node","friendly","busy","openSettings","action","api","setTab","document",
  "let currentSession=null; const projectId='project';\n" + functions + "\nreturn {renderRecovery,renderDelivery,renderRepairHistory,checkCard,renderChecks,setSession:s=>currentSession=s};")(
  id,node,s=>s,()=>working,()=>settingsOpened++,fn=>fn(),async()=>({}),()=>{}, {body:{classList:{add(){}}}});

const recovery={title:"The vocabulary count does not match the test",what_happened:"The test expected 36 text symbols, but the program counted 54.",
  meaning:"The test or the code may be wrong; the count alone cannot tell us which.",next_step:"Choose Try fixing it.",
  technical_details:'Traceback: {"command":"python -c very long script"}',can_auto_fix:true,action:"checks"};
ui.renderRecovery({status:"needs_input",recovery});
const banner=id("resultBanner");
assert.match(visibleText(banner),/expected 36.*counted 54/);
assert.doesNotMatch(visibleText(banner),/Traceback|python -c|"command"/);
const details=descendants(banner).find(x=>x.tag==="details");
assert.equal(details.open,false);
details.open=true;
assert.match(visibleText(banner),/Traceback/);
const buttons=descendants(banner).filter(x=>x.tag==="button");
id("goal").value="Keep my existing requirements.";
buttons.find(x=>x.text==="Try fixing it").onclick();
assert.equal(id("taskMode").value,"build");
assert.match(id("goal").value,/Keep my existing requirements/);
assert.match(id("goal").value,/whether the code or the test is wrong/);
buttons.find(x=>x.text==="Explain this simply").onclick();
assert.equal(id("taskMode").value,"ask");
assert.equal(submissions,2);
working=true;
buttons.find(x=>x.text==="Try fixing it").onclick();
assert.equal(submissions,2);
working=false;
ui.renderRecovery({status:"needs_input",recovery:{...recovery,can_auto_fix:false,action:"connection"}});
const connectionButtons=descendants(banner).filter(x=>x.tag==="button");
assert(connectionButtons.some(x=>x.text==="Resume task"));
assert(!connectionButtons.some(x=>x.text==="Try fixing it"));
connectionButtons.find(x=>x.text==="Connection settings").onclick();
assert.equal(settingsOpened,1);

const failed={id:"failed",active:true,ok:false,label:"Text reader checks",command:"python -c long-script",output:"Traceback",explanation:recovery};
ui.setSession({checks:[failed,{...failed,active:false,superseded:true,correction_reason:"Corrected from source evidence"}]});
ui.renderChecks();
assert.match(visibleText(id("checksList")),/Text reader checks/);
assert.match(visibleText(id("checksList")),/Earlier checks and corrections/);
assert.doesNotMatch(visibleText(id("checksList")),/long-script|Traceback/);

ui.renderDelivery({delivery:{summary:"Text tool",how_to_use:["Open the project folder"],limitations:["Training has not been checked"]},
  proof:{total:2,passed:0,needs_recheck:1,note:"Recorded checks cover only the behavior they test.",features:[
    {feature:"Read text",status:"needs_recheck"},{feature:"Train",status:"not_checked"}]}});
const delivery=id("deliveryPanel");
assert.equal(delivery.hidden,false);
assert.match(visibleText(delivery),/0 of 2 current checks passed/);
assert.match(visibleText(delivery),/Needs another check/);
assert.match(visibleText(delivery),/Not checked yet/);
assert.match(visibleText(delivery),/Open the project folder/);
assert.doesNotMatch(visibleText(delivery),/Check passed/);
ui.renderDelivery(null);
assert.equal(delivery.hidden,true);

ui.renderDelivery({proof:{total:0,requirements_passed:0,requirements:[{text:"Keep data after restart",status:"not_checked"}]}});
assert.equal(delivery.hidden,false);
assert.match(visibleText(delivery),/Keep data after restart/);
assert.match(visibleText(delivery),/0 of 1 have passing evidence/);
assert.match(visibleText(delivery),/Not checked yet/);
ui.renderRepairHistory({repair_history:[{what_happened:"The result differs",next_step:"Inspect the source",files:["calculator.py"],missing_requirements:["Preserve data"]}]});
assert.equal(id("repairPanel").hidden,false);
assert.match(visibleText(id("repairPanel")),/1 reviews/);
id("repairPanel").children[0].open=true;
assert.match(visibleText(id("repairPanel")),/calculator.py/);
assert.match(visibleText(id("repairPanel")),/Preserve data/);
ui.renderRepairHistory(null);
assert.equal(id("repairPanel").hidden,true);

const setupSource=source.slice(source.indexOf("function renderSetupReport("),source.indexOf("async function refreshSetup("));
const renderSetupReport=new Function("id","node",setupSource+";return renderSetupReport;")(id,node);
renderSetupReport({attention:1,items:[{id:"tool:node",title:"Node.js",status:"attention",detail:"Not found on PATH",next_step:"Install Node.js and reopen"}],
  overview:{file_count:3,scan_truncated:false,languages:{JavaScript:2},manifests:["package.json"],entry_points:["index.html"]},checks:[{cwd:".",command:"npm run test"}]});
assert.match(id("setupSummary").textContent,/1 setup item/);
assert.match(visibleText(id("setupItems")),/Install Node.js/);
assert.match(id("setupMap").textContent,/Candidate checks \(not executed\)/);
renderSetupReport({attention:0,items:[],overview:{file_count:0,languages:{},manifests:[],entry_points:[]},checks:[]});
assert.match(id("setupSummary").textContent,/tests still need to run/);
console.log("Explanation UI: plain recovery, requirement evidence, repair history, and setup statuses passed.");
