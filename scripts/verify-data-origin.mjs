import { createHash } from 'node:crypto';

const [baseArgument, pagesOrigin] = process.argv.slice(2);
if (!baseArgument) {
  throw new Error(
    'Usage: npm run data:verify-origin -- https://data.example.org [https://history-joice.pages.dev]'
  );
}
const dataBase = baseArgument.replace(/\/+$/, '');
const requestHeaders = pagesOrigin ? { Origin: pagesOrigin } : {};

const latestResponse = await fetch(`${dataBase}/v1/latest.json`, {
  cache: 'no-store',
  headers: requestHeaders
});
requireStatus(latestResponse, 200, 'latest pointer');
requireCache(latestResponse, 'must-revalidate', 'latest pointer');
if (pagesOrigin) requireCors(latestResponse, pagesOrigin);
const latest = await latestResponse.json();

const manifestUrl = `${dataBase}/v1/${latest.manifest}`;
const manifestResponse = await fetch(manifestUrl, { headers: requestHeaders });
requireStatus(manifestResponse, 200, 'manifest');
requireCache(manifestResponse, 'immutable', 'manifest');
if (pagesOrigin) requireCors(manifestResponse, pagesOrigin);
const manifestBytes = Buffer.from(await manifestResponse.arrayBuffer());
const manifestChecksum = createHash('sha256').update(manifestBytes).digest('hex');
if (manifestChecksum !== latest.manifest_checksum_sha256) {
  throw new Error('Published manifest checksum does not match latest.json');
}
const manifest = JSON.parse(manifestBytes.toString('utf8'));
if (manifest.build_id !== latest.build_id) {
  throw new Error('Published pointer and manifest build IDs differ');
}

const tile = manifest.artifacts.find((artifact) =>
  artifact.path.endsWith('.pmtiles')
);
if (!tile) throw new Error('Published release has no PMTiles artifact');
const buildBase = manifestUrl.replace(/\/manifest\.json$/, '');
const rangeResponse = await fetch(`${buildBase}/${tile.path}`, {
  headers: { ...requestHeaders, Range: 'bytes=0-7' }
});
requireStatus(rangeResponse, 206, 'PMTiles range request');
requireCache(rangeResponse, 'immutable', 'PMTiles artifact');
if (rangeResponse.headers.get('accept-ranges') !== 'bytes') {
  throw new Error('PMTiles response does not advertise byte ranges');
}
if (!rangeResponse.headers.get('content-range')?.startsWith('bytes 0-7/')) {
  throw new Error('PMTiles response has an invalid Content-Range');
}
if (pagesOrigin) requireCors(rangeResponse, pagesOrigin);
const header = Buffer.from(await rangeResponse.arrayBuffer());
if (header.subarray(0, 7).toString('ascii') !== 'PMTiles' || header[7] !== 3) {
  throw new Error('PMTiles range response is not a PMTiles v3 header');
}

if (manifest.search_index_path) {
  const searchResponse = await fetch(
    `${buildBase}/${manifest.search_index_path}`,
    { headers: requestHeaders }
  );
  requireStatus(searchResponse, 200, 'search index');
  requireCache(searchResponse, 'immutable', 'search index');
  if (pagesOrigin) requireCors(searchResponse, pagesOrigin);
}

console.log(
  `Verified R2 release ${manifest.build_id}: checksummed manifest, immutable caching, CORS${pagesOrigin ? '' : ' not requested'}, and PMTiles byte ranges.`
);

function requireStatus(response, expected, label) {
  if (response.status !== expected) {
    throw new Error(`${label} returned ${response.status}; expected ${expected}`);
  }
}

function requireCache(response, directive, label) {
  if (!response.headers.get('cache-control')?.includes(directive)) {
    throw new Error(`${label} is missing Cache-Control: ${directive}`);
  }
}

function requireCors(response, expectedOrigin) {
  const actual = response.headers.get('access-control-allow-origin');
  if (actual !== expectedOrigin) {
    throw new Error(
      `CORS returned ${actual ?? 'no origin'}; expected ${expectedOrigin}`
    );
  }
}
