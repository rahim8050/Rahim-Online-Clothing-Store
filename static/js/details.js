
const { createApp } = Vue;

function capitalizeWords(text) {
  return text ? text.toLowerCase().split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ') : '';
}
function capitalizeSlug(slug) {
  return slug ? slug.replace(/[-_]/g, ' ').split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ') : '';
}
function getCookie(name){
  const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
  return m ? m.pop() : '';
}

createApp({
  delimiters: ['[[', ']]'],
  data() {
    let productData = {};
    try { productData = JSON.parse(document.getElementById('product-data').textContent); }
    catch (e) { console.error('Invalid product JSON:', e); }

    return {
      productName: capitalizeWords(productData.name || 'Unknown Product'),
      productSlug: capitalizeSlug(productData.slug || ''),
      productPrice: productData.price || 0,
      productDescription: productData.description || '',

      csrfToken: getCookie('csrftoken'),                                   // read CSRF from cookie
      addToCartUrl: "{% url 'cart:cart_add' product.id %}",

      showDescription: false,
      isHovered: false,
      message: '',
      toasts: []                                                            // toast state
    };
  },
  computed: {
    formattedPrice() {
      const price = parseFloat(this.productPrice);
      if (isNaN(price)) return 'Ksh 0.00';
      return `Ksh ${price.toLocaleString('en-KE', { minimumFractionDigits: 2 })}`;
    },
    shortDescription() {
      if (!this.productDescription) return '';
      const parts = this.productDescription.split('. ');
      return parts.length ? parts[0] + '.' : this.productDescription;
    },
    hasMoreDescription() {
      return this.productDescription && this.productDescription.split('. ').length > 1;
    }
  },
  methods: {
    // --- Toasts ---
    toast(message, type='success', duration=3500) {
      const id = Date.now() + Math.random();
      const t = { id, message, type, visible: false };
      this.toasts.push(t);
      requestAnimationFrame(() => { t.visible = true; });
      t._timer = setTimeout(() => this.dismissToast(id), duration);
    },
    dismissToast(id) {
      const i = this.toasts.findIndex(x => x.id === id);
      if (i >= 0) {
        const t = this.toasts[i];
        t.visible = false;
        clearTimeout(t._timer);
        setTimeout(() => { this.toasts.splice(i, 1); }, 200);
      }
    },

    async addToCart() {
      try {
        const response = await fetch(this.addToCartUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',               // ask for JSON
            'X-CSRFToken': this.csrfToken
          },
          body: JSON.stringify({ quantity: 1 })
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
          let text = data.message || 'Failed to add to cart.';
          if (data.code === 'AUTH_REQUIRED' && data.login_url) {
            this.toast('Please log in to continue.', 'warning');
            setTimeout(() => { window.location.href = data.login_url; }, 800);
            return;
          }
          if (data.code === 'OWN_LISTING')  text = 'You cannot purchase your own product.';
          if (data.code === 'OUT_OF_STOCK') text = data.message || 'Not enough stock.';
          if (data.code === 'CSRF_FAILED')  text = 'Session expired. Refresh and try again.';
          this.message = text;
          this.toast(text, 'error');
          return;
        }

        const successMsg = data.message || 'Added to cart.';
        this.message = successMsg;
        this.toast(successMsg, 'success');
        this.updateCartCounterDisplay();
      } catch (error) {
        console.error('Add to cart error:', error);
        this.message = 'Something went wrong.';
        this.toast('Something went wrong.', 'error');
      }
    },

    async updateCartCounterDisplay() {
      try {
        const res = await fetch("/cart/count/", { headers: { 'Accept': 'application/json' } });
        const data = await res.json();
        const counter = document.getElementById("cart-counter");
        if (counter && typeof data.count === 'number') counter.textContent = data.count;
      } catch (err) {
        console.error("Cart count update failed:", err);
      }
    }
  },
  mounted() {
    this.updateCartCounterDisplay();
  }
}).mount('#product-app');
