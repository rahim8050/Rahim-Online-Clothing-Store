// static/js/vendor-dashboard.js

(function () {
  // --- helpers ---
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return decodeURIComponent(parts.pop().split(";").shift());
    return "";
  }
  async function getJSON(url) {
    const r = await fetch(url, { credentials: "same-origin" });
    if (!r.ok) throw new Error(`GET ${url} -> ${r.status}`);
    return r.json();
  }
  async function postJSON(url, body) {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
      credentials: "same-origin",
      body: JSON.stringify(body || {}),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || data.message || `POST ${url} -> ${r.status}`);
    return data;
  }

  const owner = new URLSearchParams(location.search).get("owner_id") || "";

  // --- Deliveries panel ---
  if (document.getElementById("vendor-deliveries")) {
    new Vue({
      el: "#vendor-deliveries",
      delimiters: ["[[", "]]"],
      template: "#tpl-vendor-deliveries",
      data: {
        rows: [],
        loading: false,
        error: "",
        owner,
        assignId: {},
        busy: {},
      },
      mounted() { this.load(); },
      methods: {
        fmt(dt) { try { return dt ? new Date(dt).toLocaleString() : "—"; } catch { return dt || "—"; } },
        async load() {
          this.loading = true; this.error = "";
          try {
            const u = new URL("/apis/vendor/deliveries/", location.origin);
            if (this.owner) u.searchParams.set("owner_id", this.owner);
            this.rows = await getJSON(u.toString());
          } catch (e) { this.error = e.message || "Failed to load"; }
          finally { this.loading = false; }
        },
        async assign(d) {
          const driver = Number(this.assignId[d.id]);
          if (!driver) return alert("Enter driver id");
          this.$set(this.busy, d.id, true);
          try {
            const j = await postJSON(`/apis/deliveries/${d.id}/assign/`, { driver_id: driver });
            d.status = j.status; d.driver_id = j.driver; d.assigned_at = j.assigned_at || d.assigned_at;
          } catch (e) { alert(`Assign failed: ${e.message}`); }
          finally { this.$set(this.busy, d.id, false); }
        },
        async unassign(d) {
          this.$set(this.busy, d.id, true);
          try {
            const j = await postJSON(`/apis/deliveries/${d.id}/unassign/`, {});
            d.status = j.status; d.driver_id = null; d.assigned_at = null;
          } catch (e) { alert(`Unassign failed: ${e.message}`); }
          finally { this.$set(this.busy, d.id, false); }
        },
      },
    });
  }

  // --- Staff panel ---
  if (document.getElementById("vendor-staff")) {
    new Vue({
      el: "#vendor-staff",
      delimiters: ["[[", "]]"],
      template: "#tpl-vendor-staff",
      data: {
        list: [],
        staffId: "",
        role: "staff",
        owner,
        loading: false,
        error: "",
        busy: false,
      },
      mounted() { this.load(); },
      methods: {
        async load() {
          this.loading = true; this.error = "";
          try {
            const u = new URL("/apis/vendor/staff/", location.origin);
            if (this.owner) u.searchParams.set("owner_id", this.owner);
            this.list = await getJSON(u.toString());
          } catch (e) { this.error = e.message || "Failed"; }
          finally { this.loading = false; }
        },
        async add() {
          const payload = { staff_id: Number(this.staffId) || 0, role: this.role };
          if (!payload.staff_id) return alert("Enter staff user id");
          this.busy = true;
          try {
            await postJSON("/apis/vendor/staff/", payload);
            this.staffId = ""; await this.load();
          } catch (e) { alert(`Add staff failed: ${e.message}`); }
          finally { this.busy = false; }
        },
      },
    });
  }

  // --- Shopable products panel ---
  if (document.getElementById("vendor-shop")) {
    new Vue({
      el: "#vendor-shop",
      delimiters: ["[[", "]]"],
      template: "#tpl-vendor-shop",
      data: {
        items: [],
        q: "",
        next: null,
        prev: null,
        addingId: null,
        loading: false,
        error: "",
      },
      mounted() { this.load(); },
      methods: {
        fmt(v) { return Number(v || 0).toLocaleString("en-KE"); },
        async load(url) {
          this.loading = true; this.error = "";
          try {
            const u = url || `/apis/vendor/shopable-products/?q=${encodeURIComponent(this.q)}`;
            const d = await getJSON(u);
            this.items = d.results || d; this.next = d.next || null; this.prev = d.previous || null;
          } catch (e) { this.error = e.message || "Failed to load products"; }
          finally { this.loading = false; }
        },
        go(url) { if (url) this.load(url); },
        async addToCart(id) {
          try {
            this.addingId = id;
            const r = await fetch(`/cart/add/${id}/`, {
              method: "POST",
              headers: { "X-CSRFToken": getCookie("csrftoken") },
              credentials: "same-origin",
            });
            const data = await r.json().catch(() => ({}));
            if (!r.ok || data.success === false) throw new Error(data.message || "Add to cart failed");
            window.dispatchEvent(new CustomEvent("cart:updated"));
          } catch (e) { alert(e.message || "Add-to-cart failed"); }
          finally { this.addingId = null; }
        },
      },
    });
  }
})();
