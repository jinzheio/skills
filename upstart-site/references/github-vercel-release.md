# GitHub 与 Vercel Release 参考

repo inspection、GitHub 创建/连接、Vercel project 设置时读取。

## Repo Inspection

```bash
pwd
git status --short --branch
git remote -v
git branch --show-current
rg --files -g 'package.json' -g 'pnpm-lock.yaml' -g 'package-lock.json' -g 'yarn.lock' -g 'bun.lockb' -g 'bun.lock'
```

检查 app entry points 和 build config：

```bash
sed -n '1,220p' package.json
find . -maxdepth 3 \( -name 'package.json' -o -name 'next.config.*' -o -name 'vercel.json' -o -name 'pnpm-workspace.yaml' \)
```

monorepo 中，任何 Vercel linking 前先识别 deploy root。常见模式：`apps/web`、`app`、`frontend`。

## 创建或连接 GitHub Repo

检查目标 repo 是否已存在：

```bash
gh repo view <owner>/<repo-name> --json nameWithOwner,visibility,defaultBranchRef
```

如果不存在，创建 private repo 并设为 origin。这里不要 push；主流程负责后续验证后的 push。

```bash
gh repo create <owner>/<repo-name> --private --source=. --remote=origin
```

如果用户明确要求 public，把 `--private` 换成 `--public`。

如果 repo 已存在，只把 `origin` 指向它，不重新创建：

```bash
git remote add origin git@github.com:<owner>/<repo-name>.git
# origin 已存在时：
git remote set-url origin git@github.com:<owner>/<repo-name>.git
```

创建或连接后验证：

```bash
git remote -v
gh repo view <owner>/<repo-name> --json nameWithOwner,url,defaultBranchRef
```

## 创建或连接 Vercel Project

检查是否已有 linked project：

```bash
cat .vercel/project.json 2>/dev/null
vercel project inspect <project-name> --scope <team>
```

如果 project 不存在，创建并 link：

```bash
vercel project add <project-name> --scope <team>
vercel link --project <project-name> --scope <team> --yes
```

## 连接 Vercel 到 GitHub

强制使用 GitHub integration。除非用户明确要求，不使用本地 checkout 的 `vercel --prod`。

```bash
vercel git connect git@github.com:<owner>/<repo-name>.git --scope <team> --yes
```

如果 SSH 不可用，但实际 remote 是 HTTPS，改用 HTTPS GitHub URL。

连接后确认后续 deployment metadata 包含：

- `githubCommitSha`
- `githubCommitRef`
- `githubRepo`

如果 deployment metadata 没有这些字段，说明 deploy 没走 GitHub path。

## 设置 Monorepo Root 和 Framework

deploy root 不是 `.` 时必需。

优先用 Vercel API。使用用户明确提供的 Vercel API token，或已认证 CLI session 的 token；不要打印 token：

```bash
TOKEN="${VERCEL_TOKEN:?set VERCEL_TOKEN}"
curl -sS -X PATCH \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "https://api.vercel.com/v9/projects/${PROJECT_ID}?teamId=${TEAM_ID}" \
  -d "{\"rootDirectory\":\"<app-root>\",\"framework\":\"nextjs\"}"
```

之后确认 Vercel project 显示：

- **Root Directory** 匹配目标 app directory
- **Framework** 正确，例如 `Next.js`
