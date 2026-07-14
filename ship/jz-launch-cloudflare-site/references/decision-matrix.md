# Decision Matrix

根据当前状态选择阶段。只调用必要 skill，不为了“全流程”强行执行不适用的步骤。

## 路线选择

| 当前状态 | 下一步 |
| --- | --- |
| 本地项目还没有 Cloudflare 可验证部署 | `jz-deploy-cloudflare` |
| 已有 Cloudflare 部署，但没有 GitHub repo | `jz-deploy-cloudflare` 的 GitHub 分支，或按用户要求先只部署 |
| 已有 Cloudflare 部署和 GitHub repo，但没有生产自动部署 workflow | `jz-push-code`，由它检查并补 Cloudflare 自动部署 |
| 已有 Cloudflare 临时 URL，用户提供正式域名 | `jz-setup-site-domain` |
| 正式域名还不可访问 | 不运行 `jz-setup-site-analytics`，先完成 `jz-setup-site-domain` |
| 正式域名可访问，但缺 robots / sitemap / GSC / Umami / Clarity / Sentry | `jz-setup-site-analytics` |
| 只缺 IndexNow 项目脚本 | `jz-setup-indexnow`，或让 `jz-setup-site-analytics` handoff |
| 用户要求注册、支付、表单等漏斗事件 | `jz-setup-conversion-tracking` |
| 用户要求自动处理 issue 或自动提 PR | `jz-setup-auto-pr` |
| 用户明确说从 Vercel 迁移旧项目 | 不走本 skill 主流程，改用 `jz-migrate-vercel-to-cloudflare` |

## 默认包含

用户说“从代码到上线”时，默认包含：

1. Cloudflare 部署
2. GitHub repo / push
3. 生产部署验证

用户同时给出正式域名时，包含：

4. 域名绑定
5. HTTPS 和跳转验证

用户说“到上线再接统计/搜索/分析工具”时，包含：

6. `jz-setup-site-analytics`

用户说“全流程包括 Auto PR”时，包含：

7. `jz-setup-auto-pr`

## 默认不包含

除非用户明确要求，不默认做：

- 转化漏斗埋点。
- Auto PR 自动化。
- 删除旧平台项目。
- 邮箱转发。
- 付费资源监控脚本。
- 生产数据迁移。

## Cloudflare 承载面

新项目默认优先：

1. Workers + Workers Static Assets
2. Workers + 官方框架适配器
3. Wrangler 直发
4. GitHub Actions 自动部署
5. Workers Builds，仅当用户要求 Git 集成且账号可关联
6. Pages，仅当用户指定或项目已有 Pages 约束

具体选择由 `jz-deploy-cloudflare` 执行。
