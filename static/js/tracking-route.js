// static/js/tracking-route.js
(function () {
  // ---- context & inputs ----
  const CTX = (window.__ROUTE_CTX__ || window.route_ctx || {}) || {};
  const el = document.querySelector("[data-delivery-id]");
  const deliveryId = CTX.delivery_id || (el && el.dataset.deliveryId);
  if (!deliveryId) { console.warn("[track] No deliveryId in page"); return; }

  const scheme = location.protocol === "https:" ? "wss" : "ws";
  const host = location.host;
  const WS_BASE = (window.WS_ORIGIN && window.WS_ORIGIN.length) ? window.WS_ORIGIN : `${scheme}://${host}`;
  const wsUrl = CTX.wsUrl || `${WS_BASE}/ws/delivery/track/${deliveryId}/`;

  // ---- Leaflet map bootstrap ----
  const mapDiv = document.getElementById("map");
  const etaBadge = document.querySelector("[data-eta-badge]");
  const statusChip = document.querySelector("[data-status-chip]");

  let map = null, marker = null, trail = null, routeLine = null;
  let retry = 0;  // ws backoff

  function ensureMap() {
    if (!mapDiv || typeof L === "undefined") return null;
    if (!map) {
      if (!mapDiv.style.height) mapDiv.style.height = "400px";
      const startLat = (CTX.destination && Number(CTX.destination.lat)) || -1.286389; // Nairobi default
      const startLng = (CTX.destination && Number(CTX.destination.lng)) || 36.817223;
      map = L.map(mapDiv).setView([startLat, startLng], 13);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19 }).addTo(map);
      setTimeout(() => { try { map.invalidateSize(); } catch {} }, 0);
    } else {
      setTimeout(() => { try { map.invalidateSize(); } catch {} }, 0);
    }
    return map;
  }

  function iconTruck() {
    return L.divIcon({
      className: "customer-truck-icon",
      html: '<div style="display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;background:#2563eb;color:white;box-shadow:0 1px 4px rgba(0,0,0,.25)"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M3 13V6a1 1 0 0 1 1-1h10v8h2.586a2 2 0 0 1 1.414.586L21 15v4h-2a3 3 0 1 1-6 0H9a3 3 0 1 1-6 0H1v-2h2v-4h0zm12-2V7H5v6h10zm4.586 4L18 13.414V15h1.586zM7 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm10 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2z"/></svg></div>',
      iconSize: [24, 24],
      iconAnchor: [12, 12]
    });
  }

  function setETA(text) { if (etaBadge) etaBadge.textContent = text; }
  function updateStatus(status) { if (statusChip) statusChip.textContent = status; console.log("status:", status); }

  function haversineKm(a, b) {
    const R = 6371;
    const dLat = (b.lat - a.lat) * Math.PI/180;
    const dLng = (b.lng - a.lng) * Math.PI/180;
    const s1 = Math.sin(dLat/2)**2 + Math.cos(a.lat*Math.PI/180)*Math.cos(b.lat*Math.PI/180)*Math.sin(dLng/2)**2;
    return 2 * R * Math.asin(Math.sqrt(s1));
  }

  function updateMarker(lat, lng) {
    const latN = Number(lat), lngN = Number(lng);
    if (!Number.isFinite(latN) || !Number.isFinite(lngN)) return;
    const m = ensureMap();
    if (!m) { console.log("position:", lat, lng); return; }
    const ll = [latN, lngN];

    if (!marker) {
      marker = L.marker(ll, { icon: iconTruck(), zIndexOffset: 500 }).addTo(m).bindTooltip("Driver");
      trail = L.polyline([ll], { weight: 3 }).addTo(m);
      try { m.setView(ll, 15); } catch {}
    } else {
      marker.setLatLng(ll);
      if (trail) trail.addLatLng(ll);
      try {
        if (m.getCenter().distanceTo(L.latLng(ll)) > 30) m.panTo(ll, { animate: true });
      } catch {}
    }

    // Simple ETA fallback if destination known
    try {
      const dest = CTX.destination;
      if (dest && Number.isFinite(dest.lat) && Number.isFinite(dest.lng)) {
        const km = haversineKm({ lat: latN, lng: lngN }, { lat: Number(dest.lat), lng: Number(dest.lng) });
        const SPEED_KMPH = 30;
        const etaMin = Math.max(1, Math.round((km / SPEED_KMPH) * 60));
        if (isFinite(etaMin)) setETA(`${km.toFixed(2)} km · ~${etaMin} min`);
      }
    } catch {}
  }

  async function fetchHistoryTrail() {
    try {
      const r = await fetch(`/orders/apis/delivery/${deliveryId}/pings/?limit=200`, { credentials: "same-origin" });
      if (!r.ok) return;
      const j = await r.json();
      if (Array.isArray(j.coords) && j.coords.length) {
        const m = ensureMap(); if (!m) return;
        if (trail) try { m.removeLayer(trail); } catch {}
        trail = L.polyline(j.coords, { weight: 3 }).addTo(m);
        try { m.fitBounds(trail.getBounds(), { padding: [20, 20] }); } catch {}
      }
    } catch (e) {
      console.warn("trail fetch failed:", e);
    }
  }

  function connect() {
    const open = () => {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        retry = 0;
        console.log("WS connected", wsUrl);
      };

      ws.onerror = (e) => console.error("WS error", e);

      ws.onmessage = (ev) => {
        let data; try { data = JSON.parse(ev.data || "{}"); } catch { return; }
        if (data.type === "hello" || data.type === "probe_ack") return;

        if (data.type === "error") {
          updateStatus(`Error: ${data.error}`);
          console.warn("WS server error:", data.error);
          return;
        }
        if (data.type === "status" || data.type === "status_update") {
          updateStatus(data.status);
          return;
        }
        if (data.type === "position_update") {
          updateMarker(data.lat, data.lng);
          return;
        }
      };

      ws.onclose = (e) => {
        console.log("WS close", e.code, e.reason || "");
        const delay = Math.min(10_000, 1000 * 2 ** (retry++)); // exp backoff up to 10s
        setTimeout(open, delay);
      };

      // Optional: driver pages can use this to push position
      window.sendDriverPosition = function (lat, lng) {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "position_update", lat, lng }));
        }
      };
    };

    open();
    fetchHistoryTrail(); // best-effort history
  }

  // kick off
  ensureMap();
  connect();
})();
