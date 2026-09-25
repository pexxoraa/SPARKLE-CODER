// Exercise the shipped admin script against the actual Worker + SQLite. The
// lightweight DOM is a rendering harness, not a live-browser verification.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {D1} from './helpers.mjs';
import worker from '../src/worker.mjs';

function dom(){
 const document={hidden:false,activeElement:null,addEventListener(){}};
 class Element {
  constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.value='';this.checked=false;this.hidden=false;this._text='';}
  set textContent(value){this._text=String(value);this.children=[];}
  get textContent(){return this._text+this.children.map(c=>c.textContent).join(' ');}
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this._text='';this.children=[...children];}
  querySelectorAll(selector){
   const match=n=>selector.split(',').some(part=>{
    const s=part.trim();if(s==='input[data-review]')return n.tagName==='input'&&Boolean(n.dataset.review);
    return s.startsWith('#')?n.id===s.slice(1):n.tagName===s;
   });
   return this.children.flatMap(n=>[...(match(n)?[n]:[]),...n.querySelectorAll(selector)]);
  }
  querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
  focus(){document.activeElement=this;}
 }
 const html=readFileSync(new URL('../public/admin.html',import.meta.url),'utf8');
 const elements=new Map([...html.matchAll(/<(\w+)[^>]*\bid="([^"]+)"/g)].map(m=>{
  const n=new Element(m[1]);n.id=m[2];return [m[2],n];
 }));
 document.getElementById=id=>{assert.ok(elements.has(id),'HTML is missing #'+id);return elements.get(id);};
 document.createElement=tag=>new Element(tag);
 const dashboard=elements.get('dashboard');
 for(const id of ['signupList','paymentList','deviceList','accountRows','requestList','auditList'])dashboard.append(elements.get(id));
 elements.get('loginForm').append(new Element('button'));
 return {document,elements};
}

async function fixture(t){
 const env={DB:new D1(),ADMIN_SECRET:'A'.repeat(64),CACHE_SECRET:'B'.repeat(64),UPI_ID:'owner@bank',PAYEE_NAME:'Owner'};
 t.after(()=>env.DB.db.close());
 let cookie='',overviews=0;
 const call=async(path,data,secret)=>{
  const response=await worker.fetch(new Request('https://sparkle.example'+path,{method:data===undefined?'GET':'POST',
   headers:{Origin:'https://sparkle.example',Cookie:cookie,'Content-Type':'application/json',...(secret?{Authorization:'Bearer '+secret}:{})},
   body:data===undefined?undefined:JSON.stringify(data)}),env);
  if(response.headers.has('Set-Cookie'))cookie=response.headers.get('Set-Cookie').split(';')[0];
  return response;
 };
 assert.equal((await call('/api/admin/login',{password:env.ADMIN_SECRET})).status,200);
 const ui=dom(),timers=[];
 const context=vm.createContext({...ui,document:ui.document,console,Date,
  setInterval:(callback,delay)=>{timers.push({callback,delay});return timers.length;},
  fetch:async(path,options)=>{if(path==='/api/admin/overview')overviews++;return call(path,options.body===undefined?undefined:JSON.parse(options.body));}
 });
 vm.runInContext(readFileSync(new URL('../public/admin.js',import.meta.url),'utf8'),context);
 await vm.runInContext('refresh()',context);
 const signup=async(email='new@example.test')=>{
  const secret=crypto.randomUUID().replaceAll('-','')+'X'.repeat(32);
  const response=await call('/api/enroll',{name:'New tester',email,phone:'12345678',consent:true},secret);
  assert.equal(response.status,201);return {secret,receipt:await response.json()};
 };
 return {...ui,context,env,call,signup,get overviews(){return overviews;},
  refresh:()=>vm.runInContext('refresh()',context),
  tick:async()=>{assert.equal(timers[0].delay,30000);await timers[0].callback();}};
}

test('admin discovers a new signup without payment or a manual reload',async t=>{
 const ui=await fixture(t),list=ui.elements.get('signupList');
 assert.match(list.textContent,/No new account requests/);
 const {receipt}=await ui.signup();await ui.tick();
 assert.match(list.textContent,/new@example.test/);assert.match(list.textContent,/New tester/);
 assert.ok(list.textContent.includes(receipt.request_id));assert.match(list.textContent,/Waiting for the tester/);
 assert.match(ui.elements.get('paymentList').textContent,/No payments waiting/);
 assert.match(ui.elements.get('auditList').textContent,/account-requested/);
 assert.equal(ui.env.DB.db.prepare('SELECT balance FROM accounts').get().balance,0);
 const before=ui.overviews;ui.document.hidden=true;await ui.tick();assert.equal(ui.overviews,before);
});

test('automatic refresh preserves review input; approval activates exactly one credit pack',async t=>{
 const ui=await fixture(t),{secret,receipt}=await ui.signup();
 const payment=await ui.call('/api/payments',{utr:'ADMINUI12345678'},secret);assert.equal(payment.status,201);
 const paymentId=(await payment.json()).id;await ui.tick();
 assert.ok(ui.elements.get('signupList').querySelector('a').href.endsWith(paymentId));
 let inputs=ui.elements.get('paymentList').querySelectorAll('input[data-review]');
 inputs.find(n=>n.type==='checkbox').checked=true;
 inputs.find(n=>n.type==='text').value='Matched bank reference';
 inputs.find(n=>n.type==='text').focus();
 await ui.signup('second@example.test');await ui.tick();
 inputs=ui.elements.get('paymentList').querySelectorAll('input[data-review]');
 assert.equal(inputs.find(n=>n.type==='checkbox').checked,true);
 assert.equal(inputs.find(n=>n.type==='text').value,'Matched bank reference');
 assert.equal(ui.document.activeElement,inputs.find(n=>n.type==='text'));
 const accept=ui.elements.get('paymentList').querySelectorAll('button').find(n=>n.textContent==='Accept + 1M tokens');
 await accept.onclick();
 const account=await (await ui.call('/api/me',undefined,secret)).json();
 assert.equal(account.ready,true);assert.equal(account.available_tokens,1000000);
 assert.ok(!ui.elements.get('signupList').textContent.includes(receipt.request_id));
 assert.match(ui.elements.get('signupList').textContent,/second@example.test/);
 await accept.onclick();
 assert.equal(ui.env.DB.db.prepare('SELECT COUNT(*) AS n FROM ledger').get().n,1);
});

test('refresh errors retain the displayed requests and clearly mark them stale',async t=>{
 const ui=await fixture(t),{receipt}=await ui.signup();await ui.tick();
 ui.context.fetch=async()=>Response.json({error:'Server temporarily unavailable'},{status:503});
 await ui.tick();
 assert.ok(ui.elements.get('signupList').textContent.includes(receipt.request_id));
 assert.match(ui.elements.get('syncStatus').textContent,/out of date.*Server temporarily unavailable/);
});

test('an overview arriving after logout cannot reopen the dashboard',async t=>{
 const ui=await fixture(t);await ui.signup();await ui.tick();
 const original=ui.context.fetch;let release,started;
 const entered=new Promise(resolve=>{started=resolve;});
 ui.context.fetch=async(path,options)=>{
  const response=await original(path,options);
  if(path==='/api/admin/overview'){started();await new Promise(resolve=>{release=resolve;});}
  return response;
 };
 const pending=ui.refresh();await entered;
 await ui.elements.get('logout').onclick();release();await pending;
 assert.equal(ui.elements.get('dashboard').hidden,true);assert.equal(ui.elements.get('login').hidden,false);
 assert.equal(ui.elements.get('signupList').children.length,0);
 const before=ui.overviews;await ui.tick();assert.equal(ui.overviews,before);
});
