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

  // 1) read from dataset
  let raw = normalizeRole(mount.dataset.role);

  // 2) heuristic: if this page has vendor widgets, force vendor
  const pageHasVendor =
    document.getElementById('vendor-deliveries') ||
    document.getElementById('vendor-staff') ||
    document.getElementById('vendor-shop');

  if ((!raw || raw === 'customer') && pageHasVendor) raw = 'vendor';

  const allowed = ['vendor','vendor_staff','customer','driver','admin','guest'];
  const role = allowed.includes(raw) ? raw : 'customer';

  console.log('[assistant] boot role:', role);
  try {
    createApp(ChatPanel, { apiUrl: '/api/assistant/ask/', role }).mount(mount);
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
