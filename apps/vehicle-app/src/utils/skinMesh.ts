/** Presentation graph only. Numerical ROIs are deliberately independent. */
export type MeshPoint={x:number;y:number};
export type SkinMesh={points:MeshPoint[];edges:[number,number][];major:number[];boundary:number[][];excluded:string[];bagCells?:number[][]};
type Graph={indices:number[];edges:[number,number][];major:number[];boundary:number[][];excluded:string[];bagCells?:number[][]};
// Every edge is explicit and anatomical; indices refer to actual MediaPipe
// landmarks in the accepted unmirrored frame, never screen-side mirroring.
// Adjacent anatomical rows; connections never skip a row or form a fan.
function rowsGraph(rows:number[][],major:number[],excluded:string[]):Graph {
 const indices=rows.flat(),edges:[number,number][]=[];let offset=0;
 for(let r=0;r<rows.length;r++){for(let c=1;c<rows[r].length;c++)edges.push([offset+c-1,offset+c]);if(r){const prev=offset-rows[r-1].length;for(let c=0;c<rows[r].length;c++){const k=Math.round(c*(rows[r-1].length-1)/Math.max(1,rows[r].length-1));edges.push([prev+k,offset+c]);if(c<rows[r].length-1 && c%2===r%2 && k<rows[r-1].length-1)edges.push([prev+k+1,offset+c]);}}offset+=rows[r].length;}
 return {indices,edges,major:major.map(i=>indices.indexOf(i)).filter(i=>i>=0),boundary:[],excluded};
}
function eyeBands():Graph {
 const rightOuter=[35,46,65,55,193,128,120,111],rightInner=[130,30,27,56,243,26,23,25];
 const leftOuter=[265,276,295,285,417,357,349,340],leftInner=[359,260,257,286,463,256,253,255];
 const indices=[...rightOuter,...rightInner,...leftOuter,...leftInner],edges:[number,number][]=[];
 for(const base of [0,16])for(let i=0;i<8;i++){const j=(i+1)%8;edges.push([base+i,base+j],[base+8+i,base+8+j],[base+i,base+8+i]);if(i%2===0)edges.push([base+i,base+8+j]);}
 // The approved sparse visible diagonals do not define holes in a closed
 // anatomical cell. Keep its four boundaries for bag support triangulation.
 const bagCells:number[][]=[];
 for(const base of [0,16])for(let i=0;i<8;i++){const j=(i+1)%8;bagCells.push([base+i,base+j,base+8+j,base+8+i]);}
 return {indices,edges,major:[0,4,16,20],boundary:[],excluded:['iris','eye-opening','nose-bridge'],bagCells};
}
export const SKIN_GRAPHS:Record<string,Graph>={
 forehead:rowsGraph([[103,67,109,10,338,297,332],[54,104,108,151,337,333,284],[21,63,66,9,296,293,251]],[10,151,9],['eyes','nose','hair']),
 rightCheek:rowsGraph([[111,117,119,100],[123,50,36,142],[147,187,205,203],[132,207,216,206],[58,215,192,212],[172,138,214,202]],[117,50,205,192],['right-eye','nose','lips','ear','occluded-cheek']),
 leftCheek:rowsGraph([[340,346,348,329],[352,280,266,371],[376,411,425,423],[361,427,436,426],[288,435,416,432],[397,367,434,422]],[346,280,425,416],['left-eye','nose','lips','ear','occluded-cheek']),
 nose:rowsGraph([[67,109,10,338,297],[104,108,151,337,333],[63,66,9,296,293],[193,168,417],[122,6,351],[196,197,419],[3,195,248],[126,51,5,281,355],[129,49,4,279,358],[209,48,1,278,429],[102,98,2,327,331]],[10,151,9,168,4,98,327],['eyes','nostril-interior','upper-lip','wide-cheek']),
 periorbital:eyeBands(),
 chin:rowsGraph([[202,106,83,18,313,406,422],[210,194,201,200,421,418,430],[169,170,208,199,428,395,394],[149,176,148,152,377,400,378]],[18,200,152],['lips','mouth','neck'])
};
export function buildSkinMesh(id:string,landmarks:MeshPoint[],width:number,height:number):SkinMesh {
 const graph=SKIN_GRAPHS[id];
 if(!graph||landmarks.length<468)throw Error('MISSING_ANATOMICAL_LANDMARKS');
 const points=graph.indices.map(i=>({x:landmarks[i].x*width,y:landmarks[i].y*height}));
 const edges:[number,number][]=[...graph.edges];
 for(const path of graph.boundary)for(let i=1;i<path.length;i++)edges.push([path[i-1],path[i]]);
 return {points,edges,major:graph.major,boundary:graph.boundary,excluded:graph.excluded,...(graph.bagCells?{bagCells:graph.bagCells}:{})};
}

export const MESH_HOLES={rightEye:[33,160,158,133,153,145,163],leftEye:[263,387,385,362,380,374,390],lips:[61,40,37,0,267,270,291,321,314,17,84,91],rightNostril:[48,1,19,97,98,64],leftNostril:[278,1,19,326,327,294]};
function inside(p:MeshPoint,polygon:MeshPoint[]) {
 let hit=false;for(let i=0,j=polygon.length-1;i<polygon.length;j=i++) {const a=polygon[i],b=polygon[j];if((a.y>p.y)!==(b.y>p.y)&&p.x<(b.x-a.x)*(p.y-a.y)/(b.y-a.y)+a.x)hit=!hit;}return hit;
}
/** Omit whole unsafe edges, never chop a regional graph into sampling boxes.
 * Current semantic head support also prevents floating lines on occluded skin.
 */
export function supportedSkinMesh(mesh:SkinMesh,landmarks:MeshPoint[],width:number,height:number,alpha?:Uint8Array):SkinMesh {
 const holes=Object.values(MESH_HOLES).map(indices=>indices.map(i=>({x:landmarks[i].x*width,y:landmarks[i].y*height})));
 const supported=(p:MeshPoint)=>p.x>=0&&p.x<width&&p.y>=0&&p.y<height&&(!alpha || alpha[Math.floor(p.y)*width+Math.floor(p.x)]>0);
 const edges=mesh.edges.filter(([a,b])=>{for(let step=1;step<40;step++){const t=step/40,p={x:mesh.points[a].x*(1-t)+mesh.points[b].x*t,y:mesh.points[a].y*(1-t)+mesh.points[b].y*t};if(!supported(p)||holes.some(h=>inside(p,h)))return false;}return supported(mesh.points[a])&&supported(mesh.points[b]);});
 // A turned or noisy projection must not draw crossing cheek chords. Keep
 // shorter supported anatomical connections when two non-node edges cross.
 {
   const cross=(a:MeshPoint,b:MeshPoint,c:MeshPoint)=>(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
   const accepted:[number,number][]=[];
   edges.sort(([a,b],[c,d])=>Math.hypot(mesh.points[a].x-mesh.points[b].x,mesh.points[a].y-mesh.points[b].y)-Math.hypot(mesh.points[c].x-mesh.points[d].x,mesh.points[c].y-mesh.points[d].y));
   for(const edge of edges) {
     const [a,b]=edge;
     if(accepted.some(([c,d])=>a!==c&&a!==d&&b!==c&&b!==d&&cross(mesh.points[a],mesh.points[b],mesh.points[c])*cross(mesh.points[a],mesh.points[b],mesh.points[d])<0&&cross(mesh.points[c],mesh.points[d],mesh.points[a])*cross(mesh.points[c],mesh.points[d],mesh.points[b])<0))continue;
     accepted.push(edge);
   }
   edges.splice(0,edges.length,...accepted);
 }
 const used=[...new Set(edges.flat())],mapping=new Map(used.map((v,i)=>[v,i]));
 const boundaryEdges=new Set(edges.map(([a,b])=>[Math.min(a,b),Math.max(a,b)].join(':')));
 const bagCells=mesh.bagCells?.filter(cell=>cell.every((a,i)=>boundaryEdges.has([Math.min(a,cell[(i+1)%4]),Math.max(a,cell[(i+1)%4])].join(':')))).map(cell=>cell.map(i=>mapping.get(i)!));
 return {...mesh,points:used.map(i=>mesh.points[i]),edges:edges.map(([a,b])=>[mapping.get(a)!,mapping.get(b)!]),major:mesh.major.filter(i=>mapping.has(i)).map(i=>mapping.get(i)!),boundary:[],...(bagCells?{bagCells}:{})};
}

/** Bag-only fill cells; visible mesh edges and other criterion ROIs stay exact. */
export function bagCellTriangles(mesh:SkinMesh):number[][] {
 const edges=new Set(mesh.edges.map(([a,b])=>[Math.min(a,b),Math.max(a,b)].join(':')));
 return (mesh.bagCells||[]).flatMap(cell=>{
  if(cell.length!==4||new Set(cell).size!==4||cell.some((a,i)=>!mesh.points[a]||!edges.has([Math.min(a,cell[(i+1)%4]),Math.max(a,cell[(i+1)%4])].join(':'))))return [];
  const cross=cell.map((a,i)=>{const p=mesh.points[a],q=mesh.points[cell[(i+1)%4]],r=mesh.points[cell[(i+2)%4]];return (q.x-p.x)*(r.y-q.y)-(q.y-p.y)*(r.x-q.x);});
  if(!cross.every(v=>v>0)&&!cross.every(v=>v<0))return [];
  const [a,b,c,d]=cell;return [[a,b,c],[a,c,d]];
 });
}
