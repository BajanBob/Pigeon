/*
  Pigeon signalling relay  (fresh build — no Shelly code)
  -------------------------------------------------------
  A tiny store-and-forward signalling service that lets two Pigeon phones set up
  a direct, encrypted WebRTC link. It only passes the short setup messages (the
  WebRTC offer/answer and ICE candidates); once the two phones are linked, the
  live location, video and audio go DIRECTLY phone-to-phone and never touch this
  server. It holds nothing for more than a few minutes.

  Each message is stored under its own key (no read-modify-write races), so
  delivery is reliable. A viewer asks to connect; the sharer approves; only then
  is an offer made. Location payloads are additionally AES-256-GCM encrypted by
  the apps with a key that never leaves the share link, so the server can't read
  them even in theory.

  Cloudflare Worker + one KV namespace bound as  SIG.
  Routes:
    POST /room/<id>     {from:"host"|"guest", type, data}   -> queues for the other side
    GET  /room/<id>?role=host|guest&since=<cursor>          -> {msgs:[...], cursor}
    GET  /ice                                               -> {iceServers:[...]}  (STUN + TURN)
*/

const TTL = 300;                       // messages expire after 5 minutes
const cors = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET,POST,OPTIONS",
  "access-control-allow-headers": "content-type",
};
const json = (o, s = 200) =>
  new Response(JSON.stringify(o), { status: s, headers: { "content-type": "application/json", ...cors } });

// Static STUN + free TURN fallback so links still form behind strict NATs.
// Replace the TURN entry with your own (e.g. Cloudflare Realtime TURN) for production.
function iceServers() {
  return [
    { urls: "stun:stun.l.google.com:19302" },
    { urls: "stun:stun.cloudflare.com:3478" },
    { urls: "turn:openrelay.metered.ca:80", username: "openrelayproject", credential: "openrelayproject" },
    { urls: "turn:openrelay.metered.ca:443", username: "openrelayproject", credential: "openrelayproject" },
    { urls: "turn:openrelay.metered.ca:443?transport=tcp", username: "openrelayproject", credential: "openrelayproject" },
  ];
}

const roomOk = (s) => /^[A-Za-z0-9_-]{6,64}$/.test(s || "");

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";

    if (request.method === "OPTIONS") return new Response(null, { headers: cors });
    if (path === "/ice") return json({ iceServers: iceServers() });

    // IP geolocation for NON-HAM phones with no GPS: approximate position from the
    // request's network address, so they still appear on the map. (Ham operators
    // instead report an exact grid square over RF — see the RF module.)
    if (path === "/where") {
      const cf = request.cf || {};
      const lat = parseFloat(cf.latitude), lon = parseFloat(cf.longitude);
      return json({
        lat: Number.isFinite(lat) ? Math.round(lat * 1000) / 1000 : null,
        lon: Number.isFinite(lon) ? Math.round(lon * 1000) / 1000 : null,
        city: cf.city || "", approx: true, source: "ip",
      });
    }

    const m = path.match(/^\/room\/([^/]+)$/);
    if (m) {
      const room = m[1];
      if (!roomOk(room)) return json({ error: "bad room" }, 400);

      if (request.method === "POST") {
        let b;
        try { b = await request.json(); } catch (e) { return json({ error: "bad json" }, 400); }
        const from = b.from === "guest" ? "guest" : "host";
        const to = from === "host" ? "guest" : "host";            // deliver to the other side
        const seq = Date.now() * 1000 + Math.floor(Math.random() * 1000);
        const msg = { seq, from, type: String(b.type || "msg"), data: b.data ?? null };
        await env.SIG.put(`m:${room}:${to}:${seq}`, JSON.stringify(msg), { expirationTtl: TTL });
        return json({ ok: true, seq });
      }

      if (request.method === "GET") {
        const role = url.searchParams.get("role") === "guest" ? "guest" : "host";
        const since = Number(url.searchParams.get("since") || 0);
        const list = await env.SIG.list({ prefix: `m:${room}:${role}:` });
        const msgs = [];
        for (const k of list.keys) {
          const seq = Number(k.name.split(":").pop());
          if (seq <= since) continue;
          const raw = await env.SIG.get(k.name);
          if (raw) { try { msgs.push(JSON.parse(raw)); } catch (e) {} }
        }
        msgs.sort((a, b) => a.seq - b.seq);
        const cursor = msgs.length ? msgs[msgs.length - 1].seq : since;
        return json({ msgs, cursor });
      }
    }
    return json({ error: "not found" }, 404);
  },
};
