import limits from '../../../../shared/dentalUploadLimits.json';
export const DENTAL_UPLOAD_LIMITS=limits;
export async function validateDentalFile(file:File){
 if(!file.size||file.size>limits.maxFileBytes)throw Error('Fotoğraf dosyası 20 MB sınırını aşmamalı.');
 const b=new Uint8Array(await file.slice(0,16).arrayBuffer());
 const jpeg=b[0]===255&&b[1]===216&&b[2]===255,png=[137,80,78,71,13,10,26,10].every((v,i)=>b[i]===v),webp=String.fromCharCode(...b.slice(0,4))==='RIFF'&&String.fromCharCode(...b.slice(8,12))==='WEBP';
 if(!jpeg&&!png&&!webp)throw Error('JPEG, PNG veya WebP fotoğraf seçin.');
 // Pixel/header limits and the actual decoder are authoritative on the local server.
 return new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=()=>reject(Error('Fotoğraf okunamadı.'));reader.readAsDataURL(file);});
}
export const UPLOAD_REASONS:Record<string,string>={FILE_LIMIT:'Fotoğraf dosyası 20 MB sınırını aşmamalı.',PIXEL_LIMIT:'Fotoğraf en fazla 24 megapiksel ve 8192 piksel kenarlı olmalı.',UNSUPPORTED_FORMAT:'JPEG, PNG veya WebP fotoğraf seçin.',DECODE_FAILED:'Fotoğraf açılamadı. Açılabilen başka bir fotoğraf seçin.',TRANSPARENT_PHOTO:'Saydam görsel yerine gerçek, opak diş fotoğrafı seçin.',TEETH_NOT_VISIBLE_OR_NON_COLOR_IMAGE:'Dişlerin ve çevresindeki diş etinin göründüğü renkli ağız içi fotoğrafı seçin.',INSUFFICIENT_TOOTH_DETAIL:'Diş ayrıntısı yetersiz. Daha ayrıntılı ağız içi fotoğrafı seçin.',TEETH_NOT_VISIBLE:'Dudak, dil veya cisim dişleri örtüyor. Dişlerin göründüğü fotoğrafı seçin.',BLURRY:'Fotoğraf net değil. Net bir diş fotoğrafı seçin.',LIGHT_INVALID:'Dişlerin eşit aydınlandığı fotoğrafı seçin.',SALIVA_OR_GLARE:'Parlama diş yüzeyini örtüyor. Yansıması daha az fotoğraf seçin.',TONGUE_OCCLUSION:'Dil dişleri örtüyor. Dişlerin göründüğü fotoğrafı seçin.',NON_COLOR_INTRAORAL_PHOTO:'Röntgen yerine renkli ağız içi fotoğrafı seçin.'};
