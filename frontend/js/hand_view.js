import * as THREE from 'three';
import { OrbitControls } from '/static/vendor/OrbitControls.js';
import { ProceduralHandModel } from './hand/hand_model_loader.js?v=20260714a';
import { HandDebugSkeleton } from './hand/hand_debug_skeleton.js?v=20260711d';
import { HandCameraController } from './hand/hand_camera.js?v=20260713b';

// Screen layout follows the requested color/side order: blue left hand on
// screen-left, pink right hand on screen-right. Data channels remain unswapped.
const HAND_OFFSET = Object.freeze({left: -86, right: 86});

function toScenePoints(points) {
  if (!points?.length) return [];
  const root = points[0];
  const scale = 820;
  // Retarget x=fingertip/y=dorsal/z=thumb-side -> scene y/z/x.
  // Keep the dorsal axis unreflected so the hand back faces the front camera.
  // Fingertip and thumb-side axes are unchanged, keeping every screen position.
  return points.map(point => new THREE.Vector3(
    (point[2] - root[2]) * scale,
    (point[0] - root[0]) * scale,
    (point[1] - root[1]) * scale,
  ));
}

export class HandView {
  constructor(card, onAngles) {
    this.card = card;
    this.canvas = card.querySelector('#hand-canvas');
    this.onAngles = onAngles;
    this.payload = {};
    this.displayMode = 'surface';
    this.showLabels = false;
    this.smoothing = true;
    this.received = new Set();
    this.lastFrames = [];
    this.lastTime = performance.now();
    this.lastHiddenRender = 0;
    this.lastRender = 0;

    this.renderer = new THREE.WebGLRenderer({canvas: this.canvas, antialias: true, alpha: true, powerPreference: 'high-performance'});
    this.renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.setClearAlpha(0);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.02;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(36, 1, 0.1, 2000);
    this.camera.position.set(0, 92, 340);
    this.controls = new OrbitControls(this.camera, this.canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.075;
    this.controls.enablePan = true;
    this.controls.minDistance = 90;
    this.controls.maxDistance = 760;

    this.scene.add(new THREE.HemisphereLight(0xffffff, 0xcbd9e8, 1.34));
    this.scene.add(new THREE.AmbientLight(0xfffbfd, 0.38));
    const key = new THREE.DirectionalLight(0xfffdfb, 1.92);
    key.position.set(-110, 275, 350);
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
    key.shadow.camera.left = -230;
    key.shadow.camera.right = 230;
    key.shadow.camera.top = 250;
    key.shadow.camera.bottom = -100;
    key.shadow.bias = -0.0002;
    key.shadow.normalBias = 0.45;
    this.scene.add(key);
    const rim = new THREE.DirectionalLight(0xffd6e1, 0.68);
    rim.position.set(190, 80, -180);
    this.scene.add(rim);
    const fill = new THREE.DirectionalLight(0xc8e5ff, 0.42);
    fill.position.set(-190, 65, 80);
    this.scene.add(fill);

    this.axes = new THREE.AxesHelper(62);
    this.axes.visible = false;
    this.scene.add(this.axes);
    this.grid = new THREE.GridHelper(320, 12, 0xc8dce8, 0xe2edf4);
    this.grid.position.y = -38;
    this.grid.material.transparent = true;
    this.grid.material.opacity = 0.28;
    this.grid.visible = false;
    this.scene.add(this.grid);
    this.floor = new THREE.Mesh(
      new THREE.PlaneGeometry(420, 250),
      new THREE.ShadowMaterial({color: 0x6f8fa3, transparent: true, opacity: 0.075}),
    );
    this.floor.rotation.x = -Math.PI / 2;
    this.floor.position.y = -38.5;
    this.floor.receiveShadow = true;
    this.scene.add(this.floor);

    this.hands = {};
    for (const side of ['left', 'right']) {
      const surface = new ProceduralHandModel(side);
      const debug = new HandDebugSkeleton(side);
      surface.group.position.x = HAND_OFFSET[side];
      debug.group.position.x = HAND_OFFSET[side];
      this.scene.add(surface.group, debug.group);
      this.hands[side] = {surface, debug};
    }
    this.cameraController = new HandCameraController(this.camera, this.controls, () => this.fitObjects());

    this.bind();
    this.updateVisibility();
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(this.canvas.parentElement);
    this.resize();
    this.renderer.setAnimationLoop(timestamp => this.loop(timestamp));
  }

  update(side, data) {
    this.payload[side] = data;
    if (!data.points?.length) return;
    const points = toScenePoints(data.points);
    const hand = this.hands[side];
    const firstFrame = !this.received.has(side);
    // The presentation surface receives raw angle metadata for its bounded
    // three-DOF thumb map. The debug skeleton below still receives exact FK.
    hand.surface.setTarget(points, data);
    // From the hand-back view, positive finger flexion travels into the screen
    // (negative scene depth). Use the same unreflected FK points as the mesh.
    hand.debug.update(points, data.bones, data.joint_names);
    this.received.add(side);
    this.updateVisibility();
    const status = this.card.querySelector(`#hand-${side}-status`);
    status.textContent = `${side === 'left' ? '左' : '右'}手 ${data.present ? 'LIVE' : '待有效解算'}`;
    status.classList.toggle('pending', !data.present);
    this.onAngles?.(side, data.angles || []);
    if (firstFrame) requestAnimationFrame(() => this.cameraController.fit('front'));
  }

  updateTactile(side, data) {
    this.hands[side]?.surface.setTactile(data);
  }

  fitObjects() {
    const visibleSide = this.card.querySelector('#hand-visible')?.value || 'both';
    const useSurface = this.displayMode !== 'skeleton';
    return ['left', 'right']
      .filter(side => visibleSide === 'both' || visibleSide === side)
      .filter(side => this.received.has(side))
      .map(side => useSurface ? this.hands[side].surface.group : this.hands[side].debug.group);
  }

  updateVisibility() {
    const visibleSide = this.card.querySelector('#hand-visible')?.value || 'both';
    // All display modes share the dashboard's pale radial stage. The skeleton
    // uses normal-blended halos, so it remains saturated without a black field.
    this.renderer.setClearColor(0x000000, 0);
    for (const side of ['left', 'right']) {
      const enabled = (visibleSide === 'both' || visibleSide === side) && this.received.has(side);
      const hand = this.hands[side];
      hand.surface.group.visible = enabled && this.displayMode !== 'skeleton';
      hand.debug.group.visible = enabled && this.displayMode !== 'surface';
      hand.debug.setOverlay(this.displayMode === 'both');
      hand.debug.setLabels(this.showLabels && hand.debug.group.visible);
    }
  }

  bind() {
    this.card.querySelectorAll('[data-camera]').forEach(button => button.addEventListener('click', () => this.cameraController.fit(button.dataset.camera)));
    this.card.querySelector('#toggle-axes').addEventListener('click', event => {
      this.axes.visible = !this.axes.visible;
      this.grid.visible = this.axes.visible;
      event.currentTarget.classList.toggle('active', this.axes.visible);
    });
    this.card.querySelector('#toggle-labels').addEventListener('click', event => {
      this.showLabels = !this.showLabels;
      if (this.showLabels && this.displayMode === 'surface') {
        this.displayMode = 'both';
        this.card.querySelector('#hand-display-mode').value = 'both';
      }
      this.updateVisibility();
      event.currentTarget.classList.toggle('active', this.showLabels);
    });
    this.card.querySelector('#toggle-hand-smoothing').addEventListener('click', event => {
      this.smoothing = !this.smoothing;
      Object.values(this.hands).forEach(hand => hand.surface.setSmoothing(this.smoothing));
      event.currentTarget.classList.toggle('active', this.smoothing);
    });
    this.card.querySelector('#hand-display-mode').addEventListener('change', event => {
      this.displayMode = event.target.value;
      this.updateVisibility();
      requestAnimationFrame(() => this.cameraController.fit());
    });
    this.card.querySelector('#hand-visible').addEventListener('change', () => {
      this.updateVisibility();
      requestAnimationFrame(() => this.cameraController.fit());
    });
  }

  resize() {
    const bounds = this.canvas.parentElement.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return;
    this.renderer.setSize(bounds.width, bounds.height, false);
    this.camera.aspect = bounds.width / bounds.height;
    this.camera.updateProjectionMatrix();
  }

  loop(timestamp) {
    if (document.hidden && timestamp - this.lastHiddenRender < 240) return;
    this.lastHiddenRender = timestamp;
    if (!document.hidden && timestamp - this.lastRender < 1000 / 30) return;
    this.lastRender = timestamp;
    const deltaSeconds = Math.min((timestamp - this.lastTime) / 1000, 0.05);
    this.lastTime = timestamp;
    Object.values(this.hands).forEach(hand => hand.surface.update(deltaSeconds));
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
    this.lastFrames.push(timestamp);
    while (this.lastFrames.length && timestamp - this.lastFrames[0] > 1000) this.lastFrames.shift();
    this.card.querySelector('#frontend-fps').textContent = `Render ${this.lastFrames.length} FPS`;
  }

  dispose() {
    this.renderer.setAnimationLoop(null);
    this.resizeObserver.disconnect();
    this.controls.dispose();
    Object.values(this.hands).forEach(hand => { hand.surface.dispose(); hand.debug.dispose(); });
    this.floor.geometry.dispose();
    this.floor.material.dispose();
    this.renderer.dispose();
  }
}

// Dependency-free last resort for browsers/drivers that cannot create WebGL.
// It intentionally remains a diagnostic FK projection and is never selected
// when the reconstructed Three.js surface is available.
export class HandFallbackView {
  constructor(card, onAngles, error) {
    this.card = card;
    this.onAngles = onAngles;
    this.payload = {};
    const failed = card.querySelector('#hand-canvas');
    const canvas = failed.cloneNode(false);
    failed.replaceWith(canvas);
    this.canvas = canvas;
    this.context = canvas.getContext('2d');
    this.error = error instanceof Error ? error.message : String(error || 'WebGL unavailable');
    card.querySelectorAll('[data-camera],#toggle-axes,#toggle-labels,#toggle-hand-smoothing,#hand-display-mode').forEach(element => {
      element.disabled = true;
      element.title = '当前浏览器不可用 WebGL，已使用二维 FK 诊断视图';
    });
    card.querySelector('#hand-visible')?.addEventListener('change', () => this.draw());
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(canvas.parentElement);
    this.resize();
    card.querySelector('#frontend-fps').textContent = 'Canvas FK fallback';
  }

  update(side, data) {
    this.payload[side] = data;
    const status = this.card.querySelector(`#hand-${side}-status`);
    if (status) status.textContent = `${side === 'left' ? '左' : '右'}手 ${data.present ? 'LIVE' : '无有效数据'}`;
    this.onAngles?.(side, data.angles || []);
    this.draw();
  }

  updateTactile() {}

  resize() {
    const bounds = this.canvas.parentElement.getBoundingClientRect();
    const pixelRatio = Math.min(devicePixelRatio || 1, 2);
    if (!bounds.width || !bounds.height) return;
    this.canvas.width = Math.round(bounds.width * pixelRatio);
    this.canvas.height = Math.round(bounds.height * pixelRatio);
    this.canvas.style.width = `${bounds.width}px`;
    this.canvas.style.height = `${bounds.height}px`;
    this.draw();
  }

  draw() {
    if (!this.context) return;
    const context = this.context;
    const width = this.canvas.width;
    const height = this.canvas.height;
    const pixelRatio = Math.min(devicePixelRatio || 1, 2);
    context.clearRect(0, 0, width, height);
    context.fillStyle = '#f1f7fb';
    context.fillRect(0, 0, width, height);
    context.save();
    context.scale(pixelRatio, pixelRatio);
    const canvasWidth = width / pixelRatio;
    const canvasHeight = height / pixelRatio;
    context.fillStyle = '#647d8d';
    context.font = '12px sans-serif';
    context.fillText('WebGL 不可用 · 二维 FK 诊断视图', 14, 22);
    const visible = this.card.querySelector('#hand-visible')?.value || 'both';
    for (const side of ['left', 'right']) {
      if (visible !== 'both' && visible !== side) continue;
      const data = this.payload[side];
      if (!data?.points?.length) continue;
      const root = data.points[0];
      const scale = Math.min(canvasWidth * 0.72, canvasHeight * 1.25);
      const centerX = canvasWidth * (side === 'left' ? 0.72 : 0.28);
      const centerY = canvasHeight * 0.74;
      const projected = data.points.map(point => [centerX + (point[2] - root[2]) * scale, centerY - (point[0] - root[0]) * scale]);
      context.strokeStyle = side === 'left' ? '#5aa6d2' : '#e29a68';
      context.lineWidth = 8;
      context.lineCap = 'round';
      context.lineJoin = 'round';
      context.beginPath();
      for (const [a, b] of data.bones || []) { context.moveTo(...projected[a]); context.lineTo(...projected[b]); }
      context.stroke();
    }
    context.restore();
  }

  dispose() {
    this.resizeObserver.disconnect();
  }
}
