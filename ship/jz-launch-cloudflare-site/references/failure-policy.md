# Failure Policy

Auto ship 是阶段流程。失败时先定位阶段，不要从头重跑。

## 处理原则

- Build / lint / typecheck 失败：留在当前部署或推送阶段，只修复与上线直接相关的问题。
- Cloudflare token 权限不足：交给 `jz-create-cloudflare-token`，只申请项目需要的最小权限。
- GitHub Secrets 缺失：交给 `jz-push-code` 或 `jz-setup-auto-pr` 的凭据规则处理。
- 域名未传播：标记 `partial` 或 `manual`，给出已验证记录和下一次复查方式。
- 正式域名不可访问：不要进入 `jz-setup-site-analytics`。
- 统计服务缺凭据：只跳过对应集成，不阻塞其它可做集成。
- Auto PR 真实 PR 验证不可行：完成本地和 YAML 检查后标记 `partial`。

## 恢复方式

1. 重新运行 `scripts/inspect-cloudflare-ship-state.mjs` 或手动 preflight。
2. 对照 `stage-gates.md` 找第一个未达标阶段。
3. 只调用该阶段对应 skill。
4. 阶段达标后再继续后续阶段。

## 不要做

- 不要因为后续失败回滚已经 live 的正常站点。
- 不要删除 DNS、Cloudflare resources、GitHub repo 或 workflow，除非用户明确要求，且对应 skill 已列出对象并获得确认。
- 不要为了让流程继续而把未验证结果写成 `done`。
