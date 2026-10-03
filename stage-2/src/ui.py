"""Server-rendered browser UI for Pocketful stage-2.

Every page is self-contained HTML (inline CSS + JS, no external assets:
the runtime has no outbound network). Dynamic data is loaded with
``fetch`` against the JSON API (``Accept: application/json``), so the
API routes keep serving JSON to non-browser clients.
"""

CSS = """
:root{--bg:#f4f6f8;--card:#ffffff;--ink:#1c2733;--muted:#5b6b7b;--line:#dfe6ec;
--brand:#14532d;--brand-ink:#ffffff;--accent:#0f766e;--danger:#b91c1c;
--danger-bg:#fef2f2;--warn:#92400e;--warn-bg:#fffbeb;--ok:#166534;--ok-bg:#f0fdf4;
--focus:#2563eb;--radius:12px}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
line-height:1.45}
.topbar{background:var(--brand);color:var(--brand-ink);padding:0.6rem 1rem}
.topbar .wrap{max-width:920px;margin:0 auto;display:flex;gap:0.75rem;align-items:center;flex-wrap:wrap}
.brand{font-weight:700;font-size:1.1rem;letter-spacing:0.02em}
.topbar nav{display:flex;gap:0.5rem;flex-wrap:wrap}
.topbar a{color:var(--brand-ink);text-decoration:none;padding:0.25rem 0.6rem;border-radius:8px}
.topbar a:hover{background:rgba(255,255,255,0.18)}
.userchip{margin-left:auto;display:flex;gap:0.6rem;align-items:center;font-size:0.95rem}
main{max-width:920px;margin:0 auto;padding:1rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
padding:1rem 1.1rem;margin-bottom:1rem;box-shadow:0 1px 2px rgba(16,24,40,0.05)}
h1{font-size:1.35rem;margin:0 0 0.5rem}
h2{font-size:1.1rem;margin:0 0 0.6rem}
label{display:block;font-weight:600;margin:0.55rem 0 0.2rem}
input[type=text],input[type=password],input[type=email],select{width:100%;max-width:26rem;
padding:0.55rem 0.65rem;border:1px solid var(--line);border-radius:8px;font-size:1rem;background:#fff;color:var(--ink)}
input:focus-visible,select:focus-visible,button:focus-visible,a:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
button,.btn{cursor:pointer;border:1px solid transparent;border-radius:8px;font-size:1rem;
padding:0.55rem 1rem;background:var(--brand);color:#fff;font-weight:600}
button.secondary{background:#fff;color:var(--brand);border-color:var(--brand)}
button:disabled{opacity:0.55;cursor:default}
.row{display:flex;gap:0.6rem;flex-wrap:wrap;align-items:end}
.err{background:var(--danger-bg);color:var(--danger);border:1px solid #fecaca;
border-radius:8px;padding:0.55rem 0.7rem;margin-top:0.6rem}
.err-code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:0.78rem;
opacity:0.75;letter-spacing:0.01em}
.uncertain{display:none;background:var(--warn-bg);color:var(--warn);border:1px solid #fde68a;
border-radius:8px;padding:0.55rem 0.7rem;margin-top:0.6rem}
.uncertain.show{display:block}
.balance-hero{font-size:2rem;font-weight:700}
.balance-sub{color:var(--muted);font-size:0.95rem}
.badge{display:inline-block;font-size:0.78rem;font-weight:700;border-radius:999px;
padding:0.1rem 0.55rem;margin-left:0.4rem;vertical-align:middle}
.b-public{background:#dcfce7;color:#166534}
.b-private{background:#e0e7ff;color:#3730a3}
.b-pending{background:#fef9c3;color:#854d0e}
.b-paid,.b-captured{background:#dcfce7;color:#166534}
.b-declined,.b-cancelled,.b-voided{background:#fee2e2;color:#991b1b}
.b-open{background:#ffedd5;color:#9a3412}
.b-expired{background:#f1f5f9;color:#475569}
.item{border-top:1px solid var(--line);padding:0.65rem 0}
.item:first-of-type{border-top:none}
.muted{color:var(--muted);font-size:0.9rem}
.amt{font-variant-numeric:tabular-nums;font-weight:600}
.empty{border:1px dashed var(--line);border-radius:8px;padding:1rem;color:var(--muted);text-align:center}
.loading{color:var(--muted)}
@media (max-width:480px){main{padding:0.6rem}.balance-hero{font-size:1.6rem}}
"""

COMMON_JS = """
function tok(){return localStorage.getItem('pf_token')||'';}
function setTok(t){if(t){localStorage.setItem('pf_token',t);}else{localStorage.removeItem('pf_token');}}
function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
.replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
async function api(path,opts){
  opts=opts||{};
  var h={'Accept':'application/json'};
  var t=tok(); if(t){h['Authorization']='Bearer '+t;}
  if(opts.body!==undefined){h['Content-Type']='application/json';}
  if(opts.key){h['Idempotency-Key']=opts.key;}
  return fetch(path,{method:opts.method||'GET',headers:h,body:opts.body});
}
const ERR_TEXT={
  not_found:'We could not find that. Check the handle and try again.',
  unauthenticated:'Your session has ended. Sign in again to continue.',
  forbidden:'That account is not allowed to do this.',
  validation_failed:'Some of the details are not right. Check them and try again.',
  malformed_request:'We could not read what was sent. Try again.',
  insufficient_funds:'Not enough available funds for this.',
  self_payment:'You cannot pay yourself.',
  self_request:'You cannot request money from yourself.',
  request_not_pending:'That request is no longer waiting to be paid.',
  email_taken:'An account already uses that email address.',
  handle_taken:'That handle is already taken.',
  idempotency_key_reuse:'This retry does not match the original, so nothing was changed.',
  missing_idempotency_key:'This request needs a retry key, so nothing was changed.',
  stale_revision:'Someone else changed this first. Reload to see the current version.',
  historical_overdraft:'That change would overdraw an earlier balance.',
  incomplete_settlement:'This settlement is not finished, so it cannot be changed.',
  linked_payment_immutable:'This payment came from a settlement and cannot be changed on its own.',
  refund_exceeds_payment:'The refund is more than this payment is worth.',
  invalid_refund_target:'That is not something this payment can be refunded against.',
  authorization_expired:'That authorisation has expired.',
  authorization_not_open:'That authorisation is no longer open.',
  capture_exceeds_authorization:'That is more than the authorisation has left.',
  range:'That value is outside the allowed range.'
};
function errText(code){
  return ERR_TEXT[code]||('That did not go through. Nothing was changed.');
}
async function apiErr(res){
  var code='error', msg='';
  try{var j=await res.json();
    if(j&&j.error&&j.error.code){code=j.error.code;msg=j.error.message||'';}
  }catch(e){}
  // The specification asks for messages written for people, with technical identifiers
  // only where they help. So the sentence leads, and the code follows in small muted
  // type: a person reads what happened, and someone reporting the problem can quote
  // the code instead of describing a screenshot.
  var text=errText(code);
  if(msg&&msg!=='error'&&msg!==code){text=text+' ('+msg+')';}
  return {text:text,code:code};
}
function fmt(minor,currency,amount){
  var neg=amount<0?'':'';
  var a=Math.abs(amount);
  var s=String(a);
  if(minor===0){return neg+s+' '+currency;}
  while(s.length<minor+1){s='0'+s;}
  var ip=s.slice(0,s.length-minor), fp=s.slice(s.length-minor);
  return neg+ip+'.'+fp+' '+currency;
}
function parseDec(str,minor){
  var s=String(str==null?'':str).trim();
  if(!s){return {ok:false};}
  var m;
  if(minor===0){m=/^(\\d+)$/.exec(s); if(!m){return {ok:false};}
    var v=parseInt(m[1],10); if(!isFinite(v)){return {ok:false};} return {ok:true,minor:v};}
  m=/^(\\d+)(?:\\.(\\d+))?$/.exec(s);
  if(!m){return {ok:false};}
  var frac=m[2]||'';
  if(frac.length>minor){return {ok:false};}
  while(frac.length<minor){frac+='0';}
  var ip=parseInt(m[1],10), fp=frac?parseInt(frac,10):0;
  var mult=1; for(var i=0;i<minor;i++){mult*=10;}
  return {ok:true,minor:ip*mult+fp};
}
function equalSplit(amount,n){
  var base=Math.floor(amount/n), rem=amount-base*n, out=[];
  for(var i=0;i<n;i++){out.push(base+(i<rem?1:0));}
  return out;
}
function newKey(){
  if(window.crypto&&crypto.randomUUID){return crypto.randomUUID();}
  return 'k-'+Date.now()+'-'+Math.floor(Math.random()*1e9);
}
function errSlot(id){
  var slot=document.querySelector('[data-errslot="'+id+'"]');
  if(slot){return slot;}
  return document.querySelector('[data-testid="'+id+'"]')||null;
}
// An error element exists only while there is an error to show: it is created on
// demand and removed when cleared, so a caller can ask whether one is on screen.
function showErr(id,msg){
  var slot=errSlot(id);
  if(!slot){return;}
  var el=slot.querySelector('[data-testid="'+id+'"]');
  if(!msg){
    if(el){el.remove();}
    return;
  }
  if(!el){
    el=document.createElement('div');
    el.className='err';
    el.setAttribute('data-testid',id);
    el.setAttribute('role','alert');
    slot.appendChild(el);
  }
  // `msg` is either a plain sentence or the {text, code} pair apiErr returns. The
  // sentence leads and the code follows in small muted type: a person reads what
  // happened, and someone reporting the problem can quote the code rather than
  // describe a screenshot.
  if(typeof msg==='string'){
    el.textContent=msg;
    return;
  }
  el.textContent='';
  el.appendChild(document.createTextNode(msg.text+' '));
  var code=document.createElement('span');
  code.className='err-code';
  code.textContent=msg.code;
  el.appendChild(code);
}
async function loadMe(){
  try{
    var r=await api('/me');
    if(!r.ok){return null;}
    return await r.json();
  }catch(e){return null;}
}
function paintHeader(me){
  var area=document.getElementById('auth-area');
  if(!area){return;}
  if(!me){
    area.innerHTML='<a href="/login">Log in</a><a href="/signup">Sign up</a>';
    return;
  }
  area.innerHTML='<span data-testid="current-user">'+esc(me.display_name)+'</span>'
    +'<span data-testid="current-handle">'+esc(me.handle)+'</span>'
    +'<button data-testid="logout-button" id="logout-btn" class="secondary">Log out</button>';
  var b=document.getElementById('logout-btn');
  if(b){b.addEventListener('click',function(){setTok('');location.href='/login';});}
}
"""

HEADER = """
<header class="topbar"><div class="wrap">
<span class="brand">Pocketful</span>
<nav><a href="/">Wallet</a><a href="/requests">Requests</a><a href="/split">Split</a><a href="/authorizations">Holds</a></nav>
<span class="userchip" id="auth-area"><span class="loading">Loading…</span></span>
</div></header>
"""


def _shell(title, main_html, page_js):
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>" + title + " — Pocketful</title>"
        "<style>" + CSS + "</style></head><body>"
        + HEADER + "<main>" + main_html + "</main>"
        "<script>" + COMMON_JS + page_js + "</script></body></html>"
    )


def page_signup():
    main = (
        '<div class="card"><h1>Create your wallet</h1>'
        '<form id="f">'
        '<label for="se">Email</label>'
        '<input id="se" data-testid="signup-email" type="email" autocomplete="email">'
        '<label for="sp">Password (8+ characters)</label>'
        '<input id="sp" data-testid="signup-password" type="password" autocomplete="new-password">'
        '<label for="sd">Display name</label>'
        '<input id="sd" data-testid="signup-display-name" type="text" autocomplete="nickname">'
        '<div class="row" style="margin-top:0.8rem">'
        '<button data-testid="signup-submit" type="submit">Sign up</button>'
        '<a class="btn secondary" style="text-decoration:none" href="/login">Log in</a>'
        "</div></form>"
        '<div data-errslot="auth-error"></div>'
        '<p class="muted">Already have an account? <a href="/login">Log in</a>.</p>'
        "</div>"
    )
    js = """
document.getElementById('f').addEventListener('submit',async function(ev){
  ev.preventDefault(); showErr('auth-error',null);
  var body={email:document.getElementById('se').value,
    password:document.getElementById('sp').value,
    display_name:document.getElementById('sd').value};
  var r;
  try{r=await api('/auth/signup',{method:'POST',body:JSON.stringify(body)});}
  catch(e){showErr('auth-error','Network error, please retry.');return;}
  if(!r.ok){showErr('auth-error',await apiErr(r));return;}
  var j=await r.json(); setTok(j.token); location.href='/';
});
(async function(){paintHeader(await loadMe());})();
"""
    return _shell("Sign up", main, js)


def page_login():
    main = (
        '<div class="card"><h1>Welcome back</h1>'
        '<form id="f">'
        '<label for="le">Email</label>'
        '<input id="le" data-testid="login-email" type="email" autocomplete="email">'
        '<label for="lp">Password</label>'
        '<input id="lp" data-testid="login-password" type="password" autocomplete="current-password">'
        '<div class="row" style="margin-top:0.8rem">'
        '<button data-testid="login-submit" type="submit">Log in</button>'
        '<a class="btn secondary" style="text-decoration:none" href="/signup">Sign up</a>'
        "</div></form>"
        '<div data-errslot="auth-error"></div>'
        '<p class="muted">New to Pocketful? <a href="/signup">Create an account</a>.</p>'
        "</div>"
    )
    js = """
document.getElementById('f').addEventListener('submit',async function(ev){
  ev.preventDefault(); showErr('auth-error',null);
  var body={email:document.getElementById('le').value,
    password:document.getElementById('lp').value};
  var r;
  try{r=await api('/auth/login',{method:'POST',body:JSON.stringify(body)});}
  catch(e){showErr('auth-error','Network error, please retry.');return;}
  if(!r.ok){showErr('auth-error',await apiErr(r));return;}
  var j=await r.json(); setTok(j.token); location.href='/';
});
(async function(){paintHeader(await loadMe());})();
"""
    return _shell("Log in", main, js)


def _authorize_form_html():
    return (
        '<div class="card"><h2>Put money on hold</h2>'
        '<p class="muted">Reserve funds for someone to collect later.</p>'
        '<label for="ah">Recipient handle</label>'
        '<input id="ah" data-testid="authorize-handle" type="text" autocomplete="off">'
        '<label for="aa">Amount</label>'
        '<input id="aa" data-testid="authorize-amount" type="text" inputmode="decimal" autocomplete="off" placeholder="25.00">'
        '<label for="an">Note (optional)</label>'
        '<input id="an" data-testid="authorize-note" type="text" autocomplete="off">'
        '<label for="av">Visibility</label>'
        '<select id="av" data-testid="authorize-visibility">'
        '<option value="public">public</option><option value="private">private</option>'
        "</select>"
        '<div class="row" style="margin-top:0.8rem">'
        '<button data-testid="authorize-submit" id="asub" type="button">Authorize</button>'
        "</div>"
        '<div data-errslot="authorize-error"></div>'
        "</div>"
    )


AUTHORIZE_JS = """
var authKey=newKey(), authLast='';
async function submitAuthorize(){
  showErr('authorize-error',null);
  var me=window.PFME; if(!me){return;}
  var h=document.querySelector('[data-testid="authorize-handle"]').value;
  var pr=parseDec(document.querySelector('[data-testid="authorize-amount"]').value,me.minor_units);
  if(!pr.ok){showErr('authorize-error','Enter an amount like 25.00.');return;}
  var body={to_handle:h.trim(),amount:pr.minor,
    note:document.querySelector('[data-testid="authorize-note"]').value,
    visibility:document.querySelector('[data-testid="authorize-visibility"]').value};
  var s=JSON.stringify(body);
  if(s!==authLast){authKey=newKey();authLast=s;}
  var r;
  try{r=await api('/authorizations',{method:'POST',key:authKey,body:s});}
  catch(e){showErr('authorize-error','Network error, please retry.');return;}
  if(r.status!==201&&r.status!==200){showErr('authorize-error',await apiErr(r));if(window.refreshAll){await window.refreshAll();}return;}
  if(window.refreshAll){await window.refreshAll();}
  if(window.refreshAuths){await window.refreshAuths();}
}
var _asub=document.getElementById('asub');
if(_asub){_asub.addEventListener('click',submitAuthorize);}
"""


def page_home():
    main = (
        '<div id="signedout" class="card" hidden>'
        "<h1>Pocketful</h1><p>Send money, request money and split bills.</p>"
        '<p><a href="/signup">Create an account</a> or <a href="/login">log in</a>.</p>'
        "</div>"
        '<div id="app" hidden>'
        '<div class="card"><h1>Wallet</h1>'
        '<div class="muted">Available to spend</div>'
        '<div class="balance-hero" data-testid="wallet-available" data-amount="0">…</div>'
        '<div class="balance-sub">Total <span data-testid="wallet-balance" data-amount="0">…</span>'
        ' <span id="held-wrap" hidden>· Held <span data-testid="wallet-held" data-amount="0">…</span></span></div>'
        '<div class="row" style="margin-top:0.6rem">'
        '<button data-testid="wallet-refresh" id="refresh-btn" class="secondary" type="button">Refresh</button>'
        "</div></div>"
        '<div class="card"><h2>Pay someone</h2>'
        '<label for="ph">Recipient handle</label>'
        '<input id="ph" data-testid="pay-handle" type="text" autocomplete="off">'
        '<label for="pa">Amount</label>'
        '<input id="pa" data-testid="pay-amount" type="text" inputmode="decimal" autocomplete="off" placeholder="15.00">'
        '<label for="pn">Note (optional)</label>'
        '<input id="pn" data-testid="pay-note" type="text" autocomplete="off">'
        '<label for="pv">Visibility</label>'
        '<select id="pv" data-testid="pay-visibility">'
        '<option value="public">public</option><option value="private">private</option>'
        "</select>"
        '<div class="row" style="margin-top:0.8rem">'
        '<button data-testid="pay-submit" id="psub" type="button">Send payment</button>'
        "</div>"
        '<div data-errslot="pay-error"></div>'
        '<div class="uncertain" data-testid="pay-uncertain" role="status"></div>'
        "</div>"
        '<div class="card"><h2>Request money</h2>'
        '<label for="rh">Payer handle</label>'
        '<input id="rh" data-testid="request-handle" type="text" autocomplete="off">'
        '<label for="ra">Amount</label>'
        '<input id="ra" data-testid="request-amount" type="text" inputmode="decimal" autocomplete="off" placeholder="12.00">'
        '<label for="rn">Note (optional)</label>'
        '<input id="rn" data-testid="request-note" type="text" autocomplete="off">'
        '<div class="row" style="margin-top:0.8rem">'
        '<button data-testid="request-submit" id="rsub" type="button">Send request</button>'
        "</div>"
        '<div data-errslot="request-error"></div>'
        "</div>"
        + _authorize_form_html()
        + '<div class="card"><h2>Activity</h2><div id="feed"><p class="loading">Loading…</p></div></div>'
        "</div>"
    )
    js = """
window.PFME=null;
var payKey=newKey(), payLast='', reqKey=newKey(), reqLast='';
var seq=0;
function dirOf(p,me){return p.from_user_id===me.user_id?'Sent':'Received';}
async function refreshAll(){
  var me=window.PFME; if(!me){return;}
  var s=++seq;
  var meR, feedR;
  try{
    meR=await api('/me');
    feedR=await api('/activity?limit=200');
  }catch(e){return;}
  if(s!==seq){return;}
  if(meR.ok){window.PFME=await meR.json();me=window.PFME;paintWallet(me);}
  if(feedR.ok){paintFeed(await feedR.json(),me);}
}
window.refreshAll=refreshAll;
function paintWallet(me){
  var b=document.querySelector('[data-testid="wallet-balance"]');
  b.textContent=fmt(me.minor_units,me.currency,me.total);b.setAttribute('data-amount',String(me.total));
  var a=document.querySelector('[data-testid="wallet-available"]');
  a.textContent=fmt(me.minor_units,me.currency,me.available);a.setAttribute('data-amount',String(me.available));
  var w=document.getElementById('held-wrap');
  if(me.held>0){w.hidden=false;
    var h=document.querySelector('[data-testid="wallet-held"]');
    if(!h){w.innerHTML='<span data-testid="wallet-held" data-amount="0"></span>';
      h=document.querySelector('[data-testid="wallet-held"]');}
    h.textContent=fmt(me.minor_units,me.currency,me.held);h.setAttribute('data-amount',String(me.held));
  }else{w.hidden=true;var old=document.querySelector('[data-testid="wallet-held"]');if(old){old.remove();}}
}
function paintFeed(j,me){
  var box=document.getElementById('feed');
  var ps=j.payments||[];
  if(!ps.length){box.innerHTML='<div class="empty" data-testid="empty-activity">No activity yet.</div>';return;}
  var h='<div data-testid="activity-list">';
  ps.forEach(function(p){
    h+='<div class="item" data-testid="activity-item-'+esc(p.payment_id)+'" data-visibility="'+esc(p.visibility)+'">'
      +'<div><span data-testid="activity-parties-'+esc(p.payment_id)+'">'+esc(p.from_handle)+' → '+esc(p.to_handle)+'</span>'
      +'<span class="badge '+(p.visibility==='public'?'b-public':'b-private')+'">'+esc(p.visibility)+'</span>'
      +'<span class="badge">'+esc(dirOf(p,me))+'</span></div>'
      +'<div class="amt" data-testid="activity-amount-'+esc(p.payment_id)+'">'+esc(fmt(me.minor_units,me.currency,p.amount))+'</div>'
      +'<div class="muted" data-testid="activity-note-'+esc(p.payment_id)+'">'+esc(p.note)+'</div>'
      +'</div>';
  });
  box.innerHTML=h+'</div>';
}
async function submitPay(){
  showErr('pay-error',null);
  var me=window.PFME; if(!me){return;}
  var pr=parseDec(document.querySelector('[data-testid="pay-amount"]').value,me.minor_units);
  if(!pr.ok){showErr('pay-error','Enter an amount like 15.00.');return;}
  var body={to_handle:document.querySelector('[data-testid="pay-handle"]').value.trim(),
    amount:pr.minor,note:document.querySelector('[data-testid="pay-note"]').value,
    visibility:document.querySelector('[data-testid="pay-visibility"]').value};
  var s=JSON.stringify(body);
  if(s!==payLast){payKey=newKey();payLast=s;}
  var r;
  try{r=await api('/payments',{method:'POST',key:payKey,body:s});}
  catch(e){
    var u=document.querySelector('[data-testid="pay-uncertain"]');
    u.textContent='Payment may have gone through. Retry to confirm — it will only ever move money once.';
    u.classList.add('show');return;
  }
  if(r.status===201||r.status===200){
    showErr('pay-error',null);
    var u2=document.querySelector('[data-testid="pay-uncertain"]');
    u2.textContent='';u2.classList.remove('show');
    await refreshAll();return;
  }
  showErr('pay-error',await apiErr(r));
  await refreshAll();
}
async function submitRequest(){
  showErr('request-error',null);
  var me=window.PFME; if(!me){return;}
  var pr=parseDec(document.querySelector('[data-testid="request-amount"]').value,me.minor_units);
  if(!pr.ok){showErr('request-error','Enter an amount like 12.00.');return;}
  var body={payer_handle:document.querySelector('[data-testid="request-handle"]').value.trim(),
    amount:pr.minor,note:document.querySelector('[data-testid="request-note"]').value};
  var s=JSON.stringify(body);
  if(s!==reqLast){reqKey=newKey();reqLast=s;}
  var r;
  try{r=await api('/requests',{method:'POST',key:reqKey,body:s});}
  catch(e){showErr('request-error','Network error, please retry.');return;}
  if(r.status===201||r.status===200){showErr('request-error',null);return;}
  showErr('request-error',await apiErr(r));
}
document.getElementById('psub').addEventListener('click',submitPay);
document.getElementById('rsub').addEventListener('click',submitRequest);
document.getElementById('refresh-btn').addEventListener('click',function(){refreshAll();});
(async function(){
  var me=await loadMe(); paintHeader(me);
  if(!me){document.getElementById('signedout').hidden=false;return;}
  window.PFME=me; document.getElementById('app').hidden=false;
  await refreshAll();
})();
""" + AUTHORIZE_JS
    return _shell("Wallet", main, js)


def page_requests():
    main = (
        '<div id="app">'
        '<div class="card"><h1>Requests</h1>'
        '<div data-errslot="request-error"></div>'
        "<h2>Incoming</h2>"
        '<div data-testid="incoming-list"><p class="loading">Loading…</p></div>'
        "<h2>Outgoing</h2>"
        '<div data-testid="outgoing-list"><p class="loading">Loading…</p></div>'
        '<div id="emptybox"></div>'
        "</div></div>"
    )
    js = """
window.PFME=null;
// Reloading the lists never touches the error element: the caller decides when an
// error starts and when it ends, so a refresh cannot wipe a message it did not set.
async function refreshReqs(){
  var r;
  try{r=await api('/requests?limit=200');}
  catch(e){showErr('request-error','Network error, please retry.');return;}
  if(r.status===401){location.href='/login';return;}
  if(!r.ok){showErr('request-error',await apiErr(r));return;}
  var j=await r.json(), me=window.PFME;
  var inc=j.requests.filter(function(x){return x.payer_id===me.user_id;});
  var out=j.requests.filter(function(x){return x.requester_id===me.user_id;});
  paintList('incoming-list',inc,true);
  paintList('outgoing-list',out,false);
  var box=document.getElementById('emptybox');
  if(!inc.length&&!out.length){box.innerHTML='<div class="empty" data-testid="empty-requests">No requests.</div>';}
  else{box.innerHTML='';}
}
function paintList(testid,items,isIncoming){
  var me=window.PFME, box=document.querySelector('[data-testid="'+testid+'"]');
  if(!items.length){box.innerHTML='<p class="muted">Nothing here.</p>';return;}
  var h='';
  items.forEach(function(q){
    h+='<div class="item" data-testid="request-item-'+esc(q.request_id)+'" data-status="'+esc(q.status)+'">'
      +'<div><span>'+esc(q.requester_handle)+' asks '+esc(q.payer_handle)+'</span>'
      +'<span class="badge b-'+esc(q.status)+'">'+esc(q.status)+'</span></div>'
      +'<div class="amt" data-testid="request-amount-'+esc(q.request_id)+'">'+esc(fmt(me.minor_units,me.currency,q.amount))+'</div>'
      +'<div class="muted">'+esc(q.note)+'</div><div class="row" style="margin-top:0.4rem">';
    if(isIncoming&&q.status==='pending'){
      h+='<button data-testid="request-pay-'+esc(q.request_id)+'" data-act="pay" data-id="'+esc(q.request_id)+'">Pay</button>'
        +'<button data-testid="request-decline-'+esc(q.request_id)+'" data-act="decline" data-id="'+esc(q.request_id)+'" class="secondary">Decline</button>';
    }
    if(!isIncoming&&q.status==='pending'){
      h+='<button data-testid="request-cancel-'+esc(q.request_id)+'" data-act="cancel" data-id="'+esc(q.request_id)+'" class="secondary">Cancel</button>';
    }
    h+='</div></div>';
  });
  box.innerHTML=h;
  box.querySelectorAll('button[data-act]').forEach(function(b){
    b.addEventListener('click',function(){doAction(b.getAttribute('data-act'),b.getAttribute('data-id'));});
  });
}
async function doAction(act,id){
  showErr('request-error',null);
  var r;
  try{
    if(act==='pay'){r=await api('/requests/'+encodeURIComponent(id)+'/pay',{method:'POST',key:newKey(),body:'{}'});}
    else{r=await api('/requests/'+encodeURIComponent(id)+'/'+act,{method:'POST',body:'{}'});}
  }catch(e){showErr('request-error','Network error, please retry.');return;}
  if(r.ok){await refreshReqs();return;}
  showErr('request-error',await apiErr(r));
  await refreshReqs();
}
(async function(){
  var me=await loadMe(); paintHeader(me);
  if(!me){location.href='/login';return;}
  window.PFME=me; await refreshReqs();
})();
"""
    return _shell("Requests", main, js)


def page_split():
    main = (
        '<div class="card"><h1>Split a bill</h1>'
        '<label for="sa">Total amount</label>'
        '<input id="sa" data-testid="split-amount" type="text" inputmode="decimal" autocomplete="off" placeholder="30.00">'
        '<label for="sh">Participants (handles separated by commas, in order)</label>'
        '<input id="sh" data-testid="split-handles" type="text" autocomplete="off" placeholder="ada, bob">'
        '<label for="sn">Note (optional)</label>'
        '<input id="sn" data-testid="split-note" type="text" autocomplete="off">'
        '<div class="row" style="margin-top:0.8rem">'
        '<button data-testid="split-submit" id="ssub" type="button">Create split</button>'
        "</div>"
        '<div data-errslot="split-error"></div>'
        '<div id="previewbox" style="margin-top:0.8rem"></div>'
        "</div>"
    )
    js = """
window.PFME=null;
var splitKey=newKey(), splitLast='';
function readSplit(){
  var me=window.PFME;
  var pr=parseDec(document.getElementById('sa').value,me.minor_units);
  var hs=document.getElementById('sa')&&document.getElementById('sh').value.split(',').map(function(x){return x.trim();}).filter(function(x){return x;});
  return {pr:pr,hs:hs,me:me};
}
function updatePreview(){
  var box=document.getElementById('previewbox');
  var r=readSplit();
  if(!r.pr.ok||!r.hs.length){box.innerHTML='';return;}
  if(new Set(r.hs).size!==r.hs.length){box.innerHTML='';return;}
  var shares=equalSplit(r.pr.minor,r.hs.length);
  var h='<div data-testid="split-preview"><div class="muted">Shares</div>';
  r.hs.forEach(function(x,i){
    // The amount lives alone in the addressed element; the handle is its own label,
    // so a caller reading that element gets the share and nothing else.
    h+='<div class="item"><span class="muted">'+esc(x)+'</span>'
      +'<span class="amt" data-testid="split-share-'+esc(x)+'">'
      +esc(fmt(r.me.minor_units,r.me.currency,shares[i]))+'</span></div>';
  });
  box.innerHTML=h+'</div>';
}
document.getElementById('sa').addEventListener('input',updatePreview);
document.getElementById('sh').addEventListener('input',updatePreview);
document.getElementById('ssub').addEventListener('click',async function(){
  showErr('split-error',null);
  var r=readSplit(), me=r.me;
  if(!r.pr.ok){showErr('split-error','Enter an amount like 30.00.');return;}
  if(!r.hs.length){showErr('split-error','Add at least one participant.');return;}
  if(new Set(r.hs).size!==r.hs.length){showErr('split-error','Duplicate handle.');return;}
  var body={amount:r.pr.minor,participant_handles:r.hs,note:document.getElementById('sn').value};
  var s=JSON.stringify(body);
  if(s!==splitLast){splitKey=newKey();splitLast=s;}
  var res;
  try{res=await api('/splits',{method:'POST',key:splitKey,body:s});}
  catch(e){showErr('split-error','Network error, please retry.');return;}
  if(res.status===201||res.status===200){showErr('split-error',null);updatePreview();return;}
  showErr('split-error',await apiErr(res));
});
(async function(){
  var me=await loadMe(); paintHeader(me);
  if(!me){location.href='/login';return;}
  window.PFME=me;
})();
"""
    return _shell("Split", main, js)


def page_authorizations():
    main = (
        '<div id="app">'
        + _authorize_form_html()
        + '<div class="card"><h1>Holds</h1>'
        '<div data-errslot="authorization-error"></div>'
        '<div data-testid="authorization-list"><p class="loading">Loading…</p></div>'
        '<div id="emptybox"></div>'
        "</div></div>"
    )
    js = """
window.PFME=null;
async function refreshAuths(){
  var r;
  try{r=await api('/authorizations?limit=200');}
  catch(e){showErr('authorization-error','Network error, please retry.');return;}
  if(r.status===401){location.href='/login';return;}
  if(!r.ok){showErr('authorization-error',await apiErr(r));return;}
  var j=await r.json(), me=window.PFME;
  var box=document.querySelector('[data-testid="authorization-list"]');
  var items=j.authorizations||[];
  if(!items.length){box.innerHTML='';}
  else{
    var h='';
    items.forEach(function(a){
      var incoming=a.to_user_id===me.user_id, outgoing=a.from_user_id===me.user_id;
      h+='<div class="item" data-testid="authorization-item-'+esc(a.authorization_id)+'" data-status="'+esc(a.status)+'">'
        +'<div><span>'+esc(a.from_handle)+' → '+esc(a.to_handle)+'</span>'
        +'<span class="badge b-'+esc(a.status)+'">'+esc(a.status)+'</span></div>'
        +'<div class="amt" data-testid="authorization-amount-'+esc(a.authorization_id)+'">'+esc(fmt(me.minor_units,me.currency,a.amount))+'</div>';
      if(a.status==='captured'){
        h+='<div class="muted">Captured <span data-testid="authorization-captured-'+esc(a.authorization_id)+'">'+esc(fmt(me.minor_units,me.currency,a.captured_amount))+'</span></div>';
      }
      h+='<div class="muted">Expires <span data-testid="authorization-expires-'+esc(a.authorization_id)+'">'+esc(a.expires_at)+'</span></div>';
      if(a.status==='open'&&incoming){
        h+='<label>Capture amount</label>'
          +'<input data-testid="authorization-capture-amount-'+esc(a.authorization_id)+'" type="text" inputmode="decimal" value="'+esc(fmt(me.minor_units,me.currency,a.amount-a.captured_amount).split(' ')[0])+'">'
          +'<div class="row" style="margin-top:0.4rem">'
          +'<button data-testid="authorization-capture-'+esc(a.authorization_id)+'" data-cap="'+esc(a.authorization_id)+'">Capture</button></div>';
      }
      if(a.status==='open'&&outgoing){
        h+='<div class="row" style="margin-top:0.4rem">'
          +'<button data-testid="authorization-void-'+esc(a.authorization_id)+'" data-void="'+esc(a.authorization_id)+'" class="secondary">Void</button></div>';
      }
      h+='</div>';
    });
    box.innerHTML=h;
    box.querySelectorAll('button[data-cap]').forEach(function(b){
      b.addEventListener('click',function(){doCapture(b.getAttribute('data-cap'));});
    });
    box.querySelectorAll('button[data-void]').forEach(function(b){
      b.addEventListener('click',function(){doVoid(b.getAttribute('data-void'));});
    });
  }
  var eb=document.getElementById('emptybox');
  if(!items.length){eb.innerHTML='<div class="empty" data-testid="empty-authorizations">No holds.</div>';}
  else{eb.innerHTML='';}
}
window.refreshAuths=refreshAuths;
window.refreshAll=refreshAuths;
var capKeys={};
async function doCapture(id){
  showErr('authorization-error',null);
  var me=window.PFME;
  var inp=document.querySelector('[data-testid="authorization-capture-amount-'+id+'"]');
  var pr=parseDec(inp.value,me.minor_units);
  if(!pr.ok){showErr('authorization-error','Enter an amount like 5.00.');return;}
  var body={amount:pr.minor}, s=JSON.stringify(body);
  var k=capKeys[id];
  if(!k||k.body!==s){k={key:newKey(),body:s};capKeys[id]=k;}
  var r;
  try{r=await api('/authorizations/'+encodeURIComponent(id)+'/capture',{method:'POST',key:k.key,body:s});}
  catch(e){showErr('authorization-error','Network error, please retry.');return;}
  if(r.status===201||r.status===200){showErr('authorization-error',null);await refreshAuths();return;}
  showErr('authorization-error',await apiErr(r));
  await refreshAuths();
}
async function doVoid(id){
  showErr('authorization-error',null);
  var r;
  try{r=await api('/authorizations/'+encodeURIComponent(id)+'/void',{method:'POST',body:'{}'});}
  catch(e){showErr('authorization-error','Network error, please retry.');return;}
  if(r.ok){showErr('authorization-error',null);await refreshAuths();return;}
  showErr('authorization-error',await apiErr(r));
  await refreshAuths();
}
(async function(){
  var me=await loadMe(); paintHeader(me);
  if(!me){location.href='/login';return;}
  window.PFME=me; await refreshAuths();
})();
""" + AUTHORIZE_JS
    return _shell("Holds", main, js)
