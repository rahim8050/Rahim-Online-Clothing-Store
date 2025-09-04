// static/js/cart.js
(function initCart() {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCart, { once: true });
    return;
  }

  const root = document.getElementById('cart-container');
  if (!root) return;

  const selectAll = root.querySelector('#select-all');
  const productCheckboxes = Array.from(root.querySelectorAll('.product-checkbox'));
  const selectedCount = root.querySelector('#selected-count');
  const selectedTotal = root.querySelector('#selected-total');
  const checkoutForm = document.getElementById('checkout-form') || document.getElementById('hidden-checkout-form');
  const checkoutBtn = document.getElementById('checkout-btn');

  let submitting = false;

  function ksh(n) {
    return 'Ksh' + Number(n).toFixed(2);
  }

  function recompute() {
    const checked = productCheckboxes.filter(cb => cb.checked);
    const count = checked.length;

    let total = 0;
    for (const cb of checked) {
      const price = parseFloat(cb.dataset.price || '0');
      const qty = parseInt(cb.dataset.quantity || '0', 10);
      if (!isNaN(price) && !isNaN(qty)) total += price * qty;
    }

    if (selectedCount) {
      selectedCount.textContent = `${count} item${count !== 1 ? 's' : ''} selected`;
    }
    if (selectedTotal) {
      selectedTotal.textContent = `Selected: ${ksh(total)}`;
    }

    if (checkoutBtn) {
      const disabled = count === 0 || submitting;
      checkoutBtn.disabled = disabled;
      checkoutBtn.classList.toggle('bg-gray-400', disabled);
      checkoutBtn.classList.toggle('cursor-not-allowed', disabled);
      checkoutBtn.classList.toggle('bg-indigo-600', !disabled);
      checkoutBtn.classList.toggle('hover:bg-indigo-700', !disabled);
      if (!submitting) {
        checkoutBtn.textContent = `Proceed to Checkout (${count} item${count !== 1 ? 's' : ''})`;
      }
    }

    if (selectAll) {
      if (count === 0) {
        selectAll.indeterminate = false;
        selectAll.checked = false;
      } else if (count === productCheckboxes.length) {
        selectAll.indeterminate = false;
        selectAll.checked = true;
      } else {
        selectAll.indeterminate = true;
      }
    }
  }

  // Guard submit: require at least one selection and prevent double-submit
  checkoutForm?.addEventListener('submit', (e) => {
    // Debug hook
    try { console.debug('[cart] submit event fired'); } catch (_){ }
    const anyChecked = productCheckboxes.some(cb => cb.checked);
    if (!anyChecked) {
      e.preventDefault();
      alert('Please select at least one item.');
      return;
    }
    if (submitting) {
      e.preventDefault();
      return;
    }
    submitting = true;
    if (checkoutBtn) {
      checkoutBtn.disabled = true;
      checkoutBtn.classList.add('cursor-wait', 'bg-gray-400');
      checkoutBtn.classList.remove('hover:bg-indigo-700', 'bg-indigo-600');
      checkoutBtn.textContent = 'Processing.';
    }
  });

  // If Select All is pre-checked on load, ensure items reflect it
  try {
    if (selectAll && selectAll.checked && productCheckboxes.some(cb => !cb.checked)) {
      productCheckboxes.forEach(cb => { cb.checked = true; });
    }
  } catch (_) {}

  // Select all toggle
  selectAll?.addEventListener('change', function () {
    productCheckboxes.forEach(cb => { cb.checked = this.checked; });
    recompute();
  });

  // Individual item toggles
  productCheckboxes.forEach(cb => cb.addEventListener('change', recompute));

  // Fallback nav: redirect via GET if submit is somehow blocked
  const orderCreateUrl = checkoutBtn?.dataset?.orderCreateUrl || '/orders/create/';
  function scheduleFallbackNav() {
    try {
      if (submitting) return;
      const ids = productCheckboxes.filter(cb => cb.checked).map(cb => cb.value);
      if (!ids.length) return;
      setTimeout(() => {
        try {
          if (!document.hidden) {
            const qs = encodeURIComponent(ids.join(','));
            window.location.assign(orderCreateUrl + '?selected=' + qs);
          }
        } catch (_) {}
      }, 500);
    } catch (_) {}
  }
  ['click', 'pointerdown', 'mousedown', 'touchstart', 'keydown'].forEach((type) => {
    checkoutBtn?.addEventListener(type, (e) => {
      try {
        if (type === 'click') {
          // Force submit via JS as well; does not prevent default.
          try {
            if (checkoutBtn.disabled || submitting) return;
            if (checkoutForm?.requestSubmit) checkoutForm.requestSubmit(); else checkoutForm?.submit();
          } catch (_) {}
        }
        if (type === 'keydown') {
          const k = (e.key || e.code || '').toLowerCase();
          if (!(k === 'enter' || k === ' ' || k === 'space')) return;
        }
        if (checkoutBtn.disabled || submitting) return;
        scheduleFallbackNav();
      } catch (_) {}
    }, true);
  });

  // Global capture: if the click lands on a nested element inside the button,
  // or other listeners interfere, still programmatically submit.
  document.addEventListener('click', (e) => {
    try {
      const t = e.target;
      const btn = (t && (t.id === 'checkout-btn' ? t : (t.closest ? t.closest('#checkout-btn') : null)));
      if (!btn) return;
      if (checkoutBtn.disabled || submitting) return;
      e.preventDefault();
      e.stopPropagation();
      if (typeof e.stopImmediatePropagation === 'function') e.stopImmediatePropagation();
      if (checkoutForm?.requestSubmit) checkoutForm.requestSubmit(); else checkoutForm?.submit();
    } catch (_) {}
  }, true);

  // Initial compute
  try { recompute(); } catch (_) {}
})();
