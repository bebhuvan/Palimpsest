import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import { resolve } from 'node:path';
import {
  assertNoBundledData,
  assertProductionDataBase,
  localDataPlugin
} from './scripts/local-data-server.mjs';

export default defineConfig(async ({ command }) => {
  if (command === 'build') {
    await assertNoBundledData();
    assertProductionDataBase(process.env.VITE_DATA_BASE);
  }
  const localDataRoot = process.env.HISTORY_DATA_ROOT
    ? resolve(process.env.HISTORY_DATA_ROOT)
    : undefined;
  return {
    plugins: [localDataPlugin(localDataRoot), sveltekit()]
  };
});
