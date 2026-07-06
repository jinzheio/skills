---
name: jz-auto-pr-cloudflare
description: "为部署在 Cloudflare Workers 或 Pages 上的 Web app 配置 Auto PR agent 工作流。适用于用户要求自动检查 GitHub issues、在独立 worktree 中修复、创建 PR、为 PR 部署 Cloudflare preview URL、保留稳定 OAuth callback preview、在 PR close 后清理 preview Worker 和本地 worktree。触发词包括 auto PR、自动提 PR、issue auto PR、Cloudflare preview、PR preview Worker、OAuth callback preview、worktree cleanup。"
---

# Auto PR for Cloudflare Web Apps

用于给已有 Cloudflare Web app 加一套可运行的 Auto PR 配置：

1. 定时检查 GitHub open issues。
2. 每次最多处理一个 issue。
3. 在独立 worktree / branch 中修改代码。
4. 跑验证，按需更新文档。
5. push branch 并创建 PR。
6. 为 PR 部署 Cloudflare preview。
7. PR 关闭后清理 PR 专属 preview Worker。
8. 下次定时任务开始时清理本地已关闭 PR 的 worktree。

默认目标是小团队或个人项目。不要把它做成能自动 merge、自动部署生产、自动删除远端分支的系统。

## 先确认

开始改目标 repo 前，确认这些信息：

- GitHub repo：`<owner>/<repo>`
- base branch：通常是 `main`
- Cloudflare 承载面：Workers、Pages，或框架适配到 Workers
- package manager：优先识别 lockfile；JS/TS 项目优先 `pnpm`
- build command：例如 `pnpm build`
- deploy command：例如 `pnpm exec wrangler deploy --config <config>`
- Cloudflare secrets：GitHub Actions 中至少有 `CLOUDFLARE_ACCOUNT_ID` 和 `CLOUDFLARE_API_TOKEN`
- 是否需要稳定 OAuth callback URL
- 是否已有文档发布流程，例如 `document-release`

如果 Cloudflare 项目还不能部署，先用 `jz-create-cf-site`。如果只是补 token，先用 `jz-create-cf-token`。

## GitHub Actions preview

对 Workers 项目，优先添加 `.github/workflows/preview.yml`。

行为：

- `pull_request` opened / synchronize / reopened：构建并部署 preview。
- `pull_request` closed：删除 PR 专属 Worker。
- 同仓库 PR 才运行；fork PR 没有 secrets，不部署。
- 不绑定生产 route。
- 删除 session KV 等会导致 preview 自动创建资源的 binding，除非项目明确需要。
- 保留共享 OAuth preview Worker，不在 PR close 时删除。

推荐 Worker 命名：

```text
PR 专属 Worker: <app-name>-pr-<pr-number>
共享 OAuth Worker: <app-name>-preview
```

PR 专属 Worker 用于人工确认具体 PR；共享 OAuth Worker 用于注册稳定 callback。多个 PR 同时运行时，共享 Worker 会被最后一次 preview 覆盖。

### Workers workflow 模板

按目标项目调整 `<node-version>`、`<app-name>`、build command 和生成的 Wrangler config 路径。

```yaml
name: Preview Cloudflare Workers

on:
  pull_request:
    branches:
      - main
    types:
      - opened
      - synchronize
      - reopened
      - closed

permissions:
  contents: read
  pull-requests: write
  issues: write

env:
  CI: true

jobs:
  preview:
    if: ${{ github.event.action != 'closed' && github.event.pull_request.head.repo.full_name == github.repository }}
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - name: Checkout
        uses: actions/checkout@v5

      - name: Setup pnpm
        uses: pnpm/action-setup@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "<node-version>"
          cache: pnpm

      - name: Install dependencies
        run: pnpm install --frozen-lockfile

      - name: Build
        run: pnpm build

      - name: Deploy preview Workers
        id: preview
        run: |
          preview_name="<app-name>-pr-${{ github.event.pull_request.number }}"
          shared_preview_name="<app-name>-preview"

          jq \
            --arg name "$preview_name" \
            '.name = $name | .topLevelName = $name | del(.routes) | del(.kv_namespaces) | del(.previews.kv_namespaces) | .workers_dev = true | .preview_urls = true' \
            <generated-wrangler-config> > "$RUNNER_TEMP/preview.wrangler.json"

          pnpm exec wrangler deploy \
            --config "$RUNNER_TEMP/preview.wrangler.json" \
            2>&1 | tee "$RUNNER_TEMP/wrangler-preview.log"

          preview_url="$(grep -Eo 'https://[^[:space:]]+\.workers\.dev[^[:space:]]*' "$RUNNER_TEMP/wrangler-preview.log" | tail -1)"
          if [ -z "$preview_url" ]; then
            echo "No isolated Cloudflare preview URL found in Wrangler output." >&2
            exit 1
          fi

          jq \
            --arg name "$shared_preview_name" \
            '.name = $name | .topLevelName = $name | del(.routes) | del(.kv_namespaces) | del(.previews.kv_namespaces) | .workers_dev = true | .preview_urls = true' \
            <generated-wrangler-config> > "$RUNNER_TEMP/shared-preview.wrangler.json"

          pnpm exec wrangler deploy \
            --config "$RUNNER_TEMP/shared-preview.wrangler.json" \
            2>&1 | tee "$RUNNER_TEMP/wrangler-shared-preview.log"

          shared_preview_url="$(grep -Eo 'https://[^[:space:]]+\.workers\.dev[^[:space:]]*' "$RUNNER_TEMP/wrangler-shared-preview.log" | tail -1)"
          if [ -z "$shared_preview_url" ]; then
            echo "No shared Cloudflare preview URL found in Wrangler output." >&2
            exit 1
          fi

          echo "url=$preview_url" >> "$GITHUB_OUTPUT"
          echo "shared_url=$shared_preview_url" >> "$GITHUB_OUTPUT"
        env:
          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}

      - name: Comment preview URL
        uses: actions/github-script@v8
        env:
          PREVIEW_URL: ${{ steps.preview.outputs.url }}
          SHARED_PREVIEW_URL: ${{ steps.preview.outputs.shared_url }}
        with:
          script: |
            const marker = "<!-- cloudflare-workers-preview -->";
            const body = [
              marker,
              `Cloudflare Workers preview: ${process.env.PREVIEW_URL}`,
              `Shared OAuth preview: ${process.env.SHARED_PREVIEW_URL}`,
            ].join("\n");
            const { owner, repo } = context.repo;
            const issue_number = context.issue.number;
            const comments = await github.paginate(github.rest.issues.listComments, {
              owner,
              repo,
              issue_number,
              per_page: 100,
            });
            const existing = comments.find((comment) =>
              comment.user?.type === "Bot" && comment.body?.includes(marker)
            );
            if (existing) {
              await github.rest.issues.updateComment({
                owner,
                repo,
                comment_id: existing.id,
                body,
              });
            } else {
              await github.rest.issues.createComment({
                owner,
                repo,
                issue_number,
                body,
              });
            }

  cleanup:
    if: ${{ github.event.action == 'closed' && github.event.pull_request.head.repo.full_name == github.repository }}
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - name: Checkout
        uses: actions/checkout@v5

      - name: Setup pnpm
        uses: pnpm/action-setup@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "<node-version>"
          cache: pnpm

      - name: Install dependencies
        run: pnpm install --frozen-lockfile

      - name: Delete isolated preview Worker
        run: |
          preview_name="<app-name>-pr-${{ github.event.pull_request.number }}"
          pnpm exec wrangler delete "$preview_name" --force 2>&1 | tee "$RUNNER_TEMP/wrangler-delete.log" || {
            if grep -qiE 'not found|does not exist|could not find' "$RUNNER_TEMP/wrangler-delete.log"; then
              echo "Preview Worker already deleted: $preview_name"
            else
              exit 1
            fi
          }
        env:
          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
```

For Cloudflare Pages, keep the same lifecycle but use the project’s Pages deploy command and cleanup command. If Pages already supplies branch previews with stable URLs, document that instead of adding redundant Workers preview.

## Auto PR automation

Use the automation tool if the runtime provides it. Update an existing automation instead of creating a duplicate.

Recommended schedule: hourly.

Recommended execution environment: worktree.

The automation prompt must include:

```text
Task: first clean up local worktrees for closed PRs, then check <owner>/<repo> open issues. If a suitable issue exists, solve at most one issue in a new codex/* branch/worktree, run verification, update docs if needed, push the branch, and create a PR.

Before coding:
- Read project instructions.
- Respect the repo package manager and test commands.
- Do not push the base branch.
- Do not deploy production.

Local worktree cleanup:
- Enumerate git worktrees.
- Only consider worktrees created by this automation, with branch names under codex/.
- For each candidate branch, query the matching GitHub PR.
- If the PR is open, keep the worktree.
- If the PR is closed, check git status in that worktree.
- If it has uncommitted changes or an in-progress merge/rebase, skip and report.
- If clean, remove the worktree.
- Delete the local branch with git branch -d; only use -D when the PR is merged.
- Do not delete remote branches unless the user explicitly asked.

Issue selection:
- Process at most one issue per run.
- Skip pull requests, linked PRs, duplicate/wontfix/blocked/needs-discussion issues, and issues requiring external decisions.

PR creation:
- Use a codex/ branch name.
- Commit the code change.
- Run docs release/update workflow before PR creation when the project requires it.
- Create a PR with summary, verification, docs result, risk, and Closes #<issue>.
```

## Docs to add to the target repo

Add or update maintainer docs. Keep wording factual.

Document:

- How to read the PR comment.
- Difference between PR URL and shared OAuth URL.
- That shared OAuth preview is overwritten by the latest preview run.
- That PR close removes only the PR-specific Worker.
- Required GitHub secrets.
- How to manually delete a stuck preview Worker.
- How local worktree cleanup works and when it refuses to delete.

## Verification

Run these before handing off:

- YAML parse for the workflow file.
- `git diff --check`.
- Project build/check command.
- Locally generate preview Wrangler configs and confirm:
  - name is `<app-name>-pr-<number>` and `<app-name>-preview`
  - no production routes
  - no unwanted KV/session binding
  - `workers_dev = true`
  - `preview_urls = true`
- Open a test PR or push to an existing PR and confirm:
  - preview job succeeds
  - PR comment contains both URLs
  - PR-specific URL returns 200
  - shared OAuth URL returns 200
  - closing or merging the PR runs cleanup
  - PR-specific URL returns 404 after cleanup
  - shared OAuth URL still returns 200

If a real close/merge test is not possible, state which parts were only syntax-checked.

## Safety rules

- Do not auto merge PRs.
- Do not deploy production from the preview workflow.
- Do not bind preview Workers to production routes.
- Do not delete the shared OAuth preview Worker in PR cleanup.
- Do not commit secrets, local absolute paths, real account names, customer names, or private deployment details.
- Do not use destructive git commands unless the user explicitly asks.
- Do not overwrite unrelated workflow files without reading them first.
- If Cloudflare token permissions are insufficient, report the missing permission and stop. Use `jz-create-cf-token` only when the user asks to create or update the token.

## Final report

Report:

- Files changed.
- Automation created or updated.
- Preview URL pattern.
- Shared OAuth URL pattern.
- Cleanup behavior.
- Verification commands and results.
- Any secrets or permissions the user still needs to configure.
