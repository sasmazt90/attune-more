"""State/scoring contracts supplement, and never replace, pixel acceptance."""
from test_spoken_letter_product import run

def test_trial_token_changes_on_pause_eye_and_restart(tmp_path):
 run(tmp_path,"""
const F=load('visionFlow');const f=new F.VisionFlow();f.start('first');const prep=f.token();
assert(!f.letterVisible&&!f.canAnswer);f.instructionEye='RIGHT';f.transition('eye-check');assert(!f.matches(prep));
f.presentationId='a';f.transition('rendering');assert(f.letterVisible&&!f.canAnswer);const rendering=f.token();
f.transition('prompting');assert(!f.matches(rendering)&&!f.canAnswer);f.transition('listening');assert(!f.canAnswer);f.setConditions(true);assert(f.canAnswer);const listening=f.token();
f.setConditions(false);assert(f.letterVisible&&!f.canAnswer&&f.matches(listening));f.setConditions(true);assert(f.canAnswer&&f.matches(listening));
f.transition('condition-paused');assert(!f.canAnswer&&!f.letterVisible&&!f.matches(listening));f.eye='LEFT';assert(!f.matches(listening));
f.start('second');assert(!f.matches(listening));f.instructionEye='RIGHT';assert.equal(f.gatedEye('LEFT'),null);assert.equal(f.gatedEye('RIGHT'),'RIGHT');assert(F.eyeInstruction('RIGHT').includes('Sol gözünüzü kapatın veya örtün'));
assert(F.eyeInstruction('LEFT').includes('Sağ gözünüzü kapatın veya örtün'));
""")

def test_head_anchor_policy_not_legacy_scale_or_motion_override(tmp_path):
 run(tmp_path,"""
const policy={...c,distancePolicy:'head-anchors-hysteresis-v1',distanceState:'stable',relativeScaleChange:.12,motionStable:false};
assert.equal(V.letterConditionFailure(policy,'RIGHT',1100),null);
assert(V.letterConditionFailure({...policy,positionValid:false,distanceState:'near'},'RIGHT',1100));
assert(V.letterConditionFailure({...policy,relativeScaleChange:null},'RIGHT',1100));
assert.equal(V.letterConditionFailure({...policy,left:{...closed,state:'covered'}},'RIGHT',1100),null);
assert(V.letterConditionFailure({...policy,right:{...open,state:'covered'}},'RIGHT',1100));
assert(V.letterConditionFailure({...policy,left:{...closed,state:'uncertain'}},'RIGHT',1100));
""")

def test_paused_tts_and_user_wait_excluded_from_response(tmp_path):
 run(tmp_path,"""
const s=new V.SpokenLetterSession();s.present(100);s.beginResponse(1000);s.suspendResponse(1100);
s.beginResponse(10000);s.suspendResponse(10150);s.beginResponse(20000);
const cc={...c,observedAt:20000};assert(s.respond({letter:s.letter,orientation:s.orientation},cc,20050,s.presentationId));
assert.equal(s.trials[0].responseTimeMs,300);assert(!s.respond({letter:s.letter,orientation:s.orientation},cc,20050,s.presentationId));
""")

def test_eye_instruction_cannot_request_missing_stimulus():
 import vision_speech
 for eye in ['right','left']:
  assert 'Harfi' not in vision_speech.PROMPTS[eye]
  assert 'veya örtün' in vision_speech.PROMPTS[eye]
 assert 'harfi ve yönünü söyleyin' in vision_speech.PROMPTS['repeat']

def test_blink_hold_and_distance_hysteresis_contract(tmp_path):
 run(tmp_path,"""
load('skinAnalyzer');load('visionFrameQuality');const T=load('visionTracking');
const e=new T.SustainedEyeState();assert.equal(e.update('closed',0).state,'uncertain');assert.equal(e.update('closed',200).state,'uncertain');e.update('open',220);
assert.equal(e.update('closed',300).state,'uncertain');e.update('closed',500);e.update('closed',700);assert.equal(e.update('closed',899).state,'uncertain');assert.equal(e.update('closed',900).state,'closed');
assert.equal(e.update('covered',1000).state,'covered');e.update('covered',1200);e.update('closed',1400);assert.equal(e.update('covered',1600).state,'covered');assert.equal(e.update('uncertain',1700).state,'uncertain');e.update('closed',1800);assert.equal(e.update('closed',2500).state,'uncertain');
const d=new T.HeadDistanceHysteresis();assert.equal(d.update(.06,0),'stable');assert.equal(d.update(.16,100),'stable');d.update(.16,300);d.update(.16,500);assert.equal(d.update(.16,699),'stable');assert.equal(d.update(.16,700),'near');
assert.equal(d.update(.12,800),'near');assert.equal(d.update(null,900),'unknown');assert.equal(d.update(.12,1000),'near');assert.equal(d.update(.09,1100),'near');d.update(.09,1300);assert.equal(d.update(.09,1450),'stable');
assert.equal(d.update(-.16,1500),'stable');d.update(-.16,1700);d.update(-.16,1900);assert.equal(d.update(-.16,2100),'far');
""")

def test_visible_test_eye_during_wink_requires_geometry_and_low_blink(tmp_path):
 run(tmp_path,"""
load('skinAnalyzer');load('visionFrameQuality');const T=load('visionTracking');
assert.equal(T.nativeLidState(.69,.19,.02),'open');
assert.equal(T.nativeLidState(.63,.25,.02),'open');
assert.equal(T.nativeLidState(.60,.19,.02),'uncertain');
assert.equal(T.nativeLidState(.69,.5,.02),'uncertain');
assert.equal(T.nativeLidState(.3,.8,.02),'closed');
assert.equal(T.nativeLidState(.69,null,.02),'uncertain');
""")

def test_personal_open_eye_baseline_rejects_cover(tmp_path):
 run(tmp_path,"""
load('skinAnalyzer');load('visionFrameQuality');const T=load('visionTracking');
assert(T.baselineEyeVisible(.25,.02,0));
assert(!T.baselineEyeVisible(.25,.02,.9));
assert(!T.baselineEyeVisible(.25,.02,.25));
assert(!T.baselineEyeVisible(.25,null,0));
assert(!T.baselineEyeVisible(.25,.8,0));
assert(!T.baselineEyeVisible(.10,.02,0));
""")

def test_strong_wide_occlusion_needs_two_independent_pixel_signals(tmp_path):
 run(tmp_path,"""
load('skinAnalyzer');load('visionFrameQuality');const T=load('visionTracking');
assert(T.opaqueEyeAppearance(.768,.039,.257));
assert(T.opaqueEyeAppearance(.85,.01,.15));
assert(!T.opaqueEyeAppearance(.768,.3,.257));
assert(!T.opaqueEyeAppearance(.04,.039,.1));
assert(!T.opaqueEyeAppearance(.7,.1,.4));
assert(!T.opaqueEyeAppearance(.04,.85,.4));
// A small opaque cover replaces the eye while preserving most of the brow.
assert(T.opaqueEyeAppearance(.20,.75,.05,.82));
assert(!T.opaqueEyeAppearance(.20,.75,.05,.10));
assert(!T.opaqueEyeAppearance(.20,.75,.85,.82));
""")

def test_eye_identity_uses_source_nose_midline_including_roll(tmp_path):
 run(tmp_path,"""
load('skinAnalyzer');load('visionFrameQuality');const T=load('visionTracking');
const bridge={x:.5,y:.4},nose={x:.5,y:.55};
assert(T.eyeOnAnatomicalSide('RIGHT',.4,.4,bridge,nose));
assert(T.eyeOnAnatomicalSide('LEFT',.6,.4,bridge,nose));
assert(!T.eyeOnAnatomicalSide('RIGHT',.6,.4,bridge,nose));
assert(!T.eyeOnAnatomicalSide('LEFT',.4,.4,bridge,nose));
assert(!T.eyeOnAnatomicalSide('LEFT',.5,.4,bridge,nose));
assert(!T.eyeOnAnatomicalSide('LEFT',.6,.4,bridge,{x:.5,y:.3}));
assert(T.eyeOnAnatomicalSide('RIGHT',.4,.35,bridge,{x:.54,y:.55}));
const F=load('visionFlow');assert(F.eyeInstruction('RIGHT').includes('harf alanına bakın'));
""")

def test_framing_depends_on_source_bounds_and_real_eye_pixels(tmp_path):
 run(tmp_path,"""
load('skinAnalyzer');load('visionFrameQuality');const T=load('visionTracking');
assert(T.sourceFaceFramed(.4,.6,.4,.6,true));
assert(!T.sourceFaceFramed(.4,.6,.4,.6,false));
assert(!T.sourceFaceFramed(-.01,.6,.4,.6,true));
assert(!T.sourceFaceFramed(.4,1.01,.4,.6,true));
assert(!T.sourceFaceFramed(.4,.6,-.01,.6,true));
assert(!T.sourceFaceFramed(.4,.6,.4,1.01,true));
""")

def test_user_reported_phrase_is_valid_without_target_fallback(tmp_path):
 run(tmp_path,"""
assert.deepEqual(V.parseLetterAnswer('sola yatmış P'),{letter:'P',rotation:270});
assert.deepEqual(V.parseLetterAnswer('P sola yatmış'),{letter:'P',rotation:270});
assert.deepEqual(V.parseLetterAnswer('baş aşağı R'),{letter:'R',rotation:180});
assert.deepEqual(V.parseLetterAnswer('baş aşağı Rize'),{letter:'R',rotation:180});
""")

def test_instruction_echo_does_not_become_an_answer_or_repeat(tmp_path):
 run(tmp_path,"""
for(const text of Object.values(V.LETTER_INSTRUCTIONS))assert(V.isLetterInstructionEcho(text));
for(const text of ['P sola yatmış','sola yatmış P','sola yatmış','tekrar','duraklat','göremiyorum','bitir','F baş aşağı','baş aşağı R','baş aşağı Rize'])assert(!V.isLetterInstructionEcho(text));
""")

def test_response_clock_follows_actual_geometry_measurement(tmp_path):
 run(tmp_path,"""
const s=new V.SpokenLetterSession();s.present(1000);s.beginResponse(1100);let now=1100;
const measure=()=>({viewportWidthCssPx:120,viewportHeightCssPx:120,pathWidthCssPx:100,pathHeightCssPx:100,strokeWidthCssPx:10,measuredAt:++now,method:'dom-svg-css-pixels'});
assert(V.respondToVisibleLetter(s,{letter:s.letter,orientation:s.orientation},c,s.presentationId,measure,()=>++now));
assert.equal(s.trials.length,1);assert.equal(s.trials[0].renderedGeometry.measuredAt,1101);assert.equal(s.trials[0].responseTimeMs,2);
s.present(1200);const cc={...c,observedAt:1200};const future={...measure(),measuredAt:1202};
assert(!V.respondToVisibleLetter(s,{letter:s.letter,orientation:s.orientation},cc,s.presentationId,()=>future,()=>1201));
assert.equal(s.trials.length,1);
""")

def test_native_letter_direction_fragments_join_without_target_or_tts_time(tmp_path):
 run(tmp_path,"""
for(const fragments of [['R','baş aşağı'],['baş aşağı','R'],['sola yatmış','P'],['P','sola yatmış']]){
const s=new V.SpokenLetterSession();s.present(1000);let partial={};for(const text of fragments)partial=V.mergeLetterAnswer(partial,V.parseLetterAnswer(text));
assert(partial.letter&&V.answerTransform(partial)&&!partial.clarify);
// No response timer has started: an answer during TTS remains admissible,
// with the speaking duration excluded, and only one trial advances.
assert(V.respondToVisibleLetter(s,partial,c,s.presentationId,()=>({viewportWidthCssPx:120,viewportHeightCssPx:120,pathWidthCssPx:100,pathHeightCssPx:100,strokeWidthCssPx:10,measuredAt:1099,method:'dom-svg-css-pixels'}),()=>1100));
assert.equal(s.trials.length,1);assert.equal(s.trials[0].responseTimeMs,0);
}
assert(V.mergeLetterAnswer({letter:'R'},V.parseLetterAnswer('ters')).clarify);
const F=load('visionFlow');const f=new F.VisionFlow();f.start('session');f.presentationId='actual';f.transition('listening');f.setConditions(true);const token=f.token();
assert(f.canAnswer&&f.matches(token));f.setConditions(false);assert(!f.canAnswer);f.transition('user-paused');assert(!f.matches(token));
""")

def test_spoken_answer_guidance_cannot_supply_missing_target_fields(tmp_path):
 import json,vision_speech
 texts=[vision_speech.PROMPTS[k] for k in ['repeat','letter','orientation','reverse']]
 run(tmp_path,'for(const text of '+json.dumps(texts)+'''){
assert(V.isLetterInstructionEcho(text));const parsed=V.parseLetterAnswer(text);
for(const partial of [{letter:'R'},{orientation:'down'}]){const merged=V.mergeLetterAnswer(partial,parsed);assert(!(merged.letter&&merged.orientation&&!merged.clarify));}
}''')
