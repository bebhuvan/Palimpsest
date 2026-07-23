import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import { extname, resolve, sep } from 'node:path';

/** @type {Record<string, string>} */
const contentTypes = {
  '.gz': 'application/gzip',
  '.json': 'application/json',
  '.ndjson': 'application/x-ndjson',
  '.parquet': 'application/vnd.apache.parquet',
  '.pmtiles': 'application/vnd.pmtiles',
  '.png': 'image/png'
};

export async function assertNoBundledData(
  staticDataRoot = resolve(import.meta.dirname, '..', 'static', 'data')
) {
  try {
    await stat(staticDataRoot);
  } catch (error) {
    if (isNodeError(error) && error.code === 'ENOENT') return;
    throw error;
  }
  throw new Error(
    'static/data exists. Remove this generated directory: production data must be served from R2, not bundled with SvelteKit.'
  );
}

/** @param {string | undefined} value */
export function assertProductionDataBase(value) {
  if (!value) {
    throw new Error(
      'VITE_DATA_BASE is required for production builds and must name the public R2 /v1 URL.'
    );
  }
  let url;
  try {
    url = new URL(value);
  } catch {
    throw new Error('VITE_DATA_BASE must be an absolute URL.');
  }
  if (
    url.protocol !== 'https:' ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    !url.pathname.replace(/\/+$/, '').endsWith('/v1')
  ) {
    throw new Error(
      'VITE_DATA_BASE must be an HTTPS R2 custom-domain URL ending in /v1, without credentials, query, or fragment.'
    );
  }
}

/** @returns {import('vite').Plugin} */
export function localDataPlugin(
  dataRoot = resolve(import.meta.dirname, '..', 'dist', 'data')
) {
  return {
    name: 'history-joice-local-data',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        void serveLocalData(request, response, dataRoot, next);
      });
    }
  };
}

/**
 * @param {import('node:http').IncomingMessage} request
 * @param {import('node:http').ServerResponse} response
 * @param {string} dataRoot
 * @param {(error?: unknown) => void} next
 */
export async function serveLocalData(
  request,
  response,
  dataRoot,
  next = () => {}
) {
  const pathname = new URL(request.url ?? '/', 'http://localhost').pathname;
  if (pathname !== '/data' && !pathname.startsWith('/data/')) {
    next();
    return;
  }
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    response.statusCode = 405;
    response.setHeader('Allow', 'GET, HEAD');
    response.end();
    return;
  }

  let relative;
  try {
    relative = decodeURIComponent(pathname.slice('/data/'.length));
  } catch {
    response.statusCode = 400;
    response.end('Malformed data path');
    return;
  }
  const root = resolve(dataRoot);
  const filePath = resolve(root, relative);
  if (!relative || !filePath.startsWith(`${root}${sep}`)) {
    response.statusCode = 404;
    response.end('Not found');
    return;
  }

  let details;
  try {
    details = await stat(filePath);
  } catch (error) {
    if (isNodeError(error) && error.code === 'ENOENT') {
      response.statusCode = 404;
      response.end('Not found');
      return;
    }
    next(error);
    return;
  }
  if (!details.isFile()) {
    response.statusCode = 404;
    response.end('Not found');
    return;
  }

  const type = contentTypes[extname(filePath)] ?? 'application/octet-stream';
  response.setHeader('Content-Type', type);
  response.setHeader('Accept-Ranges', 'bytes');
  response.setHeader(
    'Cache-Control',
    relative === 'latest.json'
      ? 'public, max-age=0, must-revalidate'
      : 'public, max-age=31536000, immutable'
  );

  const range = parseRange(request.headers.range, details.size);
  if (range === null) {
    response.statusCode = 416;
    response.setHeader('Content-Range', `bytes */${details.size}`);
    response.end();
    return;
  }
  if (details.size === 0) {
    response.statusCode = 200;
    response.setHeader('Content-Length', '0');
    response.end();
    return;
  }
  const [start, end] = range ?? [0, details.size - 1];
  response.statusCode = range ? 206 : 200;
  response.setHeader('Content-Length', String(end - start + 1));
  if (range) response.setHeader('Content-Range', `bytes ${start}-${end}/${details.size}`);
  if (request.method === 'HEAD') {
    response.end();
    return;
  }
  createReadStream(filePath, { start, end }).pipe(response);
}

/**
 * @param {string | undefined} value
 * @param {number} size
 * @returns {[number, number] | undefined | null}
 */
function parseRange(value, size) {
  if (!value) return undefined;
  const match = /^bytes=(\d*)-(\d*)$/.exec(value);
  if (!match || (!match[1] && !match[2])) return null;
  let start;
  let end;
  if (!match[1]) {
    const suffix = Number(match[2]);
    if (!Number.isSafeInteger(suffix) || suffix <= 0) return null;
    start = Math.max(0, size - suffix);
    end = size - 1;
  } else {
    start = Number(match[1]);
    end = match[2] ? Number(match[2]) : size - 1;
  }
  if (
    !Number.isSafeInteger(start) ||
    !Number.isSafeInteger(end) ||
    start < 0 ||
    start >= size ||
    end < start
  ) return null;
  return [start, Math.min(end, size - 1)];
}

/** @param {unknown} error */
function isNodeError(error) {
  return error instanceof Error && 'code' in error;
}
