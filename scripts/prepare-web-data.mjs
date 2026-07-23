import { readFile, stat } from 'node:fs/promises';
import { dirname, resolve, sep } from 'node:path';

const projectRoot = resolve(import.meta.dirname, '..');

export async function validateLocalRelease(
  sourceRoot = resolve(projectRoot, 'dist', 'data')
) {
  const latestPath = resolve(sourceRoot, 'latest.json');
  const latest = JSON.parse(await readFile(latestPath, 'utf8'));
  const manifestRelative = latest.manifest;
  if (!/^builds\/[a-z0-9_-]+\/manifest\.json$/.test(manifestRelative)) {
    throw new Error(`Refusing unexpected manifest path: ${manifestRelative}`);
  }
  const manifestPath = resolve(sourceRoot, manifestRelative);
  const allowedPrefix = `${resolve(sourceRoot, 'builds')}${sep}`;
  if (!manifestPath.startsWith(allowedPrefix)) {
    throw new Error('Resolved manifest path is outside dist/data/builds');
  }
  await stat(manifestPath);
  return latest;
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(import.meta.filename)) {
  const latest = await validateLocalRelease();
  console.log(
    `Local release ${latest.build_id} is ready; Vite serves dist/data at /data without copying it into the application.`
  );
}
