// Actual current product pose helper: skin (12°–45°) and dental (15°–45°) widened pose gates.
require('./ts_loader.js');
const assert = require('assert/strict');
const {
  matchesSkinAngle,
  skinPoseRotation,
  angleGuidance,
  SKIN_SIDE_MIN_YAW_DEG,
  SKIN_SIDE_MAX_YAW_DEG,
} = require('../../apps/vehicle-app/src/utils/skinMultiAngle.ts');
const {
  matchesDentalAngle,
  dentalPose,
  dentalGuidance,
  DENTAL_SIDE_MIN_DEG,
  DENTAL_SIDE_MAX_DEG,
} = require('../../apps/vehicle-app/src/utils/dentalCapture.ts');

assert.equal(SKIN_SIDE_MIN_YAW_DEG, 10.5);
assert.equal(SKIN_SIDE_MAX_YAW_DEG, 45);
assert.equal(DENTAL_SIDE_MIN_DEG, 15);
assert.equal(DENTAL_SIDE_MAX_DEG, 45);

const base = {
  faceDetected: true,
  isMediaPipeActive: true,
  yaw: 0,
  pitch: 0,
  roll: 0,
  scaleRatio: 0.5,
  sourceFramed: true,
  isAligned: false,
};

// 1. 2D fallback checks (preserves old valid poses and allows wider turn up to 1.15, rejects > 1.15):
assert.equal(matchesSkinAngle({ ...base, yaw: 0.25 }, 'LEFT'), true);
assert.equal(matchesSkinAngle({ ...base, yaw: 0.40 }, 'LEFT'), true);
assert.equal(matchesSkinAngle({ ...base, yaw: -0.40 }, 'RIGHT'), true);
assert.equal(matchesSkinAngle({ ...base, yaw: 0.40 }, 'FRONT'), false);
assert.equal(matchesSkinAngle({ ...base, yaw: -0.40 }, 'LEFT'), false);
assert.equal(matchesSkinAngle({ ...base, yaw: 0.40, pitch: 0.28 }, 'LEFT'), false);
assert.equal(matchesSkinAngle({ ...base, yaw: 0.40, roll: 0.20 }, 'LEFT'), false);
assert.equal(matchesSkinAngle({ ...base, yaw: 0.40, sourceFramed: false }, 'LEFT'), false);
assert.equal(matchesSkinAngle({ ...base, yaw: 0.98 }, 'LEFT'), true);
assert.equal(matchesSkinAngle({ ...base, yaw: 1.20 }, 'LEFT'), false);

// Helper to construct a column-major 4x4 rotation matrix around Y by yawDeg:
function makeTransform(yawDeg) {
  const rad = (yawDeg * Math.PI) / 180;
  const c = Math.cos(rad);
  const s = Math.sin(rad);
  return [c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, -40, 1];
}

// 2. Real gate-check-1 frame: 2D nose ratio yaw=0.93 (> old 0.92 limit!), 3D faceTransform yawDeg=+25.5°
const realGateCheckSide = { ...base, yaw: 0.93, faceTransform: makeTransform(25.5) };
assert.equal(skinPoseRotation(realGateCheckSide).yawDeg, 25.5);
assert.equal(matchesSkinAngle(realGateCheckSide, 'LEFT'), true);
assert.equal(matchesSkinAngle(realGateCheckSide, 'RIGHT'), false);
assert.equal(matchesSkinAngle(realGateCheckSide, 'FRONT'), false);

// 3. Previously accepted gentle turns (10.9°–15°, including 06_usa LEFT 10.9° / 0.30) remain accepted, AND wider turns up to 45° are now accepted:
assert.equal(matchesSkinAngle({ ...base, yaw: 0.30, faceTransform: makeTransform(10.9) }, 'LEFT'), true);
assert.equal(matchesSkinAngle({ ...base, yaw: 0.25, faceTransform: makeTransform(12.5) }, 'LEFT'), true);
assert.equal(matchesSkinAngle({ ...base, yaw: -0.70, faceTransform: makeTransform(-21.6) }, 'RIGHT'), true);
assert.equal(matchesSkinAngle({ ...base, yaw: 1.05, faceTransform: makeTransform(42.0) }, 'LEFT'), true);
assert.equal(matchesSkinAngle({ ...base, yaw: -1.05, faceTransform: makeTransform(-42.0) }, 'RIGHT'), true);

// 4. Out-of-bounds (< 10.5° & < 0.25 or > 45°) are rejected with matching guidance:
assert.equal(matchesSkinAngle({ ...base, yaw: 0.10, faceTransform: makeTransform(6.0) }, 'LEFT'), false);
assert.equal(matchesSkinAngle({ ...base, yaw: 1.25, faceTransform: makeTransform(48.0) }, 'LEFT'), false);
assert(angleGuidance({ ...base, yaw: 1.25, faceTransform: makeTransform(48.0) }, 'LEFT').includes('12°–45°'));

// 5. Dental side pose gate widened to 15°–45° (accepts 16°, 25°, 42°; rejects 10° and 48°) and preserves strict pitch (<=0.22) and roll (<=0.15):
assert.equal(matchesDentalAngle({ ...base, faceTransform: makeTransform(16.0) }, 'LEFT'), true);
assert.equal(matchesDentalAngle({ ...base, faceTransform: makeTransform(42.0) }, 'LEFT'), true);
assert.equal(matchesDentalAngle({ ...base, faceTransform: makeTransform(-42.0) }, 'RIGHT'), true);
assert.equal(matchesDentalAngle({ ...base, faceTransform: makeTransform(10.0) }, 'LEFT'), false);
assert.equal(matchesDentalAngle({ ...base, faceTransform: makeTransform(48.0) }, 'LEFT'), false);
assert(dentalGuidance({ ...base, faceTransform: makeTransform(10.0) }, 'LEFT').includes('15°–45°'));
assert.equal(dentalPose({ ...base, faceTransform: makeTransform(42.0) }).yawDeg, 42);

console.log(
  JSON.stringify({
    actualProductPoseHelper: true,
    skinRangeDeg: [SKIN_SIDE_MIN_YAW_DEG, SKIN_SIDE_MAX_YAW_DEG],
    dentalRangeDeg: [DENTAL_SIDE_MIN_DEG, DENTAL_SIDE_MAX_DEG],
    sideFrontGateRegression: true,
    rigid3DYawVerified: true,
    checks: 29,
  })
);
