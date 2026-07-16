# Skill 合并与独立发布计划

本文记录本轮重构的范围、顺序、验收门槛和后续事项。执行过程中以当前工作树为准；已存在的用户修改不得回退或覆盖。

## 已确定的原则

- 按独立产品域合并。平台是重要依据，但目录分类不是合并依据。
- 每个大 skill 单独作为 Git Repo 发布；本机统一放在 `jzskills/` 下管理。
- 每个 skill 只维护一份源码。三个全局 skill 目录都通过软链接指向对应源码目录。
- 顶层 `SKILL.md` 只负责触发、路由、共享前置检查、安全规则和结果格式。
- 具体动作放在一层 `references/*.md`；确定性操作放在 `scripts/`；避免多层 `SKILL.md` 继承。
- 完成新 skill 的验证和切换后再删除旧 skill，不长期保留兼容副本。
- 小 skill 保持现状；只有列入下方合并清单的 skill 才移动或删除。
- 本轮允许本地修改和验证。影响发布、安装链路或用户机器的内容在测试完成后再决定是否 push。

## 阶段 0：保护现场和固化上下文

- [x] 确认 `ship/jz-build-tanstack/` 保留独立 `.git` 和原仓库历史。
- [x] 确认当前根仓库与 `jz-build-tanstack` 都有未提交修改；后续不得回退。
- [x] 把独立子 Repo 加入根仓库忽略规则，并建立 `catalog.yml`，避免父仓库误收录子 Repo 内容。
- [x] 修正 `jz-build-tanstack` 的目录名、frontmatter、OpenAI metadata、README 和安装示例不一致问题；远端仓库仍使用旧地址，发布前单独确认并改名。
- [ ] 暂时保留旧状态文件兼容；部署拆分时再决定 `.jz-tanstack-ship-files.json` 的迁移策略。

## 后续事项：让 jz-build-tanstack 只负责 builder

这项工作不和本轮两个试点混在同一批修改中。

- [ ] `jz-build-tanstack` 继续负责：读取 PRD/DESIGN、能力选择、TanStack scaffold、认证/支付/积分/AI/存储资产组装、页面生成、build、typecheck、测试和部署 profile 的配置模板。
- [ ] Builder 可以执行 profile 的本地验证和 dry-run，但不负责生产平台的账号、token、资源创建、secret 同步、正式部署、域名切换和线上运维。
- [ ] Cloudflare 生产发布交给 `$jz-cloudflare`；Vercel 生产发布交给 `$jz-vercel`；Node/VPS 发布交给服务器部署 skill。
- [ ] 使用 `SELECTION.md` 和受管文件清单作为交接契约，写清双方对 `wrangler.jsonc`、`vite.config.ts`、环境变量和生成文件的修改权限。
- [ ] 删除 builder 内重复的平台凭证、资源创建和正式发布说明；保留缺少外部 skill 时可执行的最小手动交接说明。
- [ ] 更新测试：builder 的完成状态止于 `release-ready`；生产 URL 和线上冒烟测试由部署 skill 报告。
- [ ] 完成旧名称和旧状态文件的兼容迁移，避免已有生成项目无法二次组装。

## 试点 A：jz-cloudflare

目标目录：`ship/jz-cloudflare/`，独立 Git Repo。

合并来源：

- `jz-deploy-cloudflare`
- `jz-launch-cloudflare-site`
- `jz-create-cloudflare-token`
- `jz-check-cloudflare-cost`
- `jz-migrate-vercel-to-cloudflare`
- `jz-deploy-cloudflare-worker-vps`

明确不合并：

- `jz-manage-cloudflare-ai-gateway`：后续归入 `jz-llm-gateway`。
- `jz-setup-site-domain`：继续作为独立小 skill，由 `launch` action 外部调用。
- `jz-setup-site-analytics`、`jz-setup-conversion-tracking`、`jz-setup-auto-pr`：已分别并入 `jz-site-observability` 和 `jz-github`，`launch` action 已改用新入口。

动作路由：

- `deploy`：把已有 Web 项目发布到 Cloudflare Workers。
- `launch`：编排部署、域名、统计、转化和 Auto PR，可选调用其它 skill。
- `credentials`：创建、更新和验证项目级最小权限 token。
- `cost`：识别资源、查询用量、估算费用和检查 D1 查询风险。
- `migrate-from-vercel`：迁移代码、配置、预览和生产流量。
- `mirror-worker-to-vps`：把已有 Worker bundle 作为兼容部署运行在 VPS。

实施步骤：

- [x] 建立 router `SKILL.md`、`agents/openai.yaml`、README、LICENSE 和 action 清单。
- [x] 将旧流程拆成一层 `references/*.md`，保留全部安全规则和验收条件。
- [x] 将脚本移入统一 `scripts/` 并使用动作前缀避免重名。
- [x] 合并重复的 Cloudflare env 包装脚本，只保留一份实现。
- [x] 将 token 本机配置迁到 `~/.config/skills/jz-cloudflare/`；旧配置只作为有说明的 fallback。
- [x] 建立 trigger、routing、脚本和来源覆盖测试。
- [x] 验证通过后删除六个旧源码目录，更新调用方和三套全局软链接。

## 试点 B：jz-content-ingest

目标目录：`content/jz-content-ingest/`，独立 Git Repo。

合并来源：

- `jz-get-x-posts`
- `jz-get-feishu-doc`
- `jz-get-scys-article`
- `jz-get-video-transcript`
- `jz-transcribe-media`
- `jz-get-douyin-transcripts`
- `jz-get-wechat-articles`
- `jz-get-readest-highlights`

动作路由：

- `x-posts`
- `feishu-doc`
- `scys-article`
- `video-transcript`
- `transcribe-media`
- `douyin-transcripts`
- `wechat-articles`
- `readest-highlights`

实施步骤：

- [x] 建立 router `SKILL.md`、`agents/openai.yaml`、README、LICENSE 和来源清单。
- [x] 每种来源使用一层 `references/<source>.md`，保留输入、输出、认证、失败处理和调用示例。
- [x] 将脚本移动到统一 `scripts/`，修复抖音流程对兄弟 skill 路径的依赖。
- [x] 统一输出约定，同时保留各来源原有文件格式和用户指定路径能力。
- [x] 将配置迁到 `~/.config/skills/jz-content-ingest/`；旧配置只作为有说明的 fallback。
- [x] 移除缓存和编译产物，不把 `.env`、cookie、账号或本机路径写入 Repo。
- [x] 建立 trigger、routing、脚本和来源覆盖测试。
- [x] 验证通过后删除八个旧源码目录，更新三套全局软链接。

## 两个试点的通过门槛

两个试点都满足以下条件后，才进入其余大 skill：

- [x] `SKILL.md` frontmatter 名称与目录一致，描述覆盖正向触发并排除相邻 skill。
- [x] 主 `SKILL.md` 少于 500 行，具体动作只从一层 reference 加载。
- [x] `agents/openai.yaml` 存在，`default_prompt` 使用新的 `$jz-*` 名称。
- [x] 原 skill 的每个脚本、reference、asset 和重要规则都有迁移、合并或明确删除记录。
- [x] 所有脚本完成语法检查；现有单元测试通过；可离线测试的动作完成 dry-run/help 测试。
- [x] routing 测试覆盖每个 action；trigger 测试包含正例、负例和两个大 skill 之间的冲突用例。
- [x] 不依赖兄弟目录的相对路径；外部 skill 依赖必须显式、可选或有失败说明。
- [x] README 中英文列表、安装示例、调用示例和凭证表同步。
- [x] 三个全局 skill 目录只有新名称，旧名称无残留，且没有断链。
- [x] 扫描本机绝对路径、账号、token、cookie、private key、服务器内部路径和未跟踪配置；发现后先修正。
- [x] 根仓库和两个独立 Repo 的 diff 已审查，没有混入范围外修改。

## 试点通过后的大 skill 合并结果

以下 12 组均已沿用试点结构完成合并、来源覆盖检查、独立 Repo 验证和软链接切换。

1. [x] `jz-github`
   - `jz-commit-code`
   - `jz-push-code`
   - `jz-setup-auto-pr`
   - `jz-setup-github-agent-access`
2. [x] `jz-site-observability`
   - `jz-setup-site-analytics`
   - `jz-setup-conversion-tracking`
   - `jz-setup-indexnow`
   - `jz-get-site-metrics`
   - `jz-check-site-speed`
3. [x] `jz-vercel`
   - `jz-deploy-vercel`
   - `jz-check-vercel-cost`
4. [x] `jz-testing`
   - `jz-setup-testing`
   - `jz-create-test-plan`
5. [x] `jz-llm-gateway`
   - `jz-manage-litellm`
   - `jz-manage-newapi`
   - `jz-manage-cloudflare-ai-gateway`
6. [x] `jz-cloud-servers`
   - `jz-manage-hetzner-servers`
   - `jz-manage-ovh-servers`
7. [x] `jz-browser-automation`
   - `jz-launch-chrome`
   - `jz-setup-browser-automation`
8. [x] `jz-scheduler`
   - `jz-manage-cron-jobs`
   - `jz-manage-launchd-tasks`
9. [x] `jz-video-production`
   - `jz-create-marketing-video`
   - `jz-edit-talking-head-video`
10. [x] `jz-product-research`
    - `jz-check-market-demand`
    - `jz-get-revenue-sites`
11. [x] `jz-product-page`
    - `jz-make-viral`
    - `jz-setup-tailwind-theme`
12. [x] `jz-training`
    - `jz-training-outline-assembler`
    - `jz-training-profile-sync`

## 保持现状的小 skill

除非后续明确改变范围，这些 skill 不合并、不改名：

- `jz-build-tanstack`（独立 Repo；只执行上方部署拆分 TODO）
- `jz-create-book-notes`
- `jz-send-notification`
- `jz-connect-mac`
- `jz-review-bug`
- `jz-setup-personal-context`
- `jz-check-neon-usage`
- `jz-setup-mailgun-domain`
- `jz-manage-cloud-agent`
- `jz-setup-site-domain`

## 全部完成后的审计

- [x] 根据本文件逐项检查所有来源目录、目标 Repo、测试、README、metadata、配置和软链接。
- [x] 确认每个大 skill 只有一份本地源码，根仓库只保存工作区清单和未拆分的小 skill。
- [x] 确认每个独立 Repo 可单独安装，不要求访问本机兄弟目录。
- [x] 生成 45 个旧名称到新 skill/action 的迁移表，没有保留旧 skill 代码副本。
- [x] 在本地提交前执行隐私和凭证扫描。
- [x] 从三套全局入口验证 15 个独立 Repo：15 次 `quick_validate`、15 次 Repo 测试、Cloud Server typecheck 和 Training 资源库校验均通过。
- [x] 复核 220 个被删除的 tracked source 文件，全部存在迁移、合并或明确删除记录。
- [ ] 等待确认后再创建或更新远端 Repo，并 push 本地提交。
- [ ] 准备从 worktree 合并回 `main` 前，提醒是否运行 `document-release` 更新文档。
