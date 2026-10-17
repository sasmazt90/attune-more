/** Optional isolated loopback port. Ordinary installations retain each caller's origin. */
export function localBackend(path:string,ordinaryOrigin='http://localhost:8000') {
 const port=process.env.NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT;
 const origin=port&&/^\d{1,5}$/.test(port)&&Number(port)>0&&Number(port)<65536?`http://127.0.0.1:${port}`:ordinaryOrigin;
 return origin+path;
}
