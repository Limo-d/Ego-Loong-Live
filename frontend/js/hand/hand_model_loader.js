import * as THREE from 'three';
import { FINGER_CHAINS, FINGER_RADII, THUMB_VISUAL_MAPPING } from './hand_joint_mapping.js?v=20260711f';
import { createHandMaterials } from './hand_material.js?v=20260711k';
import { HandTactileOverlay } from './hand_tactile_overlay.js?v=20260711j';
import {
  createPalmGeometry,
  PalmMcpBridgeSurface,
  SmoothFingerSurface,
} from './hand_surface_geometry.js?v=20260711o';
import { buildVisualThumbPoints, readThumbRawAngles } from './thumb_visual_mapping.js?v=20260714a';

const TMP_CENTER = new THREE.Vector3();
const TMP_SIDE = new THREE.Vector3();
const TMP_LONG = new THREE.Vector3();
const TMP_NORMAL = new THREE.Vector3();
const TMP_MATRIX = new THREE.Matrix4();

function prepareMesh(mesh) {
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function average(points, indices, target) {
  target.set(0, 0, 0);
  indices.forEach(index => target.add(points[index]));
  return target.multiplyScalar(1 / indices.length);
}

// Procedural transition model (solution C). It consumes the verified Retarget
// FK points, while its fixed-topology surfaces are authored for presentation:
// one broad lofted palm and one continuous tube per finger.
export class ProceduralHandModel {
  constructor(side) {
    this.side = side;
    this.group = new THREE.Group();
    this.group.name = `${side}-reconstructed-hand`;
    this.group.visible = false;
    this.materials = createHandMaterials(side);
    this.tactile = new HandTactileOverlay(this.materials, {enabled: false});
    this.targetPoints = Array.from({length: 21}, () => new THREE.Vector3());
    this.currentPoints = Array.from({length: 21}, () => new THREE.Vector3());
    this.hasTarget = false;
    this.smoothing = true;

    this.palmGeometry = createPalmGeometry(side);
    this.palm = prepareMesh(new THREE.Mesh(this.palmGeometry, this.materials.palm));
    this.palm.name = `${side}-lofted-palm-surface`;
    this.group.add(this.palm);
    this.mcpBridge = new PalmMcpBridgeSurface(this.materials.palm);
    this.mcpBridge.mesh.name = `${side}-palm-mcp-bridge-surface`;
    this.group.add(this.mcpBridge.mesh);

    this.fingers = {};
    for (const [finger, chain] of Object.entries(FINGER_CHAINS)) {
      const surface = new SmoothFingerSurface(this.materials[finger], FINGER_RADII[finger], {
        finger,
        radialSegments: 16,
        rootExtension: finger === 'thumb' ? THUMB_VISUAL_MAPPING.geometry.rootExtension : 1.80,
      });
      surface.mesh.name = `${side}-${finger}-continuous-surface`;
      this.group.add(surface.mesh);
      this.fingers[finger] = {
        chain,
        surface,
        visualPoints: Array.from({length: 4}, () => new THREE.Vector3()),
      };
    }

    this.targetThumbAngles = {mcpFlex: 0, mcpAbduction: 0, ipFlex: 0};
    this.currentThumbAngles = {mcpFlex: 0, mcpAbduction: 0, ipFlex: 0};
    this.thumbFrame = {
      handSide: side,
      center: this.palm.position,
      long: new THREE.Vector3(),
      side: new THREE.Vector3(),
      palmar: new THREE.Vector3(),
      palmLength: 1,
      palmWidth: 1,
      palmDepth: 1,
    };
  }

  setTarget(points, handData = {}) {
    if (!Array.isArray(points) || points.length !== 21) return;
    const firstTarget = !this.hasTarget;
    points.forEach((point, index) => this.targetPoints[index].copy(point));
    this.targetThumbAngles = readThumbRawAngles(handData.angles, this.targetThumbAngles);
    if (firstTarget) {
      this.targetPoints.forEach((point, index) => this.currentPoints[index].copy(point));
      Object.assign(this.currentThumbAngles, this.targetThumbAngles);
    }
    this.hasTarget = true;
    this.group.visible = true;
    this.updateGeometry();
  }

  setSmoothing(enabled) {
    this.smoothing = Boolean(enabled);
  }

  setTactile(data) {
    // Kept as a structured future hook. Presentation mode intentionally uses
    // one quiet color and does not paint per-finger tactile values.
    this.tactile.setData(data);
  }

  update(deltaSeconds) {
    if (!this.hasTarget) return;
    const alpha = this.smoothing ? 1 - Math.exp(-Math.max(0, deltaSeconds) * 21) : 1;
    this.currentPoints.forEach((point, index) => point.lerp(this.targetPoints[index], alpha));
    for (const key of ['mcpFlex', 'mcpAbduction', 'ipFlex']) {
      this.currentThumbAngles[key] = THREE.MathUtils.lerp(
        this.currentThumbAngles[key],
        this.targetThumbAngles[key],
        alpha,
      );
    }
    this.updateGeometry();
    this.tactile.update(deltaSeconds);
  }

  updateGeometry() {
    const points = this.currentPoints;
    const wrist = points[0];
    const mcpCenter = average(points, [5, 9, 13, 17], TMP_CENTER);
    TMP_LONG.subVectors(mcpCenter, wrist).normalize();
    TMP_SIDE.subVectors(points[5], points[17]);
    TMP_SIDE.addScaledVector(TMP_LONG, -TMP_SIDE.dot(TMP_LONG)).normalize();
    TMP_NORMAL.crossVectors(TMP_SIDE, TMP_LONG).normalize();
    TMP_MATRIX.makeBasis(TMP_SIDE, TMP_LONG, TMP_NORMAL);

    const palmLength = Math.max(wrist.distanceTo(mcpCenter), 28);
    const palmWidth = Math.max(points[5].distanceTo(points[17]), 32);
    const palmDepth = Math.max(9.4, palmWidth * 0.23);
    this.palm.position.copy(wrist).lerp(mcpCenter, 0.48);
    this.palm.quaternion.setFromRotationMatrix(TMP_MATRIX);
    // A slightly shorter, fuller palm gives the presentation model a friendly
    // rounded silhouette. FK points and the diagnostic skeleton stay exact.
    this.palm.scale.set(palmWidth * 0.74, palmLength * 0.58, palmDepth * 1.10);
    this.mcpBridge.update(mcpCenter, TMP_SIDE, TMP_LONG, TMP_NORMAL, palmWidth, palmDepth);

    const signs = THUMB_VISUAL_MAPPING.sideSigns[this.side];
    this.thumbFrame.long.copy(TMP_LONG);
    this.thumbFrame.side.copy(TMP_SIDE);
    this.thumbFrame.palmar.copy(TMP_NORMAL).multiplyScalar(signs.palmNormal);
    this.thumbFrame.palmLength = palmLength;
    this.thumbFrame.palmWidth = palmWidth;
    this.thumbFrame.palmDepth = palmDepth;

    for (const [finger, structure] of Object.entries(this.fingers)) {
      if (finger === 'thumb') continue;
      const visualPoints = structure.visualPoints;
      const lengthScale = 0.74;
      visualPoints[0].copy(points[structure.chain[0]]);
      for (let index = 1; index < 4; index += 1) {
        visualPoints[index].copy(points[structure.chain[index]])
          .sub(points[structure.chain[index - 1]])
          .multiplyScalar(lengthScale)
          .add(visualPoints[index - 1]);
      }
      structure.surface.update(visualPoints, TMP_SIDE);
    }

    const thumb = this.fingers.thumb;
    buildVisualThumbPoints(
      points,
      this.currentThumbAngles,
      this.thumbFrame,
      this.fingers.index.visualPoints,
      thumb.visualPoints,
    );
    thumb.surface.update(thumb.visualPoints, TMP_SIDE);

  }

  dispose() {
    this.palmGeometry.dispose();
    this.mcpBridge.dispose();
    Object.values(this.fingers).forEach(finger => finger.surface.dispose());
    new Set(Object.values(this.materials)).forEach(material => material.dispose());
  }
}
