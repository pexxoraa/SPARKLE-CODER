'use strict';
const el=id=>document.getElementById(id), number=value=>Number(value||0).toLocaleString('en-IN');
const node=(tag,text,cls='')=>{const n=document.createElement(tag);n.textContent=text;n.className=cls;return n;};
async function api(path,body){
  const response=await fetch('/api/admin/'+path,{method:body===undefined?'GET':'POST',credentials:'same-origin',redirect:'error',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
  const result=await response.json();
  if(!response.ok){if(response.status===401)show(false);throw Error(result.error||'Request failed.');}return result;
}
function show(signedIn){el('login').hidden=signedIn;el('dashboard').hidden=!signedIn;el('refresh').hidden=!signedIn;el('logout').hidden=!signedIn;}
async function action(button,fn){button.disabled=true;el('notice').textContent='';try{await fn();}catch(e){el('notice').textContent=e.message;}finally{button.disabled=false;}}
function field(parent,label,type='text'){const l=node('label',label),input=node('input','');input.type=type;l.append(input);parent.append(l);return input;}
function button(parent,label,fn,cls=''){const b=node('button',label,cls);b.type='button';b.onclick=()=>action(b,fn);parent.append(b);return b;}
function card(parent,title,detail){const c=node('article','','card');c.append(node('h3',title),node('p',detail));parent.append(c);return c;}
async function refresh(){
  const data=await api('overview');show(true);
  el('settings').textContent='₹15 = 10,00,000 tokens · '+(data.settings.upi_id||'UPI not configured')+' · '+(data.settings.provider_configured?'Model credential configured':'Model credential missing');
  el('stats').replaceChildren();
  for(const [label,value] of [['Members',data.accounts.length],['Pending payments',data.payments.filter(p=>p.status==='pending').length],['Available tokens',data.accounts.reduce((n,a)=>n+a.balance-a.held,0)]]){const c=node('div','','stat');c.append(node('strong',number(value)),node('span',label));el('stats').append(c);}
  el('paymentList').replaceChildren();
  for(const p of data.payments.filter(p=>p.status==='pending')){
    const c=card(el('paymentList'),p.name,'₹15 → 10,00,000 tokens · '+p.email);
    c.append(node('p','UPI reference: '+p.utr,'reference'),node('p','Phone: '+(p.claimed_phone||'Not provided')+' · '+new Date(p.created*1000).toLocaleString(),'muted'));
    const verified=field(c,'I matched this ₹15 payment in my bank / UPI account.','checkbox'),note=field(c,'Review note (required for rejection)');note.maxLength=300;
    const actions=node('div','','actions');c.append(actions);
    button(actions,'Accept + 1M tokens',async()=>{if(!verified.checked)throw Error('Verify the payment in your bank app first.');await api('payments/'+p.id,{action:'approve',verified:true,note:note.value});await refresh();el('notice').textContent='Payment accepted. Credits are available in the member account.';});
    button(actions,'Reject',async()=>{if(!note.value.trim())throw Error('Enter a rejection reason.');await api('payments/'+p.id,{action:'reject',note:note.value});await refresh();},'danger');
  }
  if(!el('paymentList').children.length)el('paymentList').append(node('p','No payments waiting.'));
  el('accountRows').replaceChildren();
  for(const a of data.accounts){const tr=node('tr',''),member=node('td',a.name);member.append(node('small',a.email));tr.append(member,node('td',a.status),node('td',number(a.balance-a.held)),node('td',number(a.held)));const td=node('td','');tr.append(td);if(a.status!=='pending')button(td,a.status==='suspended'?'Reactivate':'Suspend',async()=>{await api('accounts/'+a.id,{status:a.status==='suspended'?'active':'suspended'});await refresh();},'secondary');el('accountRows').append(tr);}
  el('deviceList').replaceChildren();
  for(const d of data.devices.filter(d=>d.kind==='recovery')){
    const c=card(el('deviceList'),d.email,'Request from '+d.claimed_name+' · '+(d.claimed_phone||'No phone'));
    const verified=field(c,'I verified this person owns the existing account.','checkbox'),actions=node('div','','actions');c.append(actions);
    for(const choice of ['approve','reject'])button(actions,choice==='approve'?'Reconnect device':'Reject',async()=>{if(!verified.checked)throw Error('Verify the account owner before deciding.');await api('devices/'+d.id,{action:choice,verified:true});await refresh();},choice==='reject'?'danger':'');
  }
  if(!el('deviceList').children.length)el('deviceList').append(node('p','No reconnection requests.'));
  el('requestList').replaceChildren();
  for(const r of data.requests.filter(r=>r.state==='uncertain'||r.state==='inflight')){
    const c=card(el('requestList'),r.email,number(r.reserve)+' tokens reserved · '+r.state+' · '+new Date(r.created*1000).toLocaleString());c.append(node('p',r.id,'reference'),node('p',r.note||''));
    if(r.state==='inflight'&&Date.now()/1000-r.created<600){c.append(node('p','Request still running. Refresh later.'));continue;}
    const count=field(c,'Confirmed total tokens from the provider','number');count.min='0';count.max=String(r.reserve);const note=field(c,'Evidence / reason (at least 10 characters)');note.maxLength=300;
    const verified=field(c,'I checked provider usage. Zero means confirmed no charge.','checkbox');
    button(c,'Settle confirmed usage',async()=>{if(!verified.checked||count.value==='')throw Error('Enter confirmed usage and select the verification checkbox.');await api('requests/'+r.id,{charged_tokens:Number(count.value),note:note.value,verified:true});await refresh();});
  }
  if(!el('requestList').children.length)el('requestList').append(node('p','No unresolved usage holds.'));
  el('auditList').replaceChildren(...data.audit.map(a=>node('p',new Date(a.created*1000).toLocaleString()+' · '+a.action+' · '+a.reference+' '+a.note,'muted')));
}
el('loginForm').onsubmit=e=>{e.preventDefault();action(el('loginForm').querySelector('button'),async()=>{await api('login',{password:el('password').value});el('password').value='';await refresh();});};
el('refresh').onclick=()=>action(el('refresh'),refresh);
el('logout').onclick=()=>action(el('logout'),async()=>{await api('logout',{});show(false);el('dashboard').querySelectorAll('tbody, #paymentList, #deviceList, #requestList, #auditList').forEach(n=>n.replaceChildren());});
refresh().catch(e=>{el('notice').textContent=e.message;});
