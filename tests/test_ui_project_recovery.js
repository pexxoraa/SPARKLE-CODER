// Run the actual recovery UI functions with a DOM double and simulated HTTP.
// Native folder picking and visual browser layout are not covered here.
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const source = fs.readFileSync(path.join(__dirname, "../sparkle_coder/ui/app.js"), "utf8");
const sections = [
  source.slice(source.indexOf("function renderProjects("), source.indexOf("function renderProvider(")),
  source.slice(source.indexOf("async function selectProject("), source.indexOf("async function refreshState(")),
  source.slice(source.indexOf("function renderMigrationProjects("), source.indexOf("function updateReconnectSelection(")),
  source.slice(source.indexOf("function updateReconnectSelection("), source.indexOf('id("trackTask").onclick=')),
].join("\n");
class Element {
  constructor(tag, className="", text="") {Object.assign(this,{tag,className,text,children:[],hidden:false,value:"",open:false});}
  append(...children) {this.children.push(...children);}
  replaceChildren(...children) {this.children=children;}
  showModal() {this.open=true;}
  close() {this.open=false;}
}
const node = (...args) => new Element(...args);
const elements = new Map();
const id = name => {if(!elements.has(name))elements.set(name,node("div"));return elements.get(name);};

async function check() {
  let working=false, error="Folder not found. Choose an existing folder.", loads=0, retryReady=false;
  const requests=[], toasts=[];
  const state={projects:[{id:"ready",name:"New project",path:"/app/PROJECTS/new",available:true},
    {id:"missing",name:"Old project",path:"/old/Projects/my-project",available:false}],selected_project:"ready"};
  const api=async(route,body)=>{
    requests.push({route,body});
    if(route==="/projects/missing/reconnect") {
      if(error)throw new Error(error);
      state.projects[1]={...state.projects[1],path:body.path,available:true};
      return state.projects[1];
    }
    if(route==="/state")return state;
    if(route==="/retry-project-migration") {
      if(retryReady){state.projects[1].migration_pending=undefined;state.projects[1].available=true;state.projects[1].path="/app/PROJECTS/recovered";}
      return {copied:retryReady?1:0,pending:retryReady?0:1,message:retryReady?"Project copied. Original kept.":"Finish the previous task and retry."};
    }
    if(route==="/select-project")return {selected_project:body.project_id};
    throw new Error("Unexpected request: "+route);
  };
  const ui=new Function("id","node","api","busy","toast","loadFiles","loadHistory","newTask","initial",
    'let appState=initial,projectId="ready",transferBusy=false,selectedFile="",fileData=null;\n'+sections+
    '\nasync function refreshState(){appState=await api("/state");renderProjects();}\n'+
    'return {renderProjects,openReconnect,reconnectProject,selectProject,retryProjectMigration,selected:()=>projectId};')(
      id,node,api,()=>working,message=>toasts.push(message),async()=>loads++,async()=>loads++,async()=>{},state);
  ui.renderProjects();
  assert.equal(id("missingProjectsNotice").hidden,false);
  assert.match(id("missingProjectsText").textContent,/keep working/);
  assert.match(id("projectSelect").children[1].text,/folder not found/);
  await ui.selectProject("missing");
  assert.equal(requests.length,0);
  assert.equal(ui.selected(),"ready");
  assert.equal(id("reconnectDialog").open,true);
  assert.equal(id("missingProjectPath").textContent,"/old/Projects/my-project");
  assert.equal(id("reconnectPath").value,"/old/Projects/my-project");
  await ui.reconnectProject();
  assert.match(id("reconnectResult").textContent,/Choose an existing folder/);
  assert.equal(id("reconnectDialog").open,true);
  assert.equal(id("saveReconnect").disabled,false);
  assert.equal(ui.selected(),"ready");
  assert.equal(loads,0);
  working=true;
  const count=requests.length;
  await ui.reconnectProject();
  assert.equal(requests.length,count);
  working=false;error="";id("reconnectPath").value="/found/project";
  await ui.reconnectProject();
  assert.equal(ui.selected(),"missing");
  assert.equal(id("reconnectDialog").open,false);
  assert.equal(id("missingProjectsNotice").hidden,true);
  assert.equal(id("projectPath").textContent,"/found/project");
  assert.equal(loads,2);
  assert.equal(toasts.length,1);
  assert.match(toasts[0],/Project reconnected/);
  assert(requests.some(r=>r.route==="/projects/missing/reconnect"&&r.body.path==="/found/project"));
  await ui.selectProject("ready");
  state.projects[1].available=false;state.projects[1].migration_pending="This project is locked by a running app.";
  ui.renderProjects();
  assert.equal(id("missingProjectsNotice").hidden,true);
  assert.equal(id("pendingMigrationNotice").hidden,false);
  assert.match(id("projectSelect").children[1].text,/waiting to move/);
  await ui.selectProject("missing");
  assert.equal(ui.selected(),"ready");
  assert.equal(id("migrationDialog").open,true);
  assert.equal(id("pendingMigrationProjects").children.length,1);
  assert.match(id("pendingMigrationProjects").children[0].children[1].text,/locked by a running app/);
  working=true;
  const beforeRetry=requests.length;
  await ui.retryProjectMigration();
  assert.equal(requests.length,beforeRetry);
  working=false;
  await ui.retryProjectMigration();
  assert.match(id("migrationResult").textContent,/Finish the previous task/);
  assert.equal(id("retryProjectMigration").disabled,false);
  retryReady=true;
  await ui.retryProjectMigration();
  assert.equal(id("pendingMigrationNotice").hidden,true);
  assert.equal(id("pendingMigrationProjects").children.length,0);
  assert.equal(id("retryProjectMigration").disabled,true);
  assert.match(id("migrationResult").textContent,/project menu/);
  await ui.selectProject("missing");
  assert.equal(ui.selected(),"missing");
  console.log("Project recovery UI: missing folders, pending moves, guarded retries, inline errors, and recovered selections passed.");
}
check().catch(error=>{console.error(error);process.exitCode=1;});
