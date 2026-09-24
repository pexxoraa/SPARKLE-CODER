const enc = new TextEncoder();
const now = () => Math.floor(Date.now() / 1000);
const uid = () => crypto.randomUUID();
const hex = bytes => [...new Uint8Array(bytes)].map(x => x.toString(16).padStart(2, '0')).join('');
const hash = async value => hex(await crypto.subtle.digest('SHA-256', enc.encode(value)));
const token = () => hex(crypto.getRandomValues(new Uint8Array(32)));
const PRICE = 1500, CREDITS = 1000000;
const MODEL = 'nvidia/nemotron-3-super-120b-a12b';
class HttpError extends Error { constructor(status, message) { super(message); this.status = status; } }
const fail = (status, message) => { throw new HttpError(status, message); };
const sql = (env, query, ...args) => env.DB.prepare(query).bind(...args);
const one = (env, query, ...args) => sql(env, query, ...args).first();
const rows = async (env, query, ...args) => (await sql(env, query, ...args).all()).results;
const json = (value, status = 200, headers = {}) => Response.json(value, {status, headers});
function security(response) {
  const result = new Response(response.body, response);
  Object.entries({'Cache-Control':'no-store','Referrer-Policy':'no-referrer',
    'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY',
    'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; form-action 'self'"})
    .forEach(([key,value]) => result.headers.set(key,value));
  return result;
}
async function body(request, limit=8192) {
  if (!request.headers.get('content-type')?.startsWith('application/json')) fail(415,'Use a JSON request.');
  if (Number(request.headers.get('content-length') || 0) > limit) fail(413,'Request is too large.');
  const reader=request.body?.getReader(); if(!reader) fail(400,'Request body is missing.');
  const chunks=[]; let length=0;
  while(true) { const part=await reader.read(); if(part.done)break; length+=part.value.length;
    if(length>limit){await reader.cancel();fail(413,'Request is too large.');} chunks.push(part.value); }
  const buffer=new Uint8Array(length); let offset=0; for(const chunk of chunks){buffer.set(chunk,offset);offset+=chunk.length;}
  let value;try{value=JSON.parse(new TextDecoder().decode(buffer));}catch{fail(400,'Invalid JSON.');}
  if(!value || Array.isArray(value) || typeof value !== 'object') fail(400,'Expected an object.');
  return value;
}
function bearer(request) {
  const value=request.headers.get('authorization')||'';
  if(!/^Bearer [A-Za-z0-9_-]{43,128}$/.test(value)) fail(401,'Open the app and request access on this computer.');
  return value.slice(7);
}
function sameOrigin(request) {
  if(request.headers.get('origin')!==new URL(request.url).origin) fail(403,'Open the admin panel directly.');
}
async function rate(env, request, key, maximum, seconds=3600) {
  const stamp=now(), ip=request.headers.get('cf-connecting-ip')||'local';
  const bucket=await hash(env.ADMIN_SECRET+'|'+key+'|'+ip+'|'+Math.floor(stamp/seconds));
  const result=await env.DB.batch([
    sql(env,'DELETE FROM rate_windows WHERE expires < ?',stamp),
    sql(env,'INSERT INTO rate_windows VALUES (?,1,?) ON CONFLICT(bucket) DO UPDATE SET count=count+1 RETURNING count',bucket,stamp+seconds)
  ]);
  if(result[1].results[0].count>maximum) fail(429,'Too many attempts. Please wait before trying again.');
}
async function device(request, env, active=false) {
  const digest=await hash(bearer(request));
  const record=await one(env,`SELECT d.id AS device_id,d.status AS device_status,d.kind,d.claimed_name,a.* FROM devices d
    JOIN accounts a ON a.id=d.account_id WHERE d.secret_hash=?`,digest);
  if(!record || record.device_status==='revoked')fail(401,'This device is not connected. Request access again.');
  if(active && (record.device_status!=='active'||record.status!=='active'))fail(403,'Your account is waiting for admin approval or is suspended.');
  return record;
}
async function admin(request,env) {
  const cookie=(request.headers.get('cookie')||'').match(/(?:^|;\s*)sparkle_admin=([a-f0-9]{64})(?:;|$)/)?.[1];
  if(!cookie)fail(401,'Sign in to the admin panel.');
  const digest=await hash(cookie);
  if(!await one(env,'SELECT hash FROM admin_sessions WHERE hash=? AND expires>?',digest,now()))fail(401,'Admin session expired. Sign in again.');
  return digest;
}
async function audit(env,action,reference,note='') {
  await sql(env,'INSERT INTO audit VALUES (?,?,?,?,?)',uid(),action,reference,now(),note.slice(0,400)).run();
}
async function crypt(env,value,decrypt=false) {
  const bytes=await crypto.subtle.digest('SHA-256',enc.encode(env.CACHE_SECRET));
  const key=await crypto.subtle.importKey('raw',bytes,'AES-GCM',false,['encrypt','decrypt']);
  if(decrypt){const buffer=Uint8Array.from(atob(value),c=>c.charCodeAt(0));
    return new TextDecoder().decode(await crypto.subtle.decrypt({name:'AES-GCM',iv:buffer.slice(0,12)},key,buffer.slice(12)));}
  const iv=crypto.getRandomValues(new Uint8Array(12));
  const encrypted=new Uint8Array(await crypto.subtle.encrypt({name:'AES-GCM',iv},key,enc.encode(value)));
  const data=new Uint8Array(iv.length+encrypted.length);data.set(iv);data.set(encrypted,12);
  let binary='';for(const byte of data)binary+=String.fromCharCode(byte);return btoa(binary);
}
async function me(record,env) {
  const permitted=record.device_status==='active';
  return {id:record.id, name:permitted?record.name:record.claimed_name, email:record.email, status:record.status, kind:record.kind,
    device_status:record.device_status, ready:permitted&&record.status==='active',
    balance_tokens:permitted?record.balance:0, held_tokens:permitted?record.held:0,
    available_tokens:permitted?record.balance-record.held:0,
    model:env.MODEL||MODEL, price_paise:PRICE, credit_tokens:CREDITS,
    upi_id:env.UPI_ID||'', payee_name:env.PAYEE_NAME||'', support_email:env.SUPPORT_EMAIL||'',
    payments:await rows(env,'SELECT id,utr,status,amount_paise,credits,created,note FROM payments WHERE account_id=? AND (? OR device_id=?) ORDER BY created DESC LIMIT 20',record.id,permitted?1:0,record.device_id),
    ledger:permitted?await rows(env,'SELECT delta,kind,created,note FROM ledger WHERE account_id=? ORDER BY created DESC LIMIT 20',record.id):[]};
}
async function enroll(request,env) {
  await rate(env,request,'enroll',10);
  const data=await body(request), secret_hash=await hash(bearer(request));
  const existing=await one(env,'SELECT id FROM devices WHERE secret_hash=?',secret_hash);
  if(existing)return json(await me(await device(request,env),env));
  const name=String(data.name||'').trim(), email=String(data.email||'').trim().toLowerCase(), phone=String(data.phone||'').trim();
  if(name.length<2||name.length>80||email.length>200||!/^\S+@[^\s@]+\.[^\s@]+$/.test(email)||phone.length>32)
    fail(400,'Enter your name, a valid email and an optional phone number.');
  if(data.consent!==true)fail(400,'Confirm that project context can be processed by the model service.');
  const stamp=now(), id=uid(), deviceId=uid();
  const account=await one(env,'SELECT id FROM accounts WHERE email=?',email);
  if(account && data.recovery!==true)fail(409,'This email is registered. Choose Reconnect this device for admin review.');
  if(account){
    if((await one(env,"SELECT COUNT(*) AS n FROM devices WHERE account_id=? AND status='pending'",account.id)).n>=3)
      fail(409,'A device request is already waiting. Contact the admin.');
    await sql(env,"INSERT INTO devices VALUES (?,?,?,'pending','recovery',?,?,?)",deviceId,account.id,secret_hash,name,phone,stamp).run();
  }else{
    if(data.recovery===true)fail(400,'Request a new account first.');
    try{await env.DB.batch([
      sql(env,"INSERT INTO accounts(id,email,name,phone,created) SELECT ?,?,?,?,? WHERE (SELECT COUNT(*) FROM accounts)<?",id,email,name,phone,stamp,Number(env.MAX_MEMBERS||50)),
      sql(env,"INSERT INTO devices VALUES (?,?,?,'pending','signup',?,?,?)",deviceId,id,secret_hash,name,phone,stamp)
    ]);}catch{fail(409,'Registration is full or this email was just registered. Contact the admin.');}
  }
  return json(await me(await device(request,env),env),201);
}
async function existingResponse(env,record,account,requestHash) {
  if(record.account_id!==account.id||record.payload_hash!==requestHash)fail(409,'Request ID is already used for another request.');
  if(record.state==='succeeded'&&record.response_cipher&&record.completed>now()-900)
    return new Response(await crypt(env,record.response_cipher,true),{headers:{'Content-Type':'application/json','X-Sparkle-Replayed':'true'}});
  if(record.state==='inflight')return json({error:'The same request is still running. No second model call was started.'},409,{'Retry-After':'2'});
  if(record.state==='failed')return json({error:record.note||'The previous request failed.'},record.http_status,
    record.http_status===429?{'X-Sparkle-Safe-Retry':'true','Retry-After':'10'}:{});
  fail(409,'This request needs admin reconciliation or its response expired. It will not be charged twice.');
}
function modelBody(data,env) {
  if(data.stream===true)fail(400,'This pilot uses complete responses with confirmed token usage.');
  if(data.model && data.model!==(env.MODEL||MODEL))fail(400,'This model is not available in the pilot.');
  if(!Array.isArray(data.messages)||!data.messages.length||data.messages.length>80)fail(400,'Invalid message history.');
  for(const message of data.messages){
    if(!message||!['system','user','assistant','tool'].includes(message.role))fail(400,'Invalid message role.');
    if(message.content!=null&&typeof message.content!=='string')fail(400,'This pilot supports text and code messages.');
  }
  if(data.tools && (!Array.isArray(data.tools)||data.tools.length>40))fail(400,'Invalid tools.');
  const output=Number(data.max_tokens||4096);if(!Number.isInteger(output)||output<1||output>8192)fail(400,'Use 1–8192 output tokens per request.');
  const thinking=data.chat_template_kwargs?.enable_thinking===true;
  return {model:env.MODEL||MODEL,messages:data.messages,stream:false,max_tokens:output,
    temperature:1,top_p:0.95,chat_template_kwargs:{enable_thinking:thinking,force_nonempty_content:true},
    ...(data.tools?{tools:data.tools,tool_choice:'auto'}:{})};
}
async function inference(request,env) {
  const account=await device(request,env,true);
  const key=request.headers.get('idempotency-key');
  if(!key||!/^[-a-zA-Z0-9_]{16,100}$/.test(key))fail(400,'A unique request ID is required. Update the app.');
  const data=modelBody(await body(request,65536),env),payload=JSON.stringify(data),payloadHash=await hash(payload);
  let previous=await one(env,'SELECT * FROM requests WHERE id=?',key);
  if(previous)return existingResponse(env,previous,account,payloadHash);
  if(!env.NVIDIA_API_KEY)fail(503,'The admin has not connected the model service yet.');
  // UTF-8 bytes plus chat/tool overhead are a conservative hold, never a charge.
  const reserve=enc.encode(payload).length+4096+data.messages.length*64+data.max_tokens;
  const created=now();
  try{
    const result=await sql(env,`INSERT INTO requests(id,account_id,payload_hash,reserve,state,created)
      SELECT ?,?,?,?,'inflight',? FROM accounts WHERE id=? AND status='active' AND balance-held>=?
      AND NOT EXISTS(SELECT 1 FROM requests WHERE account_id=? AND state IN ('inflight','uncertain'))
      AND (SELECT COUNT(*) FROM requests WHERE state='inflight')<? RETURNING id`,
      key,account.id,payloadHash,reserve,created,account.id,reserve,account.id,Number(env.MAX_INFLIGHT||3)).all();
    if(!result.results.length){
      const current=await one(env,'SELECT balance,held FROM accounts WHERE id=?',account.id);
      if(current.balance-current.held<reserve)fail(402,'Not enough available tokens for this request. Add credits or reduce the request size.');
      const uncertain=await one(env,"SELECT id FROM requests WHERE account_id=? AND state='uncertain'",account.id);
      if(uncertain)fail(409,'A previous model request needs admin reconciliation. Your remaining credits are preserved.');
      return json({error:'The shared model is busy. Waiting does not consume credits.'},429,{'Retry-After':'3'});
    }
  }catch(error){
    if(error instanceof HttpError)throw error;
    previous=await one(env,'SELECT * FROM requests WHERE id=?',key);
    if(previous)return existingResponse(env,previous,account,payloadHash);
    throw error;
  }
  let upstream;
  try{
    const perform=env.UPSTREAM?.fetch?.bind(env.UPSTREAM)||fetch;
    upstream=await perform('https://integrate.api.nvidia.com/v1/chat/completions',{
      method:'POST',redirect:'error',signal:AbortSignal.timeout(240000),
      headers:{'Authorization':'Bearer '+env.NVIDIA_API_KEY,'Content-Type':'application/json'},body:payload});
    if(!upstream.ok){
      const definite=[400,401,403,404,422,429].includes(upstream.status);
      const status=upstream.status===429?429:502, note='Model service returned HTTP '+upstream.status+'.';
      await sql(env,'UPDATE requests SET state=?,http_status=?,note=?,completed=? WHERE id=? AND state=\'inflight\'',
        definite?'failed':'uncertain',status,note,now(),key).run();
      await upstream.body?.cancel();
      return json({error:note+(definite?' No tokens were charged.':' Credits are held for admin reconciliation.')},status,
        upstream.status===429?{'X-Sparkle-Safe-Retry':'true','Retry-After':'10'}:{});
    }
    const raw=await upstream.text();if(raw.length>250000)throw new Error('Oversized provider response');
    const value=JSON.parse(raw),p=value.usage?.prompt_tokens,c=value.usage?.completion_tokens;
    if(!Number.isSafeInteger(p)||!Number.isSafeInteger(c)||p<0||c<0||p+c<1||p+c>reserve||!Array.isArray(value.choices))
      throw new Error('Missing or invalid provider usage');
    const cipher=await crypt(env,raw);
    await sql(env,`UPDATE requests SET state='succeeded',prompt_tokens=?,completion_tokens=?,charged=?,
      response_cipher=?,http_status=200,completed=?,note='Provider-reported input + output tokens'
      WHERE id=? AND state='inflight'`,p,c,p+c,cipher,now(),key).run();
    return new Response(raw,{headers:{'Content-Type':'application/json','X-Sparkle-Charged-Tokens':String(p+c)}});
  }catch{
    await sql(env,"UPDATE requests SET state='uncertain',http_status=502,note='Provider outcome or usage could not be confirmed',completed=? WHERE id=? AND state='inflight'",now(),key).run();
    return json({error:'The provider outcome could not be confirmed. No estimated charge was made; the reservation needs admin review.'},502);
  }
}
async function adminRoutes(request,env,path) {
  if(path==='/api/admin/login'&&request.method==='POST'){
    sameOrigin(request);await rate(env,request,'admin-login',8,900);const data=await body(request);
    const actual=await hash(String(data.password||'')),expected=await hash(env.ADMIN_SECRET);
    let diff=0;for(let i=0;i<actual.length;i++)diff|=actual.charCodeAt(i)^expected.charCodeAt(i);
    if(diff)fail(401,'Sign-in failed.');const session=token();
    await sql(env,'INSERT INTO admin_sessions VALUES (?,?)',await hash(session),now()+43200).run();
    return json({ok:true},200,{'Set-Cookie':`sparkle_admin=${session}; Path=/api/admin; Secure; HttpOnly; SameSite=Strict; Max-Age=43200`});
  }
  const session=await admin(request,env);if(request.method!=='GET')sameOrigin(request);
  if(path==='/api/admin/logout'&&request.method==='POST'){
    await sql(env,'DELETE FROM admin_sessions WHERE hash=?',session).run();
    return json({ok:true},200,{'Set-Cookie':'sparkle_admin=; Path=/api/admin; Secure; HttpOnly; SameSite=Strict; Max-Age=0'});
  }
  if(path==='/api/admin/overview'&&request.method==='GET')return json({
    accounts:await rows(env,'SELECT * FROM accounts ORDER BY created DESC LIMIT 100'),
    payments:await rows(env,`SELECT p.*,a.name,a.email,d.claimed_name,d.claimed_phone,d.kind AS device_kind
      FROM payments p JOIN accounts a ON a.id=p.account_id JOIN devices d ON d.id=p.device_id ORDER BY (p.status='pending') DESC,p.created DESC LIMIT 150`),
    devices:await rows(env,`SELECT d.id,d.account_id,d.kind,d.claimed_name,d.claimed_phone,d.created,a.email
      FROM devices d JOIN accounts a ON a.id=d.account_id WHERE d.status='pending' ORDER BY d.created`),
    requests:await rows(env,`SELECT r.id,r.account_id,r.state,r.reserve,r.charged,r.prompt_tokens,r.completion_tokens,r.created,r.note,a.email
      FROM requests r JOIN accounts a ON a.id=r.account_id ORDER BY (r.state IN ('uncertain','inflight')) DESC,r.created DESC LIMIT 100`),
    audit:await rows(env,'SELECT * FROM audit ORDER BY created DESC LIMIT 100'),
    settings:{price_paise:PRICE,credits:CREDITS,upi_id:env.UPI_ID||'',payee_name:env.PAYEE_NAME||'',model:env.MODEL||MODEL,provider_configured:Boolean(env.NVIDIA_API_KEY)}
  });
  const match=path.match(/^\/api\/admin\/(payments|devices|accounts|requests)\/([a-zA-Z0-9_-]+)$/);
  if(!match||request.method!=='POST')fail(404,'Not found.');const [,kind,id]=match,data=await body(request);
  if(kind==='payments'){
    if(!['approve','reject'].includes(data.action))fail(400,'Choose approve or reject.');
    if(data.action==='approve'&&data.verified!==true)fail(400,'Check the UPI payment in your bank app before approving.');
    const payment=await one(env,'SELECT * FROM payments WHERE id=?',id);if(!payment)fail(404,'Payment not found.');
    if(payment.status!=='pending')return json({status:payment.status,already_reviewed:true});
    const status=data.action==='approve'?'approved':'rejected',note=String(data.note||'').slice(0,300);
    if(status==='rejected'&&!note.trim())fail(400,'Give the tester a reason.');
    await env.DB.batch([
      sql(env,"UPDATE payments SET status=?,reviewed=?,note=? WHERE id=? AND status='pending'",status,now(),note,id),
      sql(env,'INSERT INTO audit VALUES (?,?,?,?,?)',uid(),'payment-'+status,id,now(),note)
    ]);return json({status});
  }
  if(kind==='devices'){
    if(data.verified!==true||!['approve','reject'].includes(data.action))fail(400,'Verify the tester identity before reconnecting a device.');
    const record=await one(env,"SELECT * FROM devices WHERE id=? AND kind='recovery' AND status='pending'",id);
    if(!record)fail(409,'No pending recovery request.');
    await env.DB.batch([
      sql(env,"UPDATE devices SET status='revoked' WHERE account_id=? AND status='active' AND ?='approve'",record.account_id,data.action),
      sql(env,"UPDATE devices SET status=? WHERE id=? AND status='pending'",data.action==='approve'?'active':'revoked',id),
      sql(env,'INSERT INTO audit VALUES (?,?,?,?,?)',uid(),'device-'+data.action,id,now(),'Identity verified manually')
    ]);return json({ok:true});
  }
  if(kind==='accounts'){
    if(!['active','suspended'].includes(data.status))fail(400,'Invalid account status.');
    await sql(env,'UPDATE accounts SET status=? WHERE id=?',data.status,id).run();
    await audit(env,'account-'+data.status,id);return json({ok:true});
  }
  const count=Number(data.charged_tokens), record=await one(env,'SELECT * FROM requests WHERE id=?',id);
  if(!record||!['uncertain','inflight'].includes(record.state))fail(409,'Request does not need reconciliation.');
  if(record.state==='inflight'&&record.created>now()-600)fail(409,'Wait for the model request to finish.');
  if(data.verified!==true||!Number.isSafeInteger(count)||count<0||count>record.reserve||String(data.note||'').trim().length<10)
    fail(400,'Check provider usage and enter confirmed tokens plus a reason. Use zero only after confirming no charge.');
  await env.DB.batch([
    sql(env,"UPDATE requests SET state='resolved',charged=?,completed=?,note=? WHERE id=? AND state IN ('uncertain','inflight')",count,now(),String(data.note).slice(0,300),id),
    sql(env,'INSERT INTO audit VALUES (?,?,?,?,?)',uid(),'request-reconciled',id,now(),String(data.note).slice(0,300))
  ]);return json({ok:true});
}
export async function route(request,env) {
  const url=new URL(request.url),path=url.pathname;
  if(path==='/healthz')return json({ok:true,service:'sparkle-pilot',version:'0.7.0'});
  if(path==='/api/info')return json({price_paise:PRICE,credit_tokens:CREDITS,upi_id:env.UPI_ID||'',payee_name:env.PAYEE_NAME||'',support_email:env.SUPPORT_EMAIL||''});
  if(path.startsWith('/api/')||path.startsWith('/v1/')){
    if(!env.DB||!env.ADMIN_SECRET||env.ADMIN_SECRET.length<43||!env.CACHE_SECRET||env.CACHE_SECRET.length<43)
      fail(503,'The admin must finish server setup before the pilot opens.');
    const origin=request.headers.get('origin');if(origin&&origin!==url.origin)fail(403,'Use the desktop app or open the admin panel directly.');
    if(path.startsWith('/api/admin/'))return adminRoutes(request,env,path);
    if(path==='/api/enroll'&&request.method==='POST')return enroll(request,env);
    if(path==='/api/me'&&request.method==='GET')return json(await me(await device(request,env),env));
    if(path==='/api/payments'&&request.method==='POST'){
      const account=await device(request,env);await rate(env,request,'payment:'+account.id,10);
      if(account.status==='suspended')fail(403,'Account suspended. Contact the admin.');
      if(account.kind==='recovery'&&account.device_status!=='active')fail(403,'Wait for device reconnection before requesting credits.');
      if(!env.UPI_ID||!env.PAYEE_NAME)fail(503,'The admin has not added payment details yet. Do not send payment.');
      const data=await body(request),utr=String(data.utr||'').replace(/\s/g,'').toUpperCase();
      if(!/^[A-Z0-9]{8,40}$/.test(utr))fail(400,'Enter the UPI transaction reference from your payment app.');
      const old=await one(env,'SELECT id,status,account_id FROM payments WHERE utr=?',utr);
      if(old){if(old.account_id!==account.id)fail(409,'This transaction reference has already been submitted.');return json({id:old.id,status:old.status});}
      if(await one(env,"SELECT id FROM payments WHERE account_id=? AND status='pending'",account.id))fail(409,'One payment is already waiting for review.');
      const id=uid();await sql(env,'INSERT INTO payments(id,account_id,device_id,utr,created) VALUES (?,?,?,?,?)',id,account.id,account.device_id,utr,now()).run();
      return json({id,status:'pending',amount_paise:PRICE,credits:CREDITS},201);
    }
    if(path==='/v1/models'&&request.method==='GET'){await device(request,env,true);return json({data:[{id:env.MODEL||MODEL,object:'model'}]});}
    if(path==='/v1/balance'&&request.method==='GET'){const a=await device(request,env,true);return json({balance_tokens:a.balance-a.held,held_tokens:a.held,name:a.name});}
    if(path==='/v1/chat/completions'&&request.method==='POST')return inference(request,env);
    fail(404,'Not found.');
  }
  if(request.method!=='GET'&&request.method!=='HEAD')fail(405,'Method not allowed.');
  if(env.ASSETS){if(path==='/admin')url.pathname='/admin.html';return env.ASSETS.fetch(new Request(url,request));}
  return json({error:'Static assets are not configured.'},404);
}
export async function cleanup(env){
  if(!env.DB)return;
  const stamp=now();
  await env.DB.batch([
    sql(env,'UPDATE requests SET response_cipher=NULL WHERE response_cipher IS NOT NULL AND completed<?',stamp-900),
    sql(env,'DELETE FROM admin_sessions WHERE expires<?',stamp),
    sql(env,'DELETE FROM rate_windows WHERE expires<?',stamp),
    sql(env,"UPDATE requests SET state='uncertain',note='Request interrupted before settlement; reconcile provider usage' WHERE state='inflight' AND created<?",stamp-600)
  ]);
}
export default {async scheduled(event,env,ctx){ctx.waitUntil(cleanup(env));},async fetch(request,env){try{return security(await route(request,env));}
  catch(error){return security(json({error:error instanceof HttpError?error.message:'The service could not finish this request. Try again or contact the admin.'},error.status||500));}}};
