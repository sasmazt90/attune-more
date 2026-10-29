require('./ts_loader.js');
const assert=require('node:assert/strict'),{test}=require('node:test');
const {dentalCameraErrorMessage}=require('../../apps/vehicle-app/src/utils/dentalCameraError.ts');
const {t}=require('../../apps/vehicle-app/src/i18n/core.ts');
const missing='Bu cihazda kullanılabilir kamera bulunamadı. Kamera bağlayıp yeniden deneyin veya fotoğraf yükleyin.';
const denied='Kamera erişimi sağlanamadı. Lütfen kamera izinlerinizi kontrol edip tekrar deneyin.';
const busy='Kamera açılamadı; başka kamera kullanımını bitirip yeniden deneyin.';
for(const [names,expected] of [[['NotFoundError','DevicesNotFoundError'],missing],[['NotAllowedError','PermissionDeniedError','SecurityError'],denied],[['NotReadableError','TrackStartError'],busy]]){
 for(const name of names)test(name+' keeps browser details out of every display locale',()=>{
  const error=new DOMException('RAW_DEVICE_DETAILS_Requested device not found',name);
  assert.equal(dentalCameraErrorMessage(error),expected);
  for(const language of ['tr','en','de']){const display=t(dentalCameraErrorMessage(error),language);assert(!display.includes(error.message));assert(!display.includes(name));if(language!=='tr')assert.notEqual(display,expected);}
 });
}
test('unknown failures never use an exception message or coerce arbitrary thrown values',()=>{
 for(const value of [new Error('RAW_MODEL_OR_PREVIEW_DETAILS'),new DOMException('RAW_ABORT','AbortError'),new TypeError('RAW_MEDIA_API_DETAILS'),null,undefined,'RAW_STRING',{message:'RAW_OBJECT'}])assert.equal(dentalCameraErrorMessage(value),'Kamera açılamadı.');
});
test('missing-camera guidance names the device failure and existing recovery options in TR/EN/DE',()=>{
 assert.equal(t(missing,'tr'),missing);
 assert.equal(t(missing,'en'),'No available camera was found on this device. Connect a camera and try again, or upload a photo.');
 assert.equal(t(missing,'de'),'Auf diesem Gerät wurde keine verfügbare Kamera gefunden. Schließen Sie eine Kamera an und versuchen Sie es erneut oder laden Sie ein Foto hoch.');
});
