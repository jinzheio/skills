# Collector Adaptation Checklist

Use this checklist when tailoring `indexnow-collect-urls.ts` to a new project.

## Key setup

- Generate a new random IndexNow key for this project.
- Create `public/<key>.txt` with the exact same key as file content.
- Avoid reusing keys across unrelated projects or hosts unless the user explicitly wants shared operational config.

## Route inventory

- List all public pages from `src/app`, `app`, router configs, or CMS content directories.
- Identify internal-only pages such as admin, profile, auth, dashboard, settings, and API routes.
- Check whether the app has locale-prefixed routes, blog slugs, or generated content routes.

## Global files

When these change, you usually need to submit multiple or all public pages:

- root layout
- sitemap
- robots
- site config or domain config
- shared navigation or shared homepage sections

## File-to-route mapping

- Map direct page files to direct URLs.
- Map content files to their rendered routes.
- Map shared components to the pages they materially change.
- Skip assets and backend-only changes unless they affect a crawlable page.

## Validation

- Run the collector for a recent diff and inspect the output file.
- Confirm there are no API, auth, admin, or foreign-host URLs.
- Run submit with `--dry-run` first.
- Run the repo's lint command after file creation.
