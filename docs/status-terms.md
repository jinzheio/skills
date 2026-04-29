# Skill Report Status Terms

All skills in this pack use a shared set of status terms when reporting the outcome of individual steps or integrations. Using consistent terms makes multi-skill workflow summaries easier to scan and compare.

## Terms

| Term | Meaning |
|---|---|
| `done` | Completed and verified against a live or authoritative source. |
| `partial` | Some substeps completed, but verification or a dependent deployment step is still outstanding. |
| `skipped` | Not attempted because required inputs, credentials, or preconditions were absent before the step started. |
| `blocked` | Attempted but could not finish due to an external error, insufficient permissions, or an unresolved upstream dependency. |
| `manual` | Requires a user action that falls outside the current automation path (e.g. browser sign-in, email confirmation, payment). |

## Usage rules

- Every integration or step in a final report must carry one of these terms.
- When the status is not `done`, always include a brief reason. For example: `skipped — BING_WEBMASTER_API_KEY not set`, `blocked — Vercel project not linked`.
- `partial` is not a polite substitute for `blocked`. Use `partial` only when measurable progress was made and the remaining gap is minor or deferred.
- Do not use `done` unless the result has been verified against a live system (API response, HTTP check, platform dashboard). "Step ran without error" is not sufficient for `done`.

## Skills that use these terms

- `index-onboarding` — reports status for each of: analytics, Search Console, robots/sitemap, IndexNow, Bing Webmaster Tools, Clarity
- `push-code` — reports status for: IndexNow URL submission, Search Console sitemap check
- `new-domain-launch` — reports status for: nameserver delegation, domain binding, TLS, redirect, email forwarding
