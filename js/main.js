document.addEventListener('DOMContentLoaded', function () {
  var y = document.getElementById('year');
  if (y) y.textContent = new Date().getFullYear();

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
