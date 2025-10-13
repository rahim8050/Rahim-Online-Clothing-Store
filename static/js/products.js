(function () {
  const payloadEl = document.getElementById('initial-data');
  if (!payloadEl || !payloadEl.textContent.trim()) {
    console.error("❌ No initial data found in template");
    return;
  }

  let initialData = {};
  try {
    initialData = JSON.parse(payloadEl.textContent);
  } catch (err) {
    console.error("❌ Failed to parse initial data JSON:", err);
    return;
  }

  function capitalizeWords(text) {
    return text
      ? text.toLowerCase().split(' ')
          .map(w => w.charAt(0).toUpperCase() + w.slice(1))
          .join(' ')
      : '';
  }

  function capitalizeSlug(slug) {
    return slug
      ? slug.replace(/[-_]/g, ' ')
          .split(' ')
          .map(w => w.charAt(0).toUpperCase() + w.slice(1))
          .join(' ')
      : '';
  }

  new Vue({
    el: '#productApp',
    delimiters: ['[[', ']]'],
    data: {
      categories: initialData.categories || [],
      products: initialData.products || [],
      displayedProducts: initialData.products || [],
      selectedCategory: '',
      searchQuery: '',
      sortOption: 'price_asc',
      hoveredProductId: null
    },
    computed: {
      headerText() {
        if (this.searchQuery)
          return `Search results for "${this.searchQuery}"`;
        if (this.selectedCategory) {
          const cat = this.categories.find(c => c.slug === this.selectedCategory);
          return cat ? cat.name : 'Products';
        }
        return 'All Products';
      }
    },
    methods: {
      filterByCategory() {
        this.applyFilters();
        this.updateUrl();
      },
      searchProducts() {
        this.applyFilters();
        this.updateUrl();
      },
      sortProducts() {
        this.applyFilters();
        this.updateUrl();
      },
      applyFilters() {
        let filtered = [...this.products];

        if (this.selectedCategory)
          filtered = filtered.filter(p => p.category_slug === this.selectedCategory);

        if (this.searchQuery) {
          const q = this.searchQuery.toLowerCase();
          filtered = filtered.filter(p =>
            p.name.toLowerCase().includes(q) ||
            (p.description || '').toLowerCase().includes(q)
          );
        }

        if (this.sortOption === 'price_asc')
          filtered.sort((a, b) => parseFloat(a.price) - parseFloat(b.price));
        else if (this.sortOption === 'price_desc')
          filtered.sort((a, b) => parseFloat(b.price) - parseFloat(a.price));

        this.displayedProducts = filtered;
      },
      handleMouseEnter(id) {
        this.hoveredProductId = id;
      },
      handleMouseLeave() {
        this.hoveredProductId = null;
      },
      updateUrl() {
        const params = new URLSearchParams(window.location.search);
        const setOrDelete = (key, val) => {
          if (val) params.set(key, val);
          else params.delete(key);
        };
        setOrDelete('sort', this.sortOption);
        setOrDelete('category', this.selectedCategory);
        setOrDelete('search', this.searchQuery);
        const qs = params.toString();
        window.history.replaceState(
          {},
          '',
          qs ? `${window.location.pathname}?${qs}` : window.location.pathname
        );
      }
    },
    mounted() {
      this.products = this.products.map(p => ({
        ...p,
        name: capitalizeWords(p.name),
      }));
      this.categories = this.categories.map(c => ({
        ...c,
        name: capitalizeWords(c.name),
      }));

      const params = new URLSearchParams(window.location.search);
      const sort = params.get('sort');
      const cat = params.get('category');
      const search = params.get('search');

      if (sort) this.sortOption = sort;
      if (cat) this.selectedCategory = cat;
      if (search) this.searchQuery = search;

      this.applyFilters();
    }
  });
})();
