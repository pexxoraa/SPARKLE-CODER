import {test} from 'node:test';
import assert from 'node:assert/strict';
import {D1} from './helpers.mjs';
import worker, {cleanup} from '../src/worker.mjs';

function fixture(){
 const env={DB:new D1(),ADMIN_SECRET:'A'.repeat(64),CACHE_SECRET:'B'.repeat(64),UPI_ID:'owner@bank',PAYEE_NAME:'Pilot owner',NVIDIA_API_KEY:'private-provider-test-key',MAX_MEMBERS:'50',MAX_INFLIGHT:'3'};
 let calls=0;env.UPSTREAM={fetch:async(url,options)=>{calls++;assert.equal(url,'https://integrate.api.nvidia.com/v1/chat/completions');assert.equal(options.headers.Authorization,'Bearer '+env.NVIDIA_API_KEY);
  return Response.json({choices:[{message:{role:'assistant',content:'Created the page.'},finish_reason:'stop'}],usage:{prompt_tokens:120,completion_tokens:30}});}};
 const device='device_'+crypto.randomUUID().replaceAll('-','')+'A'.repeat(20);
 let cookie='';
 async function api(path,data,{secret=device,admin=false,origin,extra={}}={}){
  const headers={'CF-Connecting-IP':'192.0.2.1',...extra};
  if(secret)headers.Authorization='Bearer '+secret;
  if(data!==undefined)headers['Content-Type']='application/json';
  if(admin){headers.Cookie=cookie;headers.Origin='https://sparkle.example';}
  if(origin!==undefined)headers.Origin=origin;
  const response=await worker.fetch(new Request('https://sparkle.example'+path,{method:data===undefined?'GET':'POST',headers,body:data===undefined?undefined:JSON.stringify(data)}),env);
  if(response.headers.has('Set-Cookie'))cookie=response.headers.get('Set-Cookie').split(';')[0];
  const result=await response.json();return {status:response.status,body:result,headers:response.headers};
 }
 async function enroll(email='tester@example.com',secret=device){const r=await api('/api/enroll',{name:'Test user',email,phone:'1234567890',consent:true},{secret});assert.equal(r.status,201);return r.body;}
 async function login(){const r=await api('/api/admin/login',{password:env.ADMIN_SECRET},{admin:true,secret:null});assert.equal(r.status,200);assert.match(r.headers.get('Set-Cookie'),/HttpOnly; SameSite=Strict/);}
 async function approve(){await enroll();await login();const payment=await api('/api/payments',{utr:'UPI1234567890',credits:999999999,amount_paise:1});assert.equal(payment.status,201);
  const r=await api('/api/admin/payments/'+payment.body.id,{action:'approve',verified:true},{admin:true});assert.equal(r.status,200);return payment.body.id;}
 const payload={messages:[{role:'user',content:'Build a flower shop landing page'}],max_tokens:4096};
 const infer=(id='request_1234567890',data=payload,options={})=>api('/v1/chat/completions',data,{...options,extra:{'Idempotency-Key':id}});
 return {env,api,enroll,login,approve,infer,device,payload,get calls(){return calls;}};
}
test('registration, manual payment approval, exact credit pack and no double credit',async()=>{
 const f=fixture(),id=await f.approve();let me=(await f.api('/api/me')).body;
 assert.equal(me.balance_tokens,1000000);assert.equal(me.available_tokens,1000000);assert.equal(me.ready,true);
 assert.equal(me.payments[0].amount_paise,1500);assert.equal(me.payments[0].credits,1000000);
 const second=await f.api('/api/admin/payments/'+id,{action:'approve',verified:true},{admin:true});assert.equal(second.body.already_reviewed,true);
 assert.equal((await f.api('/api/me')).body.balance_tokens,1000000);
 assert.equal(f.env.DB.db.prepare('SELECT COUNT(*) AS n FROM ledger').get().n,1);
});
test('pending accounts cannot infer and approval requires bank verification',async()=>{
 const f=fixture();await f.enroll();assert.equal((await f.infer()).status,403);await f.login();
 const payment=await f.api('/api/payments',{utr:'123456789012'});
 assert.equal((await f.api('/api/admin/payments/'+payment.body.id,{action:'approve'},{admin:true})).status,400);
 assert.equal((await f.api('/api/me')).body.balance_tokens,0);assert.equal(f.calls,0);
});
test('credits use confirmed input + output usage; identical retry does not call or charge again',async()=>{
 const f=fixture();await f.approve();const result=await f.infer();assert.equal(result.status,200);
 let me=(await f.api('/api/me')).body;assert.equal(me.balance_tokens,999850);assert.equal(me.held_tokens,0);
 const second=await f.infer();assert.equal(second.status,200);assert.equal(second.headers.get('X-Sparkle-Replayed'),'true');assert.equal(f.calls,1);
 assert.equal((await f.api('/api/me')).body.balance_tokens,999850);
 const row=f.env.DB.db.prepare('SELECT * FROM requests').get();assert.equal(row.charged,150);assert.ok(!row.response_cipher.includes('Created the page'));
 assert.equal((await f.infer('request_1234567890',{messages:[{role:'user',content:'Different request'}]})).status,409);
});
test('concurrent use holds credits atomically and duplicate requests do not trigger two calls',async()=>{
 const f=fixture();await f.approve();let release,entered;
 const waiting=new Promise(r=>{entered=r;});f.env.UPSTREAM.fetch=async()=>{entered();await new Promise(r=>{release=r;});return Response.json({choices:[],usage:{prompt_tokens:100,completion_tokens:10}});};
 const first=f.infer();await waiting;
 assert.ok((await f.api('/api/me')).body.held_tokens>0);
 assert.equal((await f.infer()).status,409);assert.equal((await f.infer('request_other_123456')).status,429);
 release();assert.equal((await first).status,200);assert.equal((await f.api('/api/me')).body.balance_tokens,999890);
});
test('missing provider usage holds funds for reconciliation without inventing a charge',async()=>{
 const f=fixture();await f.approve();f.env.UPSTREAM.fetch=async()=>Response.json({choices:[]});
 assert.equal((await f.infer()).status,502);let me=(await f.api('/api/me')).body;
 assert.equal(me.balance_tokens,1000000);assert.ok(me.held_tokens>0);assert.equal(me.ledger.length,1);
 assert.equal((await f.infer('another_request_12345')).status,409);
 const resolve=await f.api('/api/admin/requests/request_1234567890',{verified:true,charged_tokens:25,note:'Confirmed against provider usage record'},{admin:true});assert.equal(resolve.status,200);
 me=(await f.api('/api/me')).body;assert.equal(me.balance_tokens,999975);assert.equal(me.held_tokens,0);
 assert.equal((await f.api('/api/admin/requests/request_1234567890',{verified:true,charged_tokens:25,note:'Try duplicate charge'},{admin:true})).status,409);
});
test('rejected provider calls release holds and shared NVIDIA key never reaches users',async()=>{
 const f=fixture();await f.approve();f.env.UPSTREAM.fetch=async()=>new Response('secret '+f.env.NVIDIA_API_KEY,{status:401});
 const result=await f.infer();assert.equal(result.status,502);assert.ok(!JSON.stringify(result).includes(f.env.NVIDIA_API_KEY));
 const me=(await f.api('/api/me')).body;assert.equal(me.balance_tokens,1000000);assert.equal(me.held_tokens,0);
});
test('no cross-account response, payment or admin access; CSRF and logout protection',async()=>{
 const f=fixture();await f.approve();assert.equal((await f.api('/api/admin/overview')).status,401);
 assert.equal((await f.api('/api/admin/overview',undefined,{admin:true,origin:'https://evil.example'})).status,403);
 const other='other_'+crypto.randomUUID().replaceAll('-','')+'C'.repeat(20);await f.enroll('other@example.com',other);
 assert.equal((await f.api('/api/payments',{utr:'UPI1234567890'},{secret:other})).status,409);
 assert.equal((await f.api('/api/admin/logout',{}, {admin:true})).status,200);
 assert.equal((await f.api('/api/admin/overview',undefined,{admin:true})).status,401);
});
test('account suspension, exhausted balance and invalid model cannot reach provider',async()=>{
 const f=fixture();const account=await f.enroll();await f.login();
 f.env.DB.db.prepare("UPDATE accounts SET status='active' WHERE id=?").run(account.id);
 f.env.DB.db.prepare("UPDATE devices SET status='active'").run();
 assert.equal((await f.infer()).status,402);assert.equal((await f.infer('a_request_123456789',{...f.payload,model:'other-model'})).status,400);
 assert.equal((await f.api('/api/admin/accounts/'+account.id,{status:'suspended'},{admin:true})).status,200);
 assert.equal((await f.infer()).status,403);assert.equal(f.calls,0);
});
test('device recovery is manually approved and does not expose balance or grant more credits',async()=>{
 const f=fixture();await f.approve();const replacement='new_'+crypto.randomUUID().replaceAll('-','')+'D'.repeat(20);
 const registered=await f.api('/api/enroll',{name:'New device',email:'tester@example.com',consent:true,recovery:true},{secret:replacement});
 assert.equal(registered.status,201);assert.equal(registered.body.balance_tokens,0);
 assert.equal((await f.api('/api/payments',{utr:'RECOVER1234567'},{secret:replacement})).status,403);
 const overview=(await f.api('/api/admin/overview',undefined,{admin:true})).body;
 const recover=overview.devices.find(x=>x.kind==='recovery');
 assert.equal((await f.api('/api/admin/devices/'+recover.id,{action:'approve',verified:true},{admin:true})).status,200);
 assert.equal((await f.api('/api/me',undefined,{secret:replacement})).body.balance_tokens,1000000);
 assert.equal((await f.api('/api/me')).status,401);
});
test('pilot capacity, UPI setup and oversized requests fail closed',async()=>{
 const f=fixture();f.env.MAX_MEMBERS='1';await f.enroll();f.env.UPI_ID='';
 assert.equal((await f.api('/api/payments',{utr:'123456789012'})).status,503);
 const other='member_'+crypto.randomUUID().replaceAll('-','')+'E'.repeat(20);
 assert.equal((await f.api('/api/enroll',{name:'Other',email:'other@example.com',consent:true},{secret:other})).status,409);
 assert.equal((await f.api('/api/enroll',{name:'A'.repeat(20000),email:'a@b.co',consent:true},{secret:other})).status,413);
 assert.equal(f.env.DB.db.prepare('SELECT COUNT(*) AS n FROM accounts').get().n,1);
});
test('ledger cannot be edited and concurrent approval credits exactly once',async()=>{
 const f=fixture();await f.enroll();await f.login();const p=await f.api('/api/payments',{utr:'123456789012'});
 const responses=await Promise.all([1,2].map(()=>f.api('/api/admin/payments/'+p.body.id,{action:'approve',verified:true},{admin:true})));
 assert.ok(responses.every(x=>x.status===200));assert.equal((await f.api('/api/me')).body.balance_tokens,1000000);
 assert.throws(()=>f.env.DB.db.exec('DELETE FROM ledger'),/immutable/);
});
test('an approved second account cannot replay another account response',async()=>{
 const f=fixture();await f.approve();await f.infer();
 const other='second_'+crypto.randomUUID().replaceAll('-','')+'Z'.repeat(20);await f.enroll('second@example.com',other);
 const p=await f.api('/api/payments',{utr:'SECOND12345678'},{secret:other});
 await f.api('/api/admin/payments/'+p.body.id,{action:'approve',verified:true},{admin:true});
 assert.equal((await f.infer('request_1234567890',f.payload,{secret:other})).status,409);
 assert.equal((await f.api('/api/me',undefined,{secret:other})).body.balance_tokens,1000000);assert.equal(f.calls,1);
});
test('scheduled cleanup expires response content and flags abandoned holds without charging',async()=>{
 const f=fixture();await f.approve();await f.infer();const stamp=Math.floor(Date.now()/1000);
 f.env.DB.db.prepare('UPDATE requests SET completed=?').run(stamp-1800);
 const account=(await f.api('/api/me')).body.id;
 f.env.DB.db.prepare("INSERT INTO requests(id,account_id,payload_hash,reserve,state,created) VALUES ('abandoned',?,'test',100,'inflight',?)").run(account,stamp-1000);
 await cleanup(f.env);
 assert.equal(f.env.DB.db.prepare('SELECT response_cipher FROM requests WHERE id=?').get('request_1234567890').response_cipher,null);
 assert.equal(f.env.DB.db.prepare('SELECT state FROM requests WHERE id=?').get('abandoned').state,'uncertain');
 const a=(await f.api('/api/me')).body;assert.equal(a.balance_tokens,999850);assert.equal(a.held_tokens,100);
});
