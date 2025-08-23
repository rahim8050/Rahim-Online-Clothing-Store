(function () {
  const el = document.querySelector("[data-delivery-id]");
  const deliveryId = (window.route_ctx && window.route_ctx.delivery_id) || (el && el.dataset.deliveryId);
  if (!deliveryId) { console.warn("No deliveryId in page"); return; }

  const wsUrl =
    (window.route_ctx && window.route_ctx.wsUrl) ||
    (location.origin.replace(/^http/, "ws") + `/ws/deliveries/${deliveryId}/`);

  let ws, retry = 0, reconnectTimer;

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
    ws.onopen = () => { retry = 0; console.log("WS connected", wsUrl); };
    ws.onmessage = (ev) => {
      let data = {};
      try { data = JSON.parse(ev.data || "{}"); } catch { return; }
      switch (data.event) {
        case "position": updateMarker(data.lat, data.lng); break;
        case "status": updateStatus(data.status); break;
        case "assign": toast("Driver assigned"); break;
        case "unassign": toast("Driver unassigned"); break;
        case "accept": toast("Driver accepted"); break;
        default: /* ignore */ break;
      }
    };
    ws.onclose = () => {
      const delay = Math.min(30000, 1000 * Math.pow(2, retry++));
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connect, delay);
    };
    ws.onerror = () => { try { ws.close(); } catch {} };
  }

  connect();

  // Optional: export a way to send pings if this page runs on the driver side
  window.sendDriverPing = function (lat, lng) {
    if (ws && ws.readyState === 1) {
      ws.send(JSON.stringify({ type: "ping", lat, lng }));
    }
  };
})();
