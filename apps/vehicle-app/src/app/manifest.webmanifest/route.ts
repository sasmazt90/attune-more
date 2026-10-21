import manifest from '../../i18n/webManifest';

export const dynamic='force-static';
/** Preserve the original default URL/body without Next's automatic metadata
 * link ownership; LanguageProvider owns the single selected-locale link. */
export function GET(){
 return Response.json(manifest(),{headers:{'Content-Type':'application/manifest+json'}});
}
