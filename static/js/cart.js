// static/js/cart.js
document.addEventListener("DOMContentLoaded", function () {
  const root = document.getElementById("cart-container");
  if (!root) return;

  const selectAll = root.querySelector("#select-all");
  const productCheckboxes = Array.from(root.querySelectorAll(".product-checkbox"));
  const selectedCount = root.querySelector("#selected-count");
  const selectedTotal = root.querySelector("#selected-total");
  const checkoutForm = document.getElementById("hidden-checkout-form");
  const checkoutBtn = document.getElementById("checkout-btn");

  let submitting = false;

  function ksh(n) {
    // ensure 2dp; tweak if you want locale formatting
    return `Ksh${Number(n).toFixed(2)}`;
  }

  function recompute() {
    const checked = productCheckboxes.filter(cb => cb.checked);
    const count = checked.length;

    let total = 0;
    for (const cb of checked) {
      const price = parseFloat(cb.dataset.price || "0");
      const qty = parseInt(cb.dataset.quantity || "0", 10);
      if (!isNaN(price) && !isNaN(qty)) total += price * qty;
    }

    if (selectedCount) {
      selectedCount.textContent = `${count} item${count !== 1 ? "s" : ""} selected`;
    }
    if (selectedTotal) {
      selectedTotal.textContent = `Selected: ${ksh(total)}`;
    }

    if (checkoutBtn) {
      const disabled = count === 0 || submitting;
      checkoutBtn.disabled = disabled;
      checkoutBtn.classList.toggle("bg-gray-400", disabled);
      checkoutBtn.classList.toggle("cursor-not-allowed", disabled);
      checkoutBtn.classList.toggle("bg-indigo-600", !disabled);
      checkoutBtn.classList.toggle("hover:bg-indigo-700", !disabled);
      if (!submitting) {
        checkoutBtn.textContent = `Proceed to Checkout (${count} item${count !== 1 ? "s" : ""})`;
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

  // Button is type="submit" and bound to the hidden form via form attribute.
  // No JS needed to trigger submission; we only guard the submit below.

  // Guard submit: require at least one selection; also prevent double-submit
  checkoutForm?.addEventListener("submit", (e) => {
    const anyChecked = productCheckboxes.some(cb => cb.checked);
    if (!anyChecked) {
      e.preventDefault();
      alert("Please select at least one item.");
      return;
    }
    if (submitting) {
      e.preventDefault();
      return;
    }
    // mark submitting & lock UI
    submitting = true;
    if (checkoutBtn) {
      checkoutBtn.disabled = true;
      checkoutBtn.classList.add("cursor-wait", "bg-gray-400");
      checkoutBtn.classList.remove("hover:bg-indigo-700", "bg-indigo-600");
      checkoutBtn.textContent = "Processing…";
    }
  });

  // Select all toggle
  selectAll?.addEventListener("change", function () {
    productCheckboxes.forEach(cb => { cb.checked = this.checked; });
    recompute();
  });

  // Individual item toggles
  productCheckboxes.forEach(cb => cb.addEventListener("change", recompute));

  // Fallback nav: if something blocks default submit, navigate via GET with selected ids.
  const orderCreateUrl = checkoutBtn?.dataset?.orderCreateUrl || "/orders/create/";
  function scheduleFallbackNav() {
    try {
      if (submitting) return;
      const ids = productCheckboxes.filter(cb => cb.checked).map(cb => cb.value);
      if (!ids.length) return;
      setTimeout(() => {
        try {
          if (!document.hidden) {
            const qs = encodeURIComponent(ids.join(","));
            window.location.assign(orderCreateUrl + "?selected=" + qs);
          }
        } catch (_) {}
      }, 500);
    } catch (_) {}
  }

  // Capture multiple events to plan fallback, without preventing default submit.
  ["click", "pointerdown", "mousedown", "touchstart", "keydown"].forEach((type) => {
    checkoutBtn?.addEventListener(type, (e) => {
      try {
        if (type === "keydown") {
          const k = (e.key || e.code || "").toLowerCase();
          if (!(k === "enter" || k === "space" || k === " ")) return;
        }
        if (checkoutBtn.disabled || submitting) return;
        scheduleFallbackNav();
      } catch (_) {}
    }, true);
  });

  // Initial compute
  recompute();
});
