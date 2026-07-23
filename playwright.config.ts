import { defineConfig } from '@playwright/test';
import { existsSync } from 'node:fs';

const systemChromium = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ??
  (existsSync('/usr/bin/google-chrome') ? '/usr/bin/google-chrome' : undefined);

export default defineConfig({
  testDir: './tests/browser',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: 'http://127.0.0.1:4177',
    browserName: 'chromium',
    headless: true,
    launchOptions: systemChromium ? { executablePath: systemChromium } : undefined,
    trace: 'retain-on-failure'
  },
  webServer: {
    command:
      'HISTORY_DATA_ROOT=tests/browser/fixtures/data npm run dev -- --host 127.0.0.1 --port 4177',
    url: 'http://127.0.0.1:4177',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000
  }
});
