# Failure Policy

Load this reference when lint, build, commit, push, or post-push indexing fails.

## Safe To Fix Automatically

These can usually be fixed without asking first, if the fix is narrow and directly required for the requested push:

- stale lockfile after dependency metadata changed
- formatting or lint errors with deterministic fixes
- type errors caused by the current diff
- missing generated files that the repo already expects
- IndexNow collector exclusions that clearly include private or internal routes by mistake

After fixing, rerun only the relevant failed command before continuing.

## Stop And Report

Stop before pushing when the failure involves:

- authentication or authorization failure
- destructive migration or schema uncertainty
- secrets missing from the environment
- unrelated dirty-worktree changes
- failing tests unrelated to the current diff
- remote branch divergence that cannot be rebased cleanly
- production URL ambiguity for public URL submission

Report the failing command, the reason, and the smallest next action.
