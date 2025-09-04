// static/js/cart.js
document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('cart-container');
  if (!root) return;

  const selectAll = root.querySelector('#select-all');
  const productCheckboxes = Array.from(root.querySelectorAll('.product-checkbox'));
  const selectedCountEl = root.querySelector('#selected-count');
  const selectedTotalEl = root.querySelector('#selected-total');
  const checkoutForm =
    document.getElementById('checkout-form') ||
    document.getElementById('hidden-checkout-form');
  const checkoutBtn = document.getElementById('checkout-btn');
  const orderCreateUrl = checkoutBtn?.dataset?.orderCreateUrl || '/orders/create/';

  let submitting = false;
  const money = new Intl.NumberFormat('en-KE', {
    style: 'currency',
    currency: 'KES',
    minimumFractionDigits: 2
  });

  function recompute() {
    const checked = productCheckboxes.filter(cb => cb.checked);
    const count = checked.length;

    let total = 0;
    for (const cb of checked) {
      const price = parseFloat(cb.dataset.price ?? '0');
      const qty = parseInt(cb.dataset.quantity ?? '1', 10);
      if (Number.isFinite(price) && Number.isFinite(qty)) total += price * qty;
    }

    if (selectedCountEl) {
      selectedCountEl.textContent = `${count} item${count !== 1 ? 's' : ''} selected`;
    }
    if (selectedTotalEl) {
      selectedTotalEl.textContent = `Selected: ${money.format(total)}`;
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
        selectAll.checked = false;
      }
    }
  }

  function navigateFallback() {
    const ids = productCheckboxes.filter(cb => cb.checked).map(cb => cb.value);
    if (!ids.length) return;
    const qs = encodeURIComponent(ids.join(','));
    window.location.assign(`${orderCreateUrl}?selected=${qs}`);
  }

  // Select all
  selectAll?.addEventListener('change', () => {
    productCheckboxes.forEach(cb => { cb.checked = selectAll.checked; });
    recompute();
  });

  // Per-item
  productCheckboxes.forEach(cb => cb.addEventListener('change', recompute));

  // Guard form submit (require selection, prevent double-submit)
  checkoutForm?.addEventListener('submit', (e) => {
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
      checkoutBtn.textContent = 'Processing…';
    }
  });

  // If there is no form (or it’s blocked), use GET fallback on click
  checkoutBtn?.addEventListener('click', (e) => {
    if (checkoutForm) return; // normal form flow exists
    e.preventDefault();
    if (submitting) return;
    const anyChecked = productCheckboxes.some(cb => cb.checked);
    if (!anyChecked) {
      alert('Please select at least one item.');
      return;
    }
    navigateFallback();
  });

  // Initial compute
  recompute();
});
