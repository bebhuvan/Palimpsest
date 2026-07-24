import { expect, test, type Page } from '@playwright/test';

async function disableLiveContext(page: Page): Promise<void> {
  await page.route(
    /(?:openhistoricalmap|openstreetmap|naturalearthdata)\./,
    (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/x-protobuf',
        body: ''
      })
  );
}

async function openPilot(page: Page): Promise<void> {
  const searchIndex = page.waitForResponse(
    (response) =>
      response.url().endsWith('/search/index.json') && response.ok()
  );
  await page.goto('/?year=100');
  await searchIndex;
  await expect(page.getByText('Opening release data')).toBeHidden();
}

async function selectSearchResult(page: Page, name: string): Promise<void> {
  const search = page.getByRole('combobox', {
    name: 'Search historical places and alternate names'
  });
  await search.fill(name);
  await page.getByRole('option', { name: new RegExp(name) }).click();
}

test.beforeEach(async ({ page }) => {
  await disableLiveContext(page);
});

test('selecting a reviewed place on the map opens its release record', async ({
  page
}) => {
  const invalidBoundsWarnings: string[] = [];
  page.on('console', (message) => {
    if (message.text().includes('Bounds of PMTiles archive')) {
      invalidBoundsWarnings.push(message.text());
    }
  });
  await openPilot(page);
  const map = page.getByLabel('Interactive historical world map for 100 CE');
  const canvas = map.locator('canvas');
  const bounds = await canvas.boundingBox();
  expect(bounds).not.toBeNull();
  await expect(async () => {
    await canvas.click({
      position: { x: bounds!.width / 2, y: bounds!.height / 2 }
    });
    await expect(
      page.getByRole('heading', { name: 'Enriched Pilot Place' })
    ).toBeVisible();
  }).toPass({ timeout: 20_000 });

  await expect(page).toHaveURL(/feature=browser-pilot%3Aenriched-place/);
  expect(invalidBoundsWarnings).toEqual([]);
});

test('a rights-approved historical map image renders from the immutable release', async ({
  page
}) => {
  await openPilot(page);
  const imageResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith('/historical-maps/browser-fixture-map.png') &&
      response.ok()
  );
  const toggle = page.getByRole('button', { name: /image/ });
  await toggle.focus();
  await page.keyboard.press('Enter');
  await imageResponse;

  await expect(toggle).toHaveAttribute('aria-pressed', 'true');
  await expect(
    page.getByLabel('Interactive historical world map for 100 CE')
  ).toHaveAttribute('data-historical-map-overlay', 'map:0123456789abcdef');
  const details = page.getByLabel('Historical map image details');
  await expect(details.getByText('Browser fixture map sheet')).toBeVisible();
  await expect(details.getByText('circa 1750')).toBeVisible();
  await expect(details.getByText('PDM-1.0')).toBeVisible();
  await expect(details.getByText(/Deterministic test control points/)).toBeVisible();
  await expect(
    details.getByText(/does not treat it as geographically or politically authoritative/)
  ).toBeVisible();
  await expect(
    page.getByText(/Browser fixture map sheet historical map image enabled/)
  ).toBeVisible();

  const canvas = page.getByLabel('Interactive historical world map for 100 CE').locator('canvas');
  const bounds = await canvas.boundingBox();
  expect(bounds).not.toBeNull();
  await expect(async () => {
    await canvas.click({ position: { x: bounds!.width / 2, y: bounds!.height / 2 } });
    await expect(
      page.getByRole('heading', { name: 'Enriched Pilot Place' })
    ).toBeVisible();
  }).toPass({ timeout: 20_000 });
});

test('selecting a search result opens the matching entity and feature', async ({
  page
}) => {
  await openPilot(page);
  await selectSearchResult(page, 'Undossiered Pilot Place');

  await expect(
    page.getByRole('heading', { name: 'Undossiered Pilot Place' })
  ).toBeVisible();
  await expect(page).toHaveURL(/entity=wikidata%3AQ200/);
  await expect(page).toHaveURL(/feature=browser-pilot%3Amissing-dossier-place/);
});

test('a feature with missing enrichment shows an explicit dossier gap', async ({
  page
}) => {
  await openPilot(page);
  await selectSearchResult(page, 'Undossiered Pilot Place');

  await expect(page.getByText('Reading dossier')).toBeVisible();
  await expect(
    page.getByText(
      'This release maps the record but does not publish a dossier linked to this exact feature.'
    )
  ).toBeVisible();
  await expect(
    page.getByText(/metadata for wikidata:Q200 was not enriched/)
  ).toBeVisible();
});

test('an enriched selection loads entity, dossier, and bounded context', async ({
  page
}) => {
  let releaseOptionalContext = (): void => {};
  const optionalContextGate = new Promise<void>((resolve) => {
    releaseOptionalContext = resolve;
  });
  await page.route(
    /\/(?:context\/features|region-time\/buckets)\//,
    async (route) => {
      await optionalContextGate;
      await route.continue();
    }
  );
  await openPilot(page);
  await selectSearchResult(page, 'Enriched Pilot Place');

  await expect(
    page.getByText(
      'A fully enriched synthetic entity used to verify release joins.'
    )
  ).toBeVisible();
  await expect(
    page.getByText(
      /saved browser-pilot introduction verifies that revision-pinned tertiary summaries/
    )
  ).toBeVisible();
  releaseOptionalContext();
  await expect(
    page.getByText('Historical context near this record', { exact: true })
  ).toBeVisible();
  await expect(page.getByText('Pilot Context Event').first()).toBeVisible();
  await expect(page.getByText(/Revision 1000/)).toBeVisible();
});

test('the 1543 Knowledge lens opens Copernicus structured evidence', async ({
  page
}) => {
  const searchIndex = page.waitForResponse(
    (response) =>
      response.url().endsWith('/search/index.json') && response.ok()
  );
  await page.goto('/?year=1543&lens=knowledge');
  await searchIndex;
  await expect(page.getByText('Opening release data')).toBeHidden();

  await selectSearchResult(page, 'Publication of De revolutionibus');

  await expect(
    page.getByRole('heading', { name: 'Publication of De revolutionibus' })
  ).toBeVisible();
  await expect(page.getByText('Structured sourced facts')).toBeVisible();
  await expect(page.getByText('Authored By · Nicolaus Copernicus')).toBeVisible();
  await expect(
    page.getByText(
      'These records are subject–predicate–object assertions, not generated narrative prose.'
    )
  ).toBeVisible();
  await expect(page.getByText('Knowledge Events')).toBeVisible();
});

test('the 1543 browse page frames the year before listing the archive', async ({
  page
}) => {
  const errors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  const timeBand = page.waitForResponse(
    (response) =>
      response.url().includes('/search/time/') && response.ok()
  );

  await page.goto('/browse?year=1543');
  await timeBand;

  await expect(
    page.getByRole('heading', { name: 'The world in 1,543' })
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: /A year is a cross-section/ })
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Evidence-backed paths into 1,543 CE' })
  ).toBeVisible();
  await expect(page.getByText('Publication of De revolutionibus')).toBeVisible();
  await expect(
    page.getByRole('link', { name: /Publication of De revolutionibus/ })
  ).toHaveAttribute(
    'href',
    /feature=historyjoice%3Apublication-de-revolutionibus%3A1543/
  );
  await expect(
    page.getByRole('heading', { name: 'Read 1,543 CE through a lens' })
  ).toBeVisible();
  expect(errors).toEqual([]);
});
