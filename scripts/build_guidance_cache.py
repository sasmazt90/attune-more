"""Generate ONLY authorized, non-personal fixed guidance using the exact Edge profiles."""
import asyncio,hashlib,json
from pathlib import Path
import edge_tts
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'apps/vehicle-app/public/audio/guidance'
N=json.loads((ROOT/'shared/healthModules.json').read_text('utf-8-sig'))
TEXTS={
 'skin-neutral':'Ağzınızı kapatın. Gülümsemeden yüzünüzü rahat bırakın; başınızı istenen pozda sabit tutun.',
 'cockpit-entry':'Sağlık Merkezi menüsünden yapmak istediğiniz değerlendirmeyi seçin.',
 'profile-entry':'Sağlık Geçmişim. Bir kaydı açabilir veya yalnız seçtiğiniz kaydı silebilirsiniz.',
 'record-open':'Kayıt ayrıntısı açıldı. Uzman seçeneklerine buradan geçebilirsiniz.',
 'record-delete':'Yalnız seçtiğiniz kayıt silinecek. Silmek için onaylayın; vazgeçmek için iptal edin.',
 'care-entry':'Sağlık alanını ve branşı seçin. Uzmanı ve uygun saati sağlayıcının sayfasında doğrulayın.',
 'care-select':'Seçtiğiniz uzmanı ve saati kontrol edin. Bu adım randevu oluşturmaz.',
 'skin-entry':N['skin']['name']+'. Başınızı rahat tutun; ön, sağ ve sol görüntüyü ekrandaki yönergeyle alacağız.',
 'skin-front':'Gözlüğünüzü çıkarın. Başınız karşıda. Yüzünüz ekranda görünürken kısa süre sabit durun.',
 'skin-right':'Başınızı kendi sağınıza hafifçe çevirin; kısa süre sabit tutun.',
 'skin-left':'Başınızı kendi solunuza hafifçe çevirin; kısa süre sabit tutun.',
 'skin-complete':'Tarama tamamlandı. Bölge ve kriter kartını seçerek mevcut görünüm sonucunu inceleyin.',
 'quality-near':'Kaynak görüntüde yüz ayrıntısı yetersiz. Konumunuzu biraz yaklaştırın.',
 'quality-far':'Alın ve çene kadraja sığmalı. Biraz uzaklaşın.',
 'quality-light':'Yüzünüzü eşit aydınlatın; sert yan ışığı ve yansımayı azaltın.',
 'quality-blur':'Kameranın netliğini kontrol edin; başınızı kısa süre sabit tutun.',
 'quality-face':'Yüzünüzün görünmesini sağlayın; kamera görüşünü kapatan şeyi kaldırın.',
 'dental-entry':N['dental']['name']+'. Kamerayla tarayabilir veya net bir ağız içi diş fotoğrafı yükleyebilirsiniz.',
 'dental-upload':'Dişlerin göründüğü net, renkli ağız içi fotoğrafı seçin. Röntgen yüklemeyin.',
 'dental-front':'Başınız karşıda. Ağzınızı rahatça açın; ön dişleriniz görünsün.',
 'dental-right':'Başınızı kendi sağınıza hafifçe çevirin; ağzınızı rahatça açık tutun.',
 'dental-left':'Başınızı kendi solunuza hafifçe çevirin; ağzınızı rahatça açık tutun.',
 'dental-bite':'Dişlerinizi doğal, rahat kapanışta tutun; ön dişleriniz görünsün. Zorlamayın.',
 'dental-teeth':'Dişler görünmeli. Dudak, dil veya cisim örtüsünü kaldırın.',
 'dental-file':'JPEG, PNG veya WebP biçiminde, sınırlar içinde açılabilen bir fotoğraf seçin.',
 'dental-complete':'Analiz tamamlandı. Adaylar yalnız görünür yüzeyler içindir; sonuç kartlarını inceleyin.',
 'hearing-entry':N['hearing']['name']+'. Sessiz ortamda stereo kulaklık kullanın. Önce sağ ve sol kanalı doğrulayacağız.',
 'hearing-prepare':'Lütfen önce kulaklığınızı takın ve aşağıda ilgili butonlara basarak sadece belirtilen kulaklıktan ses duyduğunuzu onaylayın.',
 'hearing-tone':'Sesi duyana kadar bekleyin ve duyduğunuz an butona basın.',
 'hearing-digits':'Geri sayım bittikten sonra gürültü içinde üç sayı duyacaksınız. Sayıları sırayla girip yanıtı gönderin.',
 'hearing-complete':'Test tamamlandı. Sonuç bu cihazın dijital ses birimindedir. İsterseniz sayısal sonucu kaydedin.',
 'mental-entry':N['mental']['name']+'. Görüşmeyi başlatınca konuşabilir veya yazabilirsiniz. Bitir düğmesi görüşmeyi tamamlar.',
 'mental-complete':'Görüşme tamamlandı. Özeti inceleyebilir ve uzman seçeneklerine geçebilirsiniz.'
}
async def main():
 import sys
 only='skin-neutral' if '--skin-neutral-only' in sys.argv else 'skin-front' if '--skin-glasses-only' in sys.argv else None
 selected={only:TEXTS[only]} if only else TEXTS
 OUT.mkdir(parents=True,exist_ok=True);previous=json.loads((OUT/'manifest.json').read_text('utf8'));entries=previous['entries'] if only else {}
 voices=await edge_tts.list_voices()
 for name in ['tr-TR-AhmetNeural','tr-TR-EmelNeural']:
  if not any(v['ShortName']==name for v in voices):raise RuntimeError('EXACT_VOICE_UNAVAILABLE')
 # Sequential, no paid provider or personal text. Content-addressed artifacts cannot reuse a stale profile.
 for key,text in selected.items():
  voice='tr-TR-EmelNeural' if key.startswith('mental-') else 'tr-TR-AhmetNeural'
  contract=dict(text=text,voice=voice,rate='-10%',pitch='-10Hz',textVersion='guidance-20261009-v1')
  digest=hashlib.sha256(json.dumps(contract,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
  file=OUT/(digest+'.mp3')
  if not file.exists() or file.stat().st_size<1000:
   temporary=file.with_suffix('.partial.mp3')
   try:
    try:await edge_tts.Communicate(text,voice,rate='-10%',pitch='-10Hz').save(str(temporary))
    except Exception as error:raise RuntimeError('GUIDANCE_GENERATION_FAILED:'+type(error).__name__) from None
    if temporary.stat().st_size<1000:raise RuntimeError('EMPTY_GUIDANCE')
    temporary.replace(file)
   finally:
    if temporary.exists():temporary.unlink()
  if file.stat().st_size<1000:raise RuntimeError('EMPTY_GUIDANCE')
  entries[key]={**contract,'contractHash':digest,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'url':'/audio/guidance/'+file.name}
  print(key,flush=True)
 (OUT/'manifest.json').write_text(json.dumps(dict(version='guidance-20261009-v1',entries=entries,auditoryAcceptance='not-performed',provider='edge-tts'),ensure_ascii=False,indent=2),'utf8')
if __name__=='__main__':asyncio.run(main())
