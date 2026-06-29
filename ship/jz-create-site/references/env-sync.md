# Production Env 同步

只有 Vercel deployment 需要 production env vars 时读取。

## 来源选择

不要上传所有本地 env var。

按这个顺序选择来源：

- 优先 `.env.production`
- 否则 `.env`
- 否则 `.env.example` 只作为 key reference，不作为 secret 来源

只同步 production build 和 runtime 必需变量。

常见例子：

- `NEXT_PUBLIC_APP_URL`
- auth secrets 和 callback URLs
- database connection string
- analytics public keys
- third-party OAuth credentials

## 命令

检查当前 production env：

```bash
vercel env ls production --scope <team>
```

添加或更新 key：

```bash
printf '%s' '<value>' | vercel env add <KEY> production --scope <team> --yes --force
```

如果缺少必需值，停止并报告准确 key 名。不要编造 secret。
