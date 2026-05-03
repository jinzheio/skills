# 失败处理策略

lint、build、commit、push 或 push 后 indexing 失败时读取。

## 可自动修复

如果修复范围窄，且直接服务于用户要求的 push，通常可以先修：

- 依赖元数据变化导致的 lockfile 过期
- 可确定修复的 formatting 或 lint 错误
- 当前 diff 引起的 type error
- 仓库本来就要求的缺失生成文件
- IndexNow collector 明显误包含 private 或 internal route

修复后，只重跑刚才失败的相关命令。

## 停止并报告

遇到这些情况，push 前停止：

- 认证或授权失败
- 破坏性 migration 或 schema 不确定
- 环境缺少 secret
- 无关 dirty-worktree 变更
- 与当前 diff 无关的测试失败
- remote branch divergence 无法干净 rebase
- 公开 URL 提交的 production URL 不明确

报告失败命令、原因和最小下一步。
