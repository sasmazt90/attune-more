// Actual production anatomical graph, with reviewed source landmarks.
require('../../tests/unit/ts_loader.js');
const fs=require('fs');const {buildSkinMesh,supportedSkinMesh}=require('../../apps/vehicle-app/src/utils/skinMesh.ts');
const {SkinAnalyzer}=require('../../apps/vehicle-app/src/utils/skinAnalyzer.ts');
const rows=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(rows.map(r=>({sha256:r.sha256,alignment:SkinAnalyzer.calculateAlignmentFromLandmarks(r.landmarks,r.width,r.height),meshes:Object.fromEntries(['forehead','rightCheek','leftCheek','nose','chin','periorbital'].map(id=>[id,supportedSkinMesh(buildSkinMesh(id,r.landmarks,r.width,r.height),r.landmarks,r.width,r.height)]))}))));
