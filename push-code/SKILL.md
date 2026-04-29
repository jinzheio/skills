---
name: push-code
description: Safely run applicable checks, ensure a clean workspace, and push code to the remote repository.
---

# Push Code Skill

This skill ensures that applicable project checks pass and all changes are properly committed before pushing to the remote repository.

## Step-by-Step Instructions

When instructed to run the "push-code" skill, follow these steps exactly:

1. **Ask for User Confirmation**
   - Before taking any action, you MUST ask the user: "Are you sure you want to proceed with linting, building, and pushing the code?"
   - WAIT for the user to explicitly confirm before proceeding to Step 2.

2. **Resolve Verification Commands**
   - Inspect the repository before running checks:
     - `package.json`
     - lockfiles such as `pnpm-lock.yaml`, `package-lock.json`, `yarn.lock`, `bun.lockb`, or `bun.lock`
     - existing CI config if no package scripts exist
   - Choose the package manager already used by the repo.
   - Run lint only when a lint script or equivalent project check exists.
   - Run build only when a build script or equivalent project check exists.
   - If the repo has no applicable lint or build command, mark that check as `not applicable` and continue.

3. **Prepare Indexing Support Before Push**
   - Before the final clean-tree check and before pushing, inspect whether the pushed changes affect public pages or public route structure.
   - If public page updates exist, do not hardcode a project domain. Resolve the production base URL from the target repository's documented config, package scripts, environment examples, deployment metadata, or an explicit user-provided value.
   - If the base URL cannot be resolved, skip IndexNow setup and report that the production URL is missing.
   - Prefer using the `add-indexnow` skill to ensure reusable IndexNow support exists in the target repository before pushing. That skill owns the collector script, submit script, key verification file, package scripts, and validation workflow.
   - If `add-indexnow` is available, invoke it unless the target repository already has a complete IndexNow setup that includes:
     - `scripts/indexnow-collect-urls.ts` or an equivalent `indexnow:collect` package script
     - `scripts/indexnow-submit.ts` or an equivalent `indexnow:submit` package script
     - a hosted key verification file or documented `INDEXNOW_KEY` setup
   - If `add-indexnow` creates or updates files, include those files in the pre-push commit so the pushed branch contains the IndexNow support.
   - If `add-indexnow` is not available and the target repository does not already have a complete IndexNow setup, skip IndexNow and report that reusable IndexNow support is not installed.

4. **Automated Verification**
   - Run the resolved lint/check command if applicable and analyze its result.
   - Run the resolved build command if applicable and analyze its result.
   - **Error Handling**: If an applicable command fails, DO NOT proceed to pushing. Analyze the error output, fix the underlying issue automatically when safe, and then re-run the relevant commands until they complete successfully with zero errors.

5. **Ensure a Clean Git Workspace**
   - Execute `git status`.
   - If there are any uncommitted changes (tracked or untracked), you MUST commit them.
   - Create a meaningful commit message for the changes.
   - Stage only the intended files (do not use blanket staging like `git add .` unless the user explicitly requests it), then commit via `git commit -m "..."`.
   - Re-run `git status` to verify the working tree is completely clean.

6. **Push to Remote**
   - Once all applicable verification commands succeed or are marked `not applicable`, and the workspace is completely clean with all changes committed, execute `git push`.

7. **Post-Push URL Collection**
   - After pushing succeeds, inspect pushed commits and identify user-facing page updates.
   - If the base URL cannot be resolved, skip IndexNow and report that the production URL is missing.
   - Do not run `add-indexnow` after pushing. Post-push steps must not modify tracked project files.
   - If IndexNow support is still missing after push, skip IndexNow and report that it was not installed before push.
   - Generate URLs with the project-specific command, for example:
     - `pnpm tsx scripts/indexnow-collect-urls.ts --base-url <production-base-url> --from <base-ref> --to <head-ref> --out-file <tmp-url-file>`
   - The collector must exclude internal routes such as profile, admin, sign-in, API-only/internal files, and pure config changes.
   - Review the generated URL list before submitting it.

8. **Post-Push IndexNow Submit**
   - Submit the collected URL list using the IndexNow support installed or verified by `add-indexnow`.
   - Submit with the project-specific command, for example:
     - `pnpm tsx scripts/indexnow-submit.ts --base-url <production-base-url> --urls-file <tmp-url-file>`
   - The script must use the repository key setup (`public/<key>.txt`, or `INDEXNOW_KEY`/`--key` override) and push to `https://api.indexnow.org/indexnow` by default.
   - If submission fails, report the failure and include the command output; do not claim success.

9. **Search Console Sitemap Check**
   - Do not use the deprecated Google sitemap ping endpoint.
   - Do not resubmit the same sitemap to Google Search Console after every content-only page update.
   - Check or submit a sitemap through the Search Console API only when one of these is true:
     - the pushed changes add or change the sitemap file, sitemap route, robots sitemap reference, canonical production host, or public route structure
     - the site was just launched or newly verified in Search Console
     - the current Search Console sitemap state is missing, failed, stale, or unknown and credentials are available
   - If only existing pages were edited and the sitemap URL is already submitted and readable, rely on the existing sitemap plus IndexNow URL submission.
   - If Google credentials or site ownership are missing, skip this step and report the reason.

10. **Completion**
   - Notify the user that verification and push completed.
   - If IndexNow ran, include the submitted URL count and result.
   - If IndexNow was skipped, include the reason.
   - If Search Console sitemap handling ran or was skipped, include the result or skip reason.
