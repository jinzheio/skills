# Push 后索引

仅当目标 repo 是公开站点，且 push 的 commit 影响公开页面、公开路由结构、sitemap、robots 或 canonical host 配置时读取。

## 何时跳过

这些情况跳过 indexing，并说明原因：

- repo 是 backend-only、API-only、private 或 internal
- 变更文件不能映射到公开 URL
- 无法解析 production base URL
- push 后仍缺 IndexNow 支持
- 可选 Search Console 检查缺少凭据

## Push 前

最终 clean-tree 检查和 push 前：

1. 判断待提交变更是否影响公开页面或公开路由结构。
2. 从 repo 文档配置、package scripts、env examples、deployment metadata 或用户提供值解析 production base URL。
3. 除非 repo 已有以下能力，否则优先用 `add-indexnow` 安装可复用 IndexNow 支持：
   - `scripts/indexnow-collect-urls.ts` 或等价 `indexnow:collect`
   - `scripts/indexnow-submit.ts` 或等价 `indexnow:submit`
   - hosted key verification file 或已记录的 `INDEXNOW_KEY`
4. 如果 `add-indexnow` 创建或更新文件，把这些文件放进 push 前 commit。

不要在 push 后运行 `add-indexnow`。push 后步骤不能修改 tracked project files。

## URL 收集

push 成功后：

1. 检查已 push 的 commits，识别面向用户的页面更新。
2. 用项目 collector 生成 URL，例如：

```bash
pnpm tsx scripts/indexnow-collect-urls.ts --base-url <production-base-url> --from <base-ref> --to <head-ref> --out-file <tmp-url-file>
```

3. 排除 profile、admin、sign-in、API-only/internal files、纯 config 变更、scripts、database files 和 authenticated-only pages。
4. 提交前检查生成的 URL list。

## IndexNow 提交

使用 repo 的 IndexNow setup 提交：

```bash
pnpm tsx scripts/indexnow-submit.ts --base-url <production-base-url> --urls-file <tmp-url-file>
```

报告提交 URL 数量、endpoint 和结果。失败时保留命令输出，不声称成功。
