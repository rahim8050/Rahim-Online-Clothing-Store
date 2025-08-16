(function () {
  const ctx = window.__ROUTE_CTX__ || {};
  if (!ctx.destination) return;

  const dest = ctx.destination;
  const map = L.map('map').setView([dest.lat, dest.lng], 13);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);
  L.marker([dest.lat, dest.lng]).addTo(map);

  let marker;
  if (ctx.warehouse) {
    marker = L.marker([ctx.warehouse.lat, ctx.warehouse.lng]).addTo(map);
    const url = `https://api.geoapify.com/v1/routing?waypoints=${ctx.warehouse.lat},${ctx.warehouse.lng}|${dest.lat},${dest.lng}&mode=drive&apiKey=${ctx.apiKey}`;
    fetch(url)
      .then(r => r.json())
      .then(data => {
        try {
          const coords = data.features[0].geometry.coordinates[0].map(([lng, lat]) => [lat, lng]);
          L.polyline(coords, { color: 'blue', dashArray: '4' }).addTo(map);
        } catch (e) { console.error(e); }
      })
      .catch(err => console.error(err));
  } else {
    marker = L.marker([dest.lat, dest.lng]).addTo(map);
  }

  if (ctx.wsUrl) {
    const ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + ctx.wsUrl);
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.event === 'position') {
        marker.setLatLng([data.lat, data.lng]);
      } else if (data.event === 'status') {
        const el = document.getElementById('status');
        if (el) el.innerText = data.status;
      }
    };
  }
})();

