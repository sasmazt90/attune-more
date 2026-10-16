// Serialize static generation on the shared low-memory Windows workstation.
// The experimental photo preview is local-only, including its worker context.
const preview=process.env.NEXT_PUBLIC_ATTUNE_ACNE_V5==='1';
export default {experimental:{cpus:1},async headers(){return preview?[{source:'/:path*',headers:[{key:'Content-Security-Policy',value:"connect-src 'self' http://127.0.0.1:8305; object-src 'none'; base-uri 'self'; form-action 'none'"}]}]:[];}};
