# Deploy Verification

Load this reference when the repo is pushed and the Vercel project is connected.

## Trigger GitHub-Based Deploy

If Vercel was connected to GitHub after the latest push, create a follow-up commit or empty commit so GitHub emits a new deployment event:

```bash
git commit --allow-empty -m "chore: trigger vercel deployment"
git push origin $(git branch --show-current)
```

Do not treat `vercel --prod` from the local checkout as completion unless the user explicitly requested local-source deployment.

## Inspect Deployments

```bash
vercel list <project-name> --scope <team>
vercel inspect <deployment-url> --scope <team>
vercel inspect <deployment-url> --scope <team> --logs
```

If deployment fails:

1. Read logs.
2. Fix only the blocker that prevents release.
3. Validate locally.
4. Commit and push the fix.
5. Verify the next GitHub-triggered deployment.

Common first-deploy blocker:

- `ERR_PNPM_OUTDATED_LOCKFILE`: run local install to resync the lockfile, commit it, and push again.

## Completion Checks

The release is complete only when:

1. code is on GitHub
2. Vercel project is connected to that GitHub repo
3. deployment used GitHub metadata
4. latest production deployment is `Ready`
5. production URL works

Preferred checks:

```bash
vercel list <project-name> --scope <team>
vercel inspect <deployment-url> --scope <team>
curl -I "https://${PRODUCTION_HOSTNAME}"
```
