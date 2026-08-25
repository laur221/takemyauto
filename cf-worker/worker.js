// TakeMySkins Automator - Cloudflare Worker
// Cron la 6h + dashboard HTML + sesiune persistenta in KV

const API_BASE = "https://api.takemyskins.com";
const FRONTEND_VERSION = "23.07.2026_7dade";
const USER_AGENT =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

const K_COOKIES = "tms:cookies";
const K_LOGS = "tms:logs";
const K_LASTRUN = "tms:last_run";
const MAX_LOGS = 150;

// ── helpers ────────────────────────────────────────────────────────────
function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json", "access-control-allow-origin": "*" },
  });
}

function html(body) {
  return new Response(body, { headers: { "content-type": "text/html;charset=utf-8" } });
}

async function getLogs(env) {
  const raw = await env.SESSION_KV.get(K_LOGS);
  return raw ? JSON.parse(raw) : [];
}

async function addLog(env, msg) {
  const logs = await getLogs(env);
  const now = new Date().toISOString().slice(11, 19);
  let color = "b";
  const up = String(msg).toUpperCase();
  if (up.startsWith("[JOINED]") || up.startsWith("[OK]")) color = "g";
  else if (up.startsWith("[WARN]") || up.startsWith("[WAIT]")) color = "y";
  else if (up.startsWith("[ERR]")) color = "r";
  else if (up.startsWith("[AUTH]") || up.startsWith("[SESSION]")) color = "c";
  else if (up.startsWith("[API]") || up.startsWith("[CRON]")) color = "m";
  logs.push({ time: now, msg: String(msg), color });
  while (logs.length > MAX_LOGS) logs.shift();
  await env.SESSION_KV.put(K_LOGS, JSON.stringify(logs));
}

async function getCookies(env) {
  const raw = await env.SESSION_KV.get(K_COOKIES);
  if (!raw) return null;
  try {
    const data = JSON.parse(raw);
    return Array.isArray(data) ? data : data.cookies || [];
  } catch {
    return null;
  }
}

function cookieHeader(cookies) {
  return cookies.map((c) => `${c.name}=${c.value}`).join("; ");
}

function apiHeaders(cookies, csrf) {
  const h = {
    "User-Agent": USER_AGENT,
    Accept: "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "X-Frontend-Version": FRONTEND_VERSION,
    "X-Requested-With": "XMLHttpRequest",
    Origin: "https://takemyskins.com",
    Referer: "https://takemyskins.com/",
  };
  if (cookies && cookies.length) h.Cookie = cookieHeader(cookies);
  if (csrf) h["X-CSRF-Token"] = csrf;
  return h;
}

async function apiFetch(env, path, opts = {}) {
  const cookies = await getCookies(env);
  let csrf = null;
  if (!opts.noCsrf) {
    const r0 = await fetch(`${API_BASE}/root`, {
      headers: apiHeaders(cookies),
      cf: { cacheTtl: 0 },
    });
    if (r0.ok) {
      const d0 = await r0.json().catch(() => ({}));
      csrf = d0.token || null;
    }
  }
  const r = await fetch(`${API_BASE}${path}`, {
    method: opts.method || "GET",
    headers: apiHeaders(cookies, csrf),
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  let data = null;
  try {
    data = await r.json();
  } catch {
    data = { status: "error", error_message: (await r.text()).slice(0, 200) };
  }
  return { res: r, data };
}

// ── main bot logic ─────────────────────────────────────────────────────
async function runCheck(env) {
  const started = Date.now();
  await addLog(env, "[CRON] Pornesc verificarea raflelor...");

  const cookies = await getCookies(env);
  if (!cookies || !cookies.length) {
    await addLog(env, "[SESSION] Nu exista cookies salvate.");
    return { ok: false, error: "no_session" };
  }

  // 1. lista rafle active
  const listRes = await apiFetch(
    env,
    "/giveaway/active_giveaways?page=1&per_page=50",
    { noCsrf: true }
  );
  if (!listRes.res.ok) {
    await addLog(env, "[ERR] Nu am putut lista raflele.");
    return { ok: false };
  }
  const giveaways = listRes.data.giveaways || [];
  const totalInfo = listRes.data.total || {};
  const total = typeof totalInfo === "object" ? totalInfo.active_total : totalInfo;
  await addLog(env, `[API] ${giveaways.length} rafle pe pagina (${total} active).`);

  let joinedCount = 0,
    alreadyJoined = 0,
    skippedConditions = 0;

  for (const g of giveaways) {
    try {
      const gid = g.id;
      const segment = g.custom_url_segment || gid;
      const name = g.name || `raffle-${gid}`;
      const joined = !!(g.joined || g.is_joined);

      if (joined) {
        alreadyJoined++;
        await addLog(env, `[OK] Deja inscris: ${name} (#${gid})`);
        continue;
      }

      // 2. conditii
      let condRes = await apiFetch(env, "/giveaway/get_conditions", {
        method: "POST",
        body: { id_or_code: segment },
      });
      let inner = condRes.data.data || condRes.data || {};
      if (inner.is_joined) {
        alreadyJoined++;
        await addLog(env, `[OK] Deja inscris (detail): ${name}`);
        continue;
      }

      let conditions = inner.conditions || {};
      const pendingCodes = () =>
        Object.entries(conditions)
          .filter(([code, c]) => code !== "join" && !(c && c.verified))
          .map(([code]) => code);

      let pending = pendingCodes();
      if (pending.length) {
        await addLog(env, `-> Verific conditiile: ${pending.join(", ")}`);
        for (const code of pending) {
          try {
            const chk = await apiFetch(env, "/giveaway/check_reward_conditions", {
              method: "POST",
              body: { condition: code, ga_id: gid },
            });
            const v = chk.data && (chk.data.verified ?? chk.data.status === "success");
            if (v) await addLog(env, `    [OK] ${code} verificat`);
            else await addLog(env, `    [WARN] ${code}: ${(chk.data && chk.data.error_message) || "failed"}`);
          } catch (e) {
            await addLog(env, `    [ERR] check ${code}: ${e.message}`);
          }
        }
        // re-citeste conditiile
        condRes = await apiFetch(env, "/giveaway/get_conditions", {
          method: "POST",
          body: { id_or_code: segment },
        });
        inner = condRes.data.data || condRes.data || {};
        conditions = inner.conditions || {};
        const stillPending = pendingCodes();
        if (stillPending.length) {
          skippedConditions++;
          await addLog(env, `[WAIT] ${name}: conditii ramase: ${stillPending.join(", ")}`);
          continue;
        }
      }

      // 3. join (id numeric obligatoriu!)
      const joinRes = await apiFetch(env, `/giveaway/join_giveaway/${gid}`, {
        method: "POST",
        body: {},
      });
      const status = joinRes.data.status;
      if (status === "success") {
        joinedCount++;
        await addLog(env, `[JOINED] INTRAT in ${name}!`);
      } else {
        const msg = joinRes.data.error_message || "unknown";
        await addLog(env, `[WARN] ${name}: ${status} (${msg})`);
        if (String(msg).toLowerCase().includes("need_auth")) {
          await addLog(env, "[AUTH] Sesiune expirata! Actualizeaza cookies din panoul admin.");
        }
      }
    } catch (e) {
      await addLog(env, `[ERR] Eroare la procesarea raflei: ${e.message}`);
    }
  }

  const summary = `[API] Gata: ${joinedCount} noi, ${alreadyJoined} deja, ${skippedConditions} cu conditii.`;
  await addLog(env, summary);

  const result = {
    ok: true,
    joined: joinedCount,
    already: alreadyJoined,
    skipped: skippedConditions,
    seconds: Math.round((Date.now() - started) / 1000),
    finishedAt: new Date().toISOString(),
  };
  await env.SESSION_KV.put(K_LASTRUN, JSON.stringify(result));
  return result;
}

// ── prizes (profil) ────────────────────────────────────────────────────
async function getWinnings(env) {
  const me = await apiFetch(env, "/profile/user", { noCsrf: true });
  const user = me.data && me.data.user;
  if (!user) return { error: "Nu esti logat." };
  const uid = user.id;

  const norm = (entry) => {
    const item = entry.item || {};
    return {
      name: item.steam_market_hash_name || item.skin_name || "-",
      price: item.price || 0,
      image: item.steam_image || "",
      exterior: item.steam_short_exterior || "",
      time_finished: entry.time_finished || "",
      url: entry.url || "",
    };
  };

  const activeItems = [],
    historyItems = [];
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  for (const game of ["csgo", "dota2", "rust"]) {
    for (const [tab, bucket] of [
      ["items", activeItems],
      ["items_history", historyItems],
    ]) {
      try {
        const r = await fetch(
          `${API_BASE}/profile/get_profile_${tab}/${uid}?game=${game}&limit=64&page=1&sort_field=item_price&sort_direction=desc`,
          { headers: apiHeaders(await getCookies(env)) }
        );
        if (!r.ok) {
          await sleep(350);
          continue;
        }
        const d = await r.json();
        for (const entry of d.items || []) {
          const p = norm(entry);
          if (p.name !== "-") bucket.push(p);
        }
      } catch {}
      await sleep(350);
    }
  }

  let stats = {};
  try {
    const r = await fetch(
      `${API_BASE}/profile/get_profile_general_information/${uid}?game=csgo`,
      { headers: apiHeaders(await getCookies(env)) }
    );
    if (r.ok) stats = ((await r.json()).info || {}).stats || {};
  } catch {}

  const activeCost = activeItems.reduce((s, p) => s + p.price, 0);
  const historyCost = historyItems.reduce((s, p) => s + p.price, 0);

  // TMS blocheaza endpoint-urile de inventar pentru trafic Cloudflare Workers
  // (internal_error code 4). Dacă listele vin goale dar stats sunt OK,
  // servim ultimul cache reușit din KV (populat de helper-ul local).
  let fromCache = false;
  if (activeItems.length + historyItems.length === 0) {
    const cached = await env.SESSION_KV.get("tms:prizes_cache");
    if (cached) {
      try {
        const c = JSON.parse(cached);
        activeItems.push(...(c.active || []));
        historyItems.push(...(c.history || []));
        fromCache = true;
      } catch {}
    }
  }

  return {
    participated: stats.user_giveaway_count || 0,
    won_count: stats.giveaway_count || activeItems.length + historyItems.length,
    won_cost: stats.total_ga_value || +(activeCost + historyCost).toFixed(2),
    active_count: activeItems.length,
    history_count: historyItems.length,
    active: activeItems,
    history: historyItems,
    from_cache: fromCache,
    nickname: user.nickname,
  };
}

// ── keepalive GitHub Actions ───────────────────────────────────────────
// GitHub dezactiveaza cron-urile dupa 60 zile de inactivitate a repo-ului.
// Verificam starea workflow-ului G4F si il reactivam automat daca e oprit.
const GH_WORKFLOW = "repos/laur221/G4f/actions/workflows/341710200";

async function g4fKeepalive(env) {
  const tok = env.GH_TOKEN;
  if (!tok) return { skipped: "no GH_TOKEN" };
  const h = {
    Authorization: `Bearer ${tok}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "takemyauto-worker",
  };
  try {
    const r = await fetch(`https://api.github.com/${GH_WORKFLOW}`, { headers: h });
    if (!r.ok) return { error: "gh get " + r.status };
    const d = await r.json();
    if (d.state === "active") return { state: "active" };

    const en = await fetch(`https://api.github.com/${GH_WORKFLOW}/enable`, {
      method: "PUT",
      headers: h,
    });
    if (en.ok) {
      await addLog(env, `[KEEPALIVE] Workflow G4F re-activat automat (era ${d.state}).`);
      return { reactivated: true, was: d.state };
    }
    await addLog(env, `[KEEPALIVE] Reactivare esuata: HTTP ${en.status}`);
    return { error: "enable " + en.status };
  } catch (e) {
    return { error: e.message };
  }
}

// ── dashboard ──────────────────────────────────────────────────────────
function dashboardHTML() {
  return html(`<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TakeMySkins Automator</title>
<style>
  :root {
    --bg: #0a0e17;
    --card: #111827;
    --card2: #151b2b;
    --border: #1f2a3f;
    --text: #e6edf3;
    --muted: #8b949e;
    --blue: #3b82f6;
    --green: #22c55e;
    --red: #ef4444;
    --amber: #f59e0b;
    --cyan: #22d3ee;
    --purple: #8b5cf6;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: radial-gradient(1200px 600px at 15% -10%, #16204a55, transparent 60%),
                radial-gradient(900px 500px at 100% 0%, #2a1a4d44, transparent 55%),
                var(--bg);
    color: var(--text);
    font-family: "Segoe UI", -apple-system, Roboto, Helvetica, Arial, sans-serif;
    min-height: 100vh;
    padding: 0 0 30px;
  }
  .wrap { max-width: 980px; margin: 0 auto; padding: 0 20px; }

  header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 18px 0; margin-bottom: 14px;
    border-bottom: 1px solid var(--border);
  }
  .brand { display: flex; align-items: center; gap: 12px; }
  .logo {
    width: 44px; height: 44px; border-radius: 12px; display: flex;
    align-items: center; justify-content: center;
    background: linear-gradient(135deg, var(--blue), var(--purple));
    font-size: 22px; box-shadow: 0 4px 16px #3b82f655;
  }
  .brand h1 { font-size: 19px; font-weight: 700; }
  .brand p { font-size: 11.5px; color: var(--muted); margin-top: 1px; }

  .pill {
    display: flex; align-items: center; gap: 8px;
    background: var(--card2); border: 1px solid var(--border);
    border-radius: 20px; padding: 5px 14px; font-size: 12px; font-weight: 600;
  }
  .dot { width: 9px; height: 9px; border-radius: 50%; background: #3f4650; transition: background .3s; }
  .dot.ok   { background: var(--green); box-shadow: 0 0 8px var(--green); }
  @keyframes pulse { 50% { opacity: .45; } }

  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  @media (max-width: 760px) { .grid { grid-template-columns: 1fr; } }

  .card {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 16px; padding: 16px;
    box-shadow: 0 6px 18px #0003;
  }
  .card .head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
  .card .head .t { font-size: 15px; font-weight: 700; }
  .card .head .s { font-size: 11.5px; color: var(--muted); margin-top: 1px; }
  .ic {
    width: 30px; height: 30px; border-radius: 8px; display: flex;
    align-items: center; justify-content: center; font-size: 15px; flex: 0 0 auto;
  }
  .card .body { display: flex; flex-direction: column; gap: 10px; }

  .btn {
    display: inline-flex; align-items: center; gap: 8px;
    border: none; border-radius: 10px; padding: 11px 16px;
    font-size: 13px; font-weight: 600; color: #fff; cursor: pointer;
    transition: transform .08s, filter .15s;
    font-family: inherit;
  }
  .btn:hover { filter: brightness(1.1); }
  .btn:active { transform: scale(.97); }
  .btn:disabled { opacity: .55; cursor: not-allowed; transform: none; }
  .b-blue  { background: var(--blue); }
  .b-green { background: var(--green); }
  .b-gray  { background: #1f2937; color: var(--muted); }

  .statusline { font-size: 13px; color: var(--muted); min-height: 20px; }

  .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
  @media (max-width: 620px) { .stats { grid-template-columns: 1fr; } }
  .stat {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 14px; padding: 16px;
  }
  .stat .v { font-size: 28px; font-weight: 700; margin-top: 8px; }
  .stat .l { font-size: 12px; color: var(--muted); font-weight: 500; margin-top: 2px; }

  .tabs { display: flex; gap: 8px; margin-bottom: 12px; }
  .tab {
    background: var(--card2); color: var(--muted); border: 1px solid var(--border);
    border-radius: 10px; padding: 8px 16px; font-size: 13px; font-weight: 600;
    cursor: pointer; font-family: inherit; transition: all .15s;
    display: flex; align-items: center; gap: 7px;
  }
  .tab:hover { color: var(--text); }
  .tab.active { background: #22c55e22; border-color: #22c55e55; color: var(--green); }
  .tabcount {
    background: var(--card); border-radius: 10px; padding: 1px 8px;
    font-size: 11px; color: var(--muted);
  }
  .tab.active .tabcount { background: #22c55e33; color: var(--green); }

  .prizes { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
  @media (max-width: 620px) { .prizes { grid-template-columns: repeat(2, 1fr); } }
  .prize {
    background: var(--card2); border: 1px solid var(--border); border-radius: 12px;
    overflow: hidden; transition: transform .12s, border-color .15s;
  }
  .prize:hover { transform: translateY(-2px); border-color: var(--blue); }
  .prize .thumb { background: #0b0f14; display: flex; align-items: center; justify-content: center; height: 90px; }
  .prize .thumb img { max-height: 70px; max-width: 100%; }
  .prize .meta { padding: 8px 10px; }
  .prize .pname { font-size: 11.5px; font-weight: 600; line-height: 1.25; height: 29px; overflow: hidden; }
  .prize .prow { display: flex; align-items: center; justify-content: space-between; margin-top: 5px; }
  .prize .pprice { font-size: 13px; font-weight: 700; color: var(--green); }
  .prize .pdate { font-size: 10px; color: var(--muted); }
  .prize .pexterior { font-size: 10px; color: var(--blue); }
  .empty {
    grid-column: 1 / -1; background: var(--card2); border-radius: 10px;
    padding: 16px; color: var(--muted); font-size: 12px; font-style: italic; text-align: center;
  }

  #log {
    background: #0b0f14; border: 1px solid #1a2a45; border-radius: 10px;
    padding: 10px; height: 220px; overflow-y: auto;
    font-family: Consolas, "Cascadia Mono", monospace; font-size: 11.5px;
    line-height: 1.7;
  }
  #log .line { color: var(--blue); white-space: pre-wrap; word-break: break-word; }
  #log .line.g { color: var(--green); }
  #log .line.r { color: var(--red); }
  #log .line.y { color: var(--amber); }
  #log .line.c { color: var(--cyan); }
  #log .line.m { color: var(--muted); }

  .sessline {
    display: flex; align-items: center; gap: 8px;
    background: var(--card2); border: 1px solid var(--border);
    border-radius: 10px; padding: 8px 12px; font-size: 12.5px;
  }
  .sessline .ok { color: var(--green); font-weight: 600; }
  .sessline .no { color: var(--amber); font-weight: 600; }

  textarea {
    width: 100%; height: 110px; background: #0b0f14; color: var(--text);
    border: 1px solid var(--border); border-radius: 10px; padding: 9px;
    font-family: Consolas, monospace; font-size: 11px; resize: vertical;
  }

  footer { margin-top: 22px; text-align: center; font-size: 10px; color: #2a3350; display: flex; gap: 8px; justify-content: center; align-items: center; }
  .chip {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 2px 9px; border-radius: 12px; font-size: 11px; font-weight: 600;
    background: #22c55e22; color: var(--green);
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="brand">
      <div class="logo">🎮</div>
      <div>
        <h1>TakeMySkins Automator</h1>
        <p>Raffle bot 24/7 · Cloudflare</p>
      </div>
    </div>
    <div class="pill"><span class="dot" id="dot"></span><span id="rt">Idle</span></div>
  </header>

  <div class="grid">
    <div class="card">
      <div class="head">
        <div class="ic" style="background:#22c55e22;">🔑</div>
        <div><div class="t">Sesiune</div><div class="s">Contul conectat la bot</div></div>
      </div>
      <div class="body">
        <div class="sessline" id="sess">Verific sesiunea...</div>
        <details>
          <summary style="cursor:pointer;font-size:12px;color:var(--muted)">Actualizeaza cookies manual</summary>
          <textarea id="cookiestext" placeholder='{"cookies":[{"name":"takemyskins_session","value":"..."}]}'></textarea>
          <button class="btn b-blue" id="btnsave" style="margin-top:7px">Salveaza cookies</button>
        </details>
      </div>
    </div>

    <div class="card">
      <div class="head">
        <div class="ic" style="background:#22c55e22;">🚀</div>
        <div><div class="t">Verificare</div><div class="s">Ruleaza manual sau asteapta cron-ul</div></div>
      </div>
      <div class="body">
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <button class="btn b-green" id="btncheck">Ruleaza verificarea</button>
          <button class="btn b-gray" id="btnrefresh">⟳ Refresh</button>
        </div>
        <div class="statusline" id="status">Astept comenzi...</div>
        <div style="display:flex;align-items:center;gap:6px;color:var(--muted);font-size:11px;">⏱ Cron automat la fiecare 6 ore</div>
      </div>
    </div>
  </div>

  <div style="height:14px;"></div>

  <div class="card">
    <div class="head">
      <div class="ic" style="background:#8b5cf622;">📊</div>
      <div><div class="t">Statistici site</div><div class="s">Date live de pe takemyskins.com</div></div>
    </div>
    <div class="stats" id="stats"></div>
  </div>

  <div style="height:14px;"></div>

  <div class="card">
    <div class="head">
      <div class="ic" style="background:#22c55e22;">🏆</div>
      <div><div class="t">Prizele mele</div><div class="s">Cistiguri de pe profilul meu</div></div>
    </div>
    <div class="tabs">
      <button class="tab active" data-tab="active" id="tabbtn_active">Active <span id="tc_a" class="tabcount">0</span></button>
      <button class="tab" data-tab="history" id="tabbtn_history">Istoric <span id="tc_h" class="tabcount">0</span></button>
    </div>
    <div class="prizes" id="prizes_active"></div>
    <div class="prizes" id="prizes_history" style="display:none;"></div>
  </div>

  <div style="height:14px;"></div>

  <div class="card">
    <div class="head">
      <div class="ic" style="background:#22d3ee22;">⌨️</div>
      <div><div class="t">Log</div><div class="s">Iesirea in timp real</div></div>
    </div>
    <div id="log"></div>
  </div>

  <footer>
    <span class="chip">API connected</span>
    <span class="chip">Session KV</span>
    <span style="margin-left:4px;">v3.0 · Cloudflare Workers</span>
  </footer>
</div>

<script>
const $ = (id) => document.getElementById(id);
function esc(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
let lastN = 0;

async function pollLogs() {
  try {
    const r = await fetch("/api/logs?after=" + lastN);
    const d = await r.json();
    if (d.lines && d.lines.length) {
      lastN = d.count;
      const el = $("log");
      d.lines.forEach(l => {
        const div = document.createElement("div");
        div.className = "line " + (l.color || "b");
        div.textContent = "[" + l.time + "] " + l.msg;
        el.appendChild(div);
      });
      el.scrollTop = el.scrollHeight;
    }
  } catch (e) {}
}

async function pollStatus() {
  try {
    const r = await fetch("/api/status");
    const d = await r.json();
    $("dot").className = "dot " + (d.last && d.last.finishedAt ? "ok" : "");
    $("rt").textContent = d.last ? ("Ultima: " + new Date(d.last.finishedAt).toLocaleString("ro-RO")) : "Idle";
    if (d.session) $("sess").innerHTML = '<span class="ok">● Conectat: ' + esc(d.session.nickname || "?") + '</span>';
    else $("sess").innerHTML = '<span class="no">● Nu esti logat — adauga cookies mai jos</span>';
    if (d.winnings && !d.winnings.error) {
      const w = d.winnings;
      $("stats").innerHTML =
        '<div class="stat"><div class="l">Rafle participat</div><div class="v">' + w.participated + '</div></div>' +
        '<div class="stat"><div class="l">Prize cistigate</div><div class="v" style="color:var(--green)">' + w.won_count + '</div></div>' +
        '<div class="stat"><div class="l">Valoare totala</div><div class="v" style="font-size:22px;padding-top:6px;">$' + (+w.won_cost).toFixed(2) + '</div></div>';
      $("tc_a").textContent = w.active_count;
      $("tc_h").textContent = w.history_count;
      renderP("prizes_active", w.active, "Niciun premiu activ. Cele noi apar aici.");
      renderP("prizes_history", w.history, "Niciun premiu luat inca pe cont.");
    }
  } catch (e) {}
}

function renderP(id, items, msg) {
  const el = $(id);
  if (!items || !items.length) { el.innerHTML = '<div class="empty">' + esc(msg) + '</div>'; return; }
  el.innerHTML = items.map(p =>
    '<div class="prize" onclick="window.open(this.dataset.url)" data-url="' + esc(p.url || "https://takemyskins.com/") + '" title="' + esc(p.name) + '">' +
    '<div class="thumb">' + (p.image ? '<img src="' + esc(p.image) + '" loading="lazy">' : '🎁') + '</div>' +
    '<div class="meta"><div class="pname">' + esc(p.name) + '</div>' +
    '<div class="prow"><span class="pprice">$' + (+p.price).toFixed(2) + '</span><span class="pdate">' + esc(String(p.time_finished || "").slice(0, 10)) + '</span></div>' +
    (p.exterior ? '<div class="pexterior">' + esc(p.exterior) + '</div>' : '') +
    '</div></div>').join("");
}

document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    $("prizes_active").style.display = tab.dataset.tab === "active" ? "grid" : "none";
    $("prizes_history").style.display = tab.dataset.tab === "history" ? "grid" : "none";
  });
});

$("btncheck").addEventListener("click", async () => {
  $("status").textContent = "Se ruleaza... (poate dura ~1 min)";
  try {
    const r = await fetch("/api/check", { method: "POST" });
    const d = await r.json();
    $("status").textContent = d.ok ? ("Gata: " + d.joined + " noi, " + d.already + " deja") : (d.error || "Eroare");
  } catch (e) { $("status").textContent = "Eroare retea"; }
});
$("btnrefresh").addEventListener("click", () => { pollStatus(); pollLogs(); });
$("btnsave").addEventListener("click", async () => {
  try {
    JSON.parse($("cookiestext").value.trim());
    const r = await fetch("/admin/session", { method: "POST", headers: { "content-type": "application/json" }, body: $("cookiestext").value.trim() });
    const d = await r.json();
    $("status").textContent = d.ok ? "Cookies salvate!" : "Eroare: " + d.error;
  } catch (e) { $("status").textContent = "JSON invalid!"; }
});

pollStatus(); pollLogs();
setInterval(pollLogs, 3000);
setInterval(pollStatus, 30000);
</script>
</body>
</html>`);
}

// ── router ─────────────────────────────────────────────────────────────
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path === "/healthz") return json({ ok: true });

    // Link stabil catre tunelul G4f de pe PC-ul utilizatorului
    if (path === "/g4f") {
      const target = await env.SESSION_KV.get("g4f:url");
      if (!target) return html("<h1>G4f offline</h1><p>PC-ul nu e pornit sau tunelul nu e activ.</p><a href='/'>&larr; inapoi</a>");
      return new Response(null, { status: 302, headers: { Location: target } });
    }

    if (path === "/") return dashboardHTML();

    if (path === "/api/logs") {
      const after = parseInt(url.searchParams.get("after") || "0", 10);
      const logs = await getLogs(env);
      return json({ count: logs.length, lines: logs.slice(after) });
    }

    if (path === "/api/status") {
      const raw = await env.SESSION_KV.get(K_LASTRUN);
      const last = raw ? JSON.parse(raw) : null;
      const me = await apiFetch(env, "/profile/user", { noCsrf: true }).catch(() => null);
      const user = me && me.data && me.data.user;

      // winnings cu cache de 5 minute (evitam bombardarea API-ului TMS)
      let winnings = null;
      try {
        const cachedW = await env.SESSION_KV.get("tms:winnings_cache");
        let wobj = cachedW ? JSON.parse(cachedW) : null;
        if (!wobj || Date.now() - (wobj._ts || 0) > 5 * 60 * 1000) {
          winnings = await getWinnings(env);
          await env.SESSION_KV.put(
            "tms:winnings_cache",
            JSON.stringify({ ...winnings, _ts: Date.now() })
          );
        } else {
          winnings = wobj;
        }
      } catch {}

      return json({
        last,
        session: user ? { nickname: user.nickname, id: user.id } : null,
        winnings,
      });
    }

    if (path === "/api/winnings") {
      return json(await getWinnings(env));
    }

    if (path === "/api/check" && request.method === "POST") {
      // minim 5 minute intre rulari manuale
      const raw = await env.SESSION_KV.get(K_LASTRUN);
      const last = raw ? JSON.parse(raw) : null;
      if (last && last._ts && Date.now() - last._ts < 5 * 60 * 1000) {
        return json({ error: "Abia ai rulat. Asteapta 5 min." }, 429);
      }
      const result = await runCheck(env);
      if (result.ok) await env.SESSION_KV.put(K_LASTRUN, JSON.stringify({ ...result, _ts: Date.now() }));
      return json(result, result.ok ? 200 : 500);
    }

    if (path === "/api/dbg2") {
      const me2 = await apiFetch(env, "/profile/user", { noCsrf: true });
      const uid2 = me2.data.user.id;
      const out = [];
      const cookies2 = await getCookies(env);
      for (const tab of ["items", "items_history"]) {
        const r = await fetch(`${API_BASE}/profile/get_profile_${tab}/${uid2}?game=csgo&limit=64&page=1&sort_field=item_price&sort_direction=desc`, {
          headers: apiHeaders(cookies2),
        });
        const t2 = await r.text();
        out.push({ tab, status: r.status, len: t2.length, head: t2.slice(0, 150) });
      }
      return json(out);
    }

    if (path === "/admin/session-cache" && request.method === "POST") {
      // Helper-ul local publica aici lista de prize (TMS blocheaza inventarul din Workers)
      try {
        const body = await request.json();
        if (!Array.isArray(body.active) || !Array.isArray(body.history)) {
          return json({ ok: false, error: "active/history lipsa" }, 400);
        }
        await env.SESSION_KV.put("tms:prizes_cache", JSON.stringify(body));
        return json({ ok: true, active: body.active.length, history: body.history.length });
      } catch (e) {
        return json({ ok: false, error: e.message }, 400);
      }
    }

    if (path === "/api/g4f-keepalive") {
      return json(await g4fKeepalive(env));
    }

    if (path === "/admin/session" && request.method === "POST") {
      try {
        const body = await request.json();
        const cookies = Array.isArray(body) ? body : body.cookies;
        if (!Array.isArray(cookies) || !cookies.some((c) => c.name === "takemyskins_session")) {
          return json({ ok: false, error: "cookies lipsa sau invalide" }, 400);
        }
        await env.SESSION_KV.put(
          K_COOKIES,
          JSON.stringify({ cookies, saved_at: Date.now() / 1000 })
        );
        await addLog(env, "[SESSION] Cookies actualizate din panou.");
        return json({ ok: true });
      } catch (e) {
        return json({ ok: false, error: e.message }, 400);
      }
    }

    return html("<h1>404</h1><a href='/'>← dashboard</a>");
  },

  async scheduled(event, env, ctx) {
    ctx.waitUntil(runCheck(env));
    ctx.waitUntil(g4fKeepalive(env));
  },
};
