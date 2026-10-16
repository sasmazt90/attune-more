/** Build-time opt-in affects only an isolated local preview; defaults stay unchanged. */
export const ACNE_V5_PREVIEW=process.env.NEXT_PUBLIC_ATTUNE_ACNE_V5==='1';
const port=process.env.NEXT_PUBLIC_ATTUNE_PREVIEW_API_PORT||'8305';
export const LOCAL_API_BASE=ACNE_V5_PREVIEW&&/^\d{1,5}$/.test(port)&&Number(port)>0&&Number(port)<65536?`http://127.0.0.1:${port}`:'http://localhost:8000';
