(function () {
  function fadeOut(el, delay) {
    setTimeout(function () {
      el.classList.add('out');
      setTimeout(function () { el.remove(); }, 400);
    }, delay);
  }

  document.querySelectorAll('.toast').forEach(function (t, i) { fadeOut(t, 3800 + i * 300); });

  function showToast(message, kind) {
    var box = document.querySelector('.toasts');
    if (!box) return;
    var t = document.createElement('div');
    t.className = 'toast ' + (kind || 'success');
    t.textContent = message;
    box.appendChild(t);
    fadeOut(t, 3000);
  }

  // student / vendor switch on the login and register pages
  document.querySelectorAll('[data-seg]').forEach(function (seg) {
    var form = seg.parentElement.querySelector('form');
    var input = form.querySelector('input[name=role]');
    function apply(role) {
      input.value = role;
      seg.querySelectorAll('button').forEach(function (b) {
        b.classList.toggle('active', b.dataset.role === role);
      });
      form.querySelectorAll('[data-panel]').forEach(function (p) {
        var on = p.dataset.panel === role;
        p.hidden = !on;
        p.querySelectorAll('input,select').forEach(function (f) { f.disabled = !on; });
      });
      var link = document.querySelector('[data-role-link]');
      if (link) link.href = link.href.split('?')[0] + '?role=' + role;
    }
    seg.querySelectorAll('button').forEach(function (b) {
      b.addEventListener('click', function () { apply(b.dataset.role); });
    });
    apply(input.value);
  });

  // category chips on the menu page
  var chips = document.querySelectorAll('[data-chip]');
  chips.forEach(function (chip) {
    chip.addEventListener('click', function () {
      chips.forEach(function (c) { c.classList.remove('active'); });
      chip.classList.add('active');
      var cat = chip.dataset.chip;
      document.querySelectorAll('.item-card').forEach(function (card) {
        card.hidden = !(cat === 'all' || card.dataset.cat === cat);
      });
    });
  });

  // stall search
  var search = document.getElementById('stallSearch');
  if (search) {
    search.addEventListener('input', function () {
      var q = search.value.trim().toLowerCase();
      var shown = 0;
      document.querySelectorAll('.stall-card').forEach(function (card) {
        var match = card.dataset.name.indexOf(q) !== -1;
        card.hidden = !match;
        if (match) shown++;
      });
      var none = document.getElementById('noStalls');
      if (none) none.hidden = shown !== 0;
    });
  }

  // quantity stepper on menu cards
  document.querySelectorAll('.js-add .stepper button[data-step]').forEach(function (b) {
    b.addEventListener('click', function () {
      var inp = b.parentElement.querySelector('input');
      var v = parseInt(inp.value || '1', 10) + parseInt(b.dataset.step, 10);
      inp.value = Math.max(1, Math.min(20, v));
    });
  });

  // add to cart without reloading the page
  document.querySelectorAll('form.js-add').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      if (!window.fetch) return;
      e.preventDefault();
      fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: { 'X-Requested-With': 'fetch' }
      }).then(function (r) { return r.json(); }).then(function (d) {
        showToast(d.message, d.ok ? 'success' : 'error');
        if (!d.ok) return;
        var bar = document.getElementById('cartbar');
        if (bar) {
          bar.classList.remove('hide');
          bar.hidden = false;
          document.getElementById('cartbar-count').textContent = d.count;
          document.getElementById('cartbar-total').textContent = d.total;
        }
        var pill = document.getElementById('nav-cart-count');
        if (pill) { pill.textContent = d.count; pill.hidden = false; }
        var qty = form.querySelector('input[name=qty]');
        if (qty) qty.value = 1;
      }).catch(function () { form.submit(); });
    });
  });

  // photo preview when picking a file
  document.querySelectorAll('input[data-preview]').forEach(function (inp) {
    inp.addEventListener('change', function () {
      var file = inp.files && inp.files[0];
      if (!file) return;
      var holder = inp.closest('label');
      var img = holder.querySelector('img.thumb');
      if (!img) {
        var ph = holder.querySelector('.thumb');
        img = document.createElement('img');
        img.className = 'thumb';
        img.alt = 'Preview';
        ph.replaceWith(img);
      }
      img.src = URL.createObjectURL(file);
    });
  });
})();
