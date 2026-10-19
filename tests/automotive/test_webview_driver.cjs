'use strict';
// Offline policy checks; these never contact an Android device.
const assert = require('node:assert/strict');
const test = require('node:test');
const { mediaConstraints, allowedResource, ROUTES, navigate } = require('./webview_driver.cjs');

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
