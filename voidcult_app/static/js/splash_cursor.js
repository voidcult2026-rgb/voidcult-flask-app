(function () {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduceMotion) return;

  const canvas = document.createElement('canvas');
  canvas.id = 'splash-cursor-canvas';
  canvas.style.cssText = 'position:fixed;inset:0;z-index:9998;pointer-events:none;mix-blend-mode:screen;';
  document.body.appendChild(canvas);
  const ctx = canvas.getContext('2d');

  let w, h;
  function resize() { w = canvas.width = window.innerWidth; h = canvas.height = window.innerHeight; }
  window.addEventListener('resize', resize);
  resize();

  const COLORS = ['#6A0DAD', '#1A0826', '#FFFFFF', '#A9A9A9', '#6A0DAD'];
  let blobs = [];
  let last = { x: -999, y: -999, t: Date.now() };

  function spawn(x, y, speed) {
    const hue = COLORS[Math.floor(Math.random() * COLORS.length)];
    blobs.push({
      x, y,
      r: 6 + Math.random() * 10 + Math.min(speed * 0.15, 26),
      life: 1,
      color: hue,
      vx: (Math.random() - 0.5) * 0.6,
      vy: (Math.random() - 0.5) * 0.6,
    });
    if (blobs.length > 120) blobs.shift();
  }

  function pointerMove(x, y) {
    const now = Date.now();
    const dt = Math.max(now - last.t, 1);
    const dist = Math.hypot(x - last.x, y - last.y);
    const speed = dist / dt * 16;
    const steps = Math.min(Math.max(Math.floor(dist / 8), 1), 8);
    for (let i = 0; i < steps; i++) {
      const t = i / steps;
      spawn(last.x + (x - last.x) * t, last.y + (y - last.y) * t, speed);
    }
    last = { x, y, t: now };
  }

  window.addEventListener('mousemove', e => pointerMove(e.clientX, e.clientY));
  window.addEventListener('touchmove', e => {
    if (e.touches[0]) pointerMove(e.touches[0].clientX, e.touches[0].clientY);
  }, { passive: true });

  function loop() {
    ctx.clearRect(0, 0, w, h);
    blobs.forEach(b => {
      b.x += b.vx; b.y += b.vy; b.life -= 0.025; b.r *= 0.985;
      if (b.life <= 0) return;
      const g = ctx.createRadialGradient(b.x, b.y, 0, b.x, b.y, b.r);
      g.addColorStop(0, hexToRgba(b.color, b.life * 0.55));
      g.addColorStop(1, hexToRgba(b.color, 0));
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
      ctx.fill();
    });
    blobs = blobs.filter(b => b.life > 0);
    requestAnimationFrame(loop);
  }
  function hexToRgba(hex, alpha) {
    const n = parseInt(hex.slice(1), 16);
    const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
    return rgba(${r},${g},${b},${alpha});
  }
  loop();
})();