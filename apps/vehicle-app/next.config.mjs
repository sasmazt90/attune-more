// Serialize static generation on the shared low-memory Windows workstation.
// The experimental photo preview is local-only, including its worker context.
const preview=process.env.NEXT_PUBLIC_ATTUNE_ACNE_V5==='1';
const cloud=process.env.NEXT_PUBLIC_ATTUNE_SAME_ORIGIN_API==='1';
if(cloud&&(process.env.NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT||process.env.NEXT_PUBLIC_ATTUNE_PREVIEW_API_PORT)) {
  throw new Error('Cloud same-origin routing cannot be combined with loopback API overrides');
}
function loopbackOrigin(port, fallback) {
  return /^\d{1,5}$/.test(port) && Number(port) > 0 && Number(port) < 65536
    ? `http://127.0.0.1:${port}`
    : fallback;
}

// Keep the policy in sync with localBackend and previewLocalApi. The AAOS
// WebView compares the configured hostname exactly, including on loopback.
const apiOrigin = loopbackOrigin(process.env.NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT, 'http://localhost:8000');
const previewOrigin = loopbackOrigin(process.env.NEXT_PUBLIC_ATTUNE_PREVIEW_API_PORT, apiOrigin);
const connections = [...new Set([apiOrigin, previewOrigin])].join(' ');

export default {
  experimental: {cpus: 1},
  async headers() {
    if(cloud)return [{source:'/:path*',headers:[
      {key:'Content-Security-Policy',value:"connect-src 'self' blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"},
      {key:'Referrer-Policy',value:'no-referrer'},
      {key:'X-Content-Type-Options',value:'nosniff'},
    ]}];
    return preview ? [{
      source: '/:path*',
      headers: [{
        key: 'Content-Security-Policy',
        value: `connect-src 'self' ${connections}; object-src 'none'; base-uri 'self'; form-action 'none'`,
      }],
    }] : [];
  },
};
