document.addEventListener("DOMContentLoaded", function () {
  const mobileMenuButton = document.getElementById("mobile-menu-button");
  const mobileMenu = document.getElementById("mobile-menu");

  if (mobileMenuButton) {
    mobileMenuButton.addEventListener("click", () => {
      mobileMenu.classList.toggle("hidden");
    });
  }

  function showCartAddedAnimation() {
    const counter = document.getElementById("cart-counter");
    counter.classList.remove("opacity-0", "scale-50");
    void counter.offsetWidth;
    counter.classList.add("opacity-100", "scale-100");
    setTimeout(() => {
      counter.classList.remove("opacity-100", "scale-100");
      counter.classList.add("opacity-0", "scale-50");
    }, 2000);
  }

  function updateCartCounter(count) {
    const counter = document.getElementById("cart-counter");
    const current = parseInt(counter.textContent.trim()) || 0;

    const displayCount = count > 99 ? "99+" : count;
    counter.textContent = displayCount;

    if (count > current) {
      showCartAddedAnimation();
    }

    if (count > 0) {
      counter.classList.remove("opacity-0", "scale-50");
    }
  }

  fetch("/cart/count/")
    .then((response) => response.json())
    .then((data) => {
      updateCartCounter(data.count);
    });

  document.querySelectorAll(".add-to-cart").forEach((button) => {
    button.addEventListener("click", function (e) {
      e.preventDefault();
      const productId = this.dataset.productId;

      fetch(`/cart/add/${productId}/`, {
        method: "POST",
        headers: {
          "X-CSRFToken": window.CSRF_TOKEN || "", // <- fallback if not defined
          "Content-Type": "application/json",
        },
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.success) {
            updateCartCounter(data.cart_total_items);
          }
        })
        .catch((error) => console.error("Error:", error));
    });
  });
});
