# GitHub and Vercel Release Reference

Load this reference for repo inspection, GitHub creation/connection, and Vercel project setup.

---

## Repo Inspection

```bash
pwd
git status --short --branch
git remote -v
git branch --show-current
rg --files -g 'package.json' -g 'pnpm-lock.yaml' -g 'package-lock.json' -g 'yarn.lock' -g 'bun.lockb' -g 'bun.lock'
```

Inspect app entry points and build config:

```bash
sed -n '1,220p' package.json
find . -maxdepth 3 \( -name 'package.json' -o -name 'next.config.*' -o -name 'vercel.json' -o -name 'pnpm-workspace.yaml' \)
```

For monorepos, identify the deploy root before any Vercel linking. Common patterns: `apps/web`, `app`, `frontend`.

---

## Create or Connect GitHub Repo

Check whether the target repo already exists:

```bash
gh repo view <owner>/<repo-name> --json nameWithOwner,visibility,defaultBranchRef
```

If it does not exist, create a private repo and set it as origin. Do not push here; the main workflow owns the later validated push step.

```bash
gh repo create <owner>/<repo-name> --private --source=. --remote=origin
```

If the user explicitly wants public, replace `--private` with `--public`.

If it already exists, point `origin` to it without recreating:

```bash
git remote add origin git@github.com:<owner>/<repo-name>.git
# or if origin already exists:
git remote set-url origin git@github.com:<owner>/<repo-name>.git
```

Verify after creation or connection:

```bash
git remote -v
gh repo view <owner>/<repo-name> --json nameWithOwner,url,defaultBranchRef
```

---

## Create or Link Vercel Project

Check for an existing linked project:

```bash
cat .vercel/project.json 2>/dev/null
vercel project inspect <project-name> --scope <team>
```

If the project does not exist, create and link it:

```bash
vercel project add <project-name> --scope <team>
vercel link --project <project-name> --scope <team> --yes
```

---

## Connect Vercel to GitHub

Force GitHub integration. Do not use `vercel --prod` from local checkout unless the user explicitly asks for it.

```bash
vercel git connect git@github.com:<owner>/<repo-name>.git --scope <team> --yes
```

If SSH is unavailable but the actual remote is HTTPS, use the HTTPS GitHub URL instead.

After connecting, confirm a subsequent deployment includes GitHub metadata:

- `githubCommitSha`
- `githubCommitRef`
- `githubRepo`

If those fields are absent in the deployment metadata, the deploy did not go through the GitHub path.

---

## Set Monorepo Root and Framework

Required when the deploy root is not `.`.

Preferred method via Vercel API:

```bash
TOKEN=$(jq -r .token "$HOME/Library/Application Support/com.vercel.cli/auth.json")
curl -sS -X PATCH \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "https://api.vercel.com/v9/projects/${PROJECT_ID}?teamId=${TEAM_ID}" \
  -d "{\"rootDirectory\":\"<app-root>\",\"framework\":\"nextjs\"}"
```

Confirm afterward that the Vercel project shows:

- **Root Directory** matching the intended app directory
- **Framework** set correctly, for example `Next.js`
