// Serialize static generation on the shared low-memory Windows workstation.
// The experimental photo preview is local-only, including its worker context.
const preview=process.env.NEXT_PUBLIC_ATTUNE_ACNE_V5==='1';
const configuredPort=process.env.NEXT_PUBLIC_ATTUNE_PREVIEW_API_PORT||'8305';
const port=/^\d{1,5}$/.test(configuredPort)&&Number(configuredPort)>0&&Number(configuredPort)<65536?configuredPort:'8305';
export default {experimental:{cpus:1},async headers(){return preview?[{source:'/:path*',headers:[{key:'Content-Security-Policy',value:`connect-src 'self' http://127.0.0.1:${port}; object-src 'none'; base-uri 'self'; form-action 'none'`}]}]:[];}};
