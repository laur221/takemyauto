export default {
  async fetch(request, env) {
    const cookies = await env.SESSION_KV.get("tms:cookies");
    const arr = JSON.parse(cookies).cookies || [];
    const ck = arr.map(c => c.name + "=" + c.value).join("; ");
    const r = await fetch("https://httpbin.org/anything", { headers: {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      "Accept": "application/json, text/plain, */*",
      "Content-Type": "application/json",
      "X-Frontend-Version": "23.07.2026_7dade",
      "X-Requested-With": "XMLHttpRequest",
      "Origin": "https://takemyskins.com",
      "Referer": "https://takemyskins.com/",
      "Cookie": ck
    }});
    const d = await r.json();
    return new Response(JSON.stringify({headers: d.headers, cookie_len: (d.headers.Cookie||"").length}), {headers:{"content-type":"application/json"}});
  }
}
