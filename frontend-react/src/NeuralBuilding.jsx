import React, { useEffect, useRef } from 'react';

const NeuralBuilding = ({
  active = true,
  activityLevel = 'normal',
  tier = 3,
  sector = 'Services',
  status = 'STABLE'
}) => {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);

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

    const createBlock = (yBottom, yTop, widthSize, depthSize, xOffset = 0, zOffset = 0) => {
      [-widthSize / 2, widthSize / 2].forEach(x => {
        [-depthSize / 2, depthSize / 2].forEach(z => {
          for (let y = yBottom; y <= yTop; y += 10) {
            addPoint(x + xOffset, y, z + zOffset, 'structure');
          }
        });
      });

      for (let y = yBottom; y <= yTop; y += 15) {
        for (let x = -widthSize / 2; x <= widthSize / 2; x += widthSize / 2) {
          for (let z = -depthSize / 2; z <= depthSize / 2; z += 5) {
            if (Math.abs(x) === widthSize / 2) addPoint(x + xOffset, y, z + zOffset, 'window');
          }
        }
        for (let z = -depthSize / 2; z <= depthSize / 2; z += depthSize / 2) {
          for (let x = -widthSize / 2; x <= widthSize / 2; x += 5) {
            if (Math.abs(z) === depthSize / 2) addPoint(x + xOffset, y, z + zOffset, 'window');
          }
        }
      }
    };

    const baseW = tier === 3 ? 50 : tier === 2 ? 40 : 30;
    const startY = 80;
    const sectorKey = String(sector || '').toLowerCase().includes('bank') ? 'finance' : String(sector || 'services').toLowerCase();

    if (sectorKey.includes('food')) {
      createBlock(startY - 36, startY, 42, 32, -22, -10);
      createBlock(startY - 36, startY, 42, 32, 22, 10);
      createBlock(startY - 76, startY - 36, 38, 30, 0, 0);
      createBlock(startY - 112, startY - 76, 30, 24, 14, -6);
      for (let a = 0; a < Math.PI * 2; a += Math.PI / 8) {
        addPoint(Math.cos(a) * 64, startY + 8, Math.sin(a) * 38, 'core');
      }
      for (let y = startY - 112; y < startY; y += 8) {
        addPoint(0, y, 0, 'core');
      }
    } else {
      createBlock(startY - 40, startY, baseW, baseW);
      if (tier >= 2) {
        createBlock(startY - 90, startY - 40, baseW * 0.8, baseW * 0.8);
      } else {
        createBlock(startY - 60, startY - 40, baseW, baseW);
      }
      if (tier >= 3) {
        createBlock(startY - 150, startY - 90, baseW * 0.6, baseW * 0.6);
      }

      for (let y = startY - tier * 55; y < startY; y += 4) {
        addPoint(0, y, 0, 'core');
      }

      if (tier >= 2) {
        const topY = startY - (tier === 3 ? 150 : 90);
        for (let y = topY - 30; y < topY; y += 5) {
          addPoint(0, y, 0, 'spire');
        }
      }
    }

    points.forEach((p1, i) => {
      points.forEach((p2, j) => {
        if (i === j) return;
        const dx = Math.abs(p1.x - p2.x);
        const dy = Math.abs(p1.y - p2.y);
        const dz = Math.abs(p1.z - p2.z);

        let connected = false;
        if (dx < 1 && dz < 1 && dy < 16) connected = true;
        if (dy < 1) {
          if (dx < 1 && dz < 10) connected = true;
          if (dz < 1 && dx < 10) connected = true;
        }
        if (p1.tag === 'core' && p2.tag === 'core' && dy < 6) connected = true;

        if (connected) {
          connections.push([i, j]);
        }
      });
    });

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
    const targetHeight = rect.height * 0.9;
    const targetWidth = rect.width * 0.7;
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

      angle += 0.003;
      pulse += 0.05;

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

      ctx.lineWidth = 0.85;
      const sectorPalette = {
        food: { base: '203, 213, 225', pulse: '251, 191, 36', accent: '#FBBF24' },
        services: { base: '203, 213, 225', pulse: '184, 199, 217', accent: '#B8C7D9' },
        housing: { base: '203, 213, 225', pulse: '148, 184, 190', accent: '#94B8BE' },
        healthcare: { base: '203, 213, 225', pulse: '196, 202, 214', accent: '#C4CAD6' },
        finance: { base: '203, 213, 225', pulse: '251, 191, 36', accent: '#FBBF24' }
      };
      const key = String(sector || '').toLowerCase().includes('bank') ? 'finance' : String(sector || 'services').toLowerCase();
      const palette = sectorPalette[key] || sectorPalette.services;
      const isDistressed = String(status || '').toUpperCase().includes('DISTRESS') || String(status || '').toUpperCase().includes('BURN');
      const baseAlpha = activityLevel === 'high' || isDistressed ? 0.30 : 0.20;
      const pulseColor = activityLevel === 'high' || isDistressed ? '251, 191, 36' : palette.pulse;
      ctx.strokeStyle = `rgba(${palette.base}, ${baseAlpha})`;

      ctx.save();
      const baseY = centerY + rect.height * 0.33;
      const deskGlow = ctx.createRadialGradient(centerX, baseY, 8, centerX, baseY, Math.min(rect.width, rect.height) * 0.42);
      deskGlow.addColorStop(0, 'rgba(203, 213, 225, 0.08)');
      deskGlow.addColorStop(0.55, 'rgba(251, 191, 36, 0.035)');
      deskGlow.addColorStop(1, 'rgba(203, 213, 225, 0)');
      ctx.fillStyle = deskGlow;
      ctx.beginPath();
      ctx.ellipse(centerX, baseY, rect.width * 0.28, rect.height * 0.08, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = 'rgba(203, 213, 225, 0.14)';
      ctx.lineWidth = 0.7;
      ctx.beginPath();
      ctx.ellipse(centerX, baseY, rect.width * 0.25, rect.height * 0.055, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();

      connections.forEach(([i, j]) => {
        const p1 = projected[i];
        const p2 = projected[j];

        if (p1.scale > 0.25 && p2.scale > 0.25) {
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);

          if (p1.tag === 'core') {
            ctx.save();
            ctx.strokeStyle = `rgba(${pulseColor}, 0.45)`;
            ctx.lineWidth = 1.15;
            ctx.stroke();
            ctx.restore();
          } else {
            ctx.stroke();
          }
        }
      });

      projected.forEach(p => {
        let size = Math.max(0.5, 2 * p.scale);
        ctx.beginPath();

        let [r, g, b] = palette.base.split(',').map(v => Number(v.trim()));
        let a = 0.26;

        if (p.tag === 'core') {
          const wave = Math.sin(p.origY / 10 - pulse);
          if (wave > 0.7) {
            [r, g, b] = pulseColor.split(',').map(v => Number(v.trim()));
            a = 0.74;
            size *= 1.08;
            ctx.shadowBlur = 5;
            ctx.shadowColor = palette.accent;
          } else {
            [r, g, b] = palette.base.split(',').map(v => Number(v.trim())); a = 0.42;
            ctx.shadowBlur = 0;
          }
        } else if (p.tag === 'window') {
          if (Math.random() > 0.99) {
            [r, g, b] = palette.pulse.split(',').map(v => Number(v.trim())); a = 0.66;
            ctx.shadowBlur = 3;
            ctx.shadowColor = palette.accent;
          } else {
            a = 0.12;
            ctx.shadowBlur = 0;
          }
          size *= 0.8;
        } else if (p.tag === 'spire') {
          r = 184; g = 199; b = 217; a = Math.floor(pulse / 5) % 2 === 0 ? 0.16 : 0.55;
          ctx.shadowBlur = 4;
          ctx.shadowColor = '#B8C7D9';
        } else {
          ctx.shadowBlur = 0;
        }

        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${a})`;
        const dim = size * 2;
        ctx.fillRect(p.x - size, p.y - size, dim, dim);
        ctx.shadowBlur = 0;
      });

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
      resizeObserver.disconnect();
    };
  }, [active, activityLevel, tier, sector, status]);

  return (
    <div ref={containerRef} className="w-full h-full absolute inset-0">
      <canvas ref={canvasRef} className="block w-full h-full" />
    </div>
  );
};

export default NeuralBuilding;
