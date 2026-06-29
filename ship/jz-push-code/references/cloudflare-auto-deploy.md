# Cloudflare 自动部署

只在主流程已经确认以下两点时读取：

- 项目是 Cloudflare 公开站点。
- 仓库没有能在 `push` 到生产分支后部署 Cloudflare 的 GitHub Actions workflow。

目标是让 Cloudflare 站点通过 GitHub Actions 自动部署。不要保留“push 后本机 wrangler 发布”的流程。

## 凭据约定

### CLOUDFLARE_ACCOUNT_ID（共享）

所有 Cloudflare 项目共用同一个 Account ID。通过 `jz-create-cf-token` 本地配置读取 bootstrap env，再从其中读取 `CLOUDFLARE_ACCOUNT_ID`。

这是默认 Account ID 来源。项目 `.dev.vars` 可以保存同一个值，方便本地 `wrangler` 使用，但不要把其它账号的 Account ID 混进同一个项目。

### CLOUDFLARE_API_TOKEN（项目专属）

每个项目应使用最小权限 API token，而不是 account-level bootstrap token。

保存位置：

1. 项目 `.dev.vars` 中的 `CLOUDFLARE_API_TOKEN`，用于本地开发和手动验证。
2. GitHub repo secrets 中的 `CLOUDFLARE_API_TOKEN`，用于 CI/CD 自动部署。

`jz-create-cf-token` 本地配置指定的 bootstrap token 只用于创建项目 token，或给已有项目 token 增加必要权限，不得直接用于项目部署、资源创建、GitHub Secrets 或 CI/CD。

### 创建项目专属 Token

如果项目已经有 token，先验证它是否满足 workflow 需要。权限不足时，优先在 token id 可确认的情况下更新这个项目 token 的 policy；不能安全更新时，再创建新 token。

用 `jz-create-cf-token` 本地配置指定的、具备 Account API Tokens Write 权限的 bootstrap token 调用 Cloudflare API 创建或更新项目 token。先查询 permission group id，再按项目实际 workflow 选择最小权限。

读取 `wrangler.jsonc` 或 `wrangler.toml`（如果存在），根据项目实际使用的 Cloudflare 资源确定所需权限。常见项目 profile：

| 项目类型 | 所需权限 |
|----------|----------|
| Workers（纯脚本） | `Workers Scripts Write` |
| Workers + D1 | `Workers Scripts Write`, `D1 Metadata Read`, `D1 Read`, `D1 Write` |
| Workers + R2 | `Workers Scripts Write`, `Workers R2 Storage Read`, `Workers R2 Storage Write` |
| Workers + D1 + R2 | 合并以上所有 D1 + R2 权限 |
| Workers + KV | `Workers Scripts Write`, `Workers KV Storage Read`, `Workers KV Storage Write` |
| Workers + AI | `Workers Scripts Write`, `Workers AI Read`, `Workers AI Write` |

只有 workflow 或项目脚本会通过 Cloudflare API 读写对应资源时，才添加对应权限。

#### Workers + routes + custom domain

当 `wrangler.jsonc` 或 `wrangler.toml` 中包含 `routes` 数组且 route 带有 `custom_domain: true` 时，`wrangler deploy` 需要操作 Zone Workers Routes 和验证 DNS。

token 必须额外包含 Zone 级权限：

| 资源层级 | 权限 | 说明 |
|----------|------|------|
| Zone | `Workers Routes Write` | 注册/更新 Worker routes |
| Zone | `DNS Read` | 验证 custom domain DNS 记录 |

注意：Zone 级权限必须嵌套在 Account 资源下写入 token policy（`com.cloudflare.api.account.zone.*` 放在 account resource 内部），否则 Cloudflare API 返回 400（`Must specify a zone for account owned tokens, or nest zone under specific account resource`）。

创建 token 的 policy 结构：

```python
"resources": {
    f"com.cloudflare.api.account.{account_id}": {
        "com.cloudflare.api.account.zone.*": "*"
    }
}
```

不止 Workers Scripts Write 时需要这条规则。部署失败确认报错是 worker routes API 403 (`code: 10000`) 或 400 时，就按本条重新检查 project token 的权限和 policy 结构。

Cloudflare Pages 项目按实际部署命令选择 Pages 对应权限。不要为了省事使用全账号编辑权限。

创建或更新后先验证 token active 和目标 API 权限，再写入 `.dev.vars` 与 GitHub repo secrets。不要输出 token 值到日志或提交到 Git。

## Workflow 模板

Cloudflare Pages 项目默认使用这个 workflow。按项目实际包管理器、生产分支和部署脚本调整。

```yaml
name: Deploy Cloudflare Pages

on:
  push:
    branches:
      - main
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: cloudflare-pages-production
  cancel-in-progress: true

env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true

jobs:
  deploy:
    if: ${{ github.event_name != 'push' || !contains(join(github.event.commits.*.message, ' '), '[skip deploy]') }}
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup pnpm
        uses: pnpm/action-setup@v4
        with:
          version: 10.23.0

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 24
          cache: pnpm

      - name: Install dependencies
        run: pnpm install --frozen-lockfile

      - name: Check
        run: pnpm run check

      - name: Deploy Cloudflare Pages
        run: pnpm run pages:deploy
        env:
          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
```

## 适配规则

- 项目不是 pnpm 时，按仓库已有包管理器改安装、缓存和命令。
- 生产分支不是 `main` 时，按项目实际分支改。
- 项目没有 `check` script 时，使用已有 build/test 命令；没有适用命令时删除 `Check` step。
- Cloudflare Workers 项目用已有 Workers 发布脚本替换 `pnpm run pages:deploy`。
- Workers 项目需要在 Deploy 步骤前增加 D1 migration 步骤。
- workflow 必须保留 `[skip deploy]` 判断，并检查本次 push 的完整 commit range。

## Secrets 检查

添加 workflow 后检查 GitHub repo secrets：

```bash
gh secret list --repo OWNER/REPO
```

Cloudflare 自动部署需要：

- `CLOUDFLARE_ACCOUNT_ID`（从 `jz-create-cf-token` 本地配置指定的 bootstrap env 获取）
- `CLOUDFLARE_API_TOKEN`（项目专属最小权限 token）

## Token 创建约定

缺少 secrets 时，不要 push 后声称会自动部署。默认按下面的顺序处理：

1. 通过 `jz-create-cf-token` 本地配置读取共享 `CLOUDFLARE_ACCOUNT_ID`。
2. 先检查当前项目 `.dev.vars`、`.env.local` 或其它本地 env 中是否已有项目专属 `CLOUDFLARE_API_TOKEN`。
3. 如果项目 token 存在，验证它的目标 API 权限；权限足够就直接写入 GitHub Secrets。
4. 如果项目 token 缺失或权限不足，通过 `jz-create-cf-token` 本地配置读取具备 Account API Tokens Write 权限的 bootstrap token。
5. 用 bootstrap token 调用 Cloudflare API 创建当前项目专属 token，或给已有项目 token 增加必要权限。
6. 把项目 token 写入当前项目 `.dev.vars` 的 `CLOUDFLARE_API_TOKEN`。
7. 用 `gh secret set` 写入 GitHub repo secrets：
   - `CLOUDFLARE_ACCOUNT_ID`
   - `CLOUDFLARE_API_TOKEN`

共享 bootstrap token 只用于创建或更新项目 token，不得写入当前项目 `.dev.vars` 或 GitHub Secrets，也不得用于项目部署、资源创建或 CI/CD。不要输出任何 token 值。

创建 token 前先读取 permission group id：

```bash
curl -fsS "https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID/tokens/permission_groups" \
  -H "Authorization: Bearer $BOOTSTRAP_CLOUDFLARE_API_TOKEN"
```

按项目实际 workflow 选择最小权限。Workers + D1 migrations 项目通常需要：

- `Workers Scripts Write`：`wrangler deploy`
- `D1 Metadata Read`：读取 D1 元数据
- `D1 Read`：读取 migration 状态
- `D1 Write`：执行 migration

只有 workflow 或项目脚本会通过 Cloudflare API 读写 R2 时，才添加：

- `Workers R2 Storage Read`
- `Workers R2 Storage Write`

创建或更新后用项目 token 验证目标 API 权限。至少验证 token active、账号可访问；涉及 D1 migration 时验证 D1 API；涉及 R2 时验证 R2 API。验证通过后再写入 `.dev.vars` 和 GitHub Secrets。

只有共享凭据不可用、bootstrap token 缺少 Account API Tokens Write、Cloudflare API 创建失败、项目 token 权限不足，或 GitHub repo secrets 无法写入时，才使用本机 `infra-credential-lookup` skill 继续查找，或询问用户提供最小所需凭据。
