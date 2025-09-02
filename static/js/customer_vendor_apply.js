// static/js/customer_vendor_apply.js
(function () {
  const card    = document.getElementById('vendor-apply-card');
  if (!card) return;

  const endpoint = card.dataset.applyEndpoint || '/apis/vendor/apply/';
  const form     = document.getElementById('vendor-apply-form');
  const statusEl = document.getElementById('vendor-apply-status');
  const hintEl   = document.getElementById('vendor-apply-hint');
  const btn      = document.getElementById('btn-apply-vendor');

  function safeText(el, text){ if (el) el.textContent = text; }
  function safeHtml(el, html){ if (el) el.innerHTML = html; }

  function getCookie(name){
    const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? m.pop() : '';
  }
  function getCsrf() {
    const inp = form?.querySelector('input[name=csrfmiddlewaretoken]');
    return inp?.value || getCookie('csrftoken') || '';
  }

  async function submitKyc(e){
    e.preventDefault();
    if (!form) return;

    const origBtnText = btn ? btn.textContent : '';
    if (btn) { btn.disabled = true; btn.textContent = 'Submitting…'; }
    safeText(hintEl, 'Submitting…');

    const fd = new FormData(form); // includes file + fields

    try {
      const r = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCsrf(),
          'X-Requested-With': 'XMLHttpRequest',
          'Accept': 'application/json'
        },
        credentials: 'same-origin',
        body: fd
      });

      let data = null;
      try { data = await r.clone().json(); } catch {}

      if (r.status === 201 || r.status === 200) {
        safeHtml(statusEl, 'Your application is <span class="font-medium">pending review</span>.');
        safeText(hintEl, data?.created === false
          ? 'You already have a pending application (#' + (data?.id ?? '') + ').'
          : 'We will notify you when it’s approved.');
        form.remove(); // hide the form after success
        if (btn) { btn.disabled = true; btn.textContent = 'Application Submitted'; }
      } else if (r.status === 400) {
        const first = data && (data.detail || Object.values(data)[0]?.[0]);
        safeText(hintEl, first || 'Validation error. Check your inputs.');
        if (btn) { btn.disabled = false; btn.textContent = origBtnText; }
      } else if (r.status === 401) {
        safeText(hintEl, 'Please sign in and try again.');
        if (btn) { btn.disabled = false; btn.textContent = origBtnText; }
      } else if (r.status === 403) {
        safeText(hintEl, (data && data.detail) || 'Forbidden (auth/CSRF).');
        if (btn) { btn.disabled = false; btn.textContent = origBtnText; }
      } else if (r.status === 409) {
        safeText(hintEl, (data && data.detail) || 'Already approved.');
        if (btn) { btn.disabled = false; btn.textContent = origBtnText; }
      } else if (r.status === 413) {
        safeText(hintEl, 'File too large. Upload a smaller KYC document.');
        if (btn) { btn.disabled = false; btn.textContent = origBtnText; }
      } else {
        safeText(hintEl, 'Unexpected: ' + r.status);
        if (btn) { btn.disabled = false; btn.textContent = origBtnText; }
      }
    } catch (err) {
      safeText(hintEl, 'Network error. Please try again.');
      if (btn) { btn.disabled = false; btn.textContent = origBtnText; }
    }
  }

  if (form) form.addEventListener('submit', submitKyc);
})();
