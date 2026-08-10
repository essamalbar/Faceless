from __future__ import annotations

# Self-contained super-admin dashboard. Served verbatim at GET /admin.
#
# HARD CONSTRAINTS (enforced by tests + a strict CSP in prod):
#   * No external scripts / stylesheets / fonts / images. Inline only.
#   * The only network calls are same-origin fetch() to /admin/* endpoints.
#   * The service token lives in sessionStorage and is sent ONLY as a
#     bearer header — never in a URL/query string.
#
# It is a raw string (r"""...""") so JS/CSS braces and any backslashes pass
# through untouched.

ADMIN_HTML: str = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Super Admin — Faceless Lab</title>
<style>
  :root{
    --bg1:#FBF6EE; --bg2:#F2EFF7; --bg3:#E9EBF2;
    --card:#ffffff; --ink:#1B1E28; --muted:#5b6070;
    --line:#e4e6ef; --green:#1f9d63; --green-bg:#e8f6ee;
    --charcoal:#2b2f3a; --red:#c23b3b; --red-bg:#fbeaea;
    --shadow:0 1px 3px rgba(20,22,35,.08),0 6px 20px rgba(20,22,35,.05);
  }
  *{box-sizing:border-box}
  body{
    margin:0; color:var(--ink);
    font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
    background:linear-gradient(135deg,var(--bg1),var(--bg2) 50%,var(--bg3));
    min-height:100vh; line-height:1.45;
  }
  .wrap{max-width:1180px;margin:0 auto;padding:24px 18px 64px}
  h1{font-size:22px;margin:0 0 2px}
  h2{font-size:16px;margin:0 0 12px}
  .sub{color:var(--muted);font-size:13px;margin:0 0 20px}

  .topbar{
    display:flex;flex-wrap:wrap;gap:10px;align-items:center;
    background:var(--card);border:1px solid var(--line);border-radius:14px;
    box-shadow:var(--shadow);padding:14px 16px;margin-bottom:18px;
  }
  .topbar label{font-size:13px;color:var(--muted)}
  input[type=password],input[type=text],input[type=number]{
    font:inherit;padding:8px 10px;border:1px solid var(--line);border-radius:9px;
    background:#fff;color:var(--ink);min-width:0;
  }
  .tok{flex:1 1 260px}
  button{
    font:inherit;font-weight:600;cursor:pointer;border:0;border-radius:9px;
    padding:8px 14px;background:var(--charcoal);color:#fff;
  }
  button:hover{filter:brightness(1.08)}
  button.primary{background:var(--green)}
  button.danger{background:var(--red)}
  button.ghost{background:#eef0f6;color:var(--ink)}
  button.sm{padding:5px 9px;font-size:12px}

  .card{
    background:var(--card);border:1px solid var(--line);border-radius:14px;
    box-shadow:var(--shadow);padding:18px 18px 20px;margin-bottom:18px;
  }
  .card-head{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between;margin-bottom:12px}
  .card-head h2{margin:0}
  .controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
  .controls .lbl{font-size:12px;color:var(--muted)}
  .controls input{width:90px}
  .controls input.wide{width:170px}

  .notice{border-radius:10px;padding:10px 12px;font-size:13px;margin:0 0 14px}
  .notice.err{background:var(--red-bg);color:var(--red);border:1px solid #eecaca}
  .notice.ok{background:#e7f6ec;color:var(--green);border:1px solid #bfe6cb}
  .notice.hide{display:none}

  .scroll{overflow-x:auto}
  table{width:100%;border-collapse:collapse;font-size:13px;min-width:520px}
  th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
  th{color:var(--muted);font-weight:600;white-space:nowrap;font-size:12px;text-transform:uppercase;letter-spacing:.03em}
  td.mono,th.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
  .pos{color:var(--green);font-weight:600}
  .neg{color:var(--red);font-weight:600}
  .yes{color:var(--green);font-weight:700}
  .no{color:var(--red);font-weight:700}
  .unk{color:var(--muted);font-weight:700}
  .pill{display:inline-block;padding:2px 8px;border-radius:999px;background:#eef0f6;font-size:11px}
  .kv{display:flex;flex-wrap:wrap;gap:10px 26px;margin:0 0 14px}
  .kv div{font-size:13px}
  .kv b{display:block;color:var(--muted);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.03em}
  .rowmsg{font-size:12px;color:var(--muted);white-space:pre-wrap;word-break:break-word;max-width:340px}
  .rowmsg.err{color:var(--red)}
  .grant{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
  .grant input.amt{width:70px}
  .grant input.rsn{width:130px}
  .empty{color:var(--muted);font-size:13px;padding:8px 2px}
  .stamp{color:var(--muted);font-size:12px}
</style>
</head>
<body>
<div class="wrap">
  <h1>Super Admin</h1>
  <p class="sub">Faceless Lab operator console. All actions use the service token you enter below — it is stored only in this browser tab (sessionStorage) and sent as a bearer header.</p>

  <div class="topbar">
    <label for="tok">Service token</label>
    <input id="tok" class="tok" type="password" autocomplete="off" placeholder="Bearer service token">
    <button class="primary" id="saveTok">Save</button>
    <button class="ghost" id="clearTok">Clear</button>
    <span id="tokState" class="stamp"></span>
  </div>

  <div id="noToken" class="notice err">No service token set — enter it above and press Save to load data.</div>

  <!-- Activation & health -->
  <section class="card" id="cardOverview">
    <div class="card-head">
      <h2>Activation &amp; health</h2>
      <div class="controls"><button class="ghost sm" data-load="overview">Refresh</button></div>
    </div>
    <div id="overviewMsg" class="notice err hide"></div>
    <div id="overviewBody"><div class="empty">Not loaded.</div></div>
  </section>

  <!-- Users -->
  <section class="card" id="cardUsers">
    <div class="card-head">
      <h2>Users</h2>
      <div class="controls">
        <span class="lbl">limit</span><input id="usersLimit" type="number" value="50" min="1" max="200">
        <span class="lbl">offset</span><input id="usersOffset" type="number" value="0" min="0">
        <button class="ghost sm" data-load="users">Refresh</button>
      </div>
    </div>
    <div id="usersMsg" class="notice err hide"></div>
    <div class="scroll"><table id="usersTable"><thead><tr>
      <th class="mono">id</th><th>email</th><th>balance</th><th>plan</th><th>payment</th><th>ToS</th><th>grant</th>
    </tr></thead><tbody><tr><td colspan="7" class="empty">Not loaded.</td></tr></tbody></table></div>
  </section>

  <!-- Runs -->
  <section class="card" id="cardRuns">
    <div class="card-head">
      <h2>Runs</h2>
      <div class="controls">
        <span class="lbl">user_id</span><input id="runsUser" type="text" class="wide" placeholder="(all users)">
        <span class="lbl">limit</span><input id="runsLimit" type="number" value="50" min="1" max="200">
        <button class="ghost sm" data-load="runs">Refresh</button>
      </div>
    </div>
    <div id="runsMsg" class="notice err hide"></div>
    <div class="scroll"><table id="runsTable"><thead><tr>
      <th class="mono">owner</th><th class="mono">id</th><th>kind</th><th>status</th><th>title</th><th>created</th><th>actions</th>
    </tr></thead><tbody><tr><td colspan="7" class="empty">Not loaded.</td></tr></tbody></table></div>
  </section>

  <!-- Ledger -->
  <section class="card" id="cardLedger">
    <div class="card-head">
      <h2>Ledger</h2>
      <div class="controls">
        <span class="lbl">user_id</span><input id="ledgerUser" type="text" class="wide" placeholder="(all users)">
        <span class="lbl">limit</span><input id="ledgerLimit" type="number" value="50" min="1" max="500">
        <button class="ghost sm" data-load="ledger">Refresh</button>
      </div>
    </div>
    <div id="ledgerMsg" class="notice err hide"></div>
    <div class="scroll"><table id="ledgerTable"><thead><tr>
      <th>created</th><th class="mono">user_id</th><th>kind</th><th>amount</th><th>description</th>
    </tr></thead><tbody><tr><td colspan="5" class="empty">Not loaded.</td></tr></tbody></table></div>
  </section>
</div>

<script>
"use strict";
var TOKEN_KEY = "faceless_admin_token";

function esc(v){
  if(v === null || v === undefined) return "";
  return String(v)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}
function getToken(){ return sessionStorage.getItem(TOKEN_KEY) || ""; }
function authHeaders(){ return { "Authorization": "Bearer " + getToken() }; }
function hasToken(){ return getToken().trim().length > 0; }

function q(id){ return document.getElementById(id); }
function showMsg(id, text, isErr){
  var el = q(id);
  el.textContent = text;
  el.className = "notice " + (isErr ? "err" : "ok") + (text ? "" : " hide");
  if(!text) el.classList.add("hide");
}

// --- fetch helpers ---------------------------------------------------------
async function apiGet(path){
  var res = await fetch(path, { headers: authHeaders() });
  if(res.status === 401 || res.status === 403){
    throw new Error("Not authorized — check your token");
  }
  var text = await res.text();
  if(!res.ok){
    throw new Error("HTTP " + res.status + " — " + (text || res.statusText));
  }
  return text ? JSON.parse(text) : {};
}
async function apiSend(method, path, body){
  var opts = { method: method, headers: authHeaders() };
  if(body !== undefined && body !== null){
    opts.headers = Object.assign({ "Content-Type": "application/json" }, authHeaders());
    opts.body = JSON.stringify(body);
  }
  var res = await fetch(path, opts);
  if(res.status === 401 || res.status === 403){
    throw new Error("Not authorized — check your token");
  }
  var text = await res.text();
  if(!res.ok){
    throw new Error("HTTP " + res.status + " — " + (text || res.statusText));
  }
  return text ? JSON.parse(text) : { ok: true };
}

// --- token bar -------------------------------------------------------------
function refreshTokenUi(){
  var noTok = q("noToken");
  if(hasToken()){
    noTok.classList.add("hide");
    q("tokState").textContent = "token set (this tab)";
  } else {
    noTok.classList.remove("hide");
    q("tokState").textContent = "no token";
  }
}
function loadAll(){
  if(!hasToken()) return;
  loadOverview(); loadUsers(); loadRuns(); loadLedger();
}
q("saveTok").addEventListener("click", function(){
  var v = q("tok").value.trim();
  if(v) sessionStorage.setItem(TOKEN_KEY, v); else sessionStorage.removeItem(TOKEN_KEY);
  refreshTokenUi();
  loadAll();
});
q("clearTok").addEventListener("click", function(){
  sessionStorage.removeItem(TOKEN_KEY);
  q("tok").value = "";
  refreshTokenUi();
});

// --- section: overview -----------------------------------------------------
function mark(v){
  if(v === true) return '<span class="yes">&#10003;</span>';
  if(v === false) return '<span class="no">&#10007;</span>';
  return '<span class="unk">?</span>';
}
async function loadOverview(){
  if(!hasToken()) return;
  var body = q("overviewBody");
  showMsg("overviewMsg", "", true);
  body.innerHTML = '<div class="empty">Loading…</div>';
  try{
    var d = await apiGet("/admin/overview");
    var h = d.health || {};
    var c = d.counts || {};
    var a = d.activation || {};
    var html = '<div class="kv">'
      + '<div><b>writer_tier</b>' + esc(h.writer_tier) + '</div>'
      + '<div><b>writer_degraded</b>' + mark(!!h.writer_degraded) + '</div>'
      + '<div><b>user_dirs</b>' + esc(c.user_dirs) + '</div>'
      + '</div>';
    if(a.error){
      html += '<div class="notice err">activation probe error: ' + esc(a.error) + '</div>';
    } else {
      html += '<div class="scroll"><table style="min-width:0"><thead><tr>'
        + '<th>payment_status</th><th>tos_accepted_version</th><th>rate_events</th>'
        + '</tr></thead><tbody><tr>'
        + '<td>' + mark(a.payment_status) + '</td>'
        + '<td>' + mark(a.tos_accepted_version) + '</td>'
        + '<td>' + mark(a.rate_events) + '</td>'
        + '</tr></tbody></table></div>';
      var un = a.unprobed || [];
      if(un.length){
        html += '<p class="sub" style="margin-top:12px">Unprobed (verify in SQL editor): ';
        html += un.map(function(x){ return '<span class="pill">' + esc(x) + '</span>'; }).join(" ");
        html += '</p>';
      }
    }
    body.innerHTML = html;
  } catch(e){
    body.innerHTML = '<div class="empty">Failed to load.</div>';
    showMsg("overviewMsg", e.message, true);
  }
}

// --- section: users --------------------------------------------------------
async function loadUsers(){
  if(!hasToken()) return;
  var tbody = q("usersTable").querySelector("tbody");
  showMsg("usersMsg", "", true);
  tbody.innerHTML = '<tr><td colspan="7" class="empty">Loading…</td></tr>';
  try{
    var limit = q("usersLimit").value || 50;
    var offset = q("usersOffset").value || 0;
    var rows = await apiGet("/admin/users?limit=" + encodeURIComponent(limit) + "&offset=" + encodeURIComponent(offset));
    if(!rows.length){ tbody.innerHTML = '<tr><td colspan="7" class="empty">No users.</td></tr>'; return; }
    tbody.innerHTML = rows.map(function(u){
      var uid = esc(u.id);
      return '<tr data-uid="' + uid + '">'
        + '<td class="mono">' + uid + '</td>'
        + '<td>' + esc(u.email) + '</td>'
        + '<td class="bal">' + esc(u.balance) + '</td>'
        + '<td>' + esc(u.plan) + '</td>'
        + '<td>' + esc(u.payment_status) + '</td>'
        + '<td>' + esc(u.tos_accepted_version) + '</td>'
        + '<td><div class="grant">'
        +   '<input class="amt" type="number" placeholder="amt">'
        +   '<input class="rsn" type="text" placeholder="reason">'
        +   '<button class="primary sm act-grant">Grant</button>'
        +   '<span class="rowmsg"></span>'
        + '</div></td>'
        + '</tr>';
    }).join("");
    Array.prototype.forEach.call(tbody.querySelectorAll(".act-grant"), function(btn){
      btn.addEventListener("click", function(){ grant(btn); });
    });
  } catch(e){
    tbody.innerHTML = '<tr><td colspan="7" class="empty">Failed to load.</td></tr>';
    showMsg("usersMsg", e.message, true);
  }
}
async function grant(btn){
  var tr = btn.closest("tr");
  var msg = tr.querySelector(".rowmsg");
  var uid = tr.getAttribute("data-uid");
  var amount = parseInt(tr.querySelector(".amt").value, 10);
  var reason = tr.querySelector(".rsn").value.trim();
  msg.className = "rowmsg";
  if(isNaN(amount)){ msg.textContent = "enter an amount"; msg.className = "rowmsg err"; return; }
  btn.disabled = true;
  try{
    var r = await apiSend("POST", "/admin/credit-back", { user_id: uid, amount: amount, reason: reason });
    if(r && r.new_balance !== undefined) tr.querySelector(".bal").textContent = r.new_balance;
    msg.textContent = "ok → balance " + (r.new_balance !== undefined ? r.new_balance : "?");
  } catch(e){
    msg.textContent = e.message; msg.className = "rowmsg err";
  } finally { btn.disabled = false; }
}

// --- section: runs ---------------------------------------------------------
async function loadRuns(){
  if(!hasToken()) return;
  var tbody = q("runsTable").querySelector("tbody");
  showMsg("runsMsg", "", true);
  tbody.innerHTML = '<tr><td colspan="7" class="empty">Loading…</td></tr>';
  try{
    var limit = q("runsLimit").value || 50;
    var user = q("runsUser").value.trim();
    var path = "/admin/runs?limit=" + encodeURIComponent(limit);
    if(user) path += "&user_id=" + encodeURIComponent(user);
    var rows = await apiGet(path);
    if(!rows.length){ tbody.innerHTML = '<tr><td colspan="7" class="empty">No runs.</td></tr>'; return; }
    tbody.innerHTML = rows.map(function(r){
      var uid = esc(r.user_id);
      var rid = esc(r.id);
      var isSong = (r.kind === "song");
      var actions = '<button class="ghost sm act-cancel">Cancel</button> '
        + '<button class="danger sm act-delete">Delete</button>';
      if(isSong) actions += ' <button class="primary sm act-reassemble">Re-assemble</button>';
      return '<tr data-uid="' + uid + '" data-rid="' + rid + '" data-song="' + (isSong ? "1" : "0") + '">'
        + '<td class="mono">' + uid + '</td>'
        + '<td class="mono">' + rid + '</td>'
        + '<td>' + esc(r.kind || "video") + '</td>'
        + '<td>' + esc(r.status) + '</td>'
        + '<td>' + esc(r.title) + '</td>'
        + '<td class="stamp">' + esc(r.created_at) + '</td>'
        + '<td>' + actions + '<div class="rowmsg"></div></td>'
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
    tbody.innerHTML = '<tr><td colspan="7" class="empty">Failed to load.</td></tr>';
    showMsg("runsMsg", e.message, true);
  }
}
async function runAction(tr, action){
  var uid = tr.getAttribute("data-uid");
  var rid = tr.getAttribute("data-rid");
  var isSong = tr.getAttribute("data-song") === "1";
  var base = isSong ? "/admin/songs/" : "/admin/runs/";
  var msg = tr.querySelector(".rowmsg");
  msg.className = "rowmsg";
  var method = "POST", path;
  if(action === "cancel"){
    if(!confirm("Cancel + refund " + (isSong ? "song " : "run ") + rid + " for user " + uid + "?")) return;
    path = base + encodeURIComponent(uid) + "/" + encodeURIComponent(rid) + "/cancel";
  } else if(action === "delete"){
    if(!confirm("PERMANENTLY DELETE " + (isSong ? "song " : "run ") + rid + " for user " + uid + "? This cannot be undone.")) return;
    method = "DELETE";
    path = base + encodeURIComponent(uid) + "/" + encodeURIComponent(rid);
  } else if(action === "reassemble"){
    path = "/admin/re-assemble-song/" + encodeURIComponent(uid) + "/" + encodeURIComponent(rid);
  }
  try{
    var r = await apiSend(method, path);
    msg.textContent = JSON.stringify(r);
  } catch(e){
    msg.textContent = e.message; msg.className = "rowmsg err";
  }
}

// --- section: ledger -------------------------------------------------------
async function loadLedger(){
  if(!hasToken()) return;
  var tbody = q("ledgerTable").querySelector("tbody");
  showMsg("ledgerMsg", "", true);
  tbody.innerHTML = '<tr><td colspan="5" class="empty">Loading…</td></tr>';
  try{
    var limit = q("ledgerLimit").value || 50;
    var user = q("ledgerUser").value.trim();
    var path = "/admin/transactions?limit=" + encodeURIComponent(limit);
    if(user) path += "&user_id=" + encodeURIComponent(user);
    var rows = await apiGet(path);
    if(!rows.length){ tbody.innerHTML = '<tr><td colspan="5" class="empty">No transactions.</td></tr>'; return; }
    tbody.innerHTML = rows.map(function(t){
      var amt = Number(t.amount);
      var cls = amt < 0 ? "neg" : "pos";
      var amtStr = (amt > 0 ? "+" : "") + esc(t.amount);
      return '<tr>'
        + '<td class="stamp">' + esc(t.created_at) + '</td>'
        + '<td class="mono">' + esc(t.user_id) + '</td>'
        + '<td>' + esc(t.kind) + '</td>'
        + '<td class="' + cls + '">' + amtStr + '</td>'
        + '<td>' + esc(t.description) + '</td>'
        + '</tr>';
    }).join("");
  } catch(e){
    tbody.innerHTML = '<tr><td colspan="5" class="empty">Failed to load.</td></tr>';
    showMsg("ledgerMsg", e.message, true);
  }
}

// --- wire per-card Refresh buttons ----------------------------------------
Array.prototype.forEach.call(document.querySelectorAll("[data-load]"), function(btn){
  btn.addEventListener("click", function(){
    var which = btn.getAttribute("data-load");
    if(!hasToken()){ refreshTokenUi(); return; }
    if(which === "overview") loadOverview();
    else if(which === "users") loadUsers();
    else if(which === "runs") loadRuns();
    else if(which === "ledger") loadLedger();
  });
});

// --- boot ------------------------------------------------------------------
(function init(){
  var t = getToken();
  if(t) q("tok").value = t;
  refreshTokenUi();
  loadAll();
})();
</script>
</body>
</html>
"""
