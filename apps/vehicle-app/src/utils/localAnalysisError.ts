/** Stable transport classification; provider exception text never enters UI. */
export class LocalAnalysisError extends Error {
 constructor(public status:number,public code:string,message:string){super(message);this.name='LocalAnalysisError';}
}
export function localAnalysisError(status:number,code:unknown):LocalAnalysisError{
 const id=typeof code==='string'?code:'LOCAL_ANALYSIS_FAILED';
 const message=status===429?'Başka bir analiz sürüyor. Tamamlanmasını veya iptalin bitmesini bekleyip yeniden deneyin.':
  status===408||status===504?'Analiz zamanında tamamlanamadı. İşlem durduruldu; yeniden deneyebilirsiniz.':
  status===409?'Analiz durduruldu. PARK durumunu ve izinlerinizi kontrol edip yeniden deneyin.':
  status===503?'Yerel analiz şu anda kullanılamıyor. Yeniden deneyin; sorun sürerse destek alın.':
  status===422?'Görüntü veya ölçüm koşulları doğrulanamadı. Yönergeleri izleyerek yeniden çekin.':
  'Yerel analiz tamamlanamadı. Bağlantıyı kontrol edip yeniden deneyin.';
 return new LocalAnalysisError(status,id,message);
}
