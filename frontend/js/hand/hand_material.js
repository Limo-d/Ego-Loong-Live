import * as THREE from 'three';

// Soft candy palette: the cool/warm split makes the two hands immediately
// recognisable while keeping the reconstruction calm and easy to read.
export const HAND_COLORS = Object.freeze({left: '#b9dcff', right: '#ffd1dc'});

const DEBUG_PALETTE = Object.freeze({
  left: Object.freeze({bone: 0x76bdf0, palm: 0x559ed6, glow: 0xb9e3ff}),
  right: Object.freeze({bone: 0xf2a7ba, palm: 0xdd879f, glow: 0xffd6e1}),
});

export function createHandMaterials(side) {
  const result = {};
  for (const region of ['palm', 'thumb', 'index', 'middle', 'ring', 'little']) {
    // A strong same-colour emissive base leaves only restrained Lambert
    // shading for volume. Intersections stay quiet while orbiting still reads
    // as a three-dimensional hand rather than a flat silhouette.
    const material = new THREE.MeshLambertMaterial({
      color: HAND_COLORS[side],
      emissive: HAND_COLORS[side],
      emissiveIntensity: 0.46,
      transparent: false,
      side: THREE.FrontSide,
      toneMapped: true,
    });
    material.userData.baseColor = new THREE.Color(HAND_COLORS[side]);
    result[region] = material;
  }
  return result;
}

export function createDebugMaterials(side = 'left') {
  const palette = DEBUG_PALETTE[side] || DEBUG_PALETTE.left;
  // Debug geometry remains exact, but soft side-specific candy colours and
  // round apricot joints make the diagnostic skeleton feel less mechanical.
  return {
    bone: new THREE.MeshBasicMaterial({color: palette.bone, transparent: true, opacity: 1, toneMapped: false}),
    palm: new THREE.MeshBasicMaterial({color: palette.palm, transparent: true, opacity: 1, toneMapped: false}),
    joint: new THREE.MeshBasicMaterial({color: 0xffad72, transparent: true, opacity: 1, toneMapped: false}),
    glow: new THREE.MeshBasicMaterial({
      color: palette.glow,
      transparent: true,
      opacity: 0.14,
      blending: THREE.NormalBlending,
      depthWrite: false,
      toneMapped: false,
    }),
    jointGlow: new THREE.MeshBasicMaterial({
      color: 0xffd2ae,
      transparent: true,
      opacity: 0.18,
      blending: THREE.NormalBlending,
      depthWrite: false,
      toneMapped: false,
    }),
  };
}
