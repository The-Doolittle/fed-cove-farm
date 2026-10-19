document.addEventListener('DOMContentLoaded', function () {
  var y = document.getElementById('year');
  if (y) y.textContent = new Date().getFullYear();

  // Mobile nav drawer: opens on hamburger tap, closes on scrim click,
  // close button, link click, Escape, or resizing back to desktop.
  var toggle = document.querySelector('.nav-toggle');
  var drawer = document.querySelector('.nav-drawer');
  var scrim = document.querySelector('.nav-scrim');
  var closeBtn = document.querySelector('.nav-drawer-close');

  if (toggle && drawer && scrim) {
    var drawerLinks = drawer.querySelectorAll('a');

    function openDrawer() {
      drawer.classList.add('is-open');
      scrim.classList.add('is-open');
      drawer.setAttribute('aria-hidden', 'false');
      toggle.setAttribute('aria-expanded', 'true');
      document.body.classList.add('nav-open');
    }

    function closeDrawer() {
      drawer.classList.remove('is-open');
      scrim.classList.remove('is-open');
      drawer.setAttribute('aria-hidden', 'true');
      toggle.setAttribute('aria-expanded', 'false');
      document.body.classList.remove('nav-open');
    }

    toggle.addEventListener('click', openDrawer);
    scrim.addEventListener('click', closeDrawer);
    if (closeBtn) closeBtn.addEventListener('click', closeDrawer);
    drawerLinks.forEach(function (link) {
      link.addEventListener('click', closeDrawer);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeDrawer();
    });
    window.addEventListener('resize', function () {
      if (window.innerWidth > 820) closeDrawer();
    });
  }

  // Auto-rotating carousels: fades between slides, pauses on hover/focus,
  // and respects reduced-motion preference.
  var carousels = document.querySelectorAll('.testimonial-carousel');
  if (!carousels.length) return;

  function initCarousel(carousel) {
    var slides = Array.prototype.slice.call(carousel.querySelectorAll('.testimonial-card'));
    var dots = Array.prototype.slice.call(carousel.querySelectorAll('.testimonial-dot'));
    if (slides.length === 0) return;

    var current = 0;
    var intervalMs = parseInt(carousel.getAttribute('data-autorotate'), 10) || 6000;
    var prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var timer = null;

    function show(index) {
      slides.forEach(function (slide, i) {
        slide.classList.toggle('is-active', i === index);
      });
      if (dots.length) {
        dots.forEach(function (dot, i) {
          dot.classList.toggle('is-active', i === index);
        });
      }
      current = index;
    }

    function next() {
      show((current + 1) % slides.length);
    }

    function start() {
      if (prefersReducedMotion || slides.length < 2) return;
      stop();
      timer = setInterval(next, intervalMs);
    }

    function stop() {
      if (timer) clearInterval(timer);
      timer = null;
    }

    dots.forEach(function (dot, i) {
      dot.addEventListener('click', function () {
        show(i);
        start();
      });
    });

    carousel.addEventListener('mouseenter', stop);
    carousel.addEventListener('mouseleave', start);
    carousel.addEventListener('focusin', stop);
    carousel.addEventListener('focusout', start);

    show(0);
    start();
  }

  carousels.forEach(initCarousel);
});

// Order form: live running total.
document.addEventListener('DOMContentLoaded', function () {
  var form = document.querySelector('[data-order-form]');
  if (!form) return;
  var out = form.querySelector('[data-order-total]');
  var inputs = form.querySelectorAll('input[data-price]');
  function update() {
    var cents = 0;
    inputs.forEach(function (input) {
      var qty = parseInt(input.value, 10);
      if (qty > 0) cents += Math.round(parseFloat(input.dataset.price) * 100) * qty;
    });
    out.textContent = '$' + (cents / 100).toFixed(2);
  }
  inputs.forEach(function (input) { input.addEventListener('input', update); });
  update();
});

// Hero video: lighter file on small screens; just the poster image for reduced-motion or data-saver.
document.addEventListener('DOMContentLoaded', function () {
  var video = document.querySelector('video[data-src-large]');
  if (!video) return;
  var saveData = navigator.connection && navigator.connection.saveData;
  if (saveData || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  video.src = window.matchMedia('(max-width: 900px)').matches ? video.dataset.srcSmall : video.dataset.srcLarge;
  video.play().catch(function () {});
});
