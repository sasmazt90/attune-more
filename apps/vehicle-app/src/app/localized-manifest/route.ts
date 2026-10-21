import manifest from '../../i18n/webManifest';
import {isLanguage,LOCALES,t} from '../../i18n/core';
import {PRODUCT_DESCRIPTION} from '../../utils/brand';

/** Same app identity/icons/start URL; only installation copy follows the locale. */
export function GET(request:Request){
 const language=new URL(request.url).searchParams.get('language')||'tr';
 if(!isLanguage(language))return Response.json({detail:'UNSUPPORTED_LANGUAGE'},{status:422});
 return Response.json({...manifest(),lang:language,description:t(PRODUCT_DESCRIPTION,language)},
  {headers:{'Content-Type':'application/manifest+json','Content-Language':LOCALES[language],'Cache-Control':'public, max-age=3600'}});
}
