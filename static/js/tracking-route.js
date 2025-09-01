(function () {
  // ---- context & inputs ----
  const CTX = (window.__ROUTE_CTX__ || window.route_ctx || {}) || {};
  const host = location.host;
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  const WS_BASE = (window.WS_ORIGIN && window.WS_ORIGIN.length)
    ? window.WS_ORIGIN
    : `${scheme}://${host}`;

  const el = document.querySelector("[data-delivery-id]");
  const deliveryId = CTX.delivery_id || (el && el.dataset.deliveryId);

  const wsUrl = CTX.wsUrl || (deliveryId ? `${WS_BASE}/ws/delivery/track/${deliveryId}/` : null);
  if (!wsUrl) {
    console.warn("No wsUrl or deliveryId available for tracking");
    return;
  }

  // ---- Leaflet map bootstrap ----
  const mapDiv = document.getElementById("map");
  let map = null, marker = null, trail = null, routeLine = null;
  const etaBadge = document.querySelector('[data-eta-badge]');

  function iconTruck() {
    return L.divIcon({
      className: "customer-truck-icon",
      html: '<div style="display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;background:#2563eb;color:white;box-shadow:0 1px 4px rgba(0,0,0,.25)"><i class="fa-solid fa-truck" style="font-size:13px"></i></div>',
      iconSize: [24, 24],
      iconAnchor: [12, 12]
    });
  }

  function ensureMap() {
    if (!mapDiv || typeof L === "undefined") return null;
    if (!map) {
      if (!mapDiv.style.height) mapDiv.style.height = "400px";
      map = L.map(mapDiv).setView(
        [
          (CTX.destination && CTX.destination.lat) || -1.286389,
          (CTX.destination && CTX.destination.lng) || 36.817223,
        ], 13
      );
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19 }).addTo(map);
      setTimeout(() => { try { map.invalidateSize(); } catch {} }, 0);
    } else {
      setTimeout(() => { try { map.invalidateSize(); } catch {} }, 0);
    }
    return map;
  }

  function updateStatus(status) {
    const chip = document.querySelector("[data-status-chip]");
    if (chip) chip.textContent = status;
    console.log("status:", status);
  }

  function setETA(text) {
    if (etaBadge) etaBadge.textContent = text;
  }

  function updateMarker(lat, lng) {
    const latN = Number(lat), lngN = Number(lng);
    if (!Number.isFinite(latN) || !Number.isFinite(lngN)) return;
    const m = ensureMap();
    if (!m) { console.log("position:", lat, lng); return; }
    const ll = [latN, lngN];

    if (!marker) {
      marker = L.marker(ll, { icon: iconTruck(), zIndexOffset: 500 }).addTo(m).bindTooltip("Driver");
      trail = L.polyline([ll], { weight: 3, color: '#2563eb' }).addTo(m);
      try { m.setView(ll, 15); } catch {}
    } else {
      marker.setLatLng(ll);
      if (trail) trail.addLatLng(ll);
      try {
        if (m.getCenter().distanceTo(L.latLng(ll)) > 30) m.panTo(ll, { animate: true });
      } catch {}
    }

    // Update ETA (quick haversine fallback)
    try {
      const dest = CTX.destination;
      if (dest && Number.isFinite(dest.lat) && Number.isFinite(dest.lng)) {
        const km = haversineKm({lat: latN, lng: lngN}, dest);
        const SPEED_KMPH = 30;
        const etaMin = Math.max(1, Math.round((km / SPEED_KMPH) * 60));
        if (isFinite(etaMin)) setETA(`${km.toFixed(2)} km ~ ${etaMin} min`);
      }
    } catch {}
  }

  function haversineKm(a, b) {
    const R = 6371;
    const dLat = (b.lat - a.lat) * Math.PI/180;
    const dLng = (b.lng - a.lng) * Math.PI/180;
    const s1 = Math.sin(dLat/2)**2 + Math.cos(a.lat*Math.PI/180)*Math.cos(b.lat*Math.PI/180)*Math.sin(dLng/2)**2;
    return 2 * R * Math.asin(Math.sqrt(s1));
  }

  async function fetchHistoryTrail() {
    try {
      if (!deliveryId) return;
      const r = await fetch(`/orders/apis/delivery/${deliveryId}/pings/?limit=200`, { credentials: 'same-origin' });
      if (!r.ok) return;
      const j = await r.json();
      if (Array.isArray(j.coords) && j.coords.length) {
        const m = ensureMap(); if (!m) return;
        if (trail) try { m.removeLayer(trail); } catch {}
        trail = L.polyline(j.coords, { weight: 3, color: '#2563eb' }).addTo(m);
        try { m.fitBounds(trail.getBounds(), { padding: [20,20] }); } catch {}
      }
    } catch {}
  }

  function connect() {
    let retry = 0;
    let ws;

    const open = () => {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        retry = 0;
        console.log("WS connected", wsUrl);
      };

      ws.onerror = (e) => {
        console.error("WS error", e);
      };

      ws.onmessage = (ev) => {
        let data;
        try { data = JSON.parse(ev.data || "{}"); } catch { return; }

        // Common server frames we can just ignore or handle nicely
        if (data.type === "hello" || data.type === "probe_ack") return;

        if (data.type === "error") {
          // e.g. {"error":"forbidden"} if a non-driver tried to send
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
        // Exponential backoff up to 10s
        const delay = Math.min(10000, 1000 * 2 ** (retry++));
        setTimeout(open, delay);
      };

      // Optional: export a way to send pings IF this page is used by the driver.
      // NOTE: Your server only accepts position from the assigned driver.
      window.sendDriverPosition = function (lat, lng) {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "position_update", lat, lng }));
        }
      };
    };

    open();
    // Seed trail from server history (best effort)
    fetchHistoryTrail();
  }

  connect();
})();

