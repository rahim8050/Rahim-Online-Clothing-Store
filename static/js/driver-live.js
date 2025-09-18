(function () {
  const BOOT = (window.DRIVER_LIVE_BOOT || {});
  const DELIVERY_ID = parseInt(BOOT.deliveryId || 0, 10);
  const START = BOOT.start || { lat: -1.286389, lng: 36.817223 };
  const WS_BASE = BOOT.wsBase || ((location.protocol === "https:" ? "wss://" : "ws://") + location.host);
  const PERSIST_URL = BOOT.persistUrl || "";

  // knobs
  const MIN_PING_MS = 8000;
  const MIN_MOVE_M = 25;

  // dom
  const $ = (s) => document.querySelector(s);
  const elStatus = $("#chip-label");
  const elDot = $("#chip-dot");
  const elSent = $("#stat-sent");
  const elLastM = $("#stat-last-m");
  const elAcc = $("#stat-acc");
  const elSpeed = $("#stat-speed");
  const btnStart = $("#btn-start");
  const btnStop = $("#btn-stop");
  const btnSim = $("#btn-sim");
  const persistT = $("#persist-toggle");
  const debugEl = $("#debug");

  // state
  let map, marker, circle, poly, path = [];
  let ws = null, wsReady = false, outbox = [];
  let watchId = null, lastSentAt = 0, lastPt = null, lastTime = 0, sentCount = 0;

  // helpers
  const log = (...a) => {
    if (debugEl) {
      debugEl.textContent += a.join(" ") + "\n";
      debugEl.scrollTop = debugEl.scrollHeight;
    }
  };
  const setChip = (txt, cls) => {
    if (elStatus) elStatus.textContent = "WS: " + txt;
    if (elDot) elDot.className = "h-2.5 w-2.5 rounded-full " + cls;
  };
  const H = (a, b) => {
    if (!(a && b)) return 0;
    const [lat1, lng1] = a, [lat2, lng2] = b, R = 6371000;
    const dLa = (lat2 - lat1) * Math.PI / 180, dLg = (lng2 - lng1) * Math.PI / 180;
    const s = Math.sin(dLa / 2) ** 2 + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLg / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(s));
  };

  // map
  function ensureMap() {
    if (map) return map;
    const start = [isFinite(START.lat) ? START.lat : -1.286389, isFinite(START.lng) ? START.lng : 36.817223];
    map = L.map("map", { zoomControl: true }).setView(start, 14);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19 }).addTo(map);
    marker = L.marker(start, { icon: iconDriverFavicon(), zIndexOffset: 500 }).addTo(map).bindTooltip("You");
    path = [start];
    poly = L.polyline(path, { weight: 3, color: "#2563eb" }).addTo(map);
    return map;
  }

  function iconDriverFavicon() {
    return L.divIcon({
      className: "driver-live-icon",
      html: '<div style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;background:#2563eb;color:white;box-shadow:0 1px 4px rgba(0,0,0,.25)"><img src="/favicon.ico" alt="driver" style="width:16px;height:16px;border-radius:3px"/></div>',
      iconSize: [26, 26], iconAnchor: [13, 13]
    });
  }

  // WS
  function wsUrlFor(id) {
    return `${WS_BASE}/ws/delivery/track/${id}/`;
  }

  function ensureWS() {
    if (ws && wsReady) return;
    const url = wsUrlFor(DELIVERY_ID);
    ws = new WebSocket(url);
    ws.onopen = () => {
      wsReady = true;
      setChip("connected", "bg-emerald-500");
      log("WS OPEN", url);
      while (outbox.length) ws.send(JSON.stringify(outbox.shift()));
    };
    ws.onmessage = (e) => { log("WS MSG", e.data); };
    ws.onclose = (e) => { wsReady = false; setChip("closed", "bg-gray-300"); log("WS CLOSE", e.code); };
    ws.onerror = () => { setChip("error", "bg-red-500"); log("WS ERROR"); };
  }

  async function persistHTTP(lat, lng, status) {
    if (!PERSIST_URL) return;
    try {
      await fetch(PERSIST_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ lat, lng, status })
      });
    } catch (e) {
      log("HTTP persist failed");
    }
  }

  function sendPosition(lat, lng, status = "in_transit") {
    const payload = { op: "update", lat, lng, status, ts: Date.now() };
    if (wsReady) ws.send(JSON.stringify(payload)); else outbox.push(payload);
    if (persistT && persistT.checked) persistHTTP(lat, lng, status);
    sentCount += 1; if (elSent) elSent.textContent = String(sentCount);
  }

  // flows
  function start() {
    ensureMap(); ensureWS();
    if (!("geolocation" in navigator)) { log("No geolocation"); return; }

    stop(); // clear old watcher if any

    watchId = navigator.geolocation.watchPosition((pos) => {
      const now = Date.now();
      const lat = Number(pos.coords.latitude), lng = Number(pos.coords.longitude);
      const acc = Number(pos.coords.accuracy || 0);
      const pt = [lat, lng];

      marker.setLatLng(pt);
      if (!circle) circle = L.circle(pt, { radius: acc || 20 }).addTo(map);
      circle.setLatLng(pt).setRadius(acc || 20);

      const dist = lastPt ? Math.round(H(lastPt, pt)) : 0;
      if (elLastM) elLastM.textContent = dist ? (dist + " m") : "0 m";
      if (elAcc) elAcc.textContent = acc ? (Math.round(acc) + " m") : "–";
      if (lastPt && lastTime) {
        const dt = (now - lastTime) / 1000, spd = dt > 0 ? (H(lastPt, pt) / dt) : 0;
        if (elSpeed) elSpeed.textContent = (spd * 3.6).toFixed(1) + " km/h";
      }
      lastTime = now;

      if (!lastPt || dist > 10) { path.push(pt); poly.setLatLngs(path); }
      if (dist > 60) map.panTo(pt);

      const due = (now - lastSentAt) >= MIN_PING_MS;
      const movedEnough = (!lastPt || dist >= MIN_MOVE_M);
      if (due && movedEnough) {
        sendPosition(lat, lng);
        lastSentAt = now; lastPt = pt;
      }
    }, (err) => {
      log("GEO ERROR", err.message);
    }, { enableHighAccuracy: true, maximumAge: 2000, timeout: 20000 });

    btnStart.disabled = true; btnStop.disabled = false;
  }

  function stop() {
    if (watchId != null && navigator.geolocation && typeof navigator.geolocation.clearWatch === "function") {
      try { navigator.geolocation.clearWatch(watchId); } catch { }
    }
    watchId = null; btnStart.disabled = false; btnStop.disabled = true;
  }

  function simulate() {
    ensureMap(); ensureWS();
    const s = marker.getLatLng();
    const hops = [
      [s.lat + 0.002, s.lng + 0.006],
      [s.lat + 0.004, s.lng + 0.012],
      [s.lat + 0.006, s.lng + 0.017],
    ];
    let i = 0; const t = setInterval(() => {
      const p = hops[i++]; if (!p) { clearInterval(t); return; }
      marker.setLatLng(p);
      path.push([p[0], p[1]]); poly.setLatLngs(path); map.panTo(p);
      sendPosition(p[0], p[1], "demo");
      lastPt = [p[0], p[1]]; lastSentAt = Date.now();
    }, 900);
  }

  // bindings
  if (btnStart) btnStart.addEventListener("click", start);
  if (btnStop) btnStop.addEventListener("click", stop);
  if (btnSim) btnSim.addEventListener("click", simulate);

  // initial chip
  setChip("idle", "bg-gray-300");

  // tip for mobile GPS
  if (location.protocol !== "https:" && !["localhost", "127.0.0.1"].includes(location.hostname)) {
    log("Tip: use HTTPS (ngrok/tunnel) for mobile geolocation.");
  }
})();
