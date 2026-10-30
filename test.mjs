import assert from 'node:assert/strict';
import worker from './src/index.js';

const data = new TextEncoder().encode('test-video');
const accessed = [];
const env = {MEDIA: {get: async (key, options) => {
  accessed.push(key);
  return {body: new ReadableStream({start(controller) {controller.enqueue(data); controller.close();}}),
    size: data.length, httpEtag: '"etag"',
    ...(options?.range ? {range: {offset: 0, length: data.length}} : {})};
}}};
const base = 'https://piyaso-tiktok-media.example.workers.dev';
const mp4 = base + '/piyaso/2026-11-01/01_1300/video.mp4';
const mov = base + '/piyaso/2026-11-01/01_1300/video.mp4.mov';
let response = await worker.fetch(new Request(mp4, {method: 'HEAD'}), env);
assert.equal(response.status, 200);
assert.equal(response.headers.get('Content-Type'), 'video/mp4');
assert.equal(await response.text(), '');
response = await worker.fetch(new Request(mp4), env);
assert.equal(response.status, 200);
assert.equal(await response.text(), 'test-video');
response = await worker.fetch(new Request(mp4, {headers: {Range: 'bytes=0-3'}}), env);
assert.equal(response.status, 206);
assert.equal(response.headers.get('Content-Range'), `bytes 0-9/${data.length}`);
response = await worker.fetch(new Request(mov + '?utm_source=test'), env);
assert.equal(response.status, 200);
assert.equal(response.headers.get('Content-Type'), 'video/quicktime');
assert.equal(await response.text(), 'test-video');
response = await worker.fetch(new Request(base + '/piyaso/2026-11-01/01_1300/ScreenRecording_2026%2014-01-49_1.mp4'), env);
assert.equal(response.status, 200);
assert.equal(accessed[3], 'published/piyaso/2026-11-01/01_1300/video.mp4.mov');
assert.equal(accessed[4], 'published/piyaso/2026-11-01/01_1300/ScreenRecording_2026 14-01-49_1.mp4');
const privatePaths = [
  '/backgrounds/clip.mp4',
  '/app_recordings/app_recording.mp4',
  '/state/piyaso/2026-11-01/01_1300/confirmed.json',
  '/published/piyaso/2026-11-01/01_1300/video.mp4',
  '/piyaso/2026-11-01/01_1300/%2e%2e%2fsecret.mp4',
  '/piyaso/2026-11-01/01_1300/bad.mp4.exe',
  '/piyaso/2026-11-01/01_1300/image.jpg',
];
for (const path of privatePaths) {
  assert.equal((await worker.fetch(new Request(base + path), env)).status, 404, path);
}
assert.equal((await worker.fetch(new Request(mp4, {method: 'PUT', body: 'evil'}), env)).status, 405);
assert.equal(accessed.length, 5);
console.log('OK: MP4, MOV, .mp4.mov, filenames with spaces, Range/HEAD; private prefixes blocked.');
