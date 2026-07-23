import assert from 'node:assert/strict';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { createServer, request as httpRequest } from 'node:http';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { after, before, test } from 'node:test';
import {
  assertNoBundledData,
  assertProductionDataBase,
  serveLocalData
} from '../../scripts/local-data-server.mjs';

let temporaryRoot;
let origin;
let server;

before(async () => {
  temporaryRoot = await mkdtemp(join(tmpdir(), 'history-joice-local-data-'));
  await mkdir(join(temporaryRoot, 'builds', 'test', 'tiles'), { recursive: true });
  await writeFile(join(temporaryRoot, 'latest.json'), '{"build_id":"test"}\n');
  await writeFile(
    join(temporaryRoot, 'builds', 'test', 'tiles', 'ancient.pmtiles'),
    Buffer.from('PMTiles\u0003payload')
  );
  server = createServer((request, response) => {
    void serveLocalData(request, response, temporaryRoot, () => {
      response.statusCode = 404;
      response.end('Not found');
    });
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const address = server.address();
  origin = `http://127.0.0.1:${address.port}`;
});

after(async () => {
  await new Promise((resolve, reject) =>
    server.close((error) => (error ? reject(error) : resolve()))
  );
  await rm(temporaryRoot, { recursive: true, force: true });
});

test('serves immutable local artifacts with byte ranges', async () => {
  const response = await fetch(
    `${origin}/data/builds/test/tiles/ancient.pmtiles`,
    { headers: { Range: 'bytes=0-7' } }
  );
  assert.equal(response.status, 206);
  assert.equal(response.headers.get('accept-ranges'), 'bytes');
  assert.equal(response.headers.get('content-range'), 'bytes 0-7/15');
  assert.match(response.headers.get('cache-control'), /immutable/);
  assert.equal(Buffer.from(await response.arrayBuffer()).toString(), 'PMTiles\u0003');
});

test('keeps the local latest pointer revalidating', async () => {
  const response = await fetch(`${origin}/data/latest.json`);
  assert.equal(response.status, 200);
  assert.match(response.headers.get('cache-control'), /must-revalidate/);
  assert.doesNotMatch(response.headers.get('cache-control'), /immutable/);
});

test('rejects invalid ranges and paths outside the data root', async () => {
  const rangeResponse = await fetch(
    `${origin}/data/builds/test/tiles/ancient.pmtiles`,
    { headers: { Range: 'bytes=50-60' } }
  );
  assert.equal(rangeResponse.status, 416);

  const traversalResponse = await new Promise((resolve, reject) => {
    const pending = httpRequest(
      origin,
      { path: '/data/%2e%2e/latest.json' },
      resolve
    );
    pending.on('error', reject);
    pending.end();
  });
  assert.equal(traversalResponse.statusCode, 404);
  traversalResponse.resume();
});

test('production guard rejects a bundled static data directory', async () => {
  const missing = join(temporaryRoot, 'not-created');
  await assert.doesNotReject(assertNoBundledData(missing));
  const present = join(temporaryRoot, 'bundled-data');
  await mkdir(present);
  await assert.rejects(assertNoBundledData(present), /must be served from R2/);
});

test('production guard requires an immutable R2 namespace URL', () => {
  assert.doesNotThrow(() =>
    assertProductionDataBase('https://data.example.org/v1')
  );
  assert.throws(() => assertProductionDataBase(), /is required/);
  assert.throws(
    () => assertProductionDataBase('https://data.example.org'),
    /ending in \/v1/
  );
  assert.throws(
    () => assertProductionDataBase('http://data.example.org/v1'),
    /HTTPS/
  );
});
