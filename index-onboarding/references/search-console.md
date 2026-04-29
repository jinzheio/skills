# Google Search Console

Load this reference for Search Console ownership, robots, sitemap, and sitemap submission work.

## Missing Credentials

If Google credentials are missing:

1. Still check whether `robots.txt` and `sitemap.xml` are live.
2. If the repo can be resolved, add or fix `robots.txt` and `sitemap.xml` if needed.
3. Report Search Console ownership and sitemap submission as `skipped`.
4. Continue to IndexNow.

## Recommended Flow

Use the final domain as the property source of truth.

1. Check whether `sc-domain:<domain>` already exists.
2. If missing, call Google Site Verification API `getToken` with `DNS_TXT`.
3. Add the TXT token in DNS.
4. Call Site Verification API `insert` to verify ownership.
5. Call Search Console API `sites.add` for `sc-domain:<domain>`.
6. Ensure the live site exposes:
   - `robots.txt`
   - `sitemap.xml`
7. Submit the sitemap with the Search Console API.

Verification alone is not enough. If the homepage is `200` but `sitemap.xml` is `404`, report Search Console onboarding as `partial`.
