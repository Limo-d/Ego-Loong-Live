// Semantic order emitted by backend/hand_pose_processor.py.  The browser does
// not reinterpret solve_state: it only consumes these verified FK points.
export const JOINT_NAMES = Object.freeze([
  'wrist',
  'thumb_cmc', 'thumb_mcp', 'thumb_ip', 'thumb_tip',
  'index_mcp', 'index_pip', 'index_dip', 'index_tip',
  'middle_mcp', 'middle_pip', 'middle_dip', 'middle_tip',
  'ring_mcp', 'ring_pip', 'ring_dip', 'ring_tip',
  'little_mcp', 'little_pip', 'little_dip', 'little_tip',
]);

export const FINGER_CHAINS = Object.freeze({
  thumb: Object.freeze([1, 2, 3, 4]),
  index: Object.freeze([5, 6, 7, 8]),
  middle: Object.freeze([9, 10, 11, 12]),
  ring: Object.freeze([13, 14, 15, 16]),
  little: Object.freeze([17, 18, 19, 20]),
});

export const BONE_EDGES = Object.freeze(
  Object.values(FINGER_CHAINS).flatMap(chain => [
    Object.freeze([0, chain[0]]),
    Object.freeze([chain[0], chain[1]]),
    Object.freeze([chain[1], chain[2]]),
    Object.freeze([chain[2], chain[3]]),
  ]),
);

// State27 mapping audited from Retarget.  Rendering is driven by FK points,
// but keeping the mapping explicit prevents the model from silently drifting
// away from the data contract.
export const STATE_ANGLE_MAPPING = Object.freeze([
  ['index', 'mcp_flex', 0], ['index', 'mcp_abduction', 1], ['index', 'pip_flex', 2], ['index', 'dip_flex', 3],
  ['middle', 'mcp_flex', 4], ['middle', 'mcp_abduction', 5], ['middle', 'pip_flex', 6], ['middle', 'dip_flex', 7],
  ['ring', 'mcp_flex', 8], ['ring', 'mcp_abduction', 9], ['ring', 'pip_flex', 10], ['ring', 'dip_flex', 11],
  ['little', 'mcp_flex', 12], ['little', 'mcp_abduction', 13], ['little', 'pip_flex', 14], ['little', 'dip_flex', 15],
  ['thumb', 'mcp_flex', 16], ['thumb', 'mcp_abduction', 17], ['thumb', 'ip_flex', 18],
].map(Object.freeze));

export const QUATERNION_MAPPING = Object.freeze({
  thumb_cmc_wxyz: Object.freeze([19, 20, 21, 22]),
  palm_wxyz: Object.freeze([23, 24, 25, 26]),
});

// The raw thumb has six rotational DOF in state27: the three rotations encoded
// by the CMC quaternion, MCP flexion/abduction and IP flexion. Feeding all six
// independently into a presentation mesh makes the short CMC chain extremely
// sensitive to twist and calibration noise. The reconstructed surface uses
// only the three bounded outputs below. Raw values are still sent unchanged,
// shown in the angle panel and used by the optional FK debug skeleton.
export const THUMB_VISUAL_MAPPING = Object.freeze({
  rawDof: 6,
  visualDof: Object.freeze(['cmc_opposition', 'mcp_flex', 'ip_flex']),
  ignoredDof: Object.freeze({
    cmc_axial_twist: 'Ignored by the surface because it twists/extrudes the thumb root without changing opposition.',
    cmc_secondary_swing: 'Not independent: its directional component is coupled into the single opposition output.',
    mcp_abduction: 'Not independent: it is coupled into the single opposition output.',
  }),
  // Signs are explicit because Retarget mirrors thumb offsets but applies the
  // same CMC/MCP rotation matrices to both hands.
  sideSigns: Object.freeze({
    left: Object.freeze({cmcSplay: 1, cmcPalm: 1, mcpAbduction: 1, palmNormal: -1}),
    right: Object.freeze({cmcSplay: -1, cmcPalm: 1, mcpAbduction: -1, palmNormal: 1}),
  }),
  opposition: Object.freeze({
    cmcSplayWeight: 0.22,
    cmcPalmWeight: 0.38,
    mcpAbductionWeight: 0.52,
    offsetDeg: 20,
    minDeg: 8,
    maxDeg: 48,
  }),
  mcpFlex: Object.freeze({scale: 0.78, offsetDeg: 9, minDeg: 6, maxDeg: 58}),
  ipFlex: Object.freeze({scale: 0.80, offsetDeg: 5, minDeg: 3, maxDeg: 62}),
  geometry: Object.freeze({
    rootSide: 0.48,
    rootLong: -0.08,
    rootDepth: -0.22,
    rootExtension: 0.38,
    metacarpalScale: 0.40,
    proximalScale: 0.55,
    distalScale: 0.60,
    indexClearanceScale: 0.88,
    palmClearanceScale: 0.34,
    palmCollisionHalfWidth: 0.70,
    palmCollisionHalfLength: 0.57,
  }),
});

// live_tactile_68_web.py: A-E are four cells per finger, F0-F47 palm.
// This is intentionally region-level; no per-vertex MANO mapping is claimed.
export const TACTILE_REGION_INDICES = Object.freeze({
  thumb: Object.freeze([0, 1, 2, 3]),
  index: Object.freeze([4, 5, 6, 7]),
  middle: Object.freeze([8, 9, 10, 11]),
  ring: Object.freeze([12, 13, 14, 15]),
  little: Object.freeze([16, 17, 18, 19]),
  palm: Object.freeze(Array.from({length: 48}, (_, i) => i + 20)),
});

export const FINGER_RADII = Object.freeze({
  thumb: Object.freeze([9.0, 9.0, 8.2, 7.2]),
  index: Object.freeze([7.0, 6.5, 5.8, 5.1]),
  middle: Object.freeze([7.3, 6.7, 5.9, 5.1]),
  ring: Object.freeze([6.9, 6.3, 5.6, 4.9]),
  little: Object.freeze([6.0, 5.4, 4.8, 4.2]),
});
