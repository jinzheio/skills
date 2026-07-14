---
name: jz-create-cloudflare-token
description: 为项目创建或更新项目范围、最小权限的 Cloudflare API Token。当用户要求设置 Cloudflare 认证、创建 Cloudflare API Token、配置 wrangler 凭证，或提到项目需要 Cloudflare 访问权限时使用。触发短语包括"set up CF token""create wrangler token""Cloudflare API token for this project"，以及项目需要 Workers/D1/R2/KV/AI 访问权限时。
---

# Cloudflare 项目 API Token

Cloudflare 相关工作时，使用项目范围、最小权限的 Cloudflare API Token。

本技能配置的共享 token 是引导 token。它仅用于创建项目 token 或更新已有项目 token 的权限。不要将共享 token 用于项目部署、资源创建、GitHub Secrets、CI/CD 或日常 Wrangler/API 操作。

将项目 token 存储在 `.dev.vars` 中，需要时也存入 GitHub Secrets。`CLOUDFLARE_ACCOUNT_ID` 一并保存。

## 工作流

### 第 1 步：确定所需权限

根据项目上下文推断权限。如果存在 `wrangler.jsonc` 或 `wrangler.toml`，读取以了解使用了哪些绑定（D1、R2、KV、AI、Workers 等）。向用户确认权限集。

常见项目权限配置：

| 项目类型 | 所需权限 |
|---|---|
| Workers + D1 | Workers Scripts Write、D1 Read、D1 Write |
| Workers + R2 | Workers Scripts Write、R2 Read、R2 Write |
| Workers + D1 + R2 | Workers Scripts Write、D1 Read、D1 Write、R2 Read、R2 Write |
| Workers + KV | Workers Scripts Write、KV Read、KV Write |
| Workers + AI | Workers Scripts Write、AI Read、AI Write |
| 完整 Workers 技术栈 | Scripts Write、D1 R/W、R2 R/W、KV R/W、Routes R/W |

如果没有 `wrangler` 配置或不明确，询问用户项目使用了哪些服务。

### 第 2 步：检查是否已有项目 token

先检查当前项目文件：

```text
.dev.vars
.env.local
.env
.env.production
.env.development
```

如果已存在项目 token，针对任务所需的具体 API 验证其有效性。如果已经具备所需权限，直接使用。

如果存在但权限不足，当 token id 可用时，优先更新该项目 token 的策略。如果无法安全更新，创建具有所需最小权限的新项目 token，并替换 `.dev.vars` 中的项目 token。

绝不要用共享引导 token 替换项目 token。

### 第 3 步：仅在需要时读取引导凭证

配置指向引导凭证的 env 文件，并指定要读取的变量名。按以下顺序查找（先匹配的优先）：

1. `~/.config/skills/jz-create-cloudflare-token/config.toml`
2. `<skill-dir>/config.toml`

如果都不存在，向用户询问缺失的配置或值。

配置格式参考 `config.example.toml`。将该模板复制为 `config.toml` 放在首选位置，然后将 `env_file` 设为本地的引导 env 文件。**不要**提交 `config.toml` 或引导 env——上述两个路径默认都在本 skill 的 git 仓库之外。

调用 Python 脚本时，按相同两位置顺序解析配置路径，并通过 `CF_TOKEN_SKILL_CONFIG` 传入。解析逻辑示例：

```bash
if [ -f "$HOME/.config/skills/jz-create-cloudflare-token/config.toml" ]; then
    export CF_TOKEN_SKILL_CONFIG="$HOME/.config/skills/jz-create-cloudflare-token/config.toml"
elif [ -f "<skill-dir>/config.toml" ]; then
    export CF_TOKEN_SKILL_CONFIG="<skill-dir>/config.toml"
else
    echo "未找到 jz-create-cloudflare-token config.toml" >&2 && exit 1
fi
```

仅在项目没有可用 token，或现有项目 token 需要权限更新时，才读取配置的 account id 和引导 token。如果在两个位置都找不到配置文件、env 文件或所需变量，直接询问用户。

使用以下函数从 env 文件提取值：
```bash
get_env() { awk -F= -v k="$1" '$1==k {sub(/^[^=]*=/, ""); gsub(/^"|"$/, ""); print; exit}' "$2"; }
```

引导 env 文件必须定义 `account_id_var` 和 `token_var` 所指定的变量。

### 第 4 步：创建或更新项目 token

使用 Python 脚本以避免在 shell 输出中暴露密钥。涉及的端点：

- 列出权限组：`GET https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/tokens/permission_groups`
- 创建 token：`POST https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/tokens`
- 更新 token（如适用）：`PUT https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/tokens/${TOKEN_ID}`
- 验证 token：`GET https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/tokens/verify`

token 名称应与项目名称一致。使用 `urllib`（标准库）避免外部依赖。策略应仅包含当前项目所需的权限。

权限组 ID 参考（这些 ID 跨账户稳定）：

```
Workers Scripts Write  e086da7e2179491d91ee5f35b3ca210a
Workers Scripts Read   1a71c399035b4950a1bd1466bbe4f420
D1 Read                192192df92ee43ac90f2aeeffce67e35
D1 Write               09b2857d1c31407795e75e3fed8617a1
D1 Metadata Read       5b4da8a35efa4fe8be684070183cdb32
R2 Storage Read        b4992e1108244f5d8bfbd5744320c2e1
R2 Storage Write       bf7481a1826f439697cb59a20b22293e
R2 Bucket Item Read    6a018a9f2fc74eb6b293b0c548f38b39
R2 Bucket Item Write   2efd5506f9c8494dacb1fa10a3e7d5b6
KV Storage Read        8b47d2786a534c08a1f94ee8f9f599ef
KV Storage Write       f7f0eda5697f475c90846e879bab8666
AI Read                a92d2450e05d4e7bb7d0a64968f83d11
AI Write               bacc64e0f6c34fc0883a1223f938a104
Routes Read            2072033d694d415a936eaeb94e6405b8
Routes Write           28f4b596e7d643029c524985477ae49a
CI Read                ad99c5ae555e45c4bef5bdf2678388ba
CI Write               2e095cf436e2455fa62c9a9c2e18c478
Observability Read     66c1ed49f4ed46098b75696a6d4ee3c9
Observability Write    82c075da3f4647a2a03becd0fe240f8a
```

始终通过实时 API 解析权限组 ID，不要仅依赖此表，以防 Cloudflare 新增或重命名权限组。此表仅用作从名称到预期组 ID 的回退映射。

脚本模板（调整项目名称和权限组）。如果更新已有项目 token，使用相同的 `body` 通过 `PUT /accounts/${ACCOUNT_ID}/tokens/${TOKEN_ID}` 替代创建请求。如果无法确认现有 token id，创建新项目 token 并替换 `.dev.vars` 中的项目 token。

```python
import subprocess, json, os
import urllib.request
import tomllib

def get_env(key, path):
    r = subprocess.run(["awk", "-F=", "-v", f"k={key}",
        '$1==k {sub(/^[^=]*=/, ""); gsub(/^"|"$/, ""); print; exit}', path],
        capture_output=True, text=True)
    return r.stdout.strip()

config_path = os.environ.get("CF_TOKEN_SKILL_CONFIG")
if config_path:
    config_path = os.path.expanduser(config_path)
else:
    # 两位置查找：先 ~/.config/skills，再 skill 目录
    home_config = os.path.expanduser("~/.config/skills/jz-create-cloudflare-token/config.toml")
    skill_dir_config = os.path.join(os.path.dirname(__file__), "config.toml")
    if os.path.exists(home_config):
        config_path = home_config
    elif os.path.exists(skill_dir_config):
        config_path = skill_dir_config
    else:
        raise SystemExit("未找到 jz-create-cloudflare-token config.toml（~/.config/skills/jz-create-cloudflare-token/ 和 skill 目录均无）")

with open(config_path, "rb") as f:
    config = tomllib.load(f)

bootstrap = config["bootstrap"]
env_path = os.path.expanduser(bootstrap["env_file"])
account_id = get_env(bootstrap.get("account_id_var", "CLOUDFLARE_ACCOUNT_ID"), env_path)
bootstrap_token = get_env(bootstrap.get("token_var", "CLOUDFLARE_API_TOKEN"), env_path)

headers = {"Authorization": f"Bearer {bootstrap_token}"}
base = "https://api.cloudflare.com/client/v4"

# 1. 从实时 API 解析权限组 ID
req = urllib.request.Request(f"{base}/accounts/{account_id}/tokens/permission_groups", headers=headers)
perms = json.loads(urllib.request.urlopen(req).read())

def find_id(name):
    for g in perms["result"]:
        if g["name"] == name:
            return g["id"]
    raise ValueError(f"未找到权限组: {name}")

perm_ids = [
    find_id("Workers Scripts Write"),
    find_id("D1 Read"),
    find_id("D1 Write"),
    # ... 根据需要添加更多
]

# 2. 创建项目 token
project_name = os.path.basename(os.getcwd())
body = json.dumps({
    "name": project_name,
    "policies": [{
        "effect": "allow",
        "resources": {f"com.cloudflare.api.account.{account_id}": "*"},
        "permission_groups": [{"id": pid} for pid in perm_ids]
    }]
}).encode()

req2 = urllib.request.Request(f"{base}/accounts/{account_id}/tokens",
    data=body, headers={**headers, "Content-Type": "application/json"})
resp = json.loads(urllib.request.urlopen(req2).read())

if not resp.get("success"):
    print(f"错误: {json.dumps(resp, indent=2)}")
    exit(1)

new_token = resp["result"]["value"]
token_id = resp["result"]["id"]

# 3. 验证
req3 = urllib.request.Request(f"{base}/accounts/{account_id}/tokens/verify",
    headers={"Authorization": f"Bearer {new_token}"})
verify = json.loads(urllib.request.urlopen(req3).read())
status = verify.get("result", {}).get("status", "unknown")
assert verify.get("success") and status == "active", f"验证失败: {status}"

# 4. 写入 .dev.vars
dev_vars = ".dev.vars"
existing = ""
if os.path.exists(dev_vars):
    with open(dev_vars) as f:
        existing = f.read()

lines = existing.split("\n")
new_lines = []
found_acct = False
found_token = False
for line in lines:
    if line.startswith("CLOUDFLARE_ACCOUNT_ID="):
        new_lines.append(f"CLOUDFLARE_ACCOUNT_ID={account_id}")
        found_acct = True
    elif line.startswith("CLOUDFLARE_API_TOKEN="):
        new_lines.append(f"CLOUDFLARE_API_TOKEN={new_token}")
        found_token = True
    else:
        new_lines.append(line)

if not found_acct:
    new_lines.append(f"CLOUDFLARE_ACCOUNT_ID={account_id}")
if not found_token:
    new_lines.append(f"CLOUDFLARE_API_TOKEN={new_token}")

new_content = "\n".join(new_lines).strip() + "\n"
with open(dev_vars, "w") as f:
    f.write(new_content)

# 5. 报告（绝不打印 token 值）
print(f"token_id={token_id}")
print(f"verify_status={status}")
print("已更新 .dev.vars")
```

### 第 5 步：验证项目 token 可用

写入 `.dev.vars` 后，运行 wrangler 命令确认 token 正常：

```bash
source .dev.vars 2>/dev/null; npx wrangler secret list 2>&1 | head -3
```

或者如果项目尚无 secrets，使用更轻量的检查：

```bash
curl -sS -H "Authorization: Bearer $TOKEN" "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/tokens/verify" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'status={d[\"result\"][\"status\"]}')"
```

## 安全规则

- **绝不打印或显示 token 值。** 如果必须展示值，使用 `[REDACTED]`。
- **绝不在 shell 命令中硬编码 token。** 始终使用从文件读取的变量。
- **项目工作使用项目 token。** 不要使用共享引导 token 进行部署、创建资源、运行 Wrangler 或写入 GitHub Secrets。
- **仅在创建或更新项目 token 时，从此 skill 的本地配置读取引导 `CLOUDFLARE_API_TOKEN`。**
- 项目 token 写入 `.dev.vars`，该文件必须在 gitignore 中。写入前请确认。
- 如果 GitHub Actions 部署该项目，将项目 token（而非共享 token）写入 GitHub Secrets。
- 创建或更新项目 token 后，仅报告 token id、来源文件和权限边界。
