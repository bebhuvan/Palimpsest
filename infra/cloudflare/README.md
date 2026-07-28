# Cloudflare data deployment

The public application and historical data have separate deployment lifecycles:

- Cloudflare Pages serves the small static application.
- A public R2 Standard bucket serves immutable PMTiles, GeoParquet, search, coverage, dossier, and attribution
  artifacts under `v1/builds/<build-id>/`.
- A separate private R2 bucket stores checksummed raw source snapshots. It must never be attached to
  a public domain because raw archaeological inputs can contain sensitive coordinates.
- `v1/latest.json` is the only mutable data object and is uploaded last.

## Initial setup requiring account credentials

1. In Cloudflare, create two R2 Standard buckets: one public-artifact bucket and a separate raw-
   snapshot bucket. Never enable public access or attach a domain to the snapshot bucket.
2. Create a scoped API token for the owning account with R2 object read/write and bucket settings
   permission only. Record the account ID; do not use a global API key.
3. Set `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`, `R2_BUCKET`, and
   `R2_SNAPSHOT_BUCKET` in the shell running setup. Replace the Pages origin in `r2-cors.json` with
   the final production origin (retain localhost only if local cross-origin testing is needed).
4. Run `bash infra/cloudflare/setup-r2.sh`. It creates missing buckets and applies the checked-in
   GET/HEAD/Range CORS policy only to the public bucket. Review the printed CORS result.
5. In R2 → the public bucket → Settings → Custom Domains, attach a domain such as
   `data.example.org`. Do not use the rate-limited `r2.dev` endpoint in production.
6. In the repository's GitHub Actions secrets, set the same four values and
   `WIKIMEDIA_USER_AGENT`. The latter must contain a descriptive client name/version and at least
   one monitored contact channel: an email address, an HTTP(S) project/contact page, or a Wikimedia
   `User:Name`. A URL and email are not both required.
7. Run the “Historical data release” workflow manually with `publish=false`; download and inspect
   its release artifact and resource metrics. Re-run with `publish=true` only after verification.
8. Confirm `https://data.example.org/v1/latest.json`, then its checksummed manifest, one PMTiles
   Range request, one `content/links/<shard>.json` request, and the schema 1.7
   `context/index.json`, `region-time/index.json`, `chronology/index.json`, and
   `source-registry.json` requests from the Pages origin. For schema 1.9, also confirm
   `search/index.json`, one time-band shard and one query n-gram shard are lazy. The checked-in
   smoke command verifies the pointer/manifest checksum, caching, CORS and PMTiles byte ranges:

   ```bash
   npm run data:verify-origin -- \
     https://data.example.org \
     https://palimpsest.pages.dev
   ```

## Static site

Create a Cloudflare Pages project connected to the repository with `npm run build` as the build
command and `build` as the output directory. No Pages Functions are required. Set the frontend's
`VITE_DATA_BASE` variable to the R2 custom-domain namespace including `/v1`, for example
`https://data.example.org/v1`. The production build intentionally fails if this variable is absent,
not HTTPS, or does not end in `/v1`, and also fails if a generated `static/data` directory exists.
Keep all Cloudflare and source API credentials in GitHub Actions or Cloudflare secrets, never in
`PUBLIC_*` variables. The checked-in `_headers` file supplies conservative browser security
headers and immutable caching for hashed assets.

Local development does not need R2 or `VITE_DATA_BASE`: `npm run data:prepare` validates
`dist/data/latest.json`, and `npm run dev` range-serves `dist/data` at the same-origin `/data`
route. This middleware is development-only and is absent from the Pages build.

## Publication and rollback

`uv run history-data publish-r2 --bucket "$R2_BUCKET"` verifies every local checksum,
uploads immutable artifacts with four-way concurrency, then advances `latest.json`. It never
deletes an object. Wrangler is intentionally fetched only for infrastructure and publication; it
is not part of the browser application's dependency tree.

The weekly scheduled workflow builds and retains a candidate for inspection but never publishes
it. Advancing the public pointer requires a manually dispatched workflow with `publish=true`.
This keeps source changes and editorial content behind an explicit release decision.

`make build-smoke` never advances `latest.json`. Only a complete, inspected release build should
become the candidate that the publisher advances; this prevents a limited-source smoke artifact
from becoming the public pointer.

Rollback is performed by publishing a previously retained `latest.json` that names the desired
build. Build folders are content-addressed and immutable, so no data rewrite is required.

Exact rollback, after downloading the prior `latest.json` from a retained workflow artifact and
verifying that its manifest and artifacts still exist, is:

```bash
npx --yes wrangler@latest r2 object put "$R2_BUCKET/v1/latest.json" \
  --file ./previous-latest.json \
  --content-type application/json \
  --cache-control 'public, max-age=60, must-revalidate' \
  --remote
```

Do not delete the failed build during rollback. Investigate using its retained manifest, quality
report, raw snapshot object keys and workflow resource metrics. Bucket lifecycle rules must never
expire an immutable build while any retained `latest.json` can point to it.

## Cache and CORS invariants

- Immutable artifacts and manifests are uploaded with a one-year immutable cache policy.
- `v1/latest.json` is the only mutable public object and uses 60-second revalidation.
- CORS permits only GET/HEAD from named Pages/local origins and exposes Range response headers for
  PMTiles. Do not allow `*` origins with credentials; no credentials are needed for public reads.
- Search JSON gzip files are ordinary immutable objects (`application/gzip`) decompressed by the
  client after their compressed bytes pass manifest checksum and size verification. They do not
  affect PMTiles range handling.
- The public bucket must not contain keys under the private snapshot prefix. The publisher requires
  a distinct snapshot bucket when a manifest contains raw snapshots.
