# IndexNow Onboarding

Load this reference for IndexNow work inside the post-domain onboarding flow.

Treat IndexNow as post-domain indexing setup, not core deployment.

## Flow

1. Check whether the repo already has an IndexNow implementation.
2. If it does not, use `add-indexnow` from this skill pack.
3. Generate a fresh host-scoped key only for the final domain.
4. Ensure the verification file is served on the final domain.
5. Ensure the repo has a collect-and-submit path for URL submission.
6. Validate against the real final host, not the temporary deployment URL.

## Minimum Goal

- key file is present and publicly reachable on the final host
- repo has a reusable submission workflow
- IndexNow setup matches the final canonical domain

Do not reuse a key tied to a temporary host. If an implementation already exists, update it instead of duplicating scripts.

If the repo cannot be resolved or edited, report IndexNow as `skipped` and continue to Bing Webmaster Tools.
