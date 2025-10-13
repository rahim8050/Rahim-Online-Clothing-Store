// CSRF Token
window.CSRF_TOKEN = document.querySelector('meta[name="csrf-token"]')?.content || null;

// Flash messages
document.addEventListener('DOMContentLoaded', function () {
  const flashMessages = document.querySelectorAll('.flash-message');

  flashMessages.forEach(message => {
    const closeBtn = message.querySelector('.close-btn');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        message.classList.add('opacity-0');
        setTimeout(() => message.remove(), 500);
      });
    }

    // Auto-dismiss after 20 seconds
    setTimeout(() => {
      message.classList.add('opacity-0');
      setTimeout(() => message.remove(), 500);
    }, 20000);
  });
});

// WebSocket notification handler
(function () {
  if (!("WebSocket" in window)) return;

  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(proto + "://" + location.host + "/ws/notifications/");

  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      toast(data.title, data.message, data.level);
    } catch (err) {
      console.error("Invalid notification payload", err);
    }
  };

  function toast(title, msg, level) {
    const wrap = document.getElementById("toaster") || (() => {
      const d = document.createElement("div");
      d.id = "toaster";
      d.className = "fixed top-4 right-4 space-y-2 z-50";
      document.body.appendChild(d);
      return d;
    })();
    const el = document.createElement("div");
    el.className = "rounded-xl shadow px-4 py-3 bg-white border w-80";
    el.innerHTML = `<div class="font-semibold">${title}</div>
                    <div class="text-sm text-gray-700 mt-1">${msg}</div>`;
    wrap.appendChild(el);
    setTimeout(() => el.remove(), 6000);
  }
})();

// Vendor application updates
(function(){
  function wsUrl(p){
    const s = location.protocol === 'https:' ? 'wss' : 'ws';
    return s + '://' + location.host + (p.startsWith('/') ? p : '/' + p);
  }
  try {
    const ws = new WebSocket(wsUrl('/ws/notifications/'));
    ws.onmessage = function(ev){
      let d;
      try { d = JSON.parse(ev.data); } catch (_) { d = null; }
      if (d && d.type === 'vendor_application.updated') {
        const el = document.createElement('div');
        el.className = 'fixed bottom-20 right-4 z-[9999] bg-black text-white text-sm px-3 py-2 rounded shadow';
        el.textContent = d.message || ('Vendor application status: ' + (d.status || ''));
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 4000);
        if (window.AssistantPushMessage) {
          window.AssistantPushMessage({
            who: 'bot',
            text: 'Vendor application → ' + (d.status || '')
          });
        }
      }
    };
  } catch (e) {
    console.warn("WS connection failed:", e);
  }
})();
