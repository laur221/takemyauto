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

// ── G4F panel: lista rulari + dispatch actiuni ─────────────────────────
const GH_HEADERS = (tok) => ({
  Authorization: `Bearer ${tok}`,
  Accept: "application/vnd.github+json",
  "User-Agent": "takemyauto-worker",
});

async function g4fRuns(env) {
  const tok = env.GH_TOKEN;
  if (!tok) return { error: "no token" };
  const r = await fetch(
    "https://api.github.com/repos/laur221/G4f/actions/workflows/341710200/runs?per_page=15",
    { headers: GH_HEADERS(tok) }
  );
  if (!r.ok) return { error: "gh " + r.status };
  const d = await r.json();
  return {
    runs: (d.workflow_runs || []).map((x) => ({
      id: x.id,
      event: x.event === "workflow_dispatch" ? "manual" : "auto",
      status: x.status,
      conclusion: x.conclusion,
      created: x.created_at,
      url: x.html_url,
    })),
  };
}

async function g4fDispatch(env, action) {
  const ALLOWED = ["extend", "start", "stop", "restart", "renew", "status"];
  if (!ALLOWED.includes(action)) return { ok: false, error: "actiune invalida" };
  const tok = env.GH_TOKEN;
  const r = await fetch(
    "https://api.github.com/repos/laur221/G4f/actions/workflows/341710200/dispatches",
    {
      method: "POST",
      headers: { ...GH_HEADERS(tok), "Content-Type": "application/json" },
      body: JSON.stringify({ ref: "main", inputs: { action } }),
    }
  );
  if (r.status === 204) return { ok: true, action };
  return { ok: false, error: "HTTP " + r.status };
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

// Status live G4F din status.json (publicat de fiecare rulare Actions)
async function g4fLive(env) {
  const h = { Accept: "application/vnd.github+json", "User-Agent": "takemyauto-worker" };
  if (env.GH_TOKEN) h.Authorization = `Bearer ${env.GH_TOKEN}`;
  try {
    const r = await fetch(
      "https://api.github.com/repos/laur221/G4f/contents/status.json",
      { headers: h, cf: { cacheTtl: 0 } }
    );
    if (!r.ok) return { error: "gh " + r.status };
    const d = await r.json();
    const raw = (d.content || "").replace(/\s/g, "");
    const bytes = Uint8Array.from(atob(raw), (c) => c.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes));
  } catch (e) {
    return { error: e.message };
  }
}

// ── panou G4F ──────────────────────────────────────────────────────────
function g4fPanelHTML() {
  return html(`<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="UTF-8">
<title>G4F — Serverul Nicu (Cloud)</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Space+Grotesk:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root{
    --pink:#ff3aa3;--lime:#a3e635;--cyan:#27e1ff;
    --purple:#7b3aff;--gold:#fbbf24;--red:#ff5c6c;
    --surface:rgba(16,18,32,0.82);--line:rgba(255,255,255,0.10);--line-2:rgba(255,255,255,0.18);
    --ink:#f5f7fa;--ink-dim:rgba(255,255,255,0.72);--ink-muted:rgba(255,255,255,0.50);--ink-faint:rgba(255,255,255,0.32);
    --pixel:'Press Start 2P',monospace;--sans:'Space Grotesk',system-ui,sans-serif;--mono:'Geist Mono',ui-monospace,monospace;
  }
  *{box-sizing:border-box;}
  html,body{height:100%;}
  body{
    margin:0;font-family:var(--sans);color:var(--ink);
    background:#0a0814;min-height:100vh;display:flex;flex-direction:column;
    align-items:center;justify-content:flex-start;padding:20px;position:relative;overflow-y:auto;
  }
  .bg{position:fixed;inset:0;pointer-events:none;z-index:0;
    background:
      radial-gradient(ellipse 80% 60% at 18% 20%, rgba(255,58,163,.18) 0%, transparent 55%),
      radial-gradient(ellipse 70% 60% at 88% 85%, rgba(123,58,255,.20) 0%, transparent 55%),
      radial-gradient(ellipse 60% 50% at 50% 110%, rgba(39,225,255,.16) 0%, transparent 60%),
      #0a0814;}
  .grid-floor{position:fixed;left:0;right:0;bottom:-10vh;height:55vh;pointer-events:none;z-index:1;
    background-image:
      linear-gradient(rgba(255,58,163,.18) 1px, transparent 1px),
      linear-gradient(90deg, rgba(39,225,255,.18) 1px, transparent 1px);
    background-size:80px 80px;
    transform:perspective(700px) rotateX(60deg);transform-origin:50% 0%;
    mask-image:linear-gradient(to bottom, transparent 0%, black 30%, black 100%);
    -webkit-mask-image:linear-gradient(to bottom, transparent 0%, black 30%, black 100%);
    animation:grid-scroll 8s linear infinite;}
  @keyframes grid-scroll{from{background-position:0 0}to{background-position:0 80px}}
  .scanlines{position:fixed;inset:0;pointer-events:none;z-index:3;
    background:repeating-linear-gradient(to bottom, rgba(255,255,255,.02) 0 1px, transparent 1px 3px);}
  .layout{position:relative;z-index:4;width:100%;max-width:760px;display:flex;
    align-items:flex-start;justify-content:center;gap:20px;flex-direction:column;align-items:center;}
  @media(min-width:740px){.layout{flex-direction:row;align-items:flex-start;}.layout .col-main{max-width:360px;}}
  .col-runs{width:100%;max-width:380px;}
  .card{position:relative;z-index:4;width:100%;max-width:360px;background:var(--surface);
    border:2px solid var(--line);border-radius:14px;padding:24px 22px 22px;overflow:hidden;
    backdrop-filter:blur(20px) saturate(140%);-webkit-backdrop-filter:blur(20px) saturate(140%);
    box-shadow:0 20px 50px rgba(0,0,0,.5);}
  .card::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;
    background:linear-gradient(90deg,var(--pink),var(--lime),var(--cyan),var(--pink));
    background-size:200% 100%;animation:rainbow 5s linear infinite;}
  @keyframes rainbow{from{background-position:0% 0}to{background-position:200% 0}}
  h1{font-family:var(--pixel);font-size:12px;margin:6px 0 16px;text-align:center;color:#fff;
    text-shadow:2px 2px 0 var(--pink),4px 4px 0 rgba(0,0,0,.4);letter-spacing:.02em;line-height:1.6;}
  .status-row{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;}
  .status-pill{display:inline-flex;align-items:center;gap:7px;padding:6px 12px;border-radius:99px;
    font-family:var(--pixel);font-size:8px;letter-spacing:.10em;}
  .status-pill .dot{width:6px;height:6px;border-radius:50%;flex-shrink:0;}
  .status-pill.online{background:rgba(163,230,53,.12);color:var(--lime);}
  .status-pill.online .dot{background:var(--lime);box-shadow:0 0 8px var(--lime);animation:blink 1.4s infinite;}
  .status-pill.offline{background:rgba(255,255,255,.05);color:var(--ink-muted);}
  .status-pill.offline .dot{background:var(--ink-faint);}
  .status-pill.suspended{background:rgba(255,92,108,.12);color:var(--red);}
  .status-pill.suspended .dot{background:var(--red);}
  @keyframes blink{50%{opacity:.35}}
  .time{font-family:var(--mono);font-size:22px;font-weight:500;letter-spacing:.01em;margin:10px 0 4px;text-align:center;}
  .time .unit{font-size:11px;color:var(--ink-muted);margin-left:6px;font-weight:400;}
  .banner{display:none;background:rgba(255,92,108,.10);border:1px solid rgba(255,92,108,.35);
    border-radius:9px;padding:11px 12px;font-family:var(--mono);font-size:11.5px;color:#ffb3bb;
    margin:14px 0;line-height:1.6;text-align:left;}
  .banner.show{display:block;}
  .extend-row{text-align:center;margin:12px 0 4px;}
  .extend-btn{display:inline-flex;align-items:center;gap:6px;padding:10px 18px;border-radius:9px;
    font-family:var(--pixel);font-size:9px;letter-spacing:.08em;cursor:pointer;
    border:2px solid rgba(251,191,36,.45);color:var(--gold);background:rgba(251,191,36,.08);transition:all .15s;}
  .extend-btn:hover:not(:disabled){border-color:var(--gold);background:rgba(251,191,36,.18);box-shadow:0 0 16px rgba(251,191,36,.35);}
  .extend-btn:active:not(:disabled){transform:translateY(1px);}
  .extend-btn:disabled{opacity:.4;cursor:not-allowed;transform:none;}
  .actions{display:flex;gap:8px;margin-top:16px;}
  .pwr-btn{flex:1;display:flex;align-items:center;justify-content:center;gap:8px;padding:12px;
    border-radius:9px;font-family:var(--pixel);font-size:9px;letter-spacing:.08em;cursor:pointer;
    border:2px solid;background:rgba(255,255,255,.03);transition:all .15s;color:var(--ink);}
  .pwr-btn:active{transform:translateY(1px);}
  .pwr-btn:disabled{opacity:.4;cursor:not-allowed;transform:none;}
  .pwr-start{border-color:rgba(163,230,53,.45);color:var(--lime);}
  .pwr-start:hover:not(:disabled){border-color:var(--lime);background:rgba(163,230,53,.12);box-shadow:0 0 14px rgba(163,230,53,.3);}
  .pwr-restart{border-color:rgba(39,225,255,.45);color:var(--cyan);}
  .pwr-restart:hover:not(:disabled){border-color:var(--cyan);background:rgba(39,225,255,.10);box-shadow:0 0 14px rgba(39,225,255,.25);}
  .pwr-stop{border-color:rgba(255,92,108,.45);color:var(--red);}
  .pwr-stop:hover:not(:disabled){border-color:var(--red);background:rgba(255,92,108,.12);box-shadow:0 0 14px rgba(255,92,108,.25);}
  #status{font-family:var(--mono);font-size:11.5px;color:var(--ink-muted);margin-top:14px;min-height:16px;text-align:center;}
  .res-panel{margin-top:16px;padding-top:14px;border-top:1px solid var(--line);}
  .res-panel-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;}
  .res-panel-title{font-family:var(--pixel);font-size:8px;color:#fff;letter-spacing:.10em;}
  .res-live{font-family:var(--mono);font-size:9px;color:var(--lime);}
  .info-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
  .info-box{background:rgba(0,0,0,.25);border:1px solid var(--line);border-radius:8px;padding:9px 10px;}
  .info-box .k{font-family:var(--pixel);font-size:6.5px;color:var(--ink-muted);letter-spacing:.12em;margin-bottom:5px;}
  .info-box .v{font-family:var(--mono);font-size:13px;font-weight:700;color:#fff;}
  table.runs{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:10.5px;}
  table.runs th{text-align:left;font-family:var(--pixel);font-size:7px;color:var(--ink-muted);
    letter-spacing:.10em;padding:6px 8px;border-bottom:1px solid var(--line);}
  table.runs td{padding:7px 8px;border-bottom:1px solid rgba(255,255,255,.05);}
  table.runs tr:last-child td{border-bottom:none;}
  .tag{display:inline-flex;padding:2px 8px;border-radius:99px;font-family:var(--mono);font-size:9px;}
  .t-ok{background:rgba(163,230,53,.12);color:var(--lime);}
  .t-fail{background:rgba(255,92,108,.12);color:var(--red);}
  .t-run{background:rgba(39,225,255,.12);color:var(--cyan);}
  .t-auto{background:rgba(255,255,255,.06);color:var(--ink-muted);}
  .t-manual{background:rgba(123,58,255,.15);color:var(--purple);}
  a.rlink{color:inherit;text-decoration:none;}
  footer{text-align:center;margin-top:16px;font-family:var(--mono);font-size:9.5px;color:var(--ink-faint);}
  button{-webkit-tap-highlight-color:transparent;touch-action:manipulation;}
  a.back{position:fixed;top:14px;right:16px;z-index:9;color:var(--cyan);text-decoration:none;
    font-family:var(--mono);font-size:11px;background:rgba(16,18,32,.7);border:1px solid var(--line);
    padding:6px 10px;border-radius:8px;}
</style></head><body>
  <div class="bg"></div>
  <div class="grid-floor"></div>
  <div class="scanlines"></div>
  <a class="back" href="/">← TMS</a>

  <div class="layout">
  <div class="col-main">
  <div class="card">
    <h1>Serverul Nicu<br>PalWorld — CLOUD</h1>

    <div class="status-row">
      <span class="status-pill offline" id="status-pill">
        <span class="dot"></span><span id="status-label">SE VERIFICA</span>
      </span>
    </div>

    <div class="time"><span id="remaining">--:--:--</span><span class="unit">ramase</span></div>

    <div class="banner" id="warn-banner">
      Mai sunt sub 30 de minute! Botul extinde automat la fiecare 30 min.
    </div>

    <div class="extend-row">
      <button class="extend-btn" id="btn-extend" onclick="run('extend')">+ 90 MIN (AUTO)</button>
    </div>

    <div class="actions">
      <button class="pwr-btn pwr-start" id="b-start" onclick="run('start')">PORNESTE</button>
      <button class="pwr-btn pwr-restart" id="b-restart" onclick="run('restart')">RESTART</button>
      <button class="pwr-btn pwr-stop" id="b-stop" onclick="run('stop')">OPRESTE</button>
    </div>

    <div id="status">Conectat la GitHub Actions...</div>

    <!-- AUTO-EXTEND (config live din workflow) -->
    <div class="res-panel">
      <div class="res-panel-head">
        <span class="res-panel-title">AUTO-EXTEND</span>
        <span class="res-live">ACTIV</span>
      </div>
      <div class="info-grid">
        <div class="info-box"><div class="k">TARGET</div><div class="v">48h</div></div>
        <div class="info-box"><div class="k">RECLAME / RUN</div><div class="v">max 15</div></div>
        <div class="info-box"><div class="k">CRON</div><div class="v">30 min</div></div>
        <div class="info-box"><div class="k">ULTIMA EXTEND</div><div class="v" style="font-size:10px" id="last-extend">—</div></div>
      </div>
    </div>
  </div>

  <div class="col-runs">
  <div class="card" style="max-width:100%;">
    <h1 style="margin-bottom:12px;">ISTORIC RULARI</h1>
    <table class="runs">
      <thead><tr><th>CAND</th><th>TIP</th><th>REZULTAT</th></tr></thead>
      <tbody id="runs"><tr><td colspan="3" style="color:var(--ink-muted)">se incarca...</td></tr></tbody>
    </table>
  </div>
  </div>
  </div>

<footer>G4F Auto-Extend · GitHub Actions · reactivare automata</footer>

<script>
const $=(i)=>document.getElementById(i);
function esc(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
let busy=false;

function setPill(state){
  const pill=$('status-pill'), lbl=$('status-label');
  pill.className='status-pill '+state;
  lbl.textContent=state==='online'?'ONLINE':state==='offline'?'OFFLINE':state==='suspended'?'SUSPENDED':'SE VERIFICA';
}

async function pollLive(){
 try{
  const r=await fetch('/api/g4f/live'); const d=await r.json();
  if(d.error||!d.ok&&d.error){$('status').textContent='Eroare: '+(d.error||'necunoscut');return}
  if(d.remainingLabel)$('remaining').textContent=d.remainingLabel;
  setPill(d.suspended?'suspended':d.online?'online':'offline');
  const b=$('warn-banner');
  if(typeof d.remainingSeconds==='number'&&d.remainingSeconds<1800)b.classList.add('show');else b.classList.remove('show');
  if(d.action){$('last-extend').textContent=(d.action==='extend'&&d.ok)?('+'+(d.addedMinutes||90)+' min'):(d.action+' '+(d.ok?'✓':'✗'));}
 }catch(e){}
}

async function pollRuns(){
 try{
  const r=await fetch('/api/g4f/runs'); const d=await r.json();
  if(d.error)return;
  $('runs').innerHTML=d.runs.map(x=>{
   const when=new Date(x.created).toLocaleString('ro-RO',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
   const kind=x.event==='manual'?'<span class="tag t-manual">manual</span>':'<span class="tag t-auto">auto</span>';
   let res;
   if(x.status!=='completed')res='<span class="tag t-run">ruleaza...</span>';
   else if(x.conclusion==='success')res='<span class="tag t-ok">✓ success</span>';
   else if(x.conclusion==='failure')res='<span class="tag t-fail">✗ esuat</span>';
   else res='<span class="tag t-auto">'+esc(x.conclusion||'-')+'</span>';
   return '<tr><td>'+esc(when)+'</td><td>'+kind+'</td><td><a class="rlink" href="'+esc(x.url)+'" target="_blank">'+res+'</a></td></tr>';
  }).join('');
 }catch(e){}
}

async function run(action){
 if(busy)return; busy=true;
 $('status').textContent='Trimit "'+action+'" catre GitHub Actions...';
 document.querySelectorAll('.extend-btn,.pwr-btn').forEach(b=>b.disabled=true);
 try{
  const r=await fetch('/api/g4f/run',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({action})});
  const d=await r.json();
  $('status').textContent=d.ok?('Comanda pornita! Statusul se actualizeaza in ~1-2 min.') :('Eroare: '+(d.error||'?'));
  setTimeout(()=>{pollRuns();},4000);
  setTimeout(()=>{pollRuns();pollLive();},90000);
 }catch(e){$('status').textContent='Eroare retea'}
 document.querySelectorAll('.extend-btn,.pwr-btn').forEach(b=>b.disabled=false);
 busy=false;
}
window.run=run;

pollLive();pollRuns();
setInterval(pollLive,30000);
setInterval(pollRuns,20000);
</script></body></html>`);
}

// ── router ─────────────────────────────────────────────────────────────
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path === "/healthz") return json({ ok: true });

    if (path === "/") return dashboardHTML();

    // Panoul de control G4F (conectat la GitHub Actions)
    if (path === "/g4f") return g4fPanelHTML();

    if (path === "/api/g4f/runs") {
      return json(await g4fRuns(env));
    }

    if (path === "/api/g4f/live") {
      return json(await g4fLive(env));
    }

    if (path === "/api/g4f/run" && request.method === "POST") {
      const body = await request.json().catch(() => ({}));
      return json(await g4fDispatch(env, body.action));
    }

    if (path === "/api/g4f-keepalive") {
      return json(await g4fKeepalive(env));
    }

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
