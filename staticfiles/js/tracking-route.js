(function () {
  const el = document.querySelector("[data-delivery-id]");
  const deliveryId = (window.route_ctx && window.route_ctx.delivery_id) || (el && el.dataset.deliveryId);
  if (!deliveryId) { console.warn("No deliveryId in page"); return; }

  const wsUrl =
    (window.route_ctx && window.route_ctx.wsUrl) ||
    (location.origin.replace(/^http/, "ws") + `/ws/delivery/track/${deliveryId}/`);

  let ws,
    retry = 0; // reconnection backoff counter

  function updateMarker(lat, lng) {
    // TODO: hook into your map lib; fallback: log
    if (window.map && window.map.updateDriverMarker) {
      window.map.updateDriverMarker(lat, lng);
    } else {
      console.log("position:", lat, lng);
    }
  }
  function updateStatus(status) {
    const chip = document.querySelector("[data-status-chip]");
    if (chip) chip.textContent = status;
    console.log("status:", status);
  }
  function toast(msg) {
    const t = document.querySelector("[data-toast]");
    if (t) { t.textContent = msg; t.classList.remove("hidden"); setTimeout(()=>t.classList.add("hidden"), 2500); }
    console.log("toast:", msg);
  }

  function connect() {
    ws = new WebSocket(wsUrl);
    ws.onopen = () => {
      retry = 0;
      console.log("WS connected", wsUrl);
    };
    ws.onerror = (e) => console.error("WS error", e);
    ws.onmessage = (ev) => {
      let data;
      try {
        data = JSON.parse(ev.data || "{}");
      } catch {
        return;
      }
      if (data.type === "position_update") {
        updateMarker(data.lat, data.lng);
      } else if (data.type === "status") {
        updateStatus(data.status);
      }
    };
    ws.onclose = () => {
      const delay = Math.min(10000, 1000 * 2 ** retry++); // exp. backoff up to 10s
      setTimeout(connect, delay);
    };
  }

  connect();

  // Optional: export a way to send pings if this page runs on the driver side
  window.sendDriverPosition = function (lat, lng) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "position_update", lat, lng }));
    }
  };
})();
