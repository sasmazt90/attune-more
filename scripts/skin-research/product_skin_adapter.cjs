const fs = require('fs');
const path = require('path');
require('../../tests/unit/ts_loader.js');
const { SkinAnalyzer, skinSourceFramed } = require('../../apps/vehicle-app/src/utils/skinAnalyzer.ts');
const { matchesSkinAngle, SKIN_ANGLES } = require('../../apps/vehicle-app/src/utils/skinMultiAngle.ts');
const { buildSkinMesh, supportedSkinMesh } = require('../../apps/vehicle-app/src/utils/skinMesh.ts');

const inputData = JSON.parse(fs.readFileSync(0, 'utf8'));
const results = [];

for (const item of inputData) {
  const { sha256, width, height, landmarks, rgbBase64 } = item;
  if (!landmarks || landmarks.length < 468) {
    results.push({
      sha256,
      landmarksFound: false,
      alignment: null,
      quality: { isValid: false, status: 'NO_FACE', avgLuminance: 0, blurScore: 0 },
      matchedAngle: null,
      allowedRegions: [],
      capturable: false,
      reasons: ['MISSING_LANDMARKS']
    });
    continue;
  }

  // 1. Calculate alignment
  const alignment = SkinAnalyzer.calculateAlignmentFromLandmarks(landmarks, width, height);

  // 2. Mock ctx for checkQuality
  let quality = { isValid: false, status: 'NO_IMAGE', avgLuminance: 0, blurScore: 0 };
  if (rgbBase64) {
    const rawRgb = Buffer.from(rgbBase64, 'base64');
    const ctx = {
      getImageData: (x0, y0, w, h) => {
        const subData = new Uint8ClampedArray(w * h * 4);
        for (let y = 0; y < h; y++) {
          for (let x = 0; x < w; x++) {
            const srcIdx = ((y0 + y) * width + (x0 + x)) * 3;
            const dstIdx = (y * w + x) * 4;
            subData[dstIdx] = rawRgb[srcIdx];
            subData[dstIdx + 1] = rawRgb[srcIdx + 1];
            subData[dstIdx + 2] = rawRgb[srcIdx + 2];
            subData[dstIdx + 3] = 255;
          }
        }
        return { width: w, height: h, data: subData };
      }
    };
    quality = SkinAnalyzer.checkQuality(ctx, width, height, alignment.faceDetected, alignment.box);
  }

  // 3. Match skin angle
  let matchedAngle = null;
  for (const angle of SKIN_ANGLES) {
    if (matchesSkinAngle(alignment, angle)) {
      matchedAngle = angle;
      break;
    }
  }

  // 4. Allowed regions based on matched angle
  const allowedRegions = matchedAngle === 'FRONT'
    ? ['forehead', 'nose', 'chin', 'periorbital', 'rightCheek', 'leftCheek']
    : matchedAngle === 'RIGHT'
    ? ['leftCheek']
    : matchedAngle === 'LEFT'
    ? ['rightCheek']
    : [];

  const allMeshIds = ['forehead', 'rightCheek', 'leftCheek', 'nose', 'chin', 'periorbital'];
  const meshes = {};
  for (const id of allMeshIds) {
    meshes[id] = supportedSkinMesh(buildSkinMesh(id, landmarks, width, height), landmarks, width, height);
  }

  const angleAligned = matchedAngle === 'FRONT'
    ? alignment.isAligned
    : (matchedAngle !== null && matchesSkinAngle(alignment, matchedAngle));
  const capturable = matchedAngle !== null && quality.isValid && angleAligned;

  results.push({
    sha256,
    landmarksFound: true,
    alignment: {
      yaw: alignment.yaw,
      pitch: alignment.pitch,
      roll: alignment.roll,
      scaleRatio: alignment.scaleRatio,
      isAligned: alignment.isAligned,
      sourceFramed: alignment.sourceFramed,
      box: alignment.box,
      guidanceTextTr: alignment.guidanceTextTr
    },
    quality: {
      isValid: quality.isValid,
      status: quality.status,
      avgLuminance: quality.avgLuminance,
      blurScore: quality.blurScore,
      warningMessageTr: quality.warningMessageTr
    },
    matchedAngle,
    allowedRegions,
    meshes,
    capturable,
    poseEligible: matchedAngle !== null
  });
}

process.stdout.write(JSON.stringify(results));
