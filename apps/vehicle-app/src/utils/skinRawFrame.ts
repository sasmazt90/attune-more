/** Raw camera frame for the skin analysis (WebCodecs).
 *
 * The canvas the app draws the video into is RGB that the browser converted from the camera's YUV frame, with a
 * matrix chosen from the frame's colour tag. A mis-tagged stream (seen: BT.601 camera data tagged BT.709 under the
 * software GPU) shifts skin colour enough to flip finding decisions. The server therefore receives the untouched YUV
 * planes of the same frame and converts them with the vehicle camera profile. Volatile: never stored in records.
 * Falls back silently (undefined) when the browser cannot expose the planes (no WebCodecs, GPU-texture frame, other
 * pixel format); the PNG path then stays as before and the server reports cameraColor.source='browser-rgb'. */
export type SkinRawFrame={
  format:'I420'|'NV12';codedWidth:number;codedHeight:number;
  visibleRect:{x:number;y:number;width:number;height:number};
  layout:{offset:number;stride:number}[];
  colorSpace:{matrix:string|null;fullRange:boolean|null;primaries:string|null;transfer:string|null};
  data:string;
};

type FrameLike={format:string|null;codedWidth:number;codedHeight:number;visibleRect:{x:number;y:number;width:number;height:number}|null;
  colorSpace:{matrix?:string|null;fullRange?:boolean|null;primaries?:string|null;transfer?:string|null};
  allocationSize():number;copyTo(dest:Uint8Array):Promise<{offset:number;stride:number}[]>;close():void};

/** The current frame of the video element, taken right after it was drawn to the canvas (same frame). */
export function grabVideoFrame(video:HTMLVideoElement):FrameLike|null{
  try{
    const Ctor=(globalThis as any).VideoFrame;
    if(typeof Ctor!=='function')return null;
    return new Ctor(video) as FrameLike;
  }catch{return null;}
}

async function base64Of(bytes:Uint8Array):Promise<string>{
  const url:string=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result));r.onerror=()=>reject(r.error);r.readAsDataURL(new Blob([bytes as BlobPart]));});
  return url.slice(url.indexOf(',')+1);
}

/** Copies the planes when the frame matches the canvas size; otherwise undefined (no guessing). */
export async function rawFrameOf(frame:FrameLike|null,width:number,height:number):Promise<SkinRawFrame|undefined>{
  if(!frame||(frame.format!=='I420'&&frame.format!=='NV12'))return undefined;
  const rect=frame.visibleRect||{x:0,y:0,width:frame.codedWidth,height:frame.codedHeight};
  if(rect.width!==width||rect.height!==height)return undefined;
  try{
    const buffer=new Uint8Array(frame.allocationSize());
    const layout=(await frame.copyTo(buffer)).map(p=>({offset:p.offset,stride:p.stride}));
    const cs=frame.colorSpace||{};
    return {format:frame.format,codedWidth:frame.codedWidth,codedHeight:frame.codedHeight,visibleRect:{x:rect.x,y:rect.y,width:rect.width,height:rect.height},layout,
      colorSpace:{matrix:cs.matrix??null,fullRange:cs.fullRange??null,primaries:cs.primaries??null,transfer:cs.transfer??null},data:await base64Of(buffer)};
  }catch{return undefined;}
}

/** Keeps exactly one open frame (closing the previous one frees the camera buffer). */
export class LatestVideoFrame{
  private frame:FrameLike|null=null;
  replace(video:HTMLVideoElement){this.close();this.frame=grabVideoFrame(video);}
  current(){return this.frame;}
  close(){try{this.frame?.close();}catch{/* already closed */}this.frame=null;}
}
