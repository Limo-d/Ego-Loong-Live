import * as THREE from 'three';
import { FINGER_RADII, THUMB_VISUAL_MAPPING } from './hand_joint_mapping.js?v=20260711f';

const DEG_TO_RAD = Math.PI / 180;
const RAD_TO_DEG = 180 / Math.PI;
const TMP_CMC = new THREE.Vector3();
const TMP_PLANAR = new THREE.Vector3();
const TMP_DIRECTION = new THREE.Vector3();
const TMP_TARGET = new THREE.Vector3();
const TMP_AXIS = new THREE.Vector3();
const TMP_SEGMENT = new THREE.Vector3();
const TMP_CLOSEST = new THREE.Vector3();
const TMP_DELTA = new THREE.Vector3();
const TMP_CORRECTION = new THREE.Vector3();
const TMP_BEST_CORRECTION = new THREE.Vector3();

function clampMapping(value, mapping) {
  return THREE.MathUtils.clamp(
    value * mapping.scale + mapping.offsetDeg,
    mapping.minDeg,
    mapping.maxDeg,
  );
}

function angleValue(rows, index, fallback) {
  const row = rows?.find(item => item.index === index);
  if (!row || row.valid === false || !Number.isFinite(Number(row.degrees))) return fallback;
  return Number(row.degrees);
}

// Keep raw state27 values available while holding a small, separately smoothed
// set of inputs for the presentation-only thumb chain.
export function readThumbRawAngles(rows, fallback = {mcpFlex: 0, mcpAbduction: 0, ipFlex: 0}) {
  return {
    mcpFlex: angleValue(rows, 16, fallback.mcpFlex),
    mcpAbduction: angleValue(rows, 17, fallback.mcpAbduction),
    ipFlex: angleValue(rows, 18, fallback.ipFlex),
  };
}

export function mapThumbVisualPose(rawPoints, rawAngles, frame) {
  const config = THUMB_VISUAL_MAPPING;
  const signs = config.sideSigns[frame.handSide];
  TMP_CMC.subVectors(rawPoints[2], rawPoints[1]);
  if (TMP_CMC.lengthSq() < 1e-6) TMP_CMC.copy(frame.long);
  else TMP_CMC.normalize();

  // Directional swing is read from the raw CMC metacarpal vector. Quaternion
  // roll around that vector therefore cannot twist the surface root. The two
  // remaining directional components and MCP abduction are compressed into
  // one opposition output instead of acting as independent joints.
  const sideComponent = TMP_CMC.dot(frame.side);
  const longComponent = TMP_CMC.dot(frame.long);
  const palmComponent = TMP_CMC.dot(frame.palmar);
  const cmcSplayDeg = Math.atan2(sideComponent, longComponent) * RAD_TO_DEG * signs.cmcSplay;
  const cmcPalmDeg = Math.atan2(
    palmComponent,
    Math.max(1e-6, Math.hypot(sideComponent, longComponent)),
  ) * RAD_TO_DEG * signs.cmcPalm;
  const opposition = config.opposition;
  const oppositionDeg = THREE.MathUtils.clamp(
    opposition.offsetDeg +
      opposition.cmcSplayWeight * cmcSplayDeg +
      opposition.cmcPalmWeight * cmcPalmDeg +
      opposition.mcpAbductionWeight * rawAngles.mcpAbduction * signs.mcpAbduction,
    opposition.minDeg,
    opposition.maxDeg,
  );

  return {
    oppositionDeg,
    mcpFlexDeg: clampMapping(rawAngles.mcpFlex, config.mcpFlex),
    ipFlexDeg: clampMapping(rawAngles.ipFlex, config.ipFlex),
  };
}

function rotateTowards(source, destination, maximumAngle, target) {
  TMP_AXIS.crossVectors(source, destination);
  const axisLengthSq = TMP_AXIS.lengthSq();
  const fullAngle = Math.acos(THREE.MathUtils.clamp(source.dot(destination), -1, 1));
  if (axisLengthSq < 1e-8 || fullAngle < 1e-5) return target.copy(source);
  TMP_AXIS.multiplyScalar(1 / Math.sqrt(axisLengthSq));
  return target.copy(source).applyAxisAngle(TMP_AXIS, Math.min(maximumAngle, fullAngle)).normalize();
}

function projectOutsidePalm(point, radius, frame) {
  const geometry = THUMB_VISUAL_MAPPING.geometry;
  TMP_DELTA.subVectors(point, frame.center);
  const side = TMP_DELTA.dot(frame.side);
  const longitudinal = TMP_DELTA.dot(frame.long);
  const halfSide = frame.palmWidth * geometry.palmCollisionHalfWidth + radius * 0.18;
  const halfLong = frame.palmLength * geometry.palmCollisionHalfLength + radius * 0.12;
  const radialSquared = (side * side) / (halfSide * halfSide) +
    (longitudinal * longitudinal) / (halfLong * halfLong);
  if (radialSquared >= 1) return;

  const surfaceDepth = frame.palmDepth * 0.94 * Math.sqrt(Math.max(0, 1 - radialSquared));
  const minimumDepth = surfaceDepth + radius * geometry.palmClearanceScale;
  const currentDepth = TMP_DELTA.dot(frame.palmar);
  if (currentDepth < minimumDepth) point.addScaledVector(frame.palmar, minimumDepth - currentDepth);
}

function closestPointOnSegment(point, start, end, target) {
  TMP_SEGMENT.subVectors(end, start);
  const lengthSquared = TMP_SEGMENT.lengthSq();
  const parameter = lengthSquared < 1e-8 ? 0 : THREE.MathUtils.clamp(
    TMP_DELTA.subVectors(point, start).dot(TMP_SEGMENT) / lengthSquared,
    0,
    1,
  );
  return target.copy(start).addScaledVector(TMP_SEGMENT, parameter);
}

function separateFromIndex(points, indexPoints, frame) {
  const clearanceScale = THUMB_VISUAL_MAPPING.geometry.indexClearanceScale;
  // The CMC and MCP centers (points 0/1) are deliberately embedded in the palm
  // and thenar. Only the exposed phalanges are projected away from the index
  // tube, with the correction propagated distally to avoid a sharp kink.
  for (let pass = 0; pass < 2; pass += 1) {
    for (let pointIndex = 2; pointIndex < 4; pointIndex += 1) {
      TMP_BEST_CORRECTION.set(0, 0, 0);
      let bestDepth = 0;
      for (let segment = 0; segment < 3; segment += 1) {
        closestPointOnSegment(points[pointIndex], indexPoints[segment], indexPoints[segment + 1], TMP_CLOSEST);
        TMP_DELTA.subVectors(points[pointIndex], TMP_CLOSEST);
        const distance = TMP_DELTA.length();
        const required = (FINGER_RADII.thumb[pointIndex] +
          Math.max(FINGER_RADII.index[segment], FINGER_RADII.index[segment + 1])) * clearanceScale;
        const penetration = required - distance;
        if (penetration <= bestDepth) continue;
        if (distance < 1e-5) TMP_CORRECTION.copy(frame.side).addScaledVector(frame.palmar, 0.4).normalize();
        else TMP_CORRECTION.copy(TMP_DELTA).multiplyScalar(1 / distance)
          .addScaledVector(frame.palmar, 0.28).normalize();
        TMP_BEST_CORRECTION.copy(TMP_CORRECTION).multiplyScalar(penetration);
        bestDepth = penetration;
      }
      if (bestDepth > 0) {
        for (let distal = pointIndex; distal < 4; distal += 1) points[distal].add(TMP_BEST_CORRECTION);
      }
    }
  }
}

export function buildVisualThumbPoints(rawPoints, rawAngles, frame, indexPoints, targetPoints) {
  const config = THUMB_VISUAL_MAPPING;
  const geometry = config.geometry;

  // The visual pivot sits well inside the lofted palm. The tube extends back
  // from this point only a fraction of its radius, so no detached root cap can
  // protrude through the palm's integrated thenar profile. Keep this root
  // calculation unchanged: only the three distal directions follow raw FK.
  targetPoints[0].copy(frame.center)
    .addScaledVector(frame.side, frame.palmWidth * geometry.rootSide)
    .addScaledVector(frame.long, frame.palmLength * geometry.rootLong)
    .addScaledVector(frame.palmar, frame.palmDepth * geometry.rootDepth);

  const metacarpalLength = Math.max(8, rawPoints[1].distanceTo(rawPoints[2])) * geometry.metacarpalScale;
  const proximalLength = Math.max(8, rawPoints[2].distanceTo(rawPoints[3])) * geometry.proximalScale;
  const distalLength = Math.max(8, rawPoints[3].distanceTo(rawPoints[4])) * geometry.distalScale;

  // Retarget/origin mirrors the right CMC offset but does not apply another
  // right-hand sign to the CMC, MCP or IP rotations. Reusing the verified FK
  // segment directions therefore avoids the previous double mirror. It also
  // preserves signed flexion (the live right IP is commonly negative), which
  // the old positive-only presentation clamp incorrectly flattened to 3 deg.
  TMP_DIRECTION.subVectors(rawPoints[2], rawPoints[1]).normalize();
  targetPoints[1].copy(targetPoints[0]).addScaledVector(TMP_DIRECTION, metacarpalLength);

  TMP_DIRECTION.subVectors(rawPoints[3], rawPoints[2]).normalize();
  targetPoints[2].copy(targetPoints[1]).addScaledVector(TMP_DIRECTION, proximalLength);

  TMP_DIRECTION.subVectors(rawPoints[4], rawPoints[3]).normalize();
  targetPoints[3].copy(targetPoints[2]).addScaledVector(TMP_DIRECTION, distalLength);

  // Collision corrections must not move kinematic joint centers. Surface-only
  // clearance can be added later without changing the reconstructed skeleton.
  return mapThumbVisualPose(rawPoints, rawAngles, frame);
}
