# Post-Push Indexing

Load this reference only when the target repo is a public site and the pushed commits affect public pages, public route structure, sitemap, robots, or canonical host configuration.

## When To Skip

Skip indexing and report the reason when:

- the repo is backend-only, API-only, private, or internal
- the changed files do not map to public URLs
- the production base URL cannot be resolved
- IndexNow support is missing after push
- credentials needed for an optional Search Console check are unavailable

## Before Push

Before the final clean-tree check and before pushing:

1. Inspect whether the pending changes affect public pages or public route structure.
2. Resolve the production base URL from documented repo config, package scripts, environment examples, deployment metadata, or an explicit user-provided value.
3. Prefer `add-indexnow` to install reusable IndexNow support unless the repo already has:
   - `scripts/indexnow-collect-urls.ts` or an equivalent `indexnow:collect` package script
   - `scripts/indexnow-submit.ts` or an equivalent `indexnow:submit` package script
   - a hosted key verification file or documented `INDEXNOW_KEY` setup
4. If `add-indexnow` creates or updates files, include those files in the pre-push commit.

Do not run `add-indexnow` after pushing. Post-push steps must not modify tracked project files.

## URL Collection

After pushing succeeds:

1. Inspect pushed commits and identify user-facing page updates.
2. Generate URLs with the project-specific collector, for example:

```bash
pnpm tsx scripts/indexnow-collect-urls.ts --base-url <production-base-url> --from <base-ref> --to <head-ref> --out-file <tmp-url-file>
```

3. Exclude internal routes such as profile, admin, sign-in, API-only/internal files, pure config changes, scripts, database files, and authenticated-only pages.
4. Review the generated URL list before submitting it.

## IndexNow Submit

Submit the collected URL list using the repository IndexNow setup:

```bash
pnpm tsx scripts/indexnow-submit.ts --base-url <production-base-url> --urls-file <tmp-url-file>
```

The script must use the repo key setup (`public/<key>.txt`, `INDEXNOW_KEY`, or `--key`) and default to `https://api.indexnow.org/indexnow`.

If submission fails, report the command output and do not claim success.

## Search Console Sitemap Check

Do not use the deprecated Google sitemap ping endpoint.

Do not resubmit the same sitemap after every content-only page update. Check or submit a sitemap through the Search Console API only when one of these is true:

- the pushed changes add or change the sitemap file, sitemap route, robots sitemap reference, canonical production host, or public route structure
- the site was just launched or newly verified in Search Console
- the current Search Console sitemap state is missing, failed, stale, or unknown and credentials are available

If only existing pages changed and the sitemap URL is already submitted and readable, rely on the existing sitemap plus IndexNow URL submission.
