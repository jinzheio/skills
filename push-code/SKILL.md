---
name: push-code
version: "1.1.0"
description: "Use when the user asks to verify and push a repo, including 'push this', '发布代码', or '推送到远端'. Run applicable checks, ensure intended changes are committed, and push. For public site repos with changed public pages, also run post-push IndexNow URL submission. Do not run IndexNow for backend-only repos, private tools, API-only changes, or changes without public URLs."
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

3. **Decide Whether Indexing Applies**
   - If the target repo is a public site and pending changes affect public pages, public route structure, sitemap, robots, or canonical host config, read `references/post-push-indexing.md` before the final clean-tree check.
   - If the repo is backend-only, API-only, private, internal, or the changes do not map to public URLs, skip IndexNow and Search Console steps and report the reason.

4. **Automated Verification**
   - Run the resolved lint/check command if applicable and analyze its result.
   - Run the resolved build command if applicable and analyze its result.
   - **Error Handling**: If an applicable command fails, DO NOT proceed to pushing. Read `references/failure-policy.md`, fix only safe narrow failures, and re-run the relevant command until it succeeds or you must stop and report.

5. **Ensure a Clean Git Workspace**
   - Execute `git status`.
   - If there are any uncommitted changes (tracked or untracked), you MUST commit them.
   - Create a meaningful commit message for the changes.
   - Stage only the intended files (do not use blanket staging like `git add .` unless the user explicitly requests it), then commit via `git commit -m "..."`.
   - Re-run `git status` to verify the working tree is completely clean.

6. **Push to Remote**
   - Once all applicable verification commands succeed or are marked `not applicable`, and the workspace is completely clean with all changes committed, execute `git push`.

7. **Post-Push URL Collection**
   - If `references/post-push-indexing.md` applied before push, follow its URL collection section.
   - Otherwise, report indexing as skipped with reason.

8. **Post-Push IndexNow Submit**
   - If public URLs were collected, follow `references/post-push-indexing.md`.
   - If submission fails, report the failure and include the command output; do not claim success.

9. **Search Console Sitemap Check**
   - Follow `references/post-push-indexing.md` only when sitemap handling is relevant.
   - If Google credentials or site ownership are missing, skip this step and report the reason.

10. **Completion**
   - Notify the user that verification and push completed.
   - If IndexNow ran, include the submitted URL count and result.
   - If IndexNow was skipped, include the reason.
   - If Search Console sitemap handling ran or was skipped, include the result or skip reason.
