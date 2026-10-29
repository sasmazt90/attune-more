/** Display-only camera startup errors. Technical exception details stay in diagnostics. */
export function dentalCameraErrorMessage(error:unknown):string {
 const name=error&&typeof error==='object'&&'name' in error?error.name:undefined;
 switch(name){
  case 'NotFoundError':
  case 'DevicesNotFoundError':
   return 'Bu cihazda kullanılabilir kamera bulunamadı. Kamera bağlayıp yeniden deneyin veya fotoğraf yükleyin.';
  case 'NotAllowedError':
  case 'PermissionDeniedError':
  case 'SecurityError':
   return 'Kamera erişimi sağlanamadı. Lütfen kamera izinlerinizi kontrol edip tekrar deneyin.';
  case 'NotReadableError':
  case 'TrackStartError':
   return 'Kamera açılamadı; başka kamera kullanımını bitirip yeniden deneyin.';
  default:
   return 'Kamera açılamadı.';
 }
}
