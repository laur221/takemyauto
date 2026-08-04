"""TakeMySkins Automator - Web dashboard (HTML/CSS/JS served by Flask)."""

PAGE_TITLE = "TakeMySkins Automator"

INDEX_HTML = """<!DOCTYPE html>
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
  .dot.run   { background: var(--blue);  box-shadow: 0 0 8px var(--blue); animation: pulse 1s infinite; }
  .dot.ok    { background: var(--green); box-shadow: 0 0 8px var(--green); }
  .dot.err   { background: var(--red);   box-shadow: 0 0 8px var(--red); }
  .dot.idle  { background: #3f4650; }
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
  .b-cyan  { background: #0e7490; }
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

  .hist { margin-top: 14px; }
  .hist h3 { font-size: 13px; font-weight: 700; margin-bottom: 8px; }
  .hist-row {
    display: flex; align-items: center; gap: 10px;
    background: var(--card2); border-radius: 8px; padding: 7px 10px;
    font-size: 12.5px; margin-bottom: 6px;
  }
  .hist-row .item { flex: 1; }
  .hist-row .date { color: var(--muted); font-size: 11px; }
  .chip {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 2px 9px; border-radius: 12px; font-size: 11px; font-weight: 600;
    background: #22c55e22; color: var(--green);
  }
  .chip.other { background: #8b949e22; color: var(--muted); }

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

  .qrbox { display: none; flex-direction: column; align-items: center; gap: 8px; padding-top: 6px; }
  .qrbox.show { display: flex; }
  .qrbox img { width: 200px; height: 200px; border-radius: 12px; background: #fff; padding: 8px; }
  .qrbox .qstat { font-size: 13px; color: var(--green); }

  footer { margin-top: 22px; text-align: center; font-size: 10px; color: #2a3350; display: flex; gap: 8px; justify-content: center; align-items: center; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="brand">
      <div class="logo">🎮</div>
      <div>
        <h1>TakeMySkins Automator</h1>
        <p>Raffle bot 24/7</p>
      </div>
    </div>
    <div class="pill"><span class="dot idle" id="dot"></span><span id="rt">Idle</span></div>
  </header>

  <div class="grid">
    <div class="card">
      <div class="head">
        <div class="ic" style="background:#22d3ee22;">🔐</div>
        <div><div class="t">Login Steam</div><div class="s">Conecteaza-te o singura data</div></div>
      </div>
      <div class="body">
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <button class="btn b-blue" id="btnqr">Genereaza QR Steam</button>
          <button class="btn b-cyan" id="btnsteam">Steam Login</button>
          <button class="btn b-green" id="btntms">TakeMySkins</button>
        </div>
        <div class="qrbox" id="qrbox">
          <img id="qrimg" alt="Steam QR">
          <div class="qstat" id="qrstat"></div>
        </div>
        <div class="statusline" id="qrmsg"></div>
      </div>
    </div>

    <div class="card">
      <div class="head">
        <div class="ic" style="background:#22c55e22;">🚀</div>
        <div><div class="t">Verificare</div><div class="s">Ruleaza manual sau asteapta programarea</div></div>
      </div>
      <div class="body">
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <button class="btn b-green" id="btncheck">Ruleaza verificarea</button>
          <button class="btn b-gray" id="btnrefresh">⟳ Refresh</button>
        </div>
        <div class="statusline" id="status">Astept comenzi...</div>
        <div style="display:flex;align-items:center;gap:6px;color:var(--muted);font-size:11px;">⏱ Scheduler automat la fiecare 6 ore</div>
      </div>
    </div>
  </div>

  <div style="height:14px;"></div>

  <div class="card">
    <div class="head">
      <div class="ic" style="background:#8b5cf622;">📊</div>
      <div><div class="t">Statistici</div><div class="s">Rezultatele si istoricul</div></div>
    </div>
    <div class="body">
      <div class="stats" id="stats"></div>
      <div class="hist" id="hist"></div>
    </div>
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
    <span class="chip">Steam session</span>
    <span style="margin-left:4px;">v2.0 · Render Free</span>
  </footer>
</div>

<script>
const $ = (id) => document.getElementById(id);
const DOT = { idle: "idle", run: "run", ok: "ok", err: "err" };
const RT  = { idle: "Idle", run: "Ruleaza...", ok: "Terminat", err: "Eroare" };
let lastLogCount = 0;

async function post(url) {
  try {
    const r = await fetch(url, { method: "POST" });
    const d = await r.json();
    if (!r.ok && d.error) setStatus(d.error, "var(--red)");
    return d;
  } catch (e) { setStatus("Eroare retea: " + e, "var(--red)"); }
}

function setStatus(msg, color) {
  $("status").textContent = msg;
  $("status").style.color = color || "var(--muted)";
}
function setRuntime(state) {
  $("dot").className = "dot " + DOT[state];
  $("rt").textContent = RT[state];
}

function esc(s) {
  return String(s).replace(/[&<>]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;" }[c]));
}
function renderLog(lines) {
  if (!lines || !lines.length) return;
  const el = $("log");
  lines.forEach(l => {
    const cls = l.color || "b";
    const div = document.createElement("div");
    div.className = "line " + cls;
    div.textContent = "[" + l.time + "] " + l.msg;
    el.appendChild(div);
  });
  el.scrollTop = el.scrollHeight;
}
async function pollLogs() {
  try {
    const r = await fetch("/api/logs?after=" + lastLogCount);
    const d = await r.json();
    if (d.lines && d.lines.length) {
      lastLogCount = d.count;
      renderLog(d.lines);
    }
  } catch (e) {}
}

async function pollStats() {
  try {
    const r = await fetch("/api/stats");
    const d = await r.json();
    $("stats").innerHTML =
      '<div class="stat"><div class="l">Rafle verificate</div><div class="v">' + d.total + '</div></div>' +
      '<div class="stat"><div class="l">Castiguri</div><div class="v" style="color:var(--green)">' + d.wins.length + '</div></div>' +
      '<div class="stat"><div class="l">Ultima rulare</div><div class="v" style="font-size:18px;padding-top:10px;">' + esc(d.last_run) + '</div></div>';
    const hist = $("hist");
    if (d.wins.length) {
      let rows = '<h3>Istoric recent</h3>';
      d.wins.slice(0, 15).forEach(w => {
        const won = String(w.status).toUpperCase() === "WON";
        rows += '<div class="hist-row"><span>' + (won ? "🏆" : "📅") + '</span>' +
                '<span class="item">' + esc(String(w.item).slice(0, 34)) + '</span>' +
                '<span class="chip' + (won ? "" : " other") + '">' + esc(w.status) + '</span>' +
                '<span class="date">' + esc(String(w.date).slice(0, 16)) + '</span></div>';
      });
      hist.innerHTML = rows;
    } else {
      hist.innerHTML = '<div style="background:var(--card2);border-radius:10px;padding:12px;color:var(--muted);font-size:12px;font-style:italic;">Niciun castig inca. Ele vor aparea automat aici.</div>';
    }
  } catch (e) {}
}

async function pollQr() {
  try {
    const r = await fetch("/api/qr");
    const d = await r.json();
    const box = $("qrbox");
    if (d.image) {
      box.classList.add("show");
      $("qrimg").src = "data:image/png;base64," + d.image;
      $("qrstat").textContent = d.message || "Scaneaza codul QR cu Steam Mobile";
    } else if (d.status === "idle") {
      box.classList.remove("show");
    } else {
      box.classList.add("show");
      $("qrimg").removeAttribute("src");
      $("qrstat").textContent = d.message || "";
      $("qrstat").style.color = d.ok ? "var(--green)" : "var(--amber)";
    }
  } catch (e) {}
}

async function pollRuntime() {
  try {
    const r = await fetch("/api/runtime");
    const d = await r.json();
    setRuntime(d.state);
  } catch (e) {}
}

$("btnqr").addEventListener("click", () => { setStatus("Se genereaza QR...", "var(--cyan)"); post("/api/qr"); });
$("btncheck").addEventListener("click", () => { post("/api/check"); });
$("btnrefresh").addEventListener("click", () => { pollStats(); setStatus("Statistici actualizate", "var(--green)"); });
$("btnsteam").addEventListener("click", () => window.open("https://store.steampowered.com/login/", "_blank"));
$("btntms").addEventListener("click", () => window.open("https://takemyskins.com/", "_blank"));

setInterval(pollLogs, 1000);
setInterval(pollStats, 5000);
setInterval(pollQr, 1500);
setInterval(pollRuntime, 2000);
pollLogs(); pollStats(); pollQr(); pollRuntime();
</script>
</body>
</html>
"""
