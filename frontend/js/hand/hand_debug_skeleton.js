import * as THREE from 'three';
import { createDebugMaterials } from './hand_material.js?v=20260711d';

const Y_AXIS = new THREE.Vector3(0, 1, 0);
// hand_view maps input meters by 820, so one origin millimetre is 0.82 scene units.
const ORIGIN_TO_SCENE = 0.82;
const FINGER_CHAINS = Object.freeze([
  Object.freeze([1, 2, 3, 4]),
  Object.freeze([5, 6, 7, 8]),
  Object.freeze([9, 10, 11, 12]),
  Object.freeze([13, 14, 15, 16]),
  Object.freeze([17, 18, 19, 20]),
]);
const BASE_INDICES = Object.freeze(FINGER_CHAINS.map(chain => chain[0]));
const FINGER_EDGES = Object.freeze(FINGER_CHAINS.flatMap(chain => [
  Object.freeze([chain[0], chain[1]]),
  Object.freeze([chain[1], chain[2]]),
  Object.freeze([chain[2], chain[3]]),
]));
const PALM_EDGES = Object.freeze([
  ...BASE_INDICES.map(index => Object.freeze([0, index])),
  ...BASE_INDICES.slice(0, -1).map((index, order) => Object.freeze([index, BASE_INDICES[order + 1]])),
]);

function labelSprite(text, color) {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 64;
  const context = canvas.getContext('2d');
  context.font = '600 25px sans-serif';
  context.fillStyle = 'rgba(247, 252, 255, .92)';
  context.fillRect(0, 0, 256, 64);
  context.strokeStyle = 'rgba(128, 185, 220, .72)';
  context.lineWidth = 2;
  context.strokeRect(1, 1, 254, 62);
  context.fillStyle = color;
  context.fillText(text, 8, 40);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({map: texture, transparent: true, depthTest: false}));
  sprite.scale.set(32, 8, 1);
  return sprite;
}

function jointRadius(index) {
  if (index === 0) return 4.5 * ORIGIN_TO_SCENE;
  const chainOffset = (index - 1) % 4;
  const radius = chainOffset === 0 ? 3.6 : chainOffset === 1 ? 3.0 : 2.4;
  return radius * ORIGIN_TO_SCENE * 1.12;
}

// Origin-style persistent cylinder: thin solid core plus a 2.8x soft glow
// shell. Unit geometry is transformed in place for each FK segment.
function createBoneSegment(cylinderGeometry, coreMaterial, glowMaterial, radius) {
  const group = new THREE.Group();
  const core = new THREE.Mesh(cylinderGeometry, coreMaterial);
  const glow = new THREE.Mesh(cylinderGeometry, glowMaterial);
  core.scale.set(radius, 1, radius);
  glow.scale.set(radius * 2.8, 1, radius * 2.8);
  group.add(core, glow);
  group.userData.core = core;
  group.userData.glow = glow;
  group.userData.radius = radius;
  return group;
}

export class HandDebugSkeleton {
  constructor(side) {
    this.side = side;
    this.group = new THREE.Group();
    this.group.name = `${side}-origin-style-skeleton`;
    this.materials = createDebugMaterials(side);
    Object.values(this.materials).forEach(material => { material.depthWrite = false; });

    this.sphereGeometry = new THREE.SphereGeometry(1, 14, 10);
    this.glowSphereGeometry = new THREE.SphereGeometry(1, 10, 8);
    this.cylinderGeometry = new THREE.CylinderGeometry(1, 1, 1, 10);
    this.points = [];
    this.labels = [];
    this.fingerSegments = [];
    this.palmSegments = [];
    this.direction = new THREE.Vector3();
    this.mcpCenter = new THREE.Vector3();
    this.forearmPoint = new THREE.Vector3();
    this.labelOffset = new THREE.Vector3(6, 6, 0);

    // Origin joint hierarchy, recoloured for the dashboard's light stage.
    for (let index = 0; index < 21; index += 1) {
      const radius = jointRadius(index);
      const point = new THREE.Mesh(this.sphereGeometry, this.materials.joint);
      point.scale.setScalar(radius);
      const glow = new THREE.Mesh(this.glowSphereGeometry, this.materials.jointGlow);
      glow.scale.setScalar(2);
      point.add(glow);
      point.renderOrder = 4;
      this.group.add(point);
      this.points.push(point);

      const label = labelSprite(index === 0 ? 'wrist' : `${side[0].toUpperCase()}${index}`, '#176d9b');
      label.visible = false;
      label.renderOrder = 6;
      this.group.add(label);
      this.labels.push(label);
    }

    // Origin uses radius 1.8 for phalanges, 1.1 for palm struts and 1.4 for
    // the short forearm indicator. All meshes remain persistent per hand.
    FINGER_EDGES.forEach(() => {
      const segment = createBoneSegment(
        this.cylinderGeometry,
        this.materials.bone,
        this.materials.glow,
        2.02 * ORIGIN_TO_SCENE,
      );
      this.group.add(segment);
      this.fingerSegments.push(segment);
    });
    PALM_EDGES.forEach(() => {
      const segment = createBoneSegment(
        this.cylinderGeometry,
        this.materials.palm,
        this.materials.glow,
        1.1 * ORIGIN_TO_SCENE,
      );
      this.group.add(segment);
      this.palmSegments.push(segment);
    });
    this.forearmSegment = createBoneSegment(
      this.cylinderGeometry,
      this.materials.palm,
      this.materials.glow,
      1.4 * ORIGIN_TO_SCENE,
    );
    this.group.add(this.forearmSegment);
  }

  placeSegment(segment, start, end) {
    this.direction.subVectors(end, start);
    const length = Math.max(this.direction.length(), 0.001);
    this.direction.multiplyScalar(1 / length);
    segment.position.copy(start).add(end).multiplyScalar(0.5);
    segment.quaternion.setFromUnitVectors(Y_AXIS, this.direction);
    const radius = segment.userData.radius;
    segment.userData.core.scale.set(radius, length, radius);
    segment.userData.glow.scale.set(radius * 2.8, length, radius * 2.8);
  }

  update(points, _bones, names) {
    if (!Array.isArray(points) || points.length !== 21) return;
    points.forEach((position, index) => {
      this.points[index].position.copy(position);
      this.labels[index].position.copy(position).add(this.labelOffset);
      if (names?.[index] && this.labels[index].userData.name !== names[index]) {
        this.labels[index].material.map.dispose();
        this.labels[index].material.dispose();
        const replacement = labelSprite(names[index], '#176d9b');
        this.labels[index].material = replacement.material;
        this.labels[index].userData.name = names[index];
      }
    });

    FINGER_EDGES.forEach((edge, index) => this.placeSegment(this.fingerSegments[index], points[edge[0]], points[edge[1]]));
    PALM_EDGES.forEach((edge, index) => this.placeSegment(this.palmSegments[index], points[edge[0]], points[edge[1]]));

    this.mcpCenter.set(0, 0, 0);
    BASE_INDICES.slice(1).forEach(index => this.mcpCenter.add(points[index]));
    this.mcpCenter.multiplyScalar(1 / 4);
    this.forearmPoint.copy(points[0]).addScaledVector(
      this.direction.subVectors(points[0], this.mcpCenter).normalize(),
      38 * ORIGIN_TO_SCENE,
    );
    this.placeSegment(this.forearmSegment, this.forearmPoint, points[0]);
  }

  setLabels(visible) {
    this.labels.forEach(label => { label.visible = visible && this.group.visible; });
  }

  setOverlay(overlay) {
    this.materials.bone.opacity = overlay ? 0.58 : 1;
    this.materials.palm.opacity = overlay ? 0.52 : 1;
    this.materials.joint.opacity = overlay ? 0.8 : 1;
    this.materials.glow.opacity = overlay ? 0.09 : 0.18;
    this.materials.jointGlow.opacity = overlay ? 0.11 : 0.2;
    Object.values(this.materials).forEach(material => {
      material.depthTest = !overlay;
      material.needsUpdate = true;
    });
  }

  dispose() {
    this.labels.forEach(label => { label.material.map.dispose(); label.material.dispose(); });
    this.sphereGeometry.dispose();
    this.glowSphereGeometry.dispose();
    this.cylinderGeometry.dispose();
    Object.values(this.materials).forEach(material => material.dispose());
  }
}
