// Public, read-only access exclusively to prepared Piyaso videos.
// All R2 footage, screen recordings, approvals and state stay inaccessible.
// Serving MP4 and MOV files does not transcode them.
const ALLOWED = /^\/piyaso\/(\d{4}-\d{2}-\d{2})\/(\d{2}_\d{4})\/([A-Za-z0-9][A-Za-z0-9 _().-]{0,159})\.(mp4|mov)$/i;

const notFound = () => new Response('Not Found', {status: 404});

export default {
  async fetch(request, env) {
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      return new Response('Method Not Allowed', {status: 405, headers: {Allow: 'GET, HEAD'}});
    }
    const url = new URL(request.url);
    let path;
    try { path = decodeURIComponent(url.pathname); }
    catch { return notFound(); }
    const match = ALLOWED.exec(path);
    if (!match || match[3].includes('..')) return notFound();
    // Safe to ignore ?utm_source=..., because it never affects the R2 key.
    const key = `published/piyaso/${match[1]}/${match[2]}/${match[3]}.${match[4]}`;
    const hasRange = request.headers.has('Range');
    const object = await env.MEDIA.get(key, hasRange ? {range: request.headers} : undefined);
    if (!object || !('body' in object)) return notFound();
    const headers = new Headers();
    headers.set('Content-Type', match[4].toLowerCase() === 'mov' ? 'video/quicktime' : 'video/mp4');
    headers.set('ETag', object.httpEtag);
    headers.set('Accept-Ranges', 'bytes');
    headers.set('Cache-Control', 'public, max-age=3600');
    let status = 200;
    if (hasRange && object.range && Number.isInteger(object.range.offset) && Number.isInteger(object.range.length)) {
      const {offset, length} = object.range;
      status = 206;
      headers.set('Content-Range', `bytes ${offset}-${offset + length - 1}/${object.size}`);
      headers.set('Content-Length', String(length));
    } else {
      headers.set('Content-Length', String(object.size));
    }
    return new Response(request.method === 'HEAD' ? null : object.body, {status, headers});
  }
};
