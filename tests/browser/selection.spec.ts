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

// Search lives in an overlay opened from the instrument rail (or the "/" shortcut),
// so a result selection has to open it first.
async function selectSearchResult(page: Page, name: string): Promise<void> {
  await page.getByRole('button', { name: 'Search historical places' }).click();
  const search = page.getByRole('combobox', {
    name: 'Search historical places and alternate names'
  });
  await search.fill(name);
  await page.getByRole('option', { name: new RegExp(name) }).click();
}

async function openViewPanel(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Map layers and evidence overlays' }).click();
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

test('the timeline accepts an exact year and updates the map', async ({ page }) => {
  await openPilot(page);
  await page.getByRole('button', { name: /^Selected year 100 CE/ }).click();
  await page.getByRole('textbox', { name: 'Year', exact: true }).fill('200');
  await page.getByRole('combobox', { name: 'Era', exact: true }).selectOption('CE');
  await page.getByRole('button', { name: 'Go', exact: true }).click();

  await expect(
    page.getByLabel('Interactive historical world map for 200 CE')
  ).toBeVisible();
  await expect(page).toHaveURL(/year=200/);
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
  const toggle = page.locator('.historical-map-control .image-control button');
  await expect(toggle).toBeHidden();
  await openViewPanel(page);
  await expect(toggle).toBeVisible();
  await expect(toggle).toHaveAttribute('aria-label', 'Show historical map image');
  await toggle.focus();
  await page.keyboard.press('Enter');
  await imageResponse;

  await expect(toggle).toHaveAttribute('aria-pressed', 'true');
  await expect(toggle).toHaveAccessibleName('Hide historical map image');
  await expect(
    page.getByLabel('Interactive historical world map for 100 CE')
  ).toHaveAttribute('data-historical-map-overlay', 'map:0123456789abcdef');
  const details = page.getByLabel('Historical map image details');
  await expect(details.getByText('circa 1750')).toBeVisible();
  await expect(details.getByText('PDM-1.0').first()).toBeVisible();
  await expect(details.getByText(/Deterministic test control points/)).toBeVisible();
  await expect(
    details.getByText(/does not treat a scan as authoritative geography/)
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
      /This release maps the record but publishes no dossier linked to this exact feature/
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
    page.getByText('A synthetic settlement that became a provincial seat')
  ).toBeVisible();
  releaseOptionalContext();
  await expect(
    page.getByText('Historical context near this record', { exact: true })
  ).toBeVisible();
  await expect(page.getByText('Pilot Context Event').first()).toBeVisible();
  await expect(page.getByText(/revision 1000/)).toBeVisible();
});

test('an accepted authority link appears on its reviewed release record', async ({
  page
}) => {
  await openPilot(page);
  await selectSearchResult(page, 'Enriched Pilot Place');

  const connections = page.getByRole('region', { name: 'Authority connections' });
  await expect(connections).toBeVisible();
  await expect(
    connections.getByRole('link', { name: /Pilot Gazetteer Place/ })
  ).toHaveAttribute(
    'href',
    'https://example.org/palimpsest/authority/pilot-place'
  );
  await expect(connections.getByText(/Close Match · reviewed/)).toBeVisible();
  await expect(connections.getByText(/CC0-1.0/)).toBeVisible();
});

test('a restated dossier reads in plain English and keeps its source one tap away', async ({
  page
}) => {
  await openPilot(page);
  await selectSearchResult(page, 'Enriched Pilot Place');

  await expect(
    page.getByText('Plain English · restated from EN Wikipedia')
  ).toBeVisible();
  await expect(
    page.getByText(/It was founded in 60 and became a provincial seat in 95/)
  ).toBeVisible();
  // The prose is year-agnostic; the timeline is what re-anchors on the selected year.
  const timeline = page.getByRole('list', {
    name: 'Dated moments, read against 100 CE'
  });
  await expect(timeline.getByText('It became a provincial seat')).toBeVisible();
  await expect(timeline.getByText('by 100 CE')).toBeVisible();

  // The restatement never replaces the source: the original stays one disclosure away.
  const original = page.getByText(
    /saved browser-pilot introduction verifies that revision-pinned tertiary summaries/
  );
  await expect(original).toBeHidden();
  await page.getByRole('button', { name: 'Show the original extract' }).click();
  await expect(original).toBeVisible();
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
  // Predicate and object are separate elements so the object can carry reading weight.
  await expect(page.getByText('Authored By', { exact: true })).toBeVisible();
  await expect(page.getByText('Nicolaus Copernicus', { exact: true })).toBeVisible();
  await expect(
    page.getByText(
      /Subject–predicate–object assertions taken from the release/
    )
  ).toBeVisible();
  await page.getByText('Classification, confidence and provenance').click();
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

  // Years are never group-separated: 1543 is a date, not a quantity.
  await expect(
    page.getByRole('heading', { name: 'The world in 1543' })
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: /A year is a cross-section/ })
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Evidence-backed paths into 1543 CE' })
  ).toBeVisible();
  await expect(page.getByText('Publication of De revolutionibus')).toBeVisible();
  await expect(
    page.getByRole('link', { name: /Publication of De revolutionibus/ })
  ).toHaveAttribute(
    'href',
    /feature=palimpsest%3Apublication-de-revolutionibus%3A1543/
  );
  await expect(
    page.getByRole('heading', { name: 'Read 1543 CE through a lens' })
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test('a release without year pages offers no year and says so plainly', async ({ page }) => {
  // The browser pilot carries no `years/` artifacts. The contract is explicit that such a
  // release is complete rather than degraded, so the interface must neither offer a year
  // page nor break when asked for one.
  await openPilot(page);
  await expect(page.getByRole('link', { name: /Read the year/ })).toHaveCount(0);

  await page.goto('/year?year=100');
  await expect(page.getByRole('heading', { name: '100 CE' })).toBeVisible();
  await expect(
    page.getByText(/does not carry a written year page/)
  ).toBeVisible();
});
