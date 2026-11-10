// Local static server for the prototype (loopback only). Serves the web prototype and, under /models/,
// the locally downloaded model and speech files. Range requests, cross-origin isolation headers, and a
// request log so a run can show that nothing left the machine during inference.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(process.argv[2] || '.');
const modelsDir = path.resolve(process.argv[3] || './models');
const port = Number(process.argv[4] || 8731);
const logFile = process.argv[5] || null;
const TYPES = {'.html':'text/html; charset=utf-8','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json',
  '.wasm':'application/wasm','.css':'text/css','.onnx':'application/octet-stream','.bin':'application/octet-stream',
  '.litertlm':'application/octet-stream','.wav':'audio/wav','.txt':'text/plain; charset=utf-8','.data':'application/octet-stream'};
const log = (line) => { if (logFile) fs.appendFileSync(logFile, `${new Date().toISOString()} ${line}\n`); };

http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  let rel = decodeURIComponent(url.pathname);
  const base = rel.startsWith('/models/') ? modelsDir : root;
  if (rel.startsWith('/models/')) rel = rel.slice('/models'.length);
  const file = path.join(base, path.normalize(rel).replace(/^([/\\])+/, ''));
  if (!file.startsWith(base)) { res.writeHead(403).end(); return; }
  let stat;
  try { stat = fs.statSync(file); if (stat.isDirectory()) throw new Error('dir'); } catch { log(`404 ${req.method} ${url.pathname}`); res.writeHead(404).end(); return; }
  const headers = {'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream', 'Accept-Ranges': 'bytes',
    'Cross-Origin-Opener-Policy': 'same-origin', 'Cross-Origin-Embedder-Policy': 'require-corp',
    'Cross-Origin-Resource-Policy': 'same-origin', 'Cache-Control': 'no-store'};
  const range = req.headers.range && /bytes=(\d*)-(\d*)/.exec(req.headers.range);
  if (range) {
    const start = range[1] ? Number(range[1]) : 0, end = range[2] ? Number(range[2]) : stat.size - 1;
    res.writeHead(206, {...headers, 'Content-Range': `bytes ${start}-${end}/${stat.size}`, 'Content-Length': end - start + 1});
    log(`206 ${req.method} ${url.pathname} ${start}-${end}`);
    if (req.method === 'HEAD') { res.end(); return; }
    fs.createReadStream(file, {start, end}).pipe(res);
  } else {
    res.writeHead(200, {...headers, 'Content-Length': stat.size});
    log(`200 ${req.method} ${url.pathname} ${stat.size}`);
    if (req.method === 'HEAD') { res.end(); return; }
    fs.createReadStream(file).pipe(res);
  }
}).listen(port, '127.0.0.1', () => console.log(`serving ${root} (+ /models -> ${modelsDir}) on http://127.0.0.1:${port}`));
