# Map reviews: implementation proposal

[Home](../README.md) | [Documentation index](README.md)

Status: assessment only. No review interface, API or storage has been implemented.

## Visitor flow

After a successful generation, show **Review this map** alongside the result.
Require an explicitly selected integer rating from 1 to 5; do not preselect a
rating. Label the scale: 1 Poor, 2 Fair, 3 Okay, 4 Good, 5 Excellent. Initially
ask about overall map quality, not proven gameplay balance. Allow an optional
plain-text comment, limited to 2,000 characters.

Explain before submission that the displayed map, generation settings and
diagnostics will be uploaded with the review for private analysis. Generation
alone does not upload maps. Do not require names, email or a GitHub account.
Show a receipt on success; preserve the draft and allow retry on network failure.

Capture an immutable snapshot of the displayed successful result when opening
the form. Parameter sliders may already describe a different, ungenerated map.
A rerun creates a new reviewable result; it must never silently retarget a draft.
Prevent accidental double clicks and reuse a submission ID on retries.

## Hosting and storage

Keep the existing GitHub Pages frontend and browser generation. Add a small
HTTPS review API backed by a private database. One suitable implementation is
a Cloudflare Worker with a D1 database binding. This requires a separate service
account/setup; it does not require moving the website or running Python remotely.

GitHub Pages is static hosting, so it cannot itself accept and persist review
POST requests. A browser-local database also cannot collect reviews centrally.
GitHub Issues is a possible manual pilot, but requires visitor accounts and
makes feedback public; it is a poor match for the proposed anonymous form.

Suggested initial routes:

- `POST /reviews`: validate and store a review and its map snapshot atomically,
  returning a receipt. A repeated submission ID returns the existing receipt;
  reject reuse of that ID with different content.
- An authenticated administrative export, outside the public UI, produces
  CSV ratings/metrics and JSON maps for analysis. No public read/list endpoint.

Use two logical tables: `maps` (one row per content hash) and `reviews` (one row
per submission referencing that map). Store settings, metrics and bounded map
JSON as structured JSON/text initially. Measure actual snapshot sizes before
choosing request limits; use object storage if snapshots exceed database limits.
If object storage is introduced, handle failed uploads and orphan cleanup.

## What to record

| Data | Reason |
|---|---|
| Server receipt ID and UTC timestamp | Trace submissions reliably |
| Rating and optional comment | Human feedback |
| SHA-256 of canonical map snapshot, computed by the API | Group reviews of identical results |
| Generator Git commit/build ID and map schema version | Compare versions and reproduce older behavior |
| Resolved generation parameters, actual stage seeds and rerun stage | Reproduce results, including randomized reruns |
| Map JSON: geometry, adjacency, terrain, SCs and power assignments | Preserve the exact rated map after algorithms change |
| Structural scores, components and power-placement diagnostics | Relate feedback to individual generation metrics |
| Completed stage and selected preview tab | Distinguish terrain reviews from power-layout reviews |

The global seed alone is insufficient: reruns deliberately randomize that stage
and downstream stages. Retain the actual stage seeds and resolved settings.
Add build provenance to generated artifacts when implementing reviews. Re-render
stored structured maps with a trusted renderer for inspection; accepting raw SVG
is unnecessary and introduces active-content handling concerns.

## Validation and abuse controls

The API must validate integer ratings 1–5, comment length, supported schemas,
map counts, JSON structure and total payload size. Bind database access only to
the backend; never put administrative credentials in frontend code. Parameterize
queries. Treat comments as text when displaying/exporting them, including CSV
formula escaping. Client-provided metrics remain untrusted unless recomputed.

Allow the production origin with CORS, while recognizing CORS is not an abuse
barrier. Apply request throttling and storage quotas; add a bot challenge if
needed. Submission IDs prevent duplicate retries, not determined repeat voters.
Anonymous reviews cannot establish one-person-one-vote without stronger identity.
Avoid long-term raw IP storage and define a retention/deletion policy. Keep
administrator access separate from anonymous write access.

## Using reviews to improve generation

Start by comparing rating distributions and sample counts within generator
version, terrain preset, topology, province count and player count. Inspect
low-rated maps alongside comments. Compare ratings with shape penalties,
connectivity, landlocked rate, neutral access and power disparity.

An overall rating combines appearance, geography and perceived fairness. It
cannot independently prove balance; the current application does not run games.
Later add optional issue tags or separate visual/playability ratings, and collect
actual playtest outcomes if balancing victory conditions or power strength.

Treat submissions as a self-selected sample. Never automatically change scoring
weights to maximize a small sample's mean rating. Form hypotheses, adjust on a
development branch, and compare fresh maps or blinded paired layouts. Preserve
version boundaries and inspect the weakest power, not only map averages.

## Suggested delivery order

1. Add build/version provenance and define the bounded snapshot/review schema.
2. Provision private storage and the validated, throttled submission endpoint.
3. Add the review form, immutable snapshots, retry handling and receipts.
4. Add private export and a small analysis utility; document retention.
5. Test snapshot association, randomized reruns, invalid ratings, duplicate
   retries, failure recovery and unauthorized reads; pilot on development.

## Sources

- [GitHub Pages hosting model](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
- [Cloudflare D1 Worker binding API](https://developers.cloudflare.com/d1/worker-api/)
- [Cloudflare D1 setup](https://developers.cloudflare.com/d1/get-started/)
