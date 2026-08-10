from __future__ import annotations

# Self-contained admin control panel. Served verbatim at GET /admin.
#
# HARD CONSTRAINTS (enforced by tests + a strict CSP in prod):
#   * No external scripts / stylesheets / fonts / images. Inline only.
#   * The only network calls are same-origin fetch() to /admin/* endpoints.
#   * The admin access token lives in sessionStorage and is sent ONLY as a
#     bearer header — never in a URL/query string.
#
# It is a raw string (r"""...""") so JS/CSS braces and any backslashes pass
# through untouched.

ADMIN_HTML: str = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Faceless Lab — Control Panel</title>
<style>
  :root{
    --bg1:#f6f7fb; --bg2:#eef1f8; --bg3:#e8ecf6;
    --card:#ffffff; --ink:#1b1e28; --muted:#616780; --faint:#8b91a6;
    --line:#e6e8f1; --line2:#eef0f6;
    --green:#1f9d63; --green-ink:#137a4a; --green-bg:#e9f7ef; --green-line:#c4e8d3;
    --amber:#b7791f; --amber-bg:#fbf1dd; --amber-line:#eed9ac;
    --grey:#5b6070; --grey-bg:#eef0f6; --grey-line:#dfe2ec;
    --charcoal:#272b36;
    --red:#c23b3b; --red-ink:#a52f2f; --red-bg:#fbeceb; --red-line:#eecaca;
    --blue-bg:#eaf1fc; --blue-line:#c9dcf6; --blue-ink:#2b5aa8;
    --shadow-sm:0 1px 2px rgba(20,22,35,.06);
    --shadow:0 1px 3px rgba(20,22,35,.07),0 8px 24px rgba(20,22,35,.06);
    --shadow-lg:0 10px 40px rgba(20,22,35,.14);
    --r-sm:8px; --r:12px; --r-lg:16px; --r-xl:20px;
  }
  *{box-sizing:border-box}
  html,body{height:100%}
  body{
    margin:0; color:var(--ink);
    font-family:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    background:
      radial-gradient(1200px 700px at 15% -10%, #ffffff 0%, rgba(255,255,255,0) 55%),
      linear-gradient(135deg,var(--bg1),var(--bg2) 50%,var(--bg3));
    background-attachment:fixed;
    min-height:100vh; line-height:1.5; font-size:14px;
    -webkit-font-smoothing:antialiased;
  }
  a{color:var(--green-ink)}
  .hide{display:none !important}

  /* ---- shared controls ---- */
  input,button,select{font:inherit}
  input[type=text],input[type=email],input[type=password],input[type=number]{
    padding:9px 11px;border:1px solid var(--line);border-radius:var(--r-sm);
    background:#fff;color:var(--ink);min-width:0;transition:border-color .15s,box-shadow .15s;
  }
  input:focus{outline:none;border-color:var(--green);box-shadow:0 0 0 3px rgba(31,157,99,.15)}
  input::placeholder{color:var(--faint)}
  label{font-size:12.5px;color:var(--muted)}
  button{
    font-weight:600;cursor:pointer;border:1px solid transparent;border-radius:var(--r-sm);
    padding:9px 15px;background:var(--charcoal);color:#fff;transition:filter .15s,opacity .15s,background .15s;
  }
  button:hover{filter:brightness(1.12)}
  button:active{filter:brightness(.95)}
  button:disabled{opacity:.55;cursor:default;filter:none}
  button.primary{background:var(--green)}
  button.danger{background:var(--red)}
  button.ghost{background:#fff;color:var(--ink);border-color:var(--line)}
  button.ghost:hover{background:#f7f8fc;filter:none}
  button.sm{padding:5px 10px;font-size:12px;border-radius:7px}
  button.block{width:100%;padding:11px 15px}

  /* ---- login view ---- */
  .login-wrap{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}
  .login-card{
    width:100%;max-width:400px;background:var(--card);border:1px solid var(--line);
    border-radius:var(--r-xl);box-shadow:var(--shadow-lg);padding:34px 32px 30px;
  }
  .brand{display:flex;align-items:center;gap:11px;margin-bottom:22px}
  .brand .dot{
    width:38px;height:38px;border-radius:11px;flex:none;
    background:linear-gradient(140deg,var(--green),#15c07a);
    box-shadow:0 4px 12px rgba(31,157,99,.35);position:relative;
  }
  .brand .dot::after{content:"";position:absolute;inset:11px;border-radius:5px;background:rgba(255,255,255,.9)}
  .brand .bt{font-size:16px;font-weight:700;letter-spacing:-.01em}
  .brand .bs{font-size:12px;color:var(--muted)}
  .login-card h1{font-size:19px;margin:0 0 4px;letter-spacing:-.01em}
  .login-card .lead{color:var(--muted);font-size:13px;margin:0 0 22px}
  .field{margin-bottom:14px}
  .field label{display:block;margin-bottom:6px;font-weight:600;color:#3a3f52}
  .field input{width:100%}
  .login-err{
    background:var(--red-bg);border:1px solid var(--red-line);color:var(--red-ink);
    border-radius:var(--r-sm);padding:9px 12px;font-size:13px;margin-bottom:14px;
  }
  .login-foot{margin-top:16px;text-align:center;color:var(--faint);font-size:11.5px}

  /* ---- app bar ---- */
  .appbar{
    position:sticky;top:0;z-index:20;
    background:rgba(255,255,255,.82);backdrop-filter:saturate(180%) blur(10px);
    border-bottom:1px solid var(--line);
  }
  .appbar-in{
    max-width:1200px;margin:0 auto;padding:12px 20px;
    display:flex;align-items:center;gap:14px;flex-wrap:wrap;
  }
  .appbar .brand{margin:0}
  .appbar .dot{width:32px;height:32px;border-radius:9px}
  .appbar .dot::after{inset:9px;border-radius:4px}
  .appbar .bt{font-size:15px}
  .spacer{flex:1 1 auto}
  .who{display:flex;align-items:center;gap:10px;font-size:13px;color:var(--muted)}
  .who .em{color:var(--ink);font-weight:600;max-width:230px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .who .avatar{
    width:28px;height:28px;border-radius:50%;flex:none;display:grid;place-items:center;
    background:var(--green-bg);color:var(--green-ink);font-weight:700;font-size:12px;border:1px solid var(--green-line);
  }

  /* ---- layout ---- */
  .wrap{max-width:1200px;margin:0 auto;padding:24px 20px 72px}
  .page-h{margin:6px 2px 20px}
  .page-h h2{font-size:20px;margin:0 0 3px;letter-spacing:-.01em}
  .page-h p{margin:0;color:var(--muted);font-size:13px}

  .card{
    background:var(--card);border:1px solid var(--line);border-radius:var(--r-lg);
    box-shadow:var(--shadow);padding:0;margin-bottom:20px;overflow:hidden;
  }
  .card-head{
    display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;
    padding:16px 18px;border-bottom:1px solid var(--line2);
  }
  .card-head .ct{display:flex;align-items:center;gap:9px}
  .card-head h3{margin:0;font-size:15px;font-weight:700}
  .card-head .desc{color:var(--faint);font-size:12px;margin:2px 0 0}
  .card-body{padding:16px 18px 18px}
  .controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
  .controls .lbl{font-size:11.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
  .controls input{width:80px}
  .controls input.wide{width:180px}

  /* ---- notices ---- */
  .notice{border-radius:var(--r-sm);padding:10px 13px;font-size:13px;margin:0 0 14px;border:1px solid transparent}
  .notice.err{background:var(--red-bg);color:var(--red-ink);border-color:var(--red-line)}
  .notice.ok{background:var(--green-bg);color:var(--green-ink);border-color:var(--green-line)}
  .notice.info{background:var(--blue-bg);color:var(--blue-ink);border-color:var(--blue-line)}
  .notice.warn{background:var(--amber-bg);color:var(--amber);border-color:var(--amber-line)}
  .notice b{font-weight:700}

  /* ---- tables ---- */
  .scroll{overflow-x:auto;border:1px solid var(--line2);border-radius:var(--r);}
  table{width:100%;border-collapse:collapse;font-size:13px;min-width:560px}
  th,td{text-align:left;padding:10px 13px;border-bottom:1px solid var(--line2);vertical-align:middle}
  tbody tr:last-child td{border-bottom:0}
  tbody tr:hover{background:#fafbfe}
  th{color:var(--muted);font-weight:600;white-space:nowrap;font-size:11px;text-transform:uppercase;letter-spacing:.04em;background:#fbfcfe}
  td.mono,th.mono,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px}
  td.mono{color:var(--muted)}
  .num{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-weight:600}
  .num.pos{color:var(--green-ink)}
  .num.neg{color:var(--red-ink)}

  /* ---- badges / pills ---- */
  .badge{
    display:inline-flex;align-items:center;gap:5px;padding:3px 9px;border-radius:999px;
    font-size:11.5px;font-weight:600;line-height:1.4;white-space:nowrap;border:1px solid transparent;
  }
  .badge.green{background:var(--green-bg);color:var(--green-ink);border-color:var(--green-line)}
  .badge.red{background:var(--red-bg);color:var(--red-ink);border-color:var(--red-line)}
  .badge.amber{background:var(--amber-bg);color:var(--amber);border-color:var(--amber-line)}
  .badge.grey{background:var(--grey-bg);color:var(--grey);border-color:var(--grey-line)}
  .badge .d{width:6px;height:6px;border-radius:50%;background:currentColor;opacity:.9}
  .kind{text-transform:capitalize}
  .chip{display:inline-block;padding:3px 9px;border-radius:7px;background:var(--grey-bg);border:1px solid var(--grey-line);font-size:11.5px;color:var(--muted);margin:0 4px 4px 0}
  .chk{font-weight:800;font-size:13px}
  .chk.yes{color:var(--green)}
  .chk.no{color:var(--red)}
  .chk.unk{color:var(--faint)}

  /* ---- overview grid ---- */
  .stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:16px}
  .stat{border:1px solid var(--line2);border-radius:var(--r);padding:13px 14px;background:#fcfdff}
  .stat .k{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-bottom:7px}
  .stat .v{font-size:18px;font-weight:700}
  .sub-panel{border:1px solid var(--line2);border-radius:var(--r);padding:14px}
  .sub-panel .sp-h{font-size:12px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin:0 0 12px}
  .check-row{display:flex;flex-wrap:wrap;gap:20px 30px;margin-bottom:12px}
  .check{display:flex;align-items:center;gap:9px}
  .check .cap{display:flex;flex-direction:column}
  .check .cap .t{font-weight:600;font-size:13px}
  .check .cap .s{font-size:11px;color:var(--faint)}

  /* ---- row actions ---- */
  .actions{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
  .grant{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
  .grant input.amt{width:66px}
  .grant input.rsn{width:130px}
  .rowmsg{font-size:12px;color:var(--muted);margin-top:6px;white-space:pre-wrap;word-break:break-word;max-width:340px}
  .rowmsg.ok{color:var(--green-ink)}
  .rowmsg.err{color:var(--red-ink)}
  .rowmsg:empty{display:none}

  .state{color:var(--muted);font-size:13px;padding:18px 4px;text-align:center}
  .state .big{font-size:14px;color:var(--ink);font-weight:600;margin-bottom:3px}
  .stamp{color:var(--muted);font-size:12px;white-space:nowrap}
  .spin{display:inline-block;width:14px;height:14px;border:2px solid rgba(255,255,255,.45);border-top-color:#fff;border-radius:50%;animation:sp .6s linear infinite;vertical-align:-2px;margin-right:6px}
  @keyframes sp{to{transform:rotate(360deg)}}

  @media (max-width:640px){
    .who .em{max-width:150px}
    .wrap{padding:18px 14px 56px}
  }
</style>
</head>
<body>

<!-- ========================= LOGIN VIEW ========================= -->
<div id="loginView" class="login-wrap">
  <div class="login-card">
    <div class="brand">
      <div class="dot"></div>
      <div>
        <div class="bt">Faceless Lab</div>
        <div class="bs">Control Panel</div>
      </div>
    </div>
    <h1>Sign in</h1>
    <p class="lead">Administrator access only.</p>
    <div id="loginErr" class="login-err hide" role="alert"></div>
    <form id="loginForm" autocomplete="on" novalidate>
      <div class="field">
        <label for="email">Email</label>
        <input id="email" name="email" type="email" autocomplete="email"
               placeholder="you@example.com" autofocus>
      </div>
      <div class="field">
        <label for="password">Password</label>
        <input id="password" name="password" type="password"
               autocomplete="current-password" placeholder="••••••••">
      </div>
      <button id="loginBtn" class="primary block" type="submit">Sign in</button>
    </form>
    <div class="login-foot">Faceless Lab · operator console</div>
  </div>
</div>

<!-- ========================= DASHBOARD VIEW ========================= -->
<div id="dashView" class="hide">
  <header class="appbar">
    <div class="appbar-in">
      <div class="brand">
        <div class="dot"></div>
        <div>
          <div class="bt">Faceless Lab</div>
          <div class="bs">Control Panel</div>
        </div>
      </div>
      <div class="spacer"></div>
      <div class="who">
        <div id="whoAvatar" class="avatar">?</div>
        <span id="whoEmail" class="em"></span>
        <button id="signOut" class="ghost sm" type="button">Sign out</button>
      </div>
    </div>
  </header>

  <div class="wrap">
    <div class="page-h">
      <h2>Operations</h2>
      <p>Cross-user health, users, runs and the credit ledger.</p>
    </div>

    <!-- Overview -->
    <section class="card" id="cardOverview">
      <div class="card-head">
        <div class="ct">
          <div>
            <h3>Overview</h3>
            <p class="desc">Writer health & activation checks</p>
          </div>
        </div>
        <div class="controls"><button class="ghost sm" data-load="overview" type="button">Refresh</button></div>
      </div>
      <div class="card-body">
        <div id="overviewMsg" class="notice err hide"></div>
        <div id="overviewBody"><div class="state">Loading…</div></div>
      </div>
    </section>

    <!-- Users -->
    <section class="card" id="cardUsers">
      <div class="card-head">
        <div class="ct">
          <div>
            <h3>Users</h3>
            <p class="desc">Profiles, balances & credit grants</p>
          </div>
        </div>
        <div class="controls">
          <span class="lbl">limit</span><input id="usersLimit" type="number" value="50" min="1" max="200">
          <span class="lbl">offset</span><input id="usersOffset" type="number" value="0" min="0">
          <button class="ghost sm" data-load="users" type="button">Refresh</button>
        </div>
      </div>
      <div class="card-body">
        <div id="usersInfo" class="notice info hide"></div>
        <div id="usersMsg" class="notice err hide"></div>
        <div class="scroll"><table id="usersTable"><thead><tr>
          <th class="mono">ID</th><th>Email</th><th>Balance</th><th>Plan</th><th>Payment</th><th>ToS</th><th>Grant credits</th>
        </tr></thead><tbody><tr><td colspan="7"><div class="state">Loading…</div></td></tr></tbody></table></div>
      </div>
    </section>

    <!-- Runs -->
    <section class="card" id="cardRuns">
      <div class="card-head">
        <div class="ct">
          <div>
            <h3>Runs</h3>
            <p class="desc">Videos & songs across all users</p>
          </div>
        </div>
        <div class="controls">
          <span class="lbl">user_id</span><input id="runsUser" type="text" class="wide" placeholder="all users">
          <span class="lbl">limit</span><input id="runsLimit" type="number" value="50" min="1" max="200">
          <button class="ghost sm" data-load="runs" type="button">Refresh</button>
        </div>
      </div>
      <div class="card-body">
        <div id="runsMsg" class="notice err hide"></div>
        <div class="scroll"><table id="runsTable"><thead><tr>
          <th>Owner</th><th class="mono">Run ID</th><th>Kind</th><th>Status</th><th>Title</th><th>Created</th><th>Actions</th>
        </tr></thead><tbody><tr><td colspan="7"><div class="state">Loading…</div></td></tr></tbody></table></div>
      </div>
    </section>

    <!-- Ledger -->
    <section class="card" id="cardLedger">
      <div class="card-head">
        <div class="ct">
          <div>
            <h3>Ledger</h3>
            <p class="desc">Credit transactions</p>
          </div>
        </div>
        <div class="controls">
          <span class="lbl">user_id</span><input id="ledgerUser" type="text" class="wide" placeholder="all users">
          <span class="lbl">limit</span><input id="ledgerLimit" type="number" value="50" min="1" max="500">
          <button class="ghost sm" data-load="ledger" type="button">Refresh</button>
        </div>
      </div>
      <div class="card-body">
        <div id="ledgerMsg" class="notice err hide"></div>
        <div class="scroll"><table id="ledgerTable"><thead><tr>
          <th>Created</th><th class="mono">User ID</th><th>Kind</th><th>Amount</th><th>Description</th>
        </tr></thead><tbody><tr><td colspan="5"><div class="state">Loading…</div></td></tr></tbody></table></div>
      </div>
    </section>
  </div>
</div>

<script>
"use strict";
var TOKEN_KEY = "faceless_admin_token";
var EMAIL_KEY = "faceless_admin_email";

// ---- html escaping: applied to EVERY server-returned value ----------------
function esc(v){
  if(v === null || v === undefined) return "";
  return String(v)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}
function q(id){ return document.getElementById(id); }

// ---- session ---------------------------------------------------------------
function getToken(){ return sessionStorage.getItem(TOKEN_KEY) || ""; }
function getEmail(){ return sessionStorage.getItem(EMAIL_KEY) || ""; }
function hasToken(){ return getToken().trim().length > 0; }
function authHeaders(){ return { "Authorization": "Bearer " + getToken() }; }

// ---- fetch helper ----------------------------------------------------------
// Throws Error with: .status (int), .detail (server detail|null),
// .expired (true on 401/403 so callers can bounce to the login view).
async function apiRequest(method, path, body){
  var opts = { method: method, headers: authHeaders() };
  if(body !== undefined && body !== null){
    opts.headers = Object.assign({ "Content-Type": "application/json" }, authHeaders());
    opts.body = JSON.stringify(body);
  }
  var res = await fetch(path, opts);
  if(res.status === 401 || res.status === 403){
    var ae = new Error("Session expired — please sign in again.");
    ae.expired = true; ae.status = res.status;
    throw ae;
  }
  var text = "";
  try{ text = await res.text(); }catch(e){ text = ""; }
  var data = null;
  if(text){ try{ data = JSON.parse(text); }catch(e){ data = null; } }
  if(!res.ok){
    var detail = (data && data.detail) ? data.detail : null;
    var e2 = new Error(detail || "Something went wrong — try Refresh.");
    e2.status = res.status; e2.detail = detail;
    throw e2;
  }
  return data === null ? {} : data;
}
function apiGet(path){ return apiRequest("GET", path); }

// ---- view switching --------------------------------------------------------
function showLogin(){
  q("dashView").classList.add("hide");
  q("loginView").classList.remove("hide");
  var em = q("email"); if(em) em.focus();
}
function showDashboard(){
  q("loginView").classList.add("hide");
  q("dashView").classList.remove("hide");
  var em = getEmail();
  q("whoEmail").textContent = em || "signed in";
  q("whoAvatar").textContent = (em ? em.charAt(0) : "?").toUpperCase();
}
function handleExpired(){
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(EMAIL_KEY);
  showLogin();
  loginError("Session expired — please sign in again.");
}
// True if the error was an auth bounce (view already switched by handleExpired).
function bounceIfExpired(e){
  if(e && e.expired){ handleExpired(); return true; }
  return false;
}

// ---- login -----------------------------------------------------------------
function loginError(text){
  var el = q("loginErr");
  el.textContent = text || "";
  el.classList.toggle("hide", !text);
}
function setSigningIn(on){
  var b = q("loginBtn");
  b.disabled = on;
  b.innerHTML = on ? '<span class="spin"></span>Signing in…' : "Sign in";
}
async function doLogin(){
  var email = q("email").value.trim();
  var password = q("password").value;
  loginError("");
  if(!email || !password){ loginError("Enter your email and password."); return; }
  setSigningIn(true);
  try{
    var res = await fetch("/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email, password: password })
    });
    var text = ""; try{ text = await res.text(); }catch(e){ text = ""; }
    var data = null; if(text){ try{ data = JSON.parse(text); }catch(e){ data = null; } }
    if(res.ok && data && data.access_token){
      sessionStorage.setItem(TOKEN_KEY, data.access_token);
      sessionStorage.setItem(EMAIL_KEY, data.email || email);
      q("password").value = "";
      showDashboard();
      loadAll();
      return;
    }
    if(res.status === 401){ loginError("Invalid email or password."); }
    else if(res.status === 403){ loginError("This account is not an administrator."); }
    else { loginError((data && data.detail) ? data.detail : "Sign in failed — please try again."); }
  }catch(e){
    loginError("Could not reach the server — check your connection and try again.");
  }finally{
    setSigningIn(false);
  }
}

// ---- badges ----------------------------------------------------------------
function badge(cls, label){
  return '<span class="badge ' + cls + '"><span class="d"></span>' + esc(label) + '</span>';
}
function statusBadge(status){
  var s = String(status || "").toLowerCase();
  var cls = "grey";
  if(s === "complete") cls = "green";
  else if(s === "failed" || s === "error" || s === "cancelled" || s === "canceled") cls = "red";
  else if(s.indexOf("awaiting") === 0 || s === "pending" || s === "running" || s.indexOf("generat") === 0) cls = "amber";
  return badge(cls, status || "unknown");
}
function paymentBadge(ps){
  var s = String(ps || "").toLowerCase();
  var cls = "grey";
  if(s === "active") cls = "green";
  else if(s === "past_due" || s === "unpaid") cls = "amber";
  else if(s === "canceled" || s === "cancelled") cls = "red";
  return badge(cls, ps || "—");
}
function kindBadge(kind){
  var isSong = (kind === "song");
  return '<span class="badge ' + (isSong ? "amber" : "grey") + ' kind">' + (isSong ? "Song" : "Video") + '</span>';
}
// tri-state check for activation flags: true ✓ / false ✗ / other ?
function chk(v){
  if(v === true)  return '<span class="chk yes">&#10003;</span>';
  if(v === false) return '<span class="chk no">&#10007;</span>';
  return '<span class="chk unk">?</span>';
}

// ---- section: overview -----------------------------------------------------
async function loadOverview(){
  if(!hasToken()) return;
  var body = q("overviewBody");
  showMsg("overviewMsg", "");
  body.innerHTML = '<div class="state">Loading…</div>';
  try{
    var d = await apiGet("/admin/overview");
    var h = d.health || {};
    var c = d.counts || {};
    var a = d.activation || {};
    var degraded = !!h.writer_degraded;
    var html = '<div class="stat-grid">'
      + '<div class="stat"><div class="k">Writer tier</div><div class="v">' + esc(h.writer_tier || "—") + '</div></div>'
      + '<div class="stat"><div class="k">Writer health</div><div class="v">'
        + (degraded ? badge("red", "Degraded") : badge("green", "Healthy")) + '</div></div>'
      + '<div class="stat"><div class="k">User directories</div><div class="v">' + esc(c.user_dirs) + '</div></div>'
      + '</div>';

    html += '<div class="sub-panel"><div class="sp-h">Activation checks</div>';
    if(a.error){
      html += '<div class="notice warn">Activation probe unavailable: ' + esc(a.error) + '</div>';
    } else {
      html += '<div class="check-row">'
        + checkItem("payment_status", a.payment_status, "Stripe status column")
        + checkItem("tos_accepted_version", a.tos_accepted_version, "ToS acceptance column")
        + checkItem("rate_events", a.rate_events, "Rate-limit events table")
        + '</div>';
      var un = a.unprobed || [];
      if(un.length){
        html += '<div style="font-size:12px;color:var(--muted);margin-bottom:7px">Not auto-probed — verify in SQL editor:</div><div>';
        html += un.map(function(x){ return '<span class="chip">' + esc(x) + '</span>'; }).join("");
        html += '</div>';
      }
    }
    html += '</div>';
    body.innerHTML = html;
  } catch(e){
    if(bounceIfExpired(e)) return;
    body.innerHTML = '<div class="state">Could not load overview.</div>';
    showMsg("overviewMsg", e.message);
  }
}
function checkItem(name, val, caption){
  return '<div class="check">' + chk(val)
    + '<div class="cap"><span class="t">' + esc(name) + '</span>'
    + '<span class="s">' + esc(caption) + '</span></div></div>';
}

// ---- section: users --------------------------------------------------------
async function loadUsers(){
  if(!hasToken()) return;
  var tbody = q("usersTable").querySelector("tbody");
  showMsg("usersMsg", "");
  hideEl("usersInfo");
  tbody.innerHTML = '<tr><td colspan="7"><div class="state">Loading…</div></td></tr>';
  try{
    var limit = q("usersLimit").value || 50;
    var offset = q("usersOffset").value || 0;
    var rows = await apiGet("/admin/users?limit=" + encodeURIComponent(limit) + "&offset=" + encodeURIComponent(offset));
    if(!rows.length){
      tbody.innerHTML = '<tr><td colspan="7"><div class="state"><div class="big">No users yet</div>Nothing to show for this page.</div></td></tr>';
      return;
    }
    tbody.innerHTML = rows.map(function(u){
      var uid = esc(u.id);
      return '<tr data-uid="' + uid + '">'
        + '<td class="mono">' + uid + '</td>'
        + '<td>' + (u.email ? esc(u.email) : '<span class="stamp">—</span>') + '</td>'
        + '<td class="bal num' + (Number(u.balance) < 0 ? " neg" : "") + '">' + esc(u.balance) + '</td>'
        + '<td>' + esc(u.plan || "—") + '</td>'
        + '<td>' + paymentBadge(u.payment_status) + '</td>'
        + '<td>' + (u.tos_accepted_version ? esc(u.tos_accepted_version) : '<span class="stamp">—</span>') + '</td>'
        + '<td><div class="grant">'
        +   '<input class="amt" type="number" min="1" placeholder="amt">'
        +   '<input class="rsn" type="text" placeholder="reason">'
        +   '<button class="primary sm act-grant" type="button">Grant</button>'
        + '</div><div class="rowmsg"></div></td>'
        + '</tr>';
    }).join("");
    Array.prototype.forEach.call(tbody.querySelectorAll(".act-grant"), function(btn){
      btn.addEventListener("click", function(){ grant(btn); });
    });
  } catch(e){
    if(bounceIfExpired(e)) return;
    tbody.innerHTML = '<tr><td colspan="7"><div class="state">Could not load users.</div></td></tr>';
    if(e.status === 503){
      // Pending-migration state — actionable, not scary.
      showInfo("usersInfo", e.detail || "Users are unavailable until the pending database migrations are applied.");
    } else {
      showMsg("usersMsg", e.message);
    }
  }
}
async function grant(btn){
  var tr = btn.closest("tr");
  var msg = tr.querySelector(".rowmsg");
  var uid = tr.getAttribute("data-uid");
  var amount = parseInt(tr.querySelector(".amt").value, 10);
  var reason = tr.querySelector(".rsn").value.trim();
  msg.className = "rowmsg";
  if(isNaN(amount) || amount <= 0){ rowMsg(msg, "Enter a positive amount.", true); return; }
  if(!reason){ rowMsg(msg, "A reason is required for the ledger.", true); return; }
  btn.disabled = true;
  rowMsg(msg, "Granting…", false);
  try{
    var r = await apiRequest("POST", "/admin/credit-back", { user_id: uid, amount: amount, reason: reason });
    if(r && r.new_balance !== undefined){
      var bal = tr.querySelector(".bal");
      bal.textContent = r.new_balance;
      bal.className = "bal num" + (Number(r.new_balance) < 0 ? " neg" : " pos");
    }
    rowMsg(msg, "Granted +" + amount + " → balance " + (r.new_balance !== undefined ? r.new_balance : "?"), false);
    tr.querySelector(".amt").value = "";
    tr.querySelector(".rsn").value = "";
  } catch(e){
    if(bounceIfExpired(e)) return;
    rowMsg(msg, e.message, true);
  } finally { btn.disabled = false; }
}

// ---- section: runs ---------------------------------------------------------
async function loadRuns(){
  if(!hasToken()) return;
  var tbody = q("runsTable").querySelector("tbody");
  showMsg("runsMsg", "");
  tbody.innerHTML = '<tr><td colspan="7"><div class="state">Loading…</div></td></tr>';
  try{
    var limit = q("runsLimit").value || 50;
    var user = q("runsUser").value.trim();
    var path = "/admin/runs?limit=" + encodeURIComponent(limit);
    if(user) path += "&user_id=" + encodeURIComponent(user);
    var rows = await apiGet(path);
    if(!rows.length){
      tbody.innerHTML = '<tr><td colspan="7"><div class="state"><div class="big">No runs yet</div>No matching runs on disk.</div></td></tr>';
      return;
    }
    tbody.innerHTML = rows.map(function(r){
      var uid = esc(r.user_id);
      var rid = esc(r.id);
      var isSong = (r.kind === "song");
      var actions = '<button class="ghost sm act-cancel" type="button">Cancel</button>'
        + '<button class="danger sm act-delete" type="button">Delete</button>';
      if(isSong) actions += '<button class="primary sm act-reassemble" type="button">Re-assemble</button>';
      return '<tr data-uid="' + uid + '" data-rid="' + rid + '" data-song="' + (isSong ? "1" : "0") + '">'
        + '<td>' + esc(r.user_id) + '</td>'
        + '<td class="mono">' + rid + '</td>'
        + '<td>' + kindBadge(r.kind) + '</td>'
        + '<td>' + statusBadge(r.status) + '</td>'
        + '<td>' + (r.title ? esc(r.title) : '<span class="stamp">—</span>') + '</td>'
        + '<td class="stamp">' + esc(r.created_at) + '</td>'
        + '<td><div class="actions">' + actions + '</div><div class="rowmsg"></div></td>'
        + '</tr>';
    }).join("");
    Array.prototype.forEach.call(tbody.querySelectorAll("tr[data-rid]"), function(tr){
      var c = tr.querySelector(".act-cancel");
      var d = tr.querySelector(".act-delete");
      var a = tr.querySelector(".act-reassemble");
      if(c) c.addEventListener("click", function(){ runAction(tr, "cancel"); });
      if(d) d.addEventListener("click", function(){ runAction(tr, "delete"); });
      if(a) a.addEventListener("click", function(){ runAction(tr, "reassemble"); });
    });
  } catch(e){
    if(bounceIfExpired(e)) return;
    tbody.innerHTML = '<tr><td colspan="7"><div class="state">Could not load runs.</div></td></tr>';
    showMsg("runsMsg", e.message);
  }
}
async function runAction(tr, action){
  var uid = tr.getAttribute("data-uid");
  var rid = tr.getAttribute("data-rid");
  var isSong = tr.getAttribute("data-song") === "1";
  var base = isSong ? "/admin/songs/" : "/admin/runs/";
  var label = isSong ? "song" : "run";
  var msg = tr.querySelector(".rowmsg");
  var pp = encodeURIComponent(uid) + "/" + encodeURIComponent(rid);
  var method = "POST", path, done;
  if(action === "cancel"){
    if(!confirm("Cancel and refund " + label + " " + rid + " for user " + uid + "?")) return;
    path = base + pp + "/cancel"; done = "Cancelled and refunded.";
  } else if(action === "delete"){
    if(!confirm("Permanently DELETE " + label + " " + rid + " for user " + uid + "?\n\nThis cannot be undone.")) return;
    method = "DELETE"; path = base + pp; done = "Deleted.";
  } else if(action === "reassemble"){
    path = "/admin/re-assemble-song/" + pp; done = "Re-assembled.";
  } else { return; }
  msg.className = "rowmsg";
  rowMsg(msg, "Working…", false);
  var btns = tr.querySelectorAll("button"); toggleBtns(btns, true);
  try{
    var r = await apiRequest(method, path);
    if(action === "reassemble" && r && r.duration_s !== undefined){
      done = "Re-assembled in " + r.duration_s + "s.";
    }
    rowMsg(msg, done, false);
    if(action === "delete"){
      // Row is gone on the server — drop it after a beat so the note is seen.
      setTimeout(function(){ if(tr.parentNode) tr.parentNode.removeChild(tr); }, 1200);
    }
  } catch(e){
    if(bounceIfExpired(e)) return;
    rowMsg(msg, e.message, true);
  } finally { toggleBtns(btns, false); }
}

// ---- section: ledger -------------------------------------------------------
async function loadLedger(){
  if(!hasToken()) return;
  var tbody = q("ledgerTable").querySelector("tbody");
  showMsg("ledgerMsg", "");
  tbody.innerHTML = '<tr><td colspan="5"><div class="state">Loading…</div></td></tr>';
  try{
    var limit = q("ledgerLimit").value || 50;
    var user = q("ledgerUser").value.trim();
    var path = "/admin/transactions?limit=" + encodeURIComponent(limit);
    if(user) path += "&user_id=" + encodeURIComponent(user);
    var rows = await apiGet(path);
    if(!rows.length){
      tbody.innerHTML = '<tr><td colspan="5"><div class="state"><div class="big">No transactions yet</div>The ledger is empty for this filter.</div></td></tr>';
      return;
    }
    tbody.innerHTML = rows.map(function(t){
      var amt = Number(t.amount);
      var cls = amt < 0 ? "neg" : "pos";
      var sign = amt > 0 ? "+" : (amt < 0 ? "−" : "");
      var mag = Math.abs(amt);
      return '<tr>'
        + '<td class="stamp">' + esc(t.created_at) + '</td>'
        + '<td class="mono">' + esc(t.user_id) + '</td>'
        + '<td>' + esc(t.kind) + '</td>'
        + '<td class="num ' + cls + '">' + sign + esc(mag) + '</td>'
        + '<td>' + (t.description ? esc(t.description) : '<span class="stamp">—</span>') + '</td>'
        + '</tr>';
    }).join("");
  } catch(e){
    if(bounceIfExpired(e)) return;
    tbody.innerHTML = '<tr><td colspan="5"><div class="state">Could not load ledger.</div></td></tr>';
    showMsg("ledgerMsg", e.message);
  }
}

// ---- small ui helpers ------------------------------------------------------
function showMsg(id, text){
  var el = q(id);
  el.textContent = text || "";
  el.className = "notice err" + (text ? "" : " hide");
}
function showInfo(id, text){
  var el = q(id);
  el.innerHTML = "<b>Heads up:</b> " + esc(text);
  el.className = "notice info" + (text ? "" : " hide");
}
function hideEl(id){ var el = q(id); if(el){ el.textContent = ""; el.classList.add("hide"); } }
function rowMsg(el, text, isErr){
  el.textContent = text || "";
  el.className = "rowmsg " + (isErr ? "err" : "ok");
}
function toggleBtns(btns, disabled){
  Array.prototype.forEach.call(btns, function(b){ b.disabled = disabled; });
}
function loadAll(){
  if(!hasToken()) return;
  loadOverview(); loadUsers(); loadRuns(); loadLedger();
}

// ---- wiring ----------------------------------------------------------------
q("loginForm").addEventListener("submit", function(ev){ ev.preventDefault(); doLogin(); });
q("signOut").addEventListener("click", function(){
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(EMAIL_KEY);
  q("email").value = "";
  q("password").value = "";
  loginError("");
  showLogin();
});
Array.prototype.forEach.call(document.querySelectorAll("[data-load]"), function(btn){
  btn.addEventListener("click", function(){
    if(!hasToken()){ handleExpired(); return; }
    var which = btn.getAttribute("data-load");
    if(which === "overview") loadOverview();
    else if(which === "users") loadUsers();
    else if(which === "runs") loadRuns();
    else if(which === "ledger") loadLedger();
  });
});

// ---- boot ------------------------------------------------------------------
(function init(){
  if(hasToken()){ showDashboard(); loadAll(); }
  else { showLogin(); }
})();
</script>
</body>
</html>
"""
