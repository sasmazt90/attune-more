/** Optional isolated loopback port; ordinary callers keep their existing origin. */
export function localBackend(path:string,ordinaryOrigin='http://localhost:8000') {
 const port=process.env.NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT;
 return (port&&/^\d{1,5}$/.test(port)&&Number(port)>0&&Number(port)<65536?`http://127.0.0.1:${port}`:ordinaryOrigin)+path;
}
