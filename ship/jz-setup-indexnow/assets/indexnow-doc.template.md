# IndexNow 集成

本项目可以在 push 或 deploy 后向 IndexNow 提交变更过的公开 URL。

## 必需设置

- 为当前项目和 host 生成新的随机 IndexNow key。
- 在 `public/` 增加验证文件：
  - 文件名：`<INDEXNOW_KEY>.txt`
  - 文件内容：`<INDEXNOW_KEY>`

默认不要复用其它项目的共享 key。优先每个 host 或项目使用独立 key。

## 可选环境变量

- `INDEXNOW_KEY`：覆盖 submit 脚本使用的 key
- `INDEXNOW_ENDPOINT`：自定义 endpoint，默认 `https://api.indexnow.org/indexnow`

## 收集变更 URL

```bash
tmp_file="$(mktemp)"
pnpm indexnow:collect --base-url https://example.com --from <old-ref> --to <new-ref> --out-file "$tmp_file"
```

## 提交 URL

```bash
pnpm indexnow:submit --base-url https://example.com --urls-file "$tmp_file"
```

## 常用流程

```bash
tmp_file="$(mktemp)"
pnpm indexnow:collect --base-url https://example.com --from <old-ref> --to <new-ref> --out-file "$tmp_file"
pnpm indexnow:submit --base-url https://example.com --urls-file "$tmp_file"
```
