import {localBackend} from './localBackend';
/** Local Acne V5 ONNX is active by default in the local product path unless explicitly disabled ('0'). */
export const ACNE_V5_PREVIEW=process.env.NEXT_PUBLIC_ATTUNE_ACNE_V5!=='0';
const port=process.env.NEXT_PUBLIC_ATTUNE_PREVIEW_API_PORT;
export const LOCAL_API_BASE=port&&/^\d{1,5}$/.test(port)&&Number(port)>0&&Number(port)<65536?`http://127.0.0.1:${port}`:localBackend('');
