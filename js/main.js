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

  // Testimonial carousel: fades between cards, optional auto-rotate,
  // pauses on hover/focus, and respects reduced-motion preference.
  var carousel = document.querySelector('.testimonial-carousel');
  if (!carousel) return;

  var cards = Array.prototype.slice.call(carousel.querySelectorAll('.testimonial-card'));
  var dots = Array.prototype.slice.call(carousel.querySelectorAll('.testimonial-dot'));
  if (cards.length === 0) return;

  var current = 0;
  var intervalMs = parseInt(carousel.getAttribute('data-autorotate'), 10) || 6000;
  var prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var timer = null;

  function show(index) {
    cards.forEach(function (card, i) {
      card.classList.toggle('is-active', i === index);
    });
    dots.forEach(function (dot, i) {
      dot.classList.toggle('is-active', i === index);
    });
    current = index;
  }

  function next() {
    show((current + 1) % cards.length);
  }

  function start() {
    if (prefersReducedMotion || cards.length < 2) return;
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
});
