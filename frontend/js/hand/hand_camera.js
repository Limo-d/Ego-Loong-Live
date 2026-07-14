import * as THREE from 'three';

const DIRECTIONS = Object.freeze({
  front: new THREE.Vector3(0, 0, 1),
  side: new THREE.Vector3(1, 0.06, 0),
  top: new THREE.Vector3(0, 1, 0.001),
  reset: new THREE.Vector3(0, 0, 1),
});

export class HandCameraController {
  constructor(camera, controls, getObjects) {
    this.camera = camera;
    this.controls = controls;
    this.getObjects = getObjects;
    this.lastView = 'front';
  }

  fit(view = this.lastView) {
    const objects = this.getObjects().filter(object => object.visible);
    if (!objects.length) return;
    objects.forEach(object => object.updateMatrixWorld(true));
    const bounds = new THREE.Box3();
    objects.forEach(object => bounds.expandByObject(object));
    if (bounds.isEmpty()) return;
    // Keep a stable human-hand motion envelope. A camera fitted to a fist must
    // not crop fingers when that same hand opens a moment later.
    const rawCenter = bounds.getCenter(new THREE.Vector3());
    const halfWidth = objects.length > 1 ? 124 : 72;
    bounds.min.x = Math.min(bounds.min.x, rawCenter.x - halfWidth);
    bounds.max.x = Math.max(bounds.max.x, rawCenter.x + halfWidth);
    bounds.min.y = Math.min(bounds.min.y, -34);
    bounds.max.y = Math.max(bounds.max.y, 184);
    bounds.min.z = Math.min(bounds.min.z, -42);
    bounds.max.z = Math.max(bounds.max.z, 42);
    const center = bounds.getCenter(new THREE.Vector3());
    const size = bounds.getSize(new THREE.Vector3());
    const halfFov = THREE.MathUtils.degToRad(this.camera.fov * 0.5);
    const verticalDistance = size.y * 0.5 / Math.tan(halfFov);
    const horizontalDistance = size.x * 0.5 / Math.tan(halfFov) / Math.max(this.camera.aspect, 0.2);
    const distance = Math.max(verticalDistance, horizontalDistance, size.z * 2.4, 100) * 1.10;
    const direction = (DIRECTIONS[view] || DIRECTIONS.reset).clone().normalize();
    this.camera.up.set(0, view === 'top' ? 0 : 1, view === 'top' ? -1 : 0);
    this.camera.position.copy(center).addScaledVector(direction, distance);
    this.camera.near = Math.max(0.1, distance / 100);
    this.camera.far = Math.max(1200, distance * 8);
    this.camera.updateProjectionMatrix();
    this.controls.target.copy(center);
    this.controls.update();
    this.lastView = view;
  }
}
