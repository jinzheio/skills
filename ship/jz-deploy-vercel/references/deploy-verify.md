# 部署验证

repo 已 push 且 Vercel project 已连接时读取。

## 触发 GitHub-based Deploy

如果 Vercel 是在最近一次 push 后才连接 GitHub，创建 follow-up commit 或 empty commit，让 GitHub 发出新的 deployment event：

```bash
git commit --allow-empty -m "chore: trigger vercel deployment"
git push origin $(git branch --show-current)
```

除非用户明确要求 local-source deployment，不要把本地 `vercel --prod` 当作完成。

## 检查 Deployments

```bash
vercel list <project-name> --scope <team>
vercel inspect <deployment-url> --scope <team>
vercel inspect <deployment-url> --scope <team> --logs
```

如果 deployment 失败：

1. 读取 logs。
2. 只修复阻塞 release 的问题。
3. 本地验证。
4. commit 并 push 修复。
5. 验证下一次 GitHub-triggered deployment。

常见 first-deploy blocker：

- `ERR_PNPM_OUTDATED_LOCKFILE`：本地 install 同步 lockfile，commit 后再 push。

## 完成检查

release 完成必须满足：

1. code 已在 GitHub
2. Vercel project 已连接该 GitHub repo
3. deployment 使用 GitHub metadata
4. 最新 production deployment 为 `Ready`
5. production URL 可访问

推荐检查：

```bash
vercel list <project-name> --scope <team>
vercel inspect <deployment-url> --scope <team>
curl -I "https://${PRODUCTION_HOSTNAME}"
```
