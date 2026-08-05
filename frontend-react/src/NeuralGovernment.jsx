import React, { useEffect, useRef } from 'react';

const NeuralGovernment = ({
  active = true,
  activityLevel = 'normal',
  mode = 'ready'
}) => {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const activityLevelRef = useRef(activityLevel);
  const modeRef = useRef(mode);

  useEffect(() => {
    activityLevelRef.current = activityLevel;
  }, [activityLevel]);

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    let ctx = canvas.getContext('2d');
    let rect = container.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;

    const handleResize = () => {
      rect = container.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx = canvas.getContext('2d');
      ctx.scale(dpr, dpr);
    };

    const resizeObserver = new ResizeObserver(() => handleResize());
    resizeObserver.observe(container);
    handleResize();

    let animationFrameId;
    const points = [];
    const connections = [];

    const addPoint = (x, y, z, tag) => points.push({ x, y, z, tag });

    // Build an Obelisk / Monument structure
    const createObelisk = () => {
      const startY = 120; // Bottom
      const endY = -120;  // Top
      const baseW = 60;
      
      // Base steps
      for (let y = startY; y > startY - 20; y -= 10) {
        let w = baseW + (startY - y);
        for (let x = -w; x <= w; x += 15) {
          addPoint(x, y, w, 'base');
          addPoint(x, y, -w, 'base');
        }
        for (let z = -w; z <= w; z += 15) {
          addPoint(w, y, z, 'base');
          addPoint(-w, y, z, 'base');
        }
      }

      // Main pillar
      for (let y = startY - 20; y > endY; y -= 15) {
        let progress = (y - endY) / (startY - 20 - endY);
        let w = baseW * 0.8 * progress; // Tapering
        for (let x = -w; x <= w; x += 10) {
          addPoint(x, y, w, 'pillar');
          addPoint(x, y, -w, 'pillar');
        }
        for (let z = -w; z <= w; z += 10) {
          addPoint(w, y, z, 'pillar');
          addPoint(-w, y, z, 'pillar');
        }
        // Core energy line in center
        addPoint(0, y, 0, 'core');
      }

      // Apex / Eye
      addPoint(0, endY - 20, 0, 'apex');
    };

    createObelisk();

    // Connect points
    points.forEach((p1, i) => {
      points.forEach((p2, j) => {
        if (i >= j) return;
        const dx = Math.abs(p1.x - p2.x);
        const dy = Math.abs(p1.y - p2.y);
        const dz = Math.abs(p1.z - p2.z);

        // Connect nearby points to form the wireframe
        if (p1.tag === 'core' && p2.tag === 'core' && dy < 20) {
          connections.push([i, j]);
        } else if (p1.tag !== 'core' && p2.tag !== 'core') {
            if (dy < 18 && dx < 18 && dz < 18) {
                // Don't connect opposite sides directly unless it's small
                if (dx + dz < 40) connections.push([i, j]);
            }
        } else if (p1.tag === 'apex' && p2.y > -140 && p2.y < -100) {
            connections.push([i, j]);
        }
      });
    });

    // Determine bounds and scale appropriately
    const bounds = points.reduce(
        (acc, p) => ({
          minX: Math.min(acc.minX, p.x),
          maxX: Math.max(acc.maxX, p.x),
          minY: Math.min(acc.minY, p.y),
          maxY: Math.max(acc.maxY, p.y),
          minZ: Math.min(acc.minZ, p.z),
          maxZ: Math.max(acc.maxZ, p.z)
        }),
        { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity, minZ: Infinity, maxZ: -Infinity }
    );
    const modelHeight = bounds.maxY - bounds.minY || 1;
    const modelWidth = bounds.maxX - bounds.minX || 1;
    const modelDepth = bounds.maxZ - bounds.minZ || 1;
    const targetHeight = rect.height * 0.8;
    const targetWidth = rect.width * 0.6;
    const scaleFactor = Math.min(targetHeight / modelHeight, targetWidth / Math.max(modelWidth, modelDepth));

    const centerXModel = (bounds.minX + bounds.maxX) / 2;
    const centerYModel = (bounds.minY + bounds.maxY) / 2;
    const centerZModel = (bounds.minZ + bounds.maxZ) / 2;

    points.forEach(p => {
      p.sx = (p.x - centerXModel) * scaleFactor;
      p.sy = (p.y - centerYModel) * scaleFactor;
      p.sz = (p.z - centerZModel) * scaleFactor;
    });

    let angle = 0;
    let pulse = 0;

    const render = () => {
      if (!active) return;

      ctx.clearRect(0, 0, rect.width, rect.height);
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;

      angle += 0.005;
      pulse += activityLevelRef.current === 'high' ? 0.08 : 0.03;

      const cos = Math.cos(angle);
      const sin = Math.sin(angle);

      const projected = points.map(p => {
        const x = p.sx * cos - p.sz * sin;
        const z = p.sx * sin + p.sz * cos;
        const y = p.sy;

        const fov = 400;
        const scale = fov / (fov + z + 200);

        return {
          x: x * scale + centerX,
          y: y * scale + centerY,
          scale,
          tag: p.tag,
          origY: p.y
        };
      });

      const palette = {
        thinking: { primary: '203, 213, 225', accent: '251, 191, 36' },
        applying: { primary: '203, 213, 225', accent: '110, 231, 183' },
        provider_unavailable: { primary: '100, 116, 139', accent: '148, 163, 184' },
        error: { primary: '190, 90, 103', accent: '231, 162, 170' },
        disabled: { primary: '100, 116, 139', accent: '148, 163, 184' },
        ready: { primary: '203, 213, 225', accent: '251, 191, 36' }
      }[modeRef.current] || { primary: '203, 213, 225', accent: '251, 191, 36' };
      const primaryRbg = palette.primary;
      const accentRgb = palette.accent;
      
      ctx.lineWidth = 0.85;

      connections.forEach(([i, j]) => {
        const p1 = projected[i];
        const p2 = projected[j];

        if (p1.scale > 0.1 && p2.scale > 0.1) {
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);

          if (p1.tag === 'core' && p2.tag === 'core') {
            ctx.save();
            ctx.strokeStyle = `rgba(${accentRgb}, 0.38)`;
            ctx.lineWidth = 1.15;
            ctx.stroke();
            ctx.restore();
          } else {
            ctx.strokeStyle = `rgba(${primaryRbg}, 0.22)`;
            ctx.stroke();
          }
        }
      });

      projected.forEach(p => {
        let size = Math.max(0.5, 2 * p.scale);
        ctx.beginPath();

        let r, g, b, a;

        if (p.tag === 'core') {
            const wave = Math.sin(p.origY / 15 - pulse);
            [r, g, b] = accentRgb.split(',').map(v => Number(v.trim()));
            if (wave > 0.5) {
                a = 0.72;
                size *= 1.35;
                ctx.shadowBlur = 0;
            } else {
                a = 0.26;
                ctx.shadowBlur = 0;
            }
        } else if (p.tag === 'apex') {
            [r, g, b] = accentRgb.split(',').map(v => Number(v.trim()));
            a = 0.68;
            size *= 1.9 + Math.sin(pulse) * 0.18;
            ctx.shadowBlur = 0;
        } else {
            ctx.shadowBlur = 0;
            [r, g, b] = primaryRbg.split(',').map(v => Number(v.trim()));
            a = 0.28;
        }

        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${a})`;
        if (p.tag === 'apex') {
            ctx.beginPath();
            ctx.arc(p.x, p.y, size, 0, Math.PI * 2);
            ctx.fill();
        } else {
            const dim = size * 2;
            ctx.fillRect(p.x - size, p.y - size, dim, dim);
        }
        ctx.shadowBlur = 0;
      });

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
      resizeObserver.disconnect();
    };
  }, [active]);

  return (
    <div ref={containerRef} className="w-full h-full absolute inset-0">
      <canvas ref={canvasRef} className="block w-full h-full" />
    </div>
  );
};

export default NeuralGovernment;
