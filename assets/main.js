// assets/main.js
import '../src/styles/m3-tokens.css';
import '../src/assets/base.css';

import { createApp } from 'vue';
import ChatPanel from '../src/components/ChatPanel.vue';

function normalizeRole(s) {
  return (s || '').trim().toLowerCase().replace(/-/g, '_');
}

function boot() {
  const mount = document.getElementById('rahim-assistant-mount');
  if (!mount) { console.error('[assistant] mount node not found'); return; }

  // prevent double-mounts (Vite HMR / duplicate script includes)
  if (mount.dataset.mounted === '1') return;

  // Optional: server can set data-auth="true|false"
  const isAuth = /^(1|true|yes)$/i.test(mount.dataset.auth || '');

  // 1) read from dataset
  let raw = normalizeRole(mount.dataset.role);

  // default fallback if not provided
  if (!raw) raw = isAuth ? 'customer' : 'guest';

  // 2) heuristic: if this page has vendor widgets, prefer vendor context
  const pageHasVendor = !!document.querySelector('#vendor-deliveries, #vendor-staff, #vendor-shop');
  if ((raw === 'customer' || raw === 'guest') && pageHasVendor) raw = 'vendor';

  const allowed = ['vendor', 'vendor_staff', 'customer', 'driver', 'admin', 'guest'];
  const role = allowed.includes(raw) ? raw : (isAuth ? 'customer' : 'guest');

  // expose + stamp resolved role
  window.__assistantRole = role;
  mount.dataset.role = role;

  console.log('[assistant] boot role:', role);
  try {
    createApp(ChatPanel, { apiUrl: '/api/assistant/ask/', role }).mount(mount);
    mount.dataset.mounted = '1';
  } catch (e) {
    console.error('[assistant] mount error:', e);
  }
}

// Run immediately if DOM is ready; otherwise wait for DOMContentLoaded
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot, { once: true });
} else {
  boot();
}
