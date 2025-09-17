(function () {
  // Read initial JSON safely
  const payloadEl = document.getElementById('initial-data');
  const initialData = JSON.parse(payloadEl.textContent);

  function capitalizeWords(text) {
    return text ? text.toLowerCase().split(' ')
      .map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ') : '';
  }

  function capitalizeSlug(slug) {
    return slug ? slug.replace(/[-_]/g, ' ').split(' ')
      .map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ') : '';
  }

  new Vue({
    el: '#productApp',
    delimiters: ['[[', ']]'],
    data: {
      categories: initialData.categories,
      products: initialData.products,
      selectedCategory: '',
      searchQuery: '',
      sortOption: 'price_asc',
      displayedProducts: initialData.products,
      hoveredProductId: null
    },
    computed: {
      headerText() {
        if (this.searchQuery) return `Search results for "${this.searchQuery}"`;
        if (this.selectedCategory) {
          const category = this.categories.find(c => c.slug === this.selectedCategory);
          return category ? category.name : 'Products';
        }
        return 'All Products';
      }
    },
    methods: {
      filterByCategory() { this.applyFilters(); this.updateUrl(); },
      searchProducts() { this.applyFilters(); this.updateUrl(); },
      sortProducts() { this.applyFilters(); this.updateUrl(); },
      applyFilters() {
        let filtered = [...this.products];

        if (this.selectedCategory) {
          filtered = filtered.filter(p => p.category_slug === this.selectedCategory);
        }

        if (this.searchQuery) {
          const q = this.searchQuery.toLowerCase();
          filtered = filtered.filter(p =>
            p.name.toLowerCase().includes(q) ||
            (p.description || '').toLowerCase().includes(q)
          );
        }

        if (this.sortOption === 'price_asc') {
          filtered.sort((a, b) => a.price - b.price);
        } else if (this.sortOption === 'price_desc') {
          filtered.sort((a, b) => b.price - a.price);
        }

        this.displayedProducts = filtered;
      },
      handleMouseEnter(id) { this.hoveredProductId = id; },
      handleMouseLeave() { this.hoveredProductId = null; },
      updateUrl() {
        const params = new URLSearchParams(window.location.search);
        // set or delete to avoid stale params
        const setOrDelete = (key, val) => {
          if (val) params.set(key, val); else params.delete(key);
        };
        setOrDelete('sort', this.sortOption);
        setOrDelete('category', this.selectedCategory);
        setOrDelete('search', this.searchQuery);
        const qs = params.toString();
        window.history.replaceState({}, '', qs ? `${window.location.pathname}?${qs}` : window.location.pathname);
      }
    },
    mounted() {
      // normalize names/slugs
      this.products = this.products.map(p => ({
        ...p, name: capitalizeWords(p.name), slug: capitalizeSlug(p.slug)
      }));
      this.categories = this.categories.map(c => ({
        ...c, name: capitalizeWords(c.name), slug: capitalizeSlug(c.slug)
      }));

      const params = new URLSearchParams(window.location.search);
      const initialSort = params.get('sort');
      if (initialSort) this.sortOption = initialSort;
      const initialCategory = params.get('category');
      if (initialCategory) this.selectedCategory = initialCategory;
      const initialSearch = params.get('search');
      if (initialSearch) this.searchQuery = initialSearch;

      this.applyFilters();
    }
  });
})();
