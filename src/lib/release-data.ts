import type {
  Artifact,
  BuildManifest,
  LatestPointer,
  LoadedRelease
} from '$lib/release-contracts';

function joinUrl(base: string, path: string): string {
  return `${base.replace(/\/$/, '')}/${path.replace(/^\//, '')}`;
}

async function sha256Hex(bytes: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(
    new Uint8Array(digest),
    (byte) => byte.toString(16).padStart(2, '0')
  ).join('');
}

export async function artifactShard(
  identifier: string,
  prefixLength: number
): Promise<string> {
  return (await sha256Hex(new TextEncoder().encode(identifier).buffer)).slice(0, prefixLength);
}

export async function loadRelease(dataBase: string): Promise<LoadedRelease> {
  const latestResponse = await fetch(joinUrl(dataBase, 'latest.json'), { cache: 'no-cache' });
  if (!latestResponse.ok) {
    throw new Error(`Could not load latest release (${latestResponse.status})`);
  }
  const latest = (await latestResponse.json()) as LatestPointer;
  if (!latest.schema_version.startsWith('1.')) {
    throw new Error(`Unsupported data schema ${latest.schema_version}`);
  }

  const manifestResponse = await fetch(joinUrl(dataBase, latest.manifest), {
    cache: 'force-cache'
  });
  if (!manifestResponse.ok) {
    throw new Error(`Could not load release manifest (${manifestResponse.status})`);
  }
  const manifestBytes = await manifestResponse.arrayBuffer();
  if ((await sha256Hex(manifestBytes)) !== latest.manifest_checksum_sha256) {
    throw new Error('Release manifest checksum did not match latest.json');
  }

  const manifest = JSON.parse(new TextDecoder().decode(manifestBytes)) as BuildManifest;
  if (manifest.build_id !== latest.build_id) {
    throw new Error('Release pointer and manifest build IDs differ');
  }
  const buildBase = joinUrl(dataBase, latest.manifest.replace(/\/manifest\.json$/, ''));
  return { latest, manifest, buildBase };
}

export function artifact(release: LoadedRelease, path: string): Artifact | undefined {
  return release.manifest.artifacts.find((item) => item.path === path);
}

export function artifactUrl(release: LoadedRelease, path: string): string {
  return joinUrl(release.buildBase, path);
}

export async function fetchVerifiedArtifact(
  release: LoadedRelease,
  path: string
): Promise<ArrayBuffer> {
  const declared = artifact(release, path);
  if (!declared) throw new Error(`Release manifest does not declare ${path}`);
  const response = await fetch(artifactUrl(release, path), { cache: 'force-cache' });
  if (!response.ok) throw new Error(`Could not load ${path} (${response.status})`);
  const bytes = await response.arrayBuffer();
  if (
    bytes.byteLength !== declared.bytes
    || (await sha256Hex(bytes)) !== declared.checksum_sha256
  ) {
    throw new Error(`Release artifact checksum did not match for ${path}`);
  }
  return bytes;
}

export async function loadJsonArtifact<T>(
  release: LoadedRelease,
  path: string
): Promise<T> {
  const bytes = await fetchVerifiedArtifact(release, path);
  return JSON.parse(new TextDecoder().decode(bytes)) as T;
}

/** Parses line-delimited JSON incrementally so large files never require one giant string. */
export async function loadNdjson<T>(url: string): Promise<T[]> {
  const response = await fetch(url, { cache: 'force-cache' });
  if (!response.ok) {
    throw new Error(`Could not load ${url.split('/').at(-1)} (${response.status})`);
  }
  if (!response.body) {
    return (await response.text())
      .split('\n')
      .filter(Boolean)
      .map((line) => JSON.parse(line) as T);
  }

  const records: T[] = [];
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let remainder = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    const lines = `${remainder}${value}`.split('\n');
    remainder = lines.pop() ?? '';
    for (const line of lines) {
      if (line.trim()) records.push(JSON.parse(line) as T);
    }
  }
  if (remainder.trim()) records.push(JSON.parse(remainder) as T);
  return records;
}
