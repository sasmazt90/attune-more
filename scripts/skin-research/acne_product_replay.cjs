// Research-only replay of the CURRENT frontend capture functions for still photos.
// Uses the repository's own TypeScript (SkinAnalyzer alignment/quality,
// matchesSkinAngle, snapshotSkinFrame geometry: meshes/exclusions/ROIs and the
// INCOMPLETE_HEAD_FRAME check). Landmarks come from a separate replay; the eyewear
// ONNX gate and the browser decode path are NOT replayed (eyewear => UNKNOWN).
// Input: NDJSON on stdin {sha256,width,height,analysisWidth,analysisHeight,landmarks,blendshapes,rgbBase64(analysis RGB)}.
// Output: NDJSON on stdout. Run with cwd = repository root.
const readline = require('readline');
require('../../tests/unit/ts_loader.js');
const { SkinAnalyzer } = require('../../apps/vehicle-app/src/utils/skinAnalyzer.ts');
const { matchesSkinAngle, SKIN_ANGLES } = require('../../apps/vehicle-app/src/utils/skinMultiAngle.ts');
const { snapshotSkinFrame } = require('../../apps/vehicle-app/src/utils/skinSnapshot.ts');
const { expressionScores } = require('../../apps/vehicle-app/src/utils/skinExpression.ts');

function replay(item) {
  const { sha256, width, height, analysisWidth, analysisHeight, landmarks, blendshapes, rgbBase64 } = item;
  const aw = analysisWidth, ah = analysisHeight;
  if (!landmarks || landmarks.length < 468) {
    return { sha256, faceDetected: false, quality: { isValid: false, status: 'NO_FACE' }, matchedAngle: null, gatePassedWithoutEyewear: false, reasons: ['NO_FACE'] };
  }
  const alignment = { ...SkinAnalyzer.calculateAlignmentFromLandmarks(landmarks, aw, ah),
    expressionScores: expressionScores(Object.entries(blendshapes || {}).map(([categoryName, score]) => ({ categoryName, score }))),
    faceCount: item.faceCount };
  if (item.faceCount !== 1) { alignment.faceDetected = false; alignment.isAligned = false; }
  const rgb = Buffer.from(rgbBase64, 'base64');
  const ctx = { getImageData: (x0, y0, w, h) => {
    const data = new Uint8ClampedArray(w * h * 4);
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const s = ((y0 + y) * aw + (x0 + x)) * 3, d = (y * w + x) * 4;
      data[d] = rgb[s]; data[d + 1] = rgb[s + 1]; data[d + 2] = rgb[s + 2]; data[d + 3] = 255;
    }
    return { width: w, height: h, data };
  } };
  // Like the product preflight: alignment/quality on the <=640 analysis canvas,
  // snapshot geometry on the native source dimensions with the same alignment.
  const quality = SkinAnalyzer.checkQuality(ctx, aw, ah, alignment.faceDetected, alignment.box);
  let matchedAngle = null;
  for (const angle of SKIN_ANGLES) if (matchesSkinAngle(alignment, angle)) { matchedAngle = angle; break; }
  const angleAligned = matchedAngle === 'FRONT' ? alignment.isAligned : matchedAngle !== null;
  let snapshot = null, snapshotError = null;
  if (matchedAngle) {
    try {
      const s = snapshotSkinFrame({ width, height }, alignment, matchedAngle);
      snapshot = { width, height, angle: matchedAngle, rois: s.rois, exclusions: s.exclusions, meshes: s.meshes };
    } catch (e) { snapshotError = String(e && e.message || e); }
  }
  const reasons = [];
  if (!alignment.faceDetected) reasons.push('NO_FACE');
  if (!quality.isValid) reasons.push('QUALITY:' + quality.status);
  if (!matchedAngle) reasons.push('POSE');
  else if (!angleAligned) reasons.push('POSE_NOT_ALIGNED');
  if (snapshotError) reasons.push('SNAPSHOT:' + snapshotError);
  return { sha256, faceDetected: alignment.faceDetected,
    alignment: { yaw: alignment.yaw, pitch: alignment.pitch, roll: alignment.roll, scaleRatio: alignment.scaleRatio,
      isAligned: alignment.isAligned, sourceFramed: alignment.sourceFramed, box: alignment.box },
    quality: { isValid: quality.isValid, status: quality.status, avgLuminance: quality.avgLuminance, blurScore: quality.blurScore },
    matchedAngle, angleAligned, snapshot, snapshotError, eyewear: 'NOT_REPLAYED',
    gatePassedWithoutEyewear: reasons.length === 0, reasons };
}

const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
rl.on('line', line => { if (!line.trim()) return; process.stdout.write(JSON.stringify(replay(JSON.parse(line))) + '\n'); });
