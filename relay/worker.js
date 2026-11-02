/*
  Pigeon relay + viewer host (Cloudflare Worker)
  Signalling for encrypted P2P sharing, IP geolocation, ham-RF board — and it
  serves the Pigeon web app (fetched from the public repo) so a share link
  https://<this-worker>/#view=room.key~relay opens the live map in any browser.
  KV namespace bound as SIG.
*/
const TTL = 300;
const cors = { "access-control-allow-origin": "*", "access-control-allow-methods": "GET,POST,OPTIONS", "access-control-allow-headers": "content-type" };
const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { "content-type": "application/json", ...cors } });
function iceServers(){ return [
  { urls: "stun:stun.l.google.com:19302" }, { urls: "stun:stun.cloudflare.com:3478" },
  { urls: "turn:openrelay.metered.ca:80", username: "openrelayproject", credential: "openrelayproject" },
  { urls: "turn:openrelay.metered.ca:443", username: "openrelayproject", credential: "openrelayproject" },
  { urls: "turn:openrelay.metered.ca:443?transport=tcp", username: "openrelayproject", credential: "openrelayproject" } ]; }
const roomOk = (s) => /^[A-Za-z0-9_-]{6,64}$/.test(s || "");
const APP_URL = "https://raw.githubusercontent.com/BajanBob/Pigeon/main/www/index.html";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });
    if (path === "/ice") return json({ iceServers: iceServers() });
    if (path === "/where") { const cf = request.cf || {}; const lat = parseFloat(cf.latitude), lon = parseFloat(cf.longitude);
      return json({ lat: Number.isFinite(lat)?Math.round(lat*1000)/1000:null, lon: Number.isFinite(lon)?Math.round(lon*1000)/1000:null, city: cf.city||"", approx:true, source:"ip" }); }
    if (path === "/rf") {
      if (request.method === "POST") { let b; try{ b = await request.json(); }catch(e){ return json({error:"bad json"},400); }
        const call = String(b.callsign||"").toUpperCase().slice(0,12); if(!/^[A-Z0-9/]{3,12}$/.test(call)) return json({error:"bad callsign"},400);
        const st = { callsign:call, grid:String(b.grid||"").slice(0,8), lat:Number(b.lat), lon:Number(b.lon), ts:Number(b.ts)||Date.now(), mode:String(b.mode||"PigeonFSK").slice(0,16) };
        await env.SIG.put("rf:"+call, JSON.stringify(st), { expirationTtl: 3600 }); return json({ ok:true }); }
      if (request.method === "GET") { const list = await env.SIG.list({ prefix:"rf:" }); const stations=[];
        for (const k of list.keys){ const raw = await env.SIG.get(k.name); if(raw){ try{ stations.push(JSON.parse(raw)); }catch(e){} } } return json({ stations }); } }
    const m = path.match(/^\/room\/([^/]+)$/);
    if (m) { const room = m[1]; if (!roomOk(room)) return json({ error:"bad room" }, 400);
      if (request.method === "POST") { let b; try{ b = await request.json(); }catch(e){ return json({error:"bad json"},400); }
        const from = b.from==="guest"?"guest":"host"; const to = from==="host"?"guest":"host";
        const seq = Date.now()*1000 + Math.floor(Math.random()*1000); const msg = { seq, from, type:String(b.type||"msg"), data:b.data??null };
        await env.SIG.put("m:"+room+":"+to+":"+seq, JSON.stringify(msg), { expirationTtl: TTL }); return json({ ok:true, seq }); }
      if (request.method === "GET") { const role = url.searchParams.get("role")==="guest"?"guest":"host"; const since = Number(url.searchParams.get("since")||0);
        const list = await env.SIG.list({ prefix:"m:"+room+":"+role+":" }); const msgs=[];
        for (const k of list.keys){ const seq = Number(k.name.split(":").pop()); if(seq<=since) continue; const raw = await env.SIG.get(k.name); if(raw){ try{ msgs.push(JSON.parse(raw)); }catch(e){} } }
        msgs.sort((a,b)=>a.seq-b.seq); return json({ msgs, cursor: msgs.length?msgs[msgs.length-1].seq:since }); } }
    if (request.method === "GET") {           // serve the Pigeon web app (share links open here)
      try { const r = await fetch(APP_URL, { cf: { cacheTtl: 300 } }); const html = await r.text();
        return new Response(html, { headers: { "content-type":"text/html; charset=utf-8", ...cors } }); }
      catch(e){ return json({ error:"app unavailable" }, 502); } }
    return json({ error:"not found" }, 404);
  }
};
