import * as THREE from 'three';

const PALM_SECTIONS = Object.freeze([
  // Separate radial (thumb) and ulnar (little-finger) widths create the
  // thenar -> first web -> index-root S curve that a symmetric oval cannot.
  {y: -1.00, thumbWidth: 0.64, ulnarWidth: 0.64, depth: 0.64},
  {y: -0.84, thumbWidth: 0.76, ulnarWidth: 0.77, depth: 0.78},
  {y: -0.58, thumbWidth: 0.90, ulnarWidth: 0.88, depth: 0.87},
  {y: -0.30, thumbWidth: 1.05, ulnarWidth: 0.97, depth: 0.98},
  {y:  0.00, thumbWidth: 1.08, ulnarWidth: 1.00, depth: 1.00},
  {y:  0.28, thumbWidth: 1.02, ulnarWidth: 1.02, depth: 0.96},
  {y:  0.52, thumbWidth: 0.88, ulnarWidth: 1.01, depth: 0.87},
  {y:  0.70, thumbWidth: 0.79, ulnarWidth: 0.98, depth: 0.77},
  {y:  0.86, thumbWidth: 0.90, ulnarWidth: 0.97, depth: 0.72},
  {y:  1.00, thumbWidth: 0.96, ulnarWidth: 0.94, depth: 0.60},
]);

const FINGER_ROOTS = Object.freeze([0.60, 0.18, -0.20, -0.60]);
const FINGER_WEBS = Object.freeze([0.39, -0.01, -0.40]);

function signedPower(value, exponent) {
  return Math.sign(value) * Math.pow(Math.abs(value), exponent);
}

function gaussian(value, center, spread) {
  return Math.exp(-0.5 * Math.pow((value - center) / spread, 2));
}

function strongestGaussian(value, centers, spread) {
  let strength = 0;
  for (const center of centers) strength = Math.max(strength, gaussian(value, center, spread));
  return strength;
}

function samplePalmProfile(y, key) {
  for (let index = 0; index < PALM_SECTIONS.length - 1; index += 1) {
    const left = PALM_SECTIONS[index];
    const right = PALM_SECTIONS[index + 1];
    if (y <= right.y) {
      const linear = THREE.MathUtils.clamp((y - left.y) / (right.y - left.y), 0, 1);
      const smooth = linear * linear * (3 - 2 * linear);
      return THREE.MathUtils.lerp(left[key], right[key], smooth);
    }
  }
  return PALM_SECTIONS.at(-1)[key];
}

export function createPalmGeometry(side = 'left', radialSegments = 32, longitudinalSegments = 28) {
  const positions = [];
  const indices = [];
  const rings = longitudinalSegments + 1;
  // TMP_NORMAL in the corrected scene basis points dorsally for left and
  // palmward for right, so the authored palmar face uses opposite local signs.
  const palmarLocalSign = side === 'left' ? -1 : 1;
  const halfRadial = Math.floor(radialSegments / 2);
  for (let longitudinal = 0; longitudinal < rings; longitudinal += 1) {
    const y = -1 + longitudinal / longitudinalSegments * 2;
    const thumbWidth = samplePalmProfile(y, 'thumbWidth');
    const ulnarWidth = samplePalmProfile(y, 'ulnarWidth');
    const sectionDepth = samplePalmProfile(y, 'depth');
    for (let radial = 0; radial < radialSegments; radial += 1) {
      // Walk across the palmar face from u=-1..1, then return across the dorsal
      // face. Unlike an angular ellipse ring, this supplies real surface points
      // across the palm and lets the top edge form subtle finger-root valleys.
      const palmar = radial <= halfRadial;
      const u = palmar
        ? -1 + radial / halfRadial * 2
        : 1 - (radial - halfRadial) / halfRadial * 2;
      const localHalfWidth = u >= 0 ? thumbWidth : ulnarWidth;
      const x = u * localHalfWidth;
      const topBlend = THREE.MathUtils.smoothstep(y, 0.68, 1);
      const rootCrown = strongestGaussian(u, FINGER_ROOTS, 0.105);
      const webValley = strongestGaussian(u, FINGER_WEBS, 0.085);
      const bottomBlend = 1 - THREE.MathUtils.smoothstep(y, -1, -0.72);
      const localY = y + topBlend * (0.018 * u + 0.082 * rootCrown - 0.016 * webValley) -
        bottomBlend * 0.032 * (1 - u * u);
      const edgeRound = Math.pow(Math.max(0, 1 - u * u), 0.56);
      let depthScale = palmar ? 1.04 : 0.86;
      const rootPad = gaussian(y, 0.82, 0.17) * rootCrown;
      if (palmar) {
        const thenarPad = gaussian(y, -0.10, 0.44) * gaussian(u, 0.58, 0.30);
        const hypothenarPad = gaussian(y, -0.14, 0.52) * gaussian(u, -0.62, 0.32);
        const palmHollow = gaussian(y, 0.10, 0.42) * gaussian(u, -0.02, 0.36);
        depthScale += 0.10 * thenarPad + 0.06 * hypothenarPad - 0.045 * palmHollow + 0.055 * rootPad;
      } else {
        depthScale += 0.035 * rootPad;
      }
      const faceSign = palmar ? palmarLocalSign : -palmarLocalSign;
      positions.push(
        x,
        localY,
        faceSign * sectionDepth * edgeRound * depthScale,
      );
    }
  }
  for (let section = 0; section < rings - 1; section += 1) {
    for (let radial = 0; radial < radialSegments; radial += 1) {
      const next = (radial + 1) % radialSegments;
      const a = section * radialSegments + radial;
      const b = section * radialSegments + next;
      const c = (section + 1) * radialSegments + next;
      const d = (section + 1) * radialSegments + radial;
      indices.push(a, b, d, b, c, d);
    }
  }
  const bottomCenter = positions.length / 3;
  positions.push(0, PALM_SECTIONS[0].y - 0.035, 0);
  for (let radial = 0; radial < radialSegments; radial += 1) {
    const next = (radial + 1) % radialSegments;
    indices.push(bottomCenter, next, radial);
  }
  // The MCP end deliberately remains open. Finger tubes and persistent root
  // blends extend into this opening; a triangle-fan cap here creates the
  // visible horizontal shelf that breaks palm-to-finger continuity.
  if (side === 'left') {
    // With the corrected handedness-preserving scene basis, the authored
    // palmar sign reflects the left geometry. Reverse that reflected side so
    // palm normals, finger normals and FrontSide culling all point outward.
    for (let triangle = 0; triangle < indices.length; triangle += 3) {
      const swap = indices[triangle + 1];
      indices[triangle + 1] = indices[triangle + 2];
      indices[triangle + 2] = swap;
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  geometry.computeBoundingBox();
  geometry.computeBoundingSphere();
  return geometry;
}

const PARAMETERS = Object.freeze([
  -0.30, -0.15, 0.00, 0.20, 0.40, 0.60, 0.80, 1.00, 1.20, 1.40,
  1.60, 1.80, 2.00, 2.20, 2.40, 2.60, 2.80, 3.00, 3.04, 3.08, 3.12,
]);

const FINGER_SHAPES = Object.freeze({
  thumb: Object.freeze({depthScale: 0.84, rootFlare: 0.24, rootDepthFlare: 0.20, jointBulge: 0.036, tipPlump: 0.07}),
  index: Object.freeze({depthScale: 0.82, rootFlare: 0.30, rootDepthFlare: 0.30, jointBulge: 0.042, tipPlump: 0.09}),
  middle: Object.freeze({depthScale: 0.81, rootFlare: 0.30, rootDepthFlare: 0.32, jointBulge: 0.042, tipPlump: 0.09}),
  ring: Object.freeze({depthScale: 0.81, rootFlare: 0.29, rootDepthFlare: 0.30, jointBulge: 0.040, tipPlump: 0.085}),
  little: Object.freeze({depthScale: 0.80, rootFlare: 0.28, rootDepthFlare: 0.28, jointBulge: 0.038, tipPlump: 0.08}),
});

function catmull(value0, value1, value2, value3, t) {
  const t2 = t * t;
  const t3 = t2 * t;
  return 0.5 * ((2 * value1) + (-value0 + value2) * t +
    (2 * value0 - 5 * value1 + 4 * value2 - value3) * t2 +
    (-value0 + 3 * value1 - 3 * value2 + value3) * t3);
}

function smoothRadius(radii, parameter) {
  if (parameter <= 0) return radii[0] * (1.04 - parameter * 0.15);
  if (parameter >= 3) {
    const fraction = THREE.MathUtils.clamp((parameter - 3) / 0.12, 0, 1);
    return radii[3] * Math.sqrt(Math.max(0.0025, 1 - fraction * fraction));
  }
  const segment = Math.min(2, Math.floor(parameter));
  const local = THREE.MathUtils.smoothstep(parameter - segment, 0, 1);
  return THREE.MathUtils.lerp(radii[segment], radii[segment + 1], local);
}

function sampleChain(points, parameter, radius, rootExtension, target, scratch) {
  if (parameter < 0) {
    scratch.subVectors(points[1], points[0]).normalize();
    return target.copy(points[0]).addScaledVector(scratch, parameter / 0.30 * radius * rootExtension);
  }
  if (parameter > 3) {
    scratch.subVectors(points[3], points[2]).normalize();
    return target.copy(points[3]).addScaledVector(scratch, (parameter - 3) / 0.12 * radius * 0.92);
  }
  const segment = Math.min(2, Math.floor(parameter === 3 ? 2.999999 : parameter));
  const t = parameter - segment;
  const p0 = points[Math.max(0, segment - 1)];
  const p1 = points[segment];
  const p2 = points[segment + 1];
  const p3 = points[Math.min(3, segment + 2)];
  return target.set(
    catmull(p0.x, p1.x, p2.x, p3.x, t),
    catmull(p0.y, p1.y, p2.y, p3.y, t),
    catmull(p0.z, p1.z, p2.z, p3.z, t),
  );
}

export class SmoothFingerSurface {
  constructor(material, radii, {finger = 'index', radialSegments = 16, rootExtension = 0.72} = {}) {
    this.radii = radii;
    this.shape = FINGER_SHAPES[finger] || FINGER_SHAPES.index;
    this.radialSegments = radialSegments;
    this.rootExtension = rootExtension;
    this.centers = PARAMETERS.map(() => new THREE.Vector3());
    this.tangents = PARAMETERS.map(() => new THREE.Vector3());
    this.normals = PARAMETERS.map(() => new THREE.Vector3());
    this.binormals = PARAMETERS.map(() => new THREE.Vector3());
    this.sampleWidths = PARAMETERS.map(() => 0);
    this.sampleDepths = PARAMETERS.map(() => 0);
    this.scratch = new THREE.Vector3();

    const ringVertexCount = PARAMETERS.length * radialSegments;
    // Finger roots remain open and extend well inside the palm. A buried cap
    // can become visible as a circular insert when fingers bend; only the
    // rounded fingertip needs an explicit cap.
    const positions = new Float32Array((ringVertexCount + 1) * 3);
    const indices = [];
    for (let ring = 0; ring < PARAMETERS.length - 1; ring += 1) {
      for (let radial = 0; radial < radialSegments; radial += 1) {
        const next = (radial + 1) % radialSegments;
        const a = ring * radialSegments + radial;
        const b = ring * radialSegments + next;
        const c = (ring + 1) * radialSegments + next;
        const d = (ring + 1) * radialSegments + radial;
        indices.push(a, b, d, b, c, d);
      }
    }
    const endCenter = ringVertexCount;
    const lastOffset = (PARAMETERS.length - 1) * radialSegments;
    for (let radial = 0; radial < radialSegments; radial += 1) {
      const next = (radial + 1) % radialSegments;
      indices.push(endCenter, lastOffset + radial, lastOffset + next);
    }
    this.geometry = new THREE.BufferGeometry();
    this.geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    this.geometry.setIndex(indices);
    this.mesh = new THREE.Mesh(this.geometry, material);
    // Separate spline tubes must not cast long slot-shaped shadows onto the
    // palm at their overlap. Their own lighting still describes volume, while
    // the unified palm keeps the hand/floor shadow readable.
    this.mesh.castShadow = false;
    this.mesh.receiveShadow = true;
  }

  update(points, referenceSide) {
    for (let index = 0; index < PARAMETERS.length; index += 1) {
      const parameter = PARAMETERS[index];
      const radius = smoothRadius(this.radii, parameter);
      const rootBlend = gaussian(parameter, 0, 0.34);
      const jointBlend = gaussian(parameter, 1, 0.17) + gaussian(parameter, 2, 0.15);
      const tipBlend = gaussian(parameter, 2.62, 0.34);
      this.sampleWidths[index] = radius *
        (1 + this.shape.rootFlare * rootBlend + this.shape.jointBulge * jointBlend + this.shape.tipPlump * tipBlend);
      this.sampleDepths[index] = radius * this.shape.depthScale *
        (1 + this.shape.rootDepthFlare * rootBlend +
          this.shape.jointBulge * 0.55 * jointBlend + this.shape.tipPlump * 0.72 * tipBlend);
      sampleChain(points, parameter, this.radii[0], this.rootExtension, this.centers[index], this.scratch);
    }
    for (let index = 0; index < PARAMETERS.length; index += 1) {
      if (index === 0) this.tangents[index].subVectors(this.centers[1], this.centers[0]);
      else if (index === PARAMETERS.length - 1) this.tangents[index].subVectors(this.centers[index], this.centers[index - 1]);
      else this.tangents[index].subVectors(this.centers[index + 1], this.centers[index - 1]);
      this.tangents[index].normalize();
      if (index === 0) this.normals[index].copy(referenceSide);
      else this.normals[index].copy(this.normals[index - 1]);
      this.normals[index].addScaledVector(this.tangents[index], -this.normals[index].dot(this.tangents[index]));
      if (this.normals[index].lengthSq() < 1e-6) this.normals[index].set(1, 0, 0).addScaledVector(this.tangents[index], -this.tangents[index].x);
      this.normals[index].normalize();
      this.binormals[index].crossVectors(this.tangents[index], this.normals[index]).normalize();
    }

    const position = this.geometry.attributes.position;
    let vertex = 0;
    for (let ring = 0; ring < PARAMETERS.length; ring += 1) {
      const center = this.centers[ring];
      const normal = this.normals[ring];
      const binormal = this.binormals[ring];
      const widthRadius = this.sampleWidths[ring];
      const depthRadius = this.sampleDepths[ring];
      for (let radial = 0; radial < this.radialSegments; radial += 1) {
        const angle = radial / this.radialSegments * Math.PI * 2;
        const width = signedPower(Math.cos(angle), 0.98) * widthRadius;
        const depth = signedPower(Math.sin(angle), 0.97) * depthRadius;
        position.setXYZ(vertex,
          center.x + normal.x * width + binormal.x * depth,
          center.y + normal.y * width + binormal.y * depth,
          center.z + normal.z * width + binormal.z * depth,
        );
        vertex += 1;
      }
    }
    const lastCenter = this.centers.at(-1);
    position.setXYZ(vertex, lastCenter.x, lastCenter.y, lastCenter.z);
    position.needsUpdate = true;
    this.geometry.computeVertexNormals();
    this.geometry.computeBoundingBox();
    this.geometry.computeBoundingSphere();
  }

  dispose() {
    this.geometry.dispose();
  }
}

// A constant-thickness rounded band spans the four MCP roots. Its lower half
// sits inside the open palm loft and its upper half sits inside the flared
// finger roots, covering the otherwise visible open edge without a centre
// bulge or per-finger transition balls.
export class PalmMcpBridgeSurface {
  constructor(material) {
    this.geometry = new THREE.CylinderGeometry(1, 1, 2, 28, 1, false);
    this.geometry.rotateZ(Math.PI / 2);
    this.mesh = new THREE.Mesh(this.geometry, material);
    this.mesh.name = 'palm-mcp-bridge-surface';
    this.mesh.castShadow = false;
    this.mesh.receiveShadow = true;
    this.center = new THREE.Vector3();
    this.basis = new THREE.Matrix4();
  }

  update(mcpCenter, sideAxis, longAxis, normalAxis, palmWidth, palmDepth) {
    this.center.copy(mcpCenter).addScaledVector(longAxis, -palmDepth * 0.38);
    this.mesh.position.copy(this.center);
    this.basis.makeBasis(sideAxis, longAxis, normalAxis);
    this.mesh.quaternion.setFromRotationMatrix(this.basis);
    this.mesh.scale.set(palmWidth * 0.60, palmDepth * 1.02, palmDepth * 0.72);
  }

  dispose() {
    this.geometry.dispose();
  }
}
