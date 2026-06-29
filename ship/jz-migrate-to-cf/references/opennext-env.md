# OpenNext 环境变量安全构建

适用于 `@opennextjs/cloudflare` 项目。

## 目录

- 变量分流
- 上传 Worker secrets
- 安全构建脚本
- 产物扫描

## 变量分流

- `NEXT_PUBLIC_*`：可在构建期暴露，Next.js 会内联到客户端。
- 运行时私密变量：用 `wrangler secret put` 或 `wrangler secret bulk` 写入 Cloudflare Worker。
- Vercel 平台变量：例如 `VERCEL`、`VERCEL_ENV`、`VERCEL_URL`、`VERCEL_OIDC_TOKEN`、`VERCEL_GIT_*`，不要带入 Cloudflare 构建。

## 上传 Worker secrets

不输出变量值，只让命令从本地 env 生成 JSON：

```bash
node - <<'NODE' | node <skill-dir>/scripts/with-cloudflare-env.mjs npx wrangler secret bulk
const fs = require("fs");
const keep = new Set([
  "DATABASE_URL",
  "SUPABASE_SERVICE_ROLE_KEY",
  "NEXT_PUBLIC_SUPABASE_URL",
  "NEXT_PUBLIC_SUPABASE_ANON_KEY",
  "MAILGUN_API_KEY",
  "MAILGUN_DOMAIN",
  "RECIPIENT_EMAIL",
]);
const out = {};
for (const line of fs.readFileSync(".env", "utf8").split(/\r?\n/)) {
  if (!line || line.trimStart().startsWith("#")) continue;
  const index = line.indexOf("=");
  if (index < 0) continue;
  const key = line.slice(0, index).trim();
  if (!keep.has(key)) continue;
  let value = line.slice(index + 1).trim();
  if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
    value = value.slice(1, -1);
  }
  out[key] = value;
}
process.stdout.write(JSON.stringify(out));
NODE
```

## 安全构建脚本

给仓库增加脚本，避免完整 `.env` 进入 OpenNext 产物：

```js
// scripts/build-cloudflare.mjs
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";

const envPath = ".env";
const hasEnv = existsSync(envPath);
const originalEnv = hasEnv ? readFileSync(envPath, "utf8") : null;

function publicOnlyEnv(source) {
  return (
    source
      .split(/\r?\n/)
      .filter((line) => {
        if (!line || line.trimStart().startsWith("#")) return false;
        const index = line.indexOf("=");
        if (index < 0) return false;
        return line.slice(0, index).trim().startsWith("NEXT_PUBLIC_");
      })
      .join("\n") + "\n"
  );
}

try {
  if (hasEnv) writeFileSync(envPath, publicOnlyEnv(originalEnv));
  const result = spawnSync("npx", ["opennextjs-cloudflare", "build"], {
    stdio: "inherit",
    shell: false,
  });
  if (result.error) throw result.error;
  process.exitCode = result.status ?? 1;
} finally {
  if (hasEnv) writeFileSync(envPath, originalEnv);
}
```

脚本示例：

```json
{
  "scripts": {
    "build:cloudflare": "node scripts/build-cloudflare.mjs",
    "deploy": "npm run build:cloudflare && opennextjs-cloudflare deploy -- --keep-vars"
  }
}
```

如果项目使用 pnpm/yarn/bun，按项目已有包管理器替换命令。

## 产物扫描

构建后扫描产物。不要用会输出匹配行的 `rg <secret> .open-next`；只输出变量名：

```bash
node - <<'NODE'
const fs = require("fs");
const path = require("path");
const sensitiveValuePattern = /^(?!NEXT_PUBLIC_).*(TOKEN|SECRET|KEY|PASSWORD|PRIVATE|SERVICE_ROLE|DATABASE_URL)/;
const embeddedNamePattern = /^(?!NEXT_PUBLIC_).*(TOKEN|SECRET|PASSWORD|PRIVATE|SERVICE_ROLE|DATABASE_URL|^VERCEL$|^VERCEL_)/;
const items = [];
const sensitiveNames = [];
for (const line of fs.readFileSync(".env", "utf8").split(/\r?\n/)) {
  const index = line.indexOf("=");
  if (index < 0) continue;
  const key = line.slice(0, index).trim();
  if (embeddedNamePattern.test(key)) sensitiveNames.push(key);
  if (!sensitiveValuePattern.test(key)) continue;
  let value = line.slice(index + 1).trim();
  if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
    value = value.slice(1, -1);
  }
  if (value.length >= 16) items.push([key, value]);
}
const hits = new Set();
function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const file = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(file);
    else if (entry.isFile()) {
      const stat = fs.statSync(file);
      if (stat.size > 20 * 1024 * 1024) continue;
      const text = fs.readFileSync(file, "utf8");
      for (const [key, value] of items) {
        if (text.includes(value)) hits.add(key);
      }
    }
  }
}
walk(".open-next");
const nextEnvPath = ".open-next/cloudflare/next-env.mjs";
if (fs.existsSync(nextEnvPath)) {
  const nextEnv = fs.readFileSync(nextEnvPath, "utf8");
  for (const key of sensitiveNames) {
    if (nextEnv.includes(key)) hits.add(key);
  }
}
console.log("embedded_sensitive_keys=" + (hits.size ? [...hits].sort().join(",") : "none"));
process.exitCode = hits.size ? 1 : 0;
NODE
```

如果扫描命中任何私密变量，停止部署，删除 `.open-next`，修正构建环境后重新构建。已部署过的情况下，先把正确版本重新部署，再考虑轮换被嵌入的密钥。
