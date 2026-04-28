---
name: add-indexnow
description: "Add reusable IndexNow support to a web app or Next.js repo. Use when a user wants IndexNow setup copied into a project, wants post-push URL submission, or asks to generate indexnow collect/submit scripts, key verification files, and validation steps for a site."
---

# add-indexnow

Use this skill to add IndexNow support to an existing web app, usually a Next.js repo.

## Start here

At the beginning:

1. Confirm the target project directory if it is not already obvious from context.
2. Generate a new random IndexNow key for that project.

Do not ask the user to prepare the key in advance. Do not reuse a key from another project or host. Each project should get its own newly generated key.

## Goal

Add a lightweight IndexNow workflow that:

- generates a project-specific random key
- exposes `public/<key>.txt` for ownership verification
- creates a URL collector script based on the repo's public routes
- creates a submit script that posts URL batches to the IndexNow endpoint
- adds package scripts for collect and submit
- documents how to run the flow
- validates the setup with a dry run and lint

## Deliverables

Create or update these project files:

- `scripts/indexnow-submit.ts`
- `scripts/indexnow-collect-urls.ts`
- `docs/indexnow.md`
- `package.json`
- `public/<INDEXNOW_KEY>.txt`

## Workflow

1. Inspect the target repo before editing.
   Check `package.json`, public route files, sitemap/robots files, and any site-domain config.

2. Determine the canonical base URL.
   Prefer the project's existing domain config. If there is both env-based and hardcoded domain logic, match the repo's existing pattern instead of introducing a new one.

3. Map changed files to public URLs.
   Build the collector around the target app's actual route structure. Skip:
   - API routes
   - admin or authenticated-only routes
   - scripts and database files
   - purely internal pages

4. Generate a new random key for this project.
   Prefer a simple locally generated token such as `openssl rand -hex 16` or an equivalent secure random string. The key should be unique per project.

5. Generate the files.
   Use the bundled templates in `assets/` as the starting point, then tailor them to the target project. Do not copy them blindly without adjusting routes, base URL defaults, and file exclusions.

6. Add the key verification file.
   Create `public/<key>.txt` with the exact key as file content.

7. Validate.
   Run:
   - a collector test against a recent git diff
   - a submit dry run using `--dry-run`
   - the project's lint command

8. Report clearly.
   Tell the user what routes are included, what was skipped, and whether lint surfaced only pre-existing warnings or new issues.
   Include the generated key in the summary so the user can store it if needed.

## Validation checklist

- The collector only outputs public site URLs for the target host.
- The submit script accepts `--urls-file` and supports `INDEXNOW_KEY` or `public/<key>.txt`.
- The submit script filters out URLs for other hosts.
- The docs show the collect command, submit command, and post-push flow.
- The key file name and content both match exactly.
- The key was newly generated for this project rather than copied from another site.

## Bundled resources

- `assets/indexnow-submit.template.ts`
  Generic submit script with key discovery, host filtering, batching, and dry-run support.
- `assets/indexnow-collect-urls.template.ts`
  Generic collector skeleton with route-map and exclusion placeholders.
- `assets/indexnow-doc.template.md`
  Minimal project-facing documentation template.
- `references/adaptation-checklist.md`
  Quick checklist for adapting the collector to a new app's routing model.

## Notes

- Prefer `tsx` for TypeScript scripts if the repo already uses it.
- Keep the implementation light. This should be a post-push or post-deploy helper, not a new service.
- Treat IndexNow keys as host-scoped operational config. Even though the protocol can validate by hosted file, default to one fresh key per project/host for cleaner isolation.
- If the repo already has an IndexNow implementation, review it first and update the existing files instead of duplicating them.
