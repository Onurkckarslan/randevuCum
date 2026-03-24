/**
 * FLOATING PARTICLES EFFECT — Canvas-based background animation
 * Lightweight, performant, zero dependencies
 * Features: X, circle, square, triangle shapes with rotation
 */

const ParticlesEffect = (() => {
  // ── PRIVATE STATE ──
  let canvas = null;
  let ctx = null;
  let particles = [];
  let animationId = null;
  let isRunning = false;
  let particlePool = [];

  const DEFAULT_CONFIG = {
    particleCount: 10,
    speed: 0.08,
    opacity: 0.10,
    rotation: true,
    shapes: ['star', 'dot', 'dash', 'circle'],
    colors: ['#7c3aed', '#ec4899', '#06b6d4']
  };

  let config = { ...DEFAULT_CONFIG };

  // ── PARTICLE CLASS ──
  class Particle {
    constructor(x, y, vx, vy, shape, size, opacity, color) {
      this.x = x;
      this.y = y;
      this.vx = vx;
      this.vy = vy;
      this.shape = shape;
      this.size = size;
      this.opacity = opacity;
      this.color = color;
      this.rotation = Math.random() * 360;
      this.rotationSpeed = (Math.random() - 0.5) * 2; // -1 to 1
      this.baseOpacity = opacity;
    }

    update(width, height) {
      // Update position
      this.x += this.vx;
      this.y += this.vy;

      // Boundary wrapping
      if (this.x > width + this.size) this.x = -this.size;
      if (this.x < -this.size) this.x = width + this.size;
      if (this.y > height + this.size) this.y = -this.size;
      if (this.y < -this.size) this.y = height + this.size;

      // Update rotation
      if (config.rotation) {
        this.rotation += this.rotationSpeed;
        this.rotation %= 360;
      }

      // Subtle opacity flicker for depth
      this.opacity = this.baseOpacity + (Math.sin(this.rotation * 0.01) * 0.05);
    }

    draw(ctx) {
      const alpha = Math.max(0, Math.min(1, this.opacity));

      switch (this.shape) {
        case 'star':
          this._drawStar(ctx, alpha);
          break;
        case 'dot':
          this._drawDot(ctx, alpha);
          break;
        case 'dash':
          this._drawDash(ctx, alpha);
          break;
        case 'circle':
          this._drawCircle(ctx, alpha);
          break;
      }
    }

    _drawStar(ctx, alpha) {
      // 4-pointed star (elegant)
      ctx.save();
      ctx.translate(this.x, this.y);
      ctx.rotate((this.rotation * Math.PI) / 180);
      ctx.strokeStyle = `rgba(124, 58, 237, ${alpha})`;
      ctx.lineWidth = 1.2;
      ctx.lineCap = 'round';

      const r = this.size / 3;
      // 4 points: up, right, down, left
      ctx.beginPath();
      ctx.moveTo(0, -r);
      ctx.lineTo(0, r);
      ctx.moveTo(-r, 0);
      ctx.lineTo(r, 0);
      ctx.stroke();

      ctx.restore();
    }

    _drawDot(ctx, alpha) {
      // Single elegant dot
      ctx.save();
      ctx.fillStyle = `rgba(236, 72, 153, ${alpha})`;
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.size / 6, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    _drawDash(ctx, alpha) {
      // Elegant short dash line
      ctx.save();
      ctx.translate(this.x, this.y);
      ctx.rotate((this.rotation * Math.PI) / 180);
      ctx.strokeStyle = `rgba(6, 182, 212, ${alpha})`;
      ctx.lineWidth = 1.5;
      ctx.lineCap = 'round';

      ctx.beginPath();
      ctx.moveTo(-this.size / 3, 0);
      ctx.lineTo(this.size / 3, 0);
      ctx.stroke();

      ctx.restore();
    }

    _drawCircle(ctx, alpha) {
      ctx.save();
      ctx.strokeStyle = `rgba(124, 58, 237, ${alpha})`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.size / 3, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }
  }

  // ── PRIVATE FUNCTIONS ──

  const createParticle = () => {
    const side = Math.random();
    let x, y;

    // Random spawn from edges
    if (side < 0.25) {
      x = Math.random() * canvas.width;
      y = -20;
    } else if (side < 0.5) {
      x = Math.random() * canvas.width;
      y = canvas.height + 20;
    } else if (side < 0.75) {
      x = -20;
      y = Math.random() * canvas.height;
    } else {
      x = canvas.width + 20;
      y = Math.random() * canvas.height;
    }

    const vx = (Math.random() - 0.5) * config.speed * 2;
    const vy = (Math.random() - 0.5) * config.speed * 2;
    const shape = config.shapes[Math.floor(Math.random() * config.shapes.length)];
    const size = 15 + Math.random() * 25; // 15-40px
    const opacity = config.opacity * (0.7 + Math.random() * 0.6); // 0.49-1.0x base
    const color = config.colors[Math.floor(Math.random() * config.colors.length)];

    return new Particle(x, y, vx, vy, shape, size, opacity, color);
  };

  const animate = () => {
    if (!isRunning) return;

    // Semi-transparent fade trail (motion blur effect) — faster fade
    ctx.fillStyle = 'rgba(18, 18, 18, 0.08)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Update and draw all particles
    particles.forEach(particle => {
      particle.update(canvas.width, canvas.height);
      particle.draw(ctx);
    });

    animationId = requestAnimationFrame(animate);
  };

  const handleResize = () => {
    if (!canvas) return;
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  };

  const handleVisibilityChange = () => {
    if (document.hidden) {
      if (isRunning) {
        cancelAnimationFrame(animationId);
        isRunning = false;
      }
    } else {
      if (!isRunning) {
        isRunning = true;
        animate();
      }
    }
  };

  // ── PUBLIC API ──
  return {
    /**
     * Initialize particles effect
     * @param {Object} userConfig - Configuration object
     * @param {number} userConfig.particleCount - Number of particles
     * @param {number} userConfig.speed - Movement speed (0.1 is good)
     * @param {number} userConfig.opacity - Base opacity (0.15 is good)
     * @param {boolean} userConfig.rotation - Enable rotation
     */
    init: (userConfig = {}) => {
      // Merge user config with defaults
      config = { ...DEFAULT_CONFIG, ...userConfig };

      // Create container if not exists
      let container = document.getElementById('particles-container');
      if (!container) {
        container = document.createElement('div');
        container.id = 'particles-container';
        document.body.insertBefore(container, document.body.firstChild);
      }

      // Create canvas
      canvas = document.createElement('canvas');
      canvas.id = 'particles-canvas';
      container.appendChild(canvas);
      ctx = canvas.getContext('2d');

      if (!ctx) {
        console.warn('Canvas 2D context not supported, particles disabled');
        return;
      }

      // Set canvas size
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;

      // Adjust particle count for mobile
      const particleCount =
        window.innerWidth < 768
          ? Math.max(5, Math.floor(config.particleCount / 2))
          : config.particleCount;

      // Create particles
      particles = [];
      for (let i = 0; i < particleCount; i++) {
        particles.push(createParticle());
      }

      // Start animation
      isRunning = true;
      animate();

      // Event listeners
      window.addEventListener('resize', handleResize);
      document.addEventListener('visibilitychange', handleVisibilityChange);

      return this; // Chainable
    },

    /**
     * Destroy particles effect and clean up
     */
    destroy: () => {
      if (animationId) {
        cancelAnimationFrame(animationId);
      }
      isRunning = false;

      if (canvas && canvas.parentNode) {
        canvas.parentNode.removeChild(canvas);
      }

      window.removeEventListener('resize', handleResize);
      document.removeEventListener('visibilitychange', handleVisibilityChange);

      particles = [];
      canvas = null;
      ctx = null;

      return this;
    },

    /**
     * Pause animation
     */
    pause: () => {
      if (animationId) {
        cancelAnimationFrame(animationId);
      }
      isRunning = false;
      return this;
    },

    /**
     * Resume animation
     */
    resume: () => {
      if (!isRunning && canvas && ctx) {
        isRunning = true;
        animate();
      }
      return this;
    },

    /**
     * Get current config
     */
    getConfig: () => ({ ...config }),

    /**
     * Update config dynamically
     */
    setConfig: (newConfig) => {
      config = { ...config, ...newConfig };
      return this;
    }
  };
})();

// ── AUTO-INIT ON DOM READY ──
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    ParticlesEffect.init({
      particleCount: 10,
      speed: 0.08,
      opacity: 0.10,
      rotation: true
    });
  });
} else {
  // Already loaded
  ParticlesEffect.init({
    particleCount: 10,
    speed: 0.08,
    opacity: 0.10,
    rotation: true
  });
}
