import * as THREE from 'three';
import { TACTILE_REGION_INDICES } from './hand_joint_mapping.js?v=20260711c';

const MID = new THREE.Color('#f2a65a');
const HIGH = new THREE.Color('#dc5252');

export class HandTactileOverlay {
  constructor(materials, {enabled = false} = {}) {
    this.materials = materials;
    this.enabled = enabled;
    this.target = Object.fromEntries(Object.keys(materials).map(name => [name, 0]));
    this.current = {...this.target};
  }

  setData(data) {
    if (!this.enabled) return;
    const values = data?.display || [];
    for (const [region, indices] of Object.entries(TACTILE_REGION_INDICES)) {
      const peak = indices.reduce((maximum, index) => Math.max(maximum, Number(values[index]) || 0), 0);
      // Suppress baseline shimmer while preserving a continuous response.
      this.target[region] = THREE.MathUtils.clamp((peak - 4) / 96, 0, 1);
    }
  }

  update(deltaSeconds) {
    if (!this.enabled) return;
    const alpha = 1 - Math.exp(-Math.max(0, deltaSeconds) * 10);
    for (const [region, material] of Object.entries(this.materials)) {
      const level = THREE.MathUtils.lerp(this.current[region], this.target[region], alpha);
      this.current[region] = level;
      const base = material.userData.baseColor;
      if (level < 0.55) material.color.copy(base).lerp(MID, level / 0.55);
      else material.color.copy(MID).lerp(HIGH, (level - 0.55) / 0.45);
      material.emissive?.copy(material.color).multiplyScalar(level * 0.045);
    }
  }

  setEnabled(enabled) {
    this.enabled = Boolean(enabled);
    if (!this.enabled) {
      for (const material of Object.values(this.materials)) {
        material.color.copy(material.userData.baseColor);
        material.emissive?.set(0x000000);
      }
    }
  }
}
