# Cloudflare hosting and feedback setup

[Home](../README.md) | [Documentation index](README.md)

This is an implementation guide for `develop-main`, not an installed backend.
The Worker, review form, migrations and deployment configuration described below
still need to be implemented. No Cloudflare resources have been provisioned.

## Recommended deployment

Use a Cloudflare Worker with Static Assets for a development site:

```text
Visitor browser
  |-- GET website files --> Worker Static Assets (_site)
  |-- map generation ----> existing Pyodide browser Web Worker
  `-- POST /api/reviews --> Cloudflare Worker
                             |-- D1: ratings, comments, metrics, snapshot key
                             `-- private R2: exact map and generation snapshot
```

The browser Web Worker and Cloudflare Worker are different programs. Keep the
expensive Python map generation on the visitor's device. The server validates
and stores feedback; it does not need to generate maps or execute Pyodide.

Initially retain `master` -> GitHub Pages for the published site. Deploy
`develop-main` to a separately named Cloudflare Worker for testing. Give that
Worker its own D1 database and R2 bucket. When ready, either deploy a production
Worker from `master`, or retain GitHub Pages and point its feedback form at a
production Worker API. Do not mix testing feedback with production feedback.

Cloudflare can serve the website and API on one `workers.dev` hostname; no
custom domain is required. Same-origin hosting makes the frontend API URL simply
`/api/reviews`. Keeping GitHub Pages requires an absolute API URL and explicit
CORS handling for `https://rl3721.github.io` (origins have no repository path).

## Why use both D1 and R2?

D1 is suitable for filtering and aggregating ratings and map metrics. Its
maximum string, BLOB or row size is 2,000,000 bytes. Existing local examples
include a 5,614,103-byte `output/sphere-default/map.json`; even before adding
reports, not all current maps fit in a D1 row. Store full snapshots in private
R2 objects and only their keys/hashes plus bounded summaries in D1. Do not enable
public bucket access or expose a general-purpose upload endpoint.

Suggested tables:

- `maps`: snapshot hash primary key, R2 key, generator build ID, schema version,
  terrain/topology, cell/province/player counts, selected score components,
  received timestamp. Index the version and comparison dimensions actually used.
- `reviews`: submission UUID primary key, map hash foreign key, rating constrained
  to 1–5, comment, selected preview tab, received timestamp, payload fingerprint.

Store a versioned JSON snapshot containing `map.json`, `parameters.json`,
`report.json`, and build provenance in R2. Hash normalized snapshot content on
the server; do not trust a submitted hash. Record client provenance as a claim,
not proof that the client ran an unmodified generator.

Write the object first, then commit the map/review rows in a D1 transaction via
its batch API. R2 and D1 do not share a transaction: a database failure can leave
an orphan object. Reuse content-addressed object keys on retries and periodically
reconcile old unreferenced objects with a grace period. Return success only after
both writes complete. A submission UUID with identical content returns the prior
receipt; reuse with different content returns a conflict.

## Files to add or change

| Location | Implementation |
|---|---|
| `cloudflare/src/index.js` | Review route, bounded validation, throttling, private bindings |
| `cloudflare/migrations/0001_reviews.sql` | D1 tables, constraints and indexes |
| `cloudflare/wrangler.jsonc` | Static assets, D1 and R2 bindings |
| `cloudflare/package.json` and lockfile | Pin Wrangler and Worker test dependencies |
| `web/feedback.js` | Review form, immutable snapshot, retry and receipt handling |
| `web/ui.js` | Notify feedback component when a result is shown; expose selected tab |
| `tools/build_site.py` | Copy feedback assets and emit build metadata/configuration |
| `tests/` and Worker tests | Snapshot association, payload validation, storage failures, duplicate submissions |

Current results already provide downloadable artifact URLs, including browser
blob URLs. Capture and read them when opening the review form, before a rerun
revokes them. Use the generated result's parameters rather than edited sliders.
Include `pipeline.stage_seeds`: the global seed alone cannot reproduce reruns.

Use a dedicated `fetch('/api/reviews', ...)` path for feedback. The existing
`api()` helper routes browser requests into Pyodide and must not receive review
submissions. This is a particularly important integration detail in this repo.
The build must distinguish feedback-disabled GitHub builds from Cloudflare builds
or builds with an explicit external feedback endpoint.

## Account and development setup

Create or sign into a Cloudflare account, enable Workers/D1/R2, and check the
chosen products' billing/usage settings. Install a supported Node.js version.
Once the above files and a locked Wrangler dependency exist, from the repository:

```powershell
git switch develop-main
python -m tools.build_site
cd cloudflare
npm ci
npx wrangler login
npx wrangler d1 create diplomacy-feedback-dev
npx wrangler r2 bucket create diplomacy-map-snapshots-dev
```

The D1 create command returns a database ID. Put it in the configuration; it is
an identifier, not a password. Example configuration for this directory layout:

```jsonc
{
  "$schema": "./node_modules/wrangler/config-schema.json",
  "name": "diplomacy-map-workshop-dev",
  "main": "src/index.js",
  "compatibility_date": "2026-10-13",
  "workers_dev": true,
  "assets": {
    "directory": "../_site",
    "binding": "ASSETS",
    "run_worker_first": ["/api/*"]
  },
  "d1_databases": [{
    "binding": "DB",
    "database_name": "diplomacy-feedback-dev",
    "database_id": "REPLACE_WITH_CREATED_DATABASE_ID",
    "migrations_dir": "migrations"
  }],
  "r2_buckets": [{
    "binding": "MAPS",
    "bucket_name": "diplomacy-map-snapshots-dev"
  }]
}
```

The Worker handles `/api/reviews`, rejects unknown API routes, and can use
`env.ASSETS.fetch(request)` for other requests. Static assets normally bypass
Worker execution; API routes explicitly run the Worker first.

Once the migration and code exist, run these from `cloudflare/`:

```powershell
npx wrangler d1 migrations apply diplomacy-feedback-dev --local
npx wrangler dev
```

Local Wrangler uses local database/bucket storage by default. Generate a map,
submit a rating, verify the D1 record and snapshot, then test invalid ratings,
duplicate retries, failed storage, an edited form followed by a rerun, and an
oversized map. Apply explicit streamed request-size limits before JSON parsing;
do not rely only on Content-Length. Choose a supported submission size from
measured maps and show a clear UI message for maps above that size.

Before public deployment, add request throttling/storage quotas and preferably
a Turnstile challenge validated by the Worker. CORS is not a spam barrier. Keep
secrets in Wrangler secrets, never browser code. Ignore `node_modules/`,
`.wrangler/`, `.dev.vars` and local secret files in Git.

Then deploy to the separate development hostname:

```powershell
npx wrangler d1 migrations apply diplomacy-feedback-dev --remote
npx wrangler deploy
```

Wrangler prints the URL. Hosting files does not require uploading the repository:
only `_site` assets and the Worker bundle are deployed. Python runtime files in
`_site/python` are intentionally public so Pyodide can fetch them.

## Reading feedback privately

For the first pilot, avoid building an admin website. Use authenticated Wrangler
queries or the Cloudflare dashboard to inspect/export records. For example:

```powershell
npx wrangler d1 execute diplomacy-feedback-dev --remote --command "SELECT rating, COUNT(*) AS count FROM reviews GROUP BY rating" --json
```

Add an administrative export script that joins D1 rows and retrieves the R2
snapshots with account credentials. Do not give browsers those credentials.
An eventual admin interface needs authenticated, authorized access to both
reviews and snapshots. Escape comments as text and protect CSV exports against
formula interpretation. Define retention/deletion rules before public collection.

## Branch automation

First establish a working manual deployment. Then add a separate Cloudflare
deployment workflow restricted to `develop-main`, with tests, static build,
locked Node dependencies, migrations, and Wrangler deploy in that order. Use
environment-scoped GitHub secrets for a restricted Cloudflare API token/account
ID; never run credentialed deployments for untrusted pull requests. Serialize
deployments per environment. Use separate production configuration/resources
when promoting `master`; do not overwrite the development bindings in place.

The existing Pages workflow remains responsible for the current published site.
Cloudflare deployment is additional automation, not a replacement until a
production hosting change is deliberately made.

## References

- [Worker Static Assets](https://developers.cloudflare.com/workers/static-assets/)
- [Asset routing and bindings](https://developers.cloudflare.com/workers/static-assets/binding/)
- [Wrangler configuration](https://developers.cloudflare.com/workers/wrangler/configuration/)
- [D1 migrations and query commands](https://developers.cloudflare.com/d1/wrangler-commands/)
- [D1 storage limits](https://developers.cloudflare.com/d1/platform/limits/)
- [R2 access from Workers](https://developers.cloudflare.com/r2/api/workers/workers-api-usage/)
