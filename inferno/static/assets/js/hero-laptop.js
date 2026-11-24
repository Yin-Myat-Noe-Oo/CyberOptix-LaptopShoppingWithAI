/* CyberOptix hero: procedural 3D laptop (three.js). Drag to rotate; idles with a slow spin. */
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const host = document.getElementById("hx-laptop");
if (host) init(host);

function init(host) {
  const canvas = document.createElement("canvas");
  canvas.setAttribute("aria-label", host.dataset.label || "3D laptop");
  host.appendChild(canvas);

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
  } catch (e) {
    host.classList.add("hx-laptop-fallback");
    return;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;

  const scene = new THREE.Scene();
  // Soft studio reflections so the aluminium reads as metal from every angle.
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.55;
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
  camera.position.set(0, 2.1, 9.2);
  camera.lookAt(0, 0.55, 0);

  // ----------------------------------------------------------------- lights
  scene.add(new THREE.HemisphereLight(0xc9d3ff, 0x1a2133, 1.3));
  const key = new THREE.DirectionalLight(0xffffff, 1.6);
  key.position.set(4, 6, 6);
  scene.add(key);
  const rimViolet = new THREE.PointLight(0x8b5cf6, 26, 14);
  rimViolet.position.set(3.2, 1.4, -2.6);
  scene.add(rimViolet);
  const rimCyan = new THREE.PointLight(0x22d3ee, 18, 14);
  rimCyan.position.set(-3.4, 0.6, -2.2);
  scene.add(rimCyan);

  // -------------------------------------------------------------- materials
  const aluminium = new THREE.MeshStandardMaterial({ color: 0x4a5266, metalness: 0.8, roughness: 0.3 });
  const aluminiumDark = new THREE.MeshStandardMaterial({ color: 0x1a1f2b, metalness: 0.8, roughness: 0.4 });
  const keyMat = new THREE.MeshStandardMaterial({ color: 0x0c0f16, metalness: 0.2, roughness: 0.7 });
  const padMat = new THREE.MeshStandardMaterial({ color: 0x232a39, metalness: 0.7, roughness: 0.25 });
  const bezelMat = new THREE.MeshStandardMaterial({ color: 0x05070c, metalness: 0.3, roughness: 0.4 });

  // Screen: a canvas texture (dark gradient + glow + wordmark).
  const sc = document.createElement("canvas");
  sc.width = 1024; sc.height = 640;
  const ctx = sc.getContext("2d");
  const g = ctx.createLinearGradient(0, 0, 1024, 640);
  g.addColorStop(0, "#0b1022");
  g.addColorStop(0.55, "#111a3a");
  g.addColorStop(1, "#1c1236");
  ctx.fillStyle = g; ctx.fillRect(0, 0, 1024, 640);
  const glow = ctx.createRadialGradient(700, 180, 10, 700, 180, 520);
  glow.addColorStop(0, "rgba(139,92,246,.45)"); glow.addColorStop(1, "rgba(139,92,246,0)");
  ctx.fillStyle = glow; ctx.fillRect(0, 0, 1024, 640);
  const glow2 = ctx.createRadialGradient(220, 520, 10, 220, 520, 420);
  glow2.addColorStop(0, "rgba(34,211,238,.28)"); glow2.addColorStop(1, "rgba(34,211,238,0)");
  ctx.fillStyle = glow2; ctx.fillRect(0, 0, 1024, 640);
  ctx.font = "700 64px 'Space Grotesk', Inter, sans-serif";
  ctx.textAlign = "center";
  const tg = ctx.createLinearGradient(330, 0, 700, 0);
  tg.addColorStop(0, "#22d3ee"); tg.addColorStop(0.55, "#8b5cf6"); tg.addColorStop(1, "#ec4899");
  ctx.fillStyle = tg;
  ctx.fillText("CyberOptix", 512, 338);
  ctx.font = "500 24px Inter, sans-serif";
  ctx.fillStyle = "rgba(231,236,247,.55)";
  ctx.fillText("AI  ·  LAPTOPS  ·  MYANMAR", 512, 384);
  const screenTex = new THREE.CanvasTexture(sc);
  screenTex.colorSpace = THREE.SRGBColorSpace;
  screenTex.anisotropy = renderer.capabilities.getMaxAnisotropy();
  const screenMat = new THREE.MeshStandardMaterial({
    map: screenTex, emissive: 0xffffff, emissiveMap: screenTex, emissiveIntensity: 0.85,
    roughness: 0.15, metalness: 0,
  });

  // ------------------------------------------------------------------ model
  const W = 4.2, D = 2.9, T = 0.16;            // base width / depth / thickness
  const laptop = new THREE.Group();
  scene.add(laptop);

  const base = new THREE.Mesh(new RoundedBoxGeometry(W, T, D, 4, 0.08), aluminium);
  base.position.y = T / 2;
  laptop.add(base);

  // keyboard well + keys (instanced)
  const well = new THREE.Mesh(new RoundedBoxGeometry(W * 0.86, 0.02, D * 0.42, 2, 0.01), aluminiumDark);
  well.position.set(0, T + 0.002, -D * 0.18);
  laptop.add(well);
  const cols = 14, rows = 6;
  const keyW = (W * 0.84) / cols, keyD = (D * 0.4) / rows;
  const keyGeo = new RoundedBoxGeometry(keyW * 0.84, 0.03, keyD * 0.8, 2, 0.008);
  const keys = new THREE.InstancedMesh(keyGeo, keyMat, cols * rows);
  const m = new THREE.Matrix4();
  let i = 0;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      m.makeTranslation(-W * 0.42 + keyW * (c + 0.5), T + 0.02, -D * 0.38 + keyD * (r + 0.5));
      keys.setMatrixAt(i++, m);
    }
  }
  laptop.add(keys);

  const pad = new THREE.Mesh(new RoundedBoxGeometry(W * 0.36, 0.012, D * 0.3, 2, 0.02), padMat);
  pad.position.set(0, T + 0.002, D * 0.24);
  laptop.add(pad);

  // lid (pivot at the hinge)
  const hinge = new THREE.Group();
  hinge.position.set(0, T, -D / 2 + 0.04);
  laptop.add(hinge);
  const lidH = D * 0.98, lidT = 0.1;
  const lid = new THREE.Mesh(new RoundedBoxGeometry(W, lidH, lidT, 4, 0.06), aluminium);
  lid.position.set(0, lidH / 2, -lidT / 2);
  hinge.add(lid);
  const bezel = new THREE.Mesh(new THREE.PlaneGeometry(W * 0.96, lidH * 0.95), bezelMat);
  bezel.position.set(0, lidH / 2, 0.002);
  hinge.add(bezel);
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(W * 0.9, lidH * 0.86), screenMat);
  screen.position.set(0, lidH / 2 + 0.02, 0.004);
  hinge.add(screen);
  const barrel = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.07, W * 0.7, 24), aluminiumDark);
  barrel.rotation.z = Math.PI / 2;
  barrel.position.set(0, T - 0.01, -D / 2 + 0.06);
  laptop.add(barrel);

  laptop.position.y = -0.35;

  // Tune lighting per colour theme (light page needs less exposure / more contrast).
  function applyTheme() {
    const light = document.documentElement.getAttribute("data-theme") === "light";
    host.dataset.theme = light ? "light" : "dark";
    renderer.toneMappingExposure = light ? 0.78 : 1.05;
    scene.environmentIntensity = light ? 0.3 : 0.55;
    aluminium.color.setHex(light ? 0x3a4152 : 0x4a5266);
    rimViolet.intensity = light ? 10 : 26;
    rimCyan.intensity = light ? 8 : 18;
  }
  applyTheme();
  window.addEventListener("cx-theme", applyTheme);
  laptop.rotation.set(0.12, -0.55, 0);

  // ------------------------------------------------------------ interaction
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const CLOSED = Math.PI / 2;                 // lid lying flat over the keyboard
  const OPEN = -0.3;                          // tilted ~17° back from vertical (~107° open)
  let lidAngle = OPEN;                        // target angle (double-click toggles open/closed)
  hinge.rotation.x = reduceMotion ? OPEN : CLOSED; // starts closed and opens on load

  let targetYaw = -0.55, yaw = -0.55, targetPitch = 0.12, pitch = 0.12;
  let dragging = false, lastX = 0, lastY = 0, velocity = 0, idle = 0;

  canvas.addEventListener("pointerdown", (e) => {
    dragging = true; lastX = e.clientX; lastY = e.clientY; velocity = 0;
    canvas.setPointerCapture(e.pointerId);
    host.classList.add("is-dragging");
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    const dx = e.clientX - lastX, dy = e.clientY - lastY;
    lastX = e.clientX; lastY = e.clientY;
    targetYaw += dx * 0.01;
    velocity = dx * 0.01;
    targetPitch = Math.max(-0.25, Math.min(0.6, targetPitch + dy * 0.006));
  });
  const end = () => { dragging = false; idle = 0; host.classList.remove("is-dragging"); };
  canvas.addEventListener("pointerup", end);
  canvas.addEventListener("pointercancel", end);
  canvas.addEventListener("dblclick", () => { tOpen = 1; lidAngle = lidAngle === OPEN ? CLOSED : OPEN; });

  // ----------------------------------------------------------------- resize
  function resize() {
    const w = host.clientWidth, h = host.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(host);
  resize();

  // ------------------------------------------------------------------- loop
  let visible = true;
  new IntersectionObserver(([en]) => { visible = en.isIntersecting; }).observe(host);
  const clock = new THREE.Clock();
  let tOpen = 0;

  function frame() {
    requestAnimationFrame(frame);
    if (!visible) return;
    const dt = Math.min(clock.getDelta(), 0.05);
    const t = clock.elapsedTime;

    // lid opening animation
    if (!reduceMotion && tOpen < 1) {
      tOpen = Math.min(1, tOpen + dt / 1.6);
      const ease = 1 - Math.pow(1 - tOpen, 3);
      hinge.rotation.x = CLOSED + (OPEN - CLOSED) * ease;
    } else {
      hinge.rotation.x += (lidAngle - hinge.rotation.x) * 0.08;
    }

    if (!dragging) {
      idle += dt;
      targetYaw += velocity;                 // inertia after a fling
      velocity *= 0.92;
      if (!reduceMotion && idle > 1.2) targetYaw += dt * 0.25;   // gentle auto-spin
    }
    yaw += (targetYaw - yaw) * 0.12;
    pitch += (targetPitch - pitch) * 0.12;
    laptop.rotation.y = yaw;
    laptop.rotation.x = pitch;
    laptop.position.y = -0.35 + (reduceMotion ? 0 : Math.sin(t * 1.2) * 0.05);

    renderer.render(scene, camera);
  }
  frame();
  host.classList.add("is-ready");
}
