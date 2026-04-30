import { useEffect, useRef } from "react";

/**
 * Interactive login background — reacts to mouse movement.
 *
 * Effects:
 * 1. Floating orbs that drift toward the cursor
 * 2. Particles that scatter away from the cursor
 * 3. Connection lines that glow brighter near the cursor
 * 4. Ripple effect on click
 * 5. Subtle grid that warps near cursor
 */
export default function LoginBackground() {
  const canvasRef = useRef(null);
  const rafRef = useRef(null);
  const mouseRef = useRef({ x: -1000, y: -1000 });
  const clickRipplesRef = useRef([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");

    function resize() {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener("resize", resize);

    // Track mouse
    function onMouseMove(e) {
      mouseRef.current = { x: e.clientX, y: e.clientY };
    }
    function onClick(e) {
      clickRipplesRef.current.push({
        x: e.clientX,
        y: e.clientY,
        radius: 0,
        maxRadius: 200,
        alpha: 0.6,
      });
    }
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("click", onClick);

    // Orbs — large soft glows that drift toward cursor
    const orbs = [
      { x: 0.2, y: 0.3, r: 250, color: [249, 115, 22], baseX: 0.2, baseY: 0.3 },
      { x: 0.8, y: 0.7, r: 200, color: [234, 88, 12], baseX: 0.8, baseY: 0.7 },
      { x: 0.5, y: 0.15, r: 180, color: [251, 146, 60], baseX: 0.5, baseY: 0.15 },
      { x: 0.75, y: 0.4, r: 220, color: [180, 83, 9], baseX: 0.75, baseY: 0.4 },
      { x: 0.3, y: 0.8, r: 190, color: [124, 45, 18], baseX: 0.3, baseY: 0.8 },
    ];

    // Particles — interactive dots
    const particles = Array.from({ length: 80 }, () => ({
      x: Math.random(),
      y: Math.random(),
      baseVx: (Math.random() - 0.5) * 0.00008,
      baseVy: (Math.random() - 0.5) * 0.00008,
      vx: 0,
      vy: 0,
      r: Math.random() * 2 + 0.5,
      alpha: Math.random() * 0.5 + 0.15,
      pulse: Math.random() * Math.PI * 2,
    }));

    let time = 0;

    function draw() {
      const w = canvas.width;
      const h = canvas.height;
      const mx = mouseRef.current.x;
      const my = mouseRef.current.y;
      time += 1;

      // Dark base
      ctx.fillStyle = "#0C0C0F";
      ctx.fillRect(0, 0, w, h);

      // Draw orbs — attracted toward cursor
      for (const orb of orbs) {
        // Drift toward mouse (subtle)
        const targetX = orb.baseX + ((mx / w) - 0.5) * 0.08;
        const targetY = orb.baseY + ((my / h) - 0.5) * 0.08;
        orb.x += (targetX - orb.x) * 0.02;
        orb.y += (targetY - orb.y) * 0.02;

        // Also add gentle autonomous float
        const floatX = Math.sin(time * 0.003 + orb.baseX * 10) * 0.03;
        const floatY = Math.cos(time * 0.004 + orb.baseY * 10) * 0.02;

        const cx = w * (orb.x + floatX);
        const cy = h * (orb.y + floatY);

        // Glow brighter when cursor is near
        const distToMouse = Math.sqrt((cx - mx) ** 2 + (cy - my) ** 2);
        const proximityBoost = Math.max(0, 1 - distToMouse / 400) * 0.04;

        const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, orb.r);
        gradient.addColorStop(0, `rgba(${orb.color.join(",")}, ${0.08 + proximityBoost})`);
        gradient.addColorStop(0.4, `rgba(${orb.color.join(",")}, ${0.03 + proximityBoost * 0.5})`);
        gradient.addColorStop(1, `rgba(${orb.color.join(",")}, 0)`);

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(cx, cy, orb.r, 0, Math.PI * 2);
        ctx.fill();
      }

      // Draw and update particles
      for (const p of particles) {
        const px = p.x * w;
        const py = p.y * h;
        const dx = px - mx;
        const dy = py - my;
        const dist = Math.sqrt(dx * dx + dy * dy);

        // Repel from cursor (within 150px radius)
        if (dist < 150 && dist > 0) {
          const force = (1 - dist / 150) * 0.0008;
          p.vx += (dx / dist) * force;
          p.vy += (dy / dist) * force;
        }

        // Apply base velocity + interaction velocity with damping
        p.vx = p.vx * 0.95 + p.baseVx;
        p.vy = p.vy * 0.95 + p.baseVy;
        p.x += p.vx;
        p.y += p.vy;
        p.pulse += 0.02;

        // Wrap around
        if (p.x < -0.05) p.x = 1.05;
        if (p.x > 1.05) p.x = -0.05;
        if (p.y < -0.05) p.y = 1.05;
        if (p.y > 1.05) p.y = -0.05;

        // Draw particle — brighter near cursor
        const glowBoost = dist < 200 ? (1 - dist / 200) * 0.4 : 0;
        const sizeBoost = dist < 200 ? (1 - dist / 200) * 1.5 : 0;
        const alpha = p.alpha * (0.6 + Math.sin(p.pulse) * 0.4) + glowBoost;

        ctx.beginPath();
        ctx.arc(p.x * w, p.y * h, p.r + sizeBoost, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(249, 115, 22, ${Math.min(alpha, 1)})`;
        ctx.fill();
      }

      // Draw connections — glow brighter near cursor
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const ax = particles[i].x * w;
          const ay = particles[i].y * h;
          const bx = particles[j].x * w;
          const by = particles[j].y * h;
          const dx = ax - bx;
          const dy = ay - by;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < 130) {
            // Check if line is near cursor
            const midX = (ax + bx) / 2;
            const midY = (ay + by) / 2;
            const distToMouse = Math.sqrt((midX - mx) ** 2 + (midY - my) ** 2);
            const mouseBoost = distToMouse < 200 ? (1 - distToMouse / 200) * 0.15 : 0;

            const alpha = (1 - dist / 130) * 0.08 + mouseBoost;
            ctx.beginPath();
            ctx.moveTo(ax, ay);
            ctx.lineTo(bx, by);
            ctx.strokeStyle = `rgba(249, 115, 22, ${alpha})`;
            ctx.lineWidth = mouseBoost > 0.05 ? 1 : 0.5;
            ctx.stroke();
          }
        }
      }

      // Mouse glow — soft radial light following cursor
      if (mx > 0 && my > 0) {
        const glow = ctx.createRadialGradient(mx, my, 0, mx, my, 250);
        glow.addColorStop(0, "rgba(249, 115, 22, 0.06)");
        glow.addColorStop(0.5, "rgba(249, 115, 22, 0.02)");
        glow.addColorStop(1, "rgba(249, 115, 22, 0)");
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(mx, my, 250, 0, Math.PI * 2);
        ctx.fill();
      }

      // Click ripples
      const ripples = clickRipplesRef.current;
      for (let i = ripples.length - 1; i >= 0; i--) {
        const rip = ripples[i];
        rip.radius += 4;
        rip.alpha -= 0.012;

        if (rip.alpha <= 0) {
          ripples.splice(i, 1);
          continue;
        }

        ctx.beginPath();
        ctx.arc(rip.x, rip.y, rip.radius, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(249, 115, 22, ${rip.alpha})`;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Inner ring
        if (rip.radius > 20) {
          ctx.beginPath();
          ctx.arc(rip.x, rip.y, rip.radius * 0.6, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(251, 146, 60, ${rip.alpha * 0.5})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }

      // Subtle grid
      ctx.strokeStyle = "rgba(255,255,255,0.012)";
      ctx.lineWidth = 0.5;
      const gridSize = 60;
      for (let x = 0; x < w; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
      for (let y = 0; y < h; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }

      rafRef.current = requestAnimationFrame(draw);
    }

    draw();

    return () => {
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("click", onClick);
      cancelAnimationFrame(rafRef.current);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 0,
        pointerEvents: "none",
      }}
    />
  );
}
