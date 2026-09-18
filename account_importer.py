"""Local tool: paste exported browser cookies, get them saved into the
account pool automatically - no need to hand them over manually each time.

Run: python account_importer.py
Then open http://127.0.0.1:8090 in a browser.
"""
import json

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from db_manager import DBManager
from engine import RaffleBot

db = DBManager()
bot = RaffleBot(db)

app = FastAPI(title="Account Importer")


@app.get("/", response_class=HTMLResponse)
def index():
    return INDEX_HTML


@app.get("/api/accounts")
def api_accounts():
    return {"accounts": bot.list_accounts()}


@app.post("/api/import")
def api_import(payload: dict):
    raw = payload.get("cookies")
    if raw is None:
        return JSONResponse({"error": "Lipseste campul cookies."}, status_code=400)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return JSONResponse({"error": "JSON invalid."}, status_code=400)
    cookies = raw if isinstance(raw, list) else raw.get("cookies", [])
    if not cookies:
        return JSONResponse({"error": "Nu am gasit cookie-uri in text."}, status_code=400)

    steam_id, nickname = bot._identity_from_cookies(cookies, log=print)
    if not steam_id:
        return JSONResponse(
            {"error": "Nu am putut identifica contul (cookie-uri de domeniu gresit sau expirate)."},
            status_code=422,
        )
    bot.save_cookies(cookies, log=print, steam_id=steam_id, nickname=nickname)
    return {"ok": True, "steam_id": steam_id, "nickname": nickname or steam_id}


@app.post("/api/switch")
def api_switch(payload: dict):
    steam_id = payload.get("steam_id")
    if not steam_id or not bot.switch_account(steam_id):
        return JSONResponse({"error": "Cont necunoscut."}, status_code=404)
    return {"ok": True}


@app.post("/api/delete")
def api_delete(payload: dict):
    steam_id = payload.get("steam_id")
    if not steam_id:
        return JSONResponse({"error": "Lipseste steam_id."}, status_code=400)
    db.clear_session(steam_id)
    return {"ok": True}


INDEX_HTML = """<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Account Importer</title>
<style>
  :root {
    --bg: #0a0e17; --card: #111827; --card2: #151b2b; --border: #1f2a3f;
    --text: #e6edf3; --muted: #8b949e; --blue: #3b82f6; --green: #22c55e;
    --red: #ef4444; --amber: #f59e0b; --cyan: #22d3ee; --purple: #8b5cf6;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: radial-gradient(1200px 600px at 15% -10%, #16204a55, transparent 60%),
                radial-gradient(900px 500px at 100% 0%, #2a1a4d44, transparent 55%),
                var(--bg);
    color: var(--text);
    font-family: "Segoe UI", -apple-system, Roboto, Helvetica, Arial, sans-serif;
    min-height: 100vh; padding: 0 0 30px;
  }
  .wrap { max-width: 760px; margin: 0 auto; padding: 0 20px; }
  header { display: flex; align-items: center; gap: 12px; padding: 22px 0; border-bottom: 1px solid var(--border); margin-bottom: 18px; }
  .logo { width: 42px; height: 42px; border-radius: 12px; display: flex; align-items: center; justify-content: center;
          background: linear-gradient(135deg, var(--blue), var(--purple)); font-size: 20px; box-shadow: 0 4px 16px #3b82f655; }
  header h1 { font-size: 18px; font-weight: 700; }
  header p { font-size: 11.5px; color: var(--muted); margin-top: 1px; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 18px; box-shadow: 0 6px 18px #0003; margin-bottom: 16px; }
  .card h2 { font-size: 14px; font-weight: 700; margin-bottom: 10px; }
  textarea {
    width: 100%; min-height: 180px; background: #0b0f14; border: 1px solid var(--border);
    border-radius: 10px; color: var(--text); font-family: Consolas, "Cascadia Mono", monospace;
    font-size: 12px; padding: 12px; resize: vertical;
  }
  textarea:focus { outline: none; border-color: var(--blue); }
  .btn {
    display: inline-flex; align-items: center; gap: 8px; border: none; border-radius: 10px;
    padding: 11px 18px; font-size: 13px; font-weight: 600; color: #fff; cursor: pointer;
    transition: filter .15s; font-family: inherit; margin-top: 12px;
  }
  .btn:hover { filter: brightness(1.1); }
  .btn:disabled { opacity: .55; cursor: not-allowed; }
  .b-blue { background: var(--blue); }
  .msg { margin-top: 10px; font-size: 13px; min-height: 18px; }
  .msg.ok { color: var(--green); } .msg.err { color: var(--red); }
  .acc-row {
    display: flex; align-items: center; justify-content: space-between; gap: 10px;
    background: var(--card2); border: 1px solid var(--border); border-radius: 10px;
    padding: 10px 14px; margin-bottom: 8px; font-size: 13px;
  }
  .acc-row .name { display: flex; align-items: center; gap: 8px; }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: #3f4650; }
  .dot.on { background: var(--green); box-shadow: 0 0 6px var(--green); }
  .acc-row .id { color: var(--muted); font-size: 11px; }
  .acc-actions { display: flex; gap: 6px; }
  .b-mini { padding: 5px 10px; font-size: 11px; margin-top: 0; }
  .b-gray { background: #1f2937; color: var(--muted); }
  .b-red { background: #7f1d1d; }
  .empty { color: var(--muted); font-size: 12.5px; font-style: italic; padding: 6px 0; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="logo">📥</div>
    <div><h1>Account Importer</h1><p>Lipeste cookie-uri exportate din browser, se salveaza automat</p></div>
  </header>

  <div class="card">
    <h2>Import cont nou</h2>
    <textarea id="cookies" placeholder='Lipeste aici JSON-ul exportat (Cookie-Editor -> Export as JSON) de pe takemyskins.com'></textarea>
    <button class="btn b-blue" id="btnImport">Importa contul</button>
    <div class="msg" id="msg"></div>
  </div>

  <div class="card">
    <h2>Conturi salvate</h2>
    <div id="accounts"></div>
  </div>
</div>

<script>
const $ = id => document.getElementById(id);
function esc(s) { return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }

async function loadAccounts() {
  const r = await fetch("/api/accounts");
  const d = await r.json();
  const box = $("accounts");
  if (!d.accounts || !d.accounts.length) { box.innerHTML = '<div class="empty">Niciun cont salvat inca.</div>'; return; }
  box.innerHTML = d.accounts.map(a => `
    <div class="acc-row">
      <div class="name"><span class="dot ${a.active ? 'on' : ''}"></span>${esc(a.nickname)} <span class="id">${esc(a.steam_id)}</span></div>
      <div class="acc-actions">
        ${a.active ? '<span style="color:var(--muted);font-size:11px;">activ</span>' :
          `<button class="btn b-gray b-mini" onclick="switchAcc('${a.steam_id}')">Foloseste</button>`}
        <button class="btn b-red b-mini" onclick="deleteAcc('${a.steam_id}')">Sterge</button>
      </div>
    </div>
  `).join("");
}

async function switchAcc(steamId) {
  await fetch("/api/switch", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({steam_id: steamId}) });
  loadAccounts();
}
async function deleteAcc(steamId) {
  if (!confirm("Sigur stergi acest cont din DB?")) return;
  await fetch("/api/delete", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({steam_id: steamId}) });
  loadAccounts();
}

$("btnImport").addEventListener("click", async () => {
  const text = $("cookies").value.trim();
  const msg = $("msg");
  msg.className = "msg"; msg.textContent = "";
  if (!text) { msg.className = "msg err"; msg.textContent = "Lipeste intai un JSON de cookie-uri."; return; }

  let cookies;
  try { cookies = JSON.parse(text); }
  catch (e) { msg.className = "msg err"; msg.textContent = "JSON invalid: " + e.message; return; }

  $("btnImport").disabled = true;
  msg.textContent = "Se importa...";
  try {
    const r = await fetch("/api/import", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({cookies}) });
    const d = await r.json();
    if (d.error) { msg.className = "msg err"; msg.textContent = d.error; }
    else {
      msg.className = "msg ok"; msg.textContent = `Cont importat si activat: ${d.nickname}`;
      $("cookies").value = "";
      loadAccounts();
    }
  } catch (e) { msg.className = "msg err"; msg.textContent = "Eroare retea: " + e; }
  $("btnImport").disabled = false;
});

loadAccounts();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn

    print("Account Importer -> http://127.0.0.1:8090")
    uvicorn.run(app, host="127.0.0.1", port=8090)
