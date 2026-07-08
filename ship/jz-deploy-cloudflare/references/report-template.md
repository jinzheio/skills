# Report Template

最终汇报使用 `docs/status-terms.md` 中的状态词。

## 模板

```text
Cloudflare deploy 结果：

- Cloudflare deploy: <done|partial|skipped|blocked|manual> — <URL / deployment id / 原因>
- GitHub repo: <status> — <repo URL / 原因>
- Production auto deploy: <status> — <workflow / run / 原因>
- Domain: <status> — <canonical host / HTTPS / redirect / 原因>
- Analytics and search: <status> — <已完成集成 / 跳过原因>
- Conversion tracking: <status> — <事件 / 验证方式 / 跳过原因>
- Auto PR: <status> — <workflow / runner / dispatcher / PR / 原因>
- Remaining changes: <status> — <git status 摘要>
- Risks / manual actions: <status> — <具体事项>
```

## 汇报规则

- `done` 必须有 live 或权威来源验证。
- `partial` 只用于已经完成一部分、剩余验证可单独补的情况。
- `skipped` 说明前置条件缺失或用户没有要求。
- `blocked` 说明已经尝试但被权限、外部错误或上游依赖卡住。
- `manual` 说明需要用户在 dashboard、邮箱、付款或浏览器登录中操作。

不要输出 secret 值、账号私密信息、客户名、内部服务器路径或本机绝对路径。
