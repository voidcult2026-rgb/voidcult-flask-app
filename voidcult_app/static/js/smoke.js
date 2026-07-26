/* smoke.js — lightweight interactive particle layer over the CSS smoke
   gradients. Runs on <canvas>, GPU-friendly (few particles, additive glow,
   transform-only updates), and reacts to mouse position. Respects
   prefers-reduced-motion. */
(function () {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const canvas = document.getElementById('smoke-canvas');
  if (!canvas || reduceMotion) return;
  const ctx = canvas.getContext('2d');
  let w, h, particles = [];
  const COUNT = window.innerWidth < 700 ? 22 : 45;
  let mouse = { x: -9999, y: -9999 };

  function resize() {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
  }
  window.addEventListener('resize', resize);
  resize();

  function Particle() {
    this.reset();
  }
  Particle.prototype.reset = function () {
    this.x = Math.random() * w;
    this.y = h + Math.random() * 100;
    this.r = 40 + Math.random() * 90;
    this.speed = 0.15 + Math.random() * 0.35;
    this.alpha = 0.03 + Math.random() * 0.05;
    this.drift = (Math.random() - 0.5) * 0.3;
  };
  Particle.prototype.update = function () {
    this.y -= this.speed;
    this.x += this.drift;
    // gentle mouse repulsion for interactivity
    const dx = this.x - mouse.x, dy = this.y - mouse.y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist < 160) {
      this.x += (dx / dist) * 1.1;
      this.y += (dy / dist) * 1.1;
    }
    if (this.y < -this.r) this.reset();
  };
  Particle.prototype.draw = function () {
    const gradient = ctx.createRadialGradient(this.x, this.y, 0, this.x, this.y, this.r);
    gradient.addColorStop(0, `rgba(106,13,173,${this.alpha})`);
    gradient.addColorStop(1, 'rgba(106,13,173,0)');
    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.r, 0, Math.PI * 2);
    ctx.fill();
  };

  for (let i = 0; i < COUNT; i++) particles.push(new Particle());

  window.addEventListener('mousemove', e => { mouse.x = e.clientX; mouse.y = e.clientY; });
  window.addEventListener('touchmove', e => {
    if (e.touches[0]) { mouse.x = e.touches[0].clientX; mouse.y = e.touches[0].clientY; }
  }, { passive: true });

  function loop() {
    ctx.clearRect(0, 0, w, h);
    particles.forEach(p => { p.update(); p.draw(); });
    requestAnimationFrame(loop);
  }
  loop();
})();
