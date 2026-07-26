/* main.js — storefront interactions: navbar scroll state, gender toggle,
   add-to-cart / wishlist AJAX, live search suggestions, toasts. */
(function () {
  const header = document.getElementById('site-header');
  window.addEventListener('scroll', () => {
    if (header) header.classList.toggle('scrolled', window.scrollY > 30);
  });

  function showToast(msg) {
    const t = document.getElementById('toast');
    if (!t) return;
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2200);
  }
  window.voidToast = showToast;

  // Gender toggle
  const genderToggle = document.getElementById('gender-toggle');
  if (genderToggle) {
    genderToggle.addEventListener('click', () => {
      const isWomen = genderToggle.classList.contains('women');
      const next = isWomen ? 'Men' : 'Women';
      fetch('/set-gender/' + next).then(() => { window.location.reload(); });
    });
  }

  // Add to cart (AJAX, works from product cards and product detail page)
  document.querySelectorAll('.add-to-cart-form').forEach(form => {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      const data = new FormData(form);
      fetch('/cart/add', { method: 'POST', body: data })
        .then(r => r.json())
        .then(res => {
          if (res.ok) {
            showToast('Added to bag');
            const countEl = document.getElementById('cart-count');
            if (countEl) countEl.textContent = res.cart_count;
          } else {
            showToast(res.error || 'Could not add to bag');
          }
        });
    });
  });

  // Wishlist toggle
  document.querySelectorAll('.wish-btn').forEach(btn => {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      const pid = btn.dataset.productId;
      fetch('/wishlist/toggle/' + pid, { method: 'POST' })
        .then(r => {
          if (r.status === 401) { window.location.href = '/login'; return; }
          return r.json();
        })
        .then(res => {
          if (!res) return;
          btn.classList.toggle('active', res.active);
          showToast(res.active ? 'Added to wishlist' : 'Removed from wishlist');
        });
    });
  });

  // Live search suggestions
  const searchInput = document.getElementById('live-search');
  const suggestBox = document.getElementById('search-suggestions');
  if (searchInput && suggestBox) {
    let debounce;
    searchInput.addEventListener('input', () => {
      clearTimeout(debounce);
      const q = searchInput.value.trim();
      if (q.length < 2) { suggestBox.innerHTML = ''; suggestBox.style.display = 'none'; return; }
      debounce = setTimeout(() => {
        fetch('/api/search-suggest?q=' + encodeURIComponent(q))
          .then(r => r.json())
          .then(items => {
            if (!items.length) { suggestBox.style.display = 'none'; return; }
            suggestBox.innerHTML = items.map(i =>
              `<a href="/product/${i.slug}">${i.name}</a>`
            ).join('');
            suggestBox.style.display = 'block';
          });
      }, 250);
    });
    document.addEventListener('click', e => {
      if (!suggestBox.contains(e.target) && e.target !== searchInput) suggestBox.style.display = 'none';
    });
  }

  // Product detail: image gallery thumbnail switching
  document.querySelectorAll('.gallery-thumb').forEach(thumb => {
    thumb.addEventListener('click', () => {
      const main = document.getElementById('gallery-main');
      if (main) main.src = thumb.dataset.full;
      document.querySelectorAll('.gallery-thumb').forEach(t => t.classList.remove('active'));
      thumb.classList.add('active');
    });
  });
})();
