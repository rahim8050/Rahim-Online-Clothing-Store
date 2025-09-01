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
  let map = null, marker = null, trail = null;

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

  function updateMarker(lat, lng) {
    const latN = Number(lat), lngN = Number(lng);
    if (!Number.isFinite(latN) || !Number.isFinite(lngN)) return;
    const m = ensureMap();
    if (!m) { console.log("position:", lat, lng); return; }
    const ll = [latN, lngN];

    if (!marker) {
      marker = L.marker(ll).addTo(m).bindTooltip("Driver");
      trail = L.polyline([ll], { weight: 3 }).addTo(m);
      try { m.setView(ll, 15); } catch {}
    } else {
      marker.setLatLng(ll);
      if (trail) trail.addLatLng(ll);
      try {
        if (m.getCenter().distanceTo(L.latLng(ll)) > 30) m.panTo(ll, { animate: true });
      } catch {}
    }
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

        if (data.type === "status") {
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
  }

  connect();
})();

