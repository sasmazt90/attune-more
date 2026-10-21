'use strict';
// Offline policy checks; these never contact an Android device.
const assert = require('node:assert/strict');
const test = require('node:test');
const { mediaConstraints, allowedResource, ROUTES, navigate } = require('./webview_driver.cjs');
const localized = require('./localized_webview.cjs');

test('Only advertised hardware is requested, preferring the image microphone', () => {
  assert.deepEqual(mediaConstraints({ microphone: 'true', camera: 'false' }), { audio: true, video: false });
  assert.deepEqual(mediaConstraints({ microphone: 'false', camera: 'true' }), { audio: false, video: true });
  assert.equal(mediaConstraints({ microphone: 'false', camera: 'false' }), null);
  assert.equal(mediaConstraints({}), null);
});

test('Observer admits exact local resources and rejects lookalike/external origins', () => {
  for (const url of ['http://localhost:3000/skin', 'http://localhost:8000/api/health', 'http://127.0.0.1:8000/api/vehicle/state', 'data:image/png;base64,', 'blob:http://localhost:3000/test']) assert.equal(allowedResource(url), true, url);
  for (const url of ['http://localhost.evil:3000/', 'http://localhost:3001/', 'https://localhost:3000/', 'https://example.com', 'file:///etc/passwd', 'not a URL']) assert.equal(allowedResource(url), false, url);
});

test('Navigation rejects routes outside the finite list before interacting', async () => {
  assert.equal(ROUTES.size, 9);
  await assert.rejects(navigate(null, '/unapproved'), /finite acceptance list/);
});

test('Integrated observer accepts only three locales and five health modules', () => {
  assert.equal(localized.LANGUAGES.size,3);
  assert.equal(Object.keys(localized.MODULE_EVENTS).length,5);
  for (const language of ['tr','en','de']) for (const moduleName of Object.keys(localized.MODULE_EVENTS)) assert.doesNotThrow(()=>localized.validate(language,moduleName));
  for (const language of ['fr','en-US','../../','']) assert.throws(()=>localized.validate(language,'mental'),/finite/);
  for (const moduleName of ['profile','privacy','__proto__','../../']) assert.throws(()=>localized.validate('de',moduleName),/finite/);
});

test('Neural acceptance uses comparable bounded utterances, not an English-only interruption script', () => {
  assert.deepEqual(Object.keys(localized.NEURAL_TEXT),['tr','en','de']);
  for(const text of Object.values(localized.NEURAL_TEXT)){
    assert(text.includes('1287'));assert(text.length<90);assert(text.length>35);
  }
});

test('Neural observer retains the actual response before playback, and preserves evidence failures', async () => {
  // Explicit Playwright/HTTP fixtures, not neural or browser-playback evidence.
  for(const unavailable of [false,true]){
    let observe,bodyReads=0;
    const result={language:'en',played:true,starts:1,stages:[{stage:'playing'}],gestureRequested:false};
    const bytes=Buffer.alloc(100);bytes.write('RIFF');bytes.write('WAVE',8);
    const page={
      on:(name,fn)=>{assert.equal(name,'response');observe=fn;},off:()=>{},
      evaluate:async(fn,arg)=>{
        if(arg?.language){
          observe({url:()=> 'http://localhost:3000/api/mental-neural-speech',status:()=>200,
            body:async()=>{bodyReads++;if(unavailable)throw Error('Explicit body-unavailable fixture');return bytes;}});
          return;
        }
        if(String(fn).includes('!!window.ApprovedAudioQA'))return true;
        if(String(fn).includes('!!attuneNeuralQA.result'))return true;
        return result;
      },
      waitForFunction:async()=>assert.equal(bodyReads,1,'start reading before waiting for playback'),
    };
    const row=await localized.neural(page,'en');
    assert.equal(row.played,true);assert.equal(row.starts,1);
    assert.equal(row.status,unavailable?'BLOCKED':'PASS');
    if(unavailable){
      assert(row.evidenceError.includes('bytes unavailable'));
      await assert.rejects(localized.activeStart(null,'mute'),/no current-run real English neural WAV/);
    }
  }
});
