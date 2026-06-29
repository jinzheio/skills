---
name: jz-create-cf-token
description: Create or update a project-scoped, minimal-permission Cloudflare API token. Use this skill whenever the user asks to set up Cloudflare authentication, create a Cloudflare API token, configure wrangler credentials, or mentions needing Cloudflare access for a project. Also trigger on phrases like "set up CF token", "create wrangler token", "Cloudflare API token for this project", or when a project needs Workers/D1/R2/KV/AI access.
---

# Cloudflare 项目 API Token

Use a project-scoped, minimal-permission Cloudflare API token for Cloudflare work.

The shared token configured for this skill is a bootstrap token. Use it only to create a project token or update an existing project token's permissions. Do not use the shared token for project deploys, resource creation, GitHub Secrets, CI/CD, or routine Wrangler/API operations.

Store the project token in `.dev.vars` and, when needed, GitHub Secrets. Keep `CLOUDFLARE_ACCOUNT_ID` with it.

## Workflow

### Step 1: Determine required permissions

Infer permissions from the project context. Read `wrangler.jsonc` or `wrangler.toml` if present to see which bindings are used (D1, R2, KV, AI, Workers, etc.). Ask the user to confirm the permission set.

Common project profiles:

| Project type | Permissions needed |
|---|---|
| Workers + D1 | Workers Scripts Write, D1 Read, D1 Write |
| Workers + R2 | Workers Scripts Write, R2 Read, R2 Write |
| Workers + D1 + R2 | Workers Scripts Write, D1 Read, D1 Write, R2 Read, R2 Write |
| Workers + KV | Workers Scripts Write, KV Read, KV Write |
| Workers + AI | Workers Scripts Write, AI Read, AI Write |
| Full Workers stack | Scripts Write, D1 R/W, R2 R/W, KV R/W, Routes R/W |

If there is no `wrangler` config or it's ambiguous, ask the user which services the project uses.

### Step 2: Check for an existing project token

Check current project files first:

```text
.dev.vars
.env.local
.env
.env.production
.env.development
```

If a project token exists, validate it against the concrete API needed for the task. If it already has the required permissions, use it.

If it exists but lacks permissions, prefer updating that project token's policy when the token id is available. If the token cannot be updated safely, create a new project token with the required minimum permissions and replace the project token in `.dev.vars`.

Never replace a project token with the shared bootstrap token.

### Step 3: Read bootstrap credentials only if needed

The config points to the bootstrap credential env file and names the variables to read. Look in **both** of these locations (first match wins):

1. `~/.config/skills/jz-create-cf-token/config.toml`
2. `<skill-dir>/config.toml`

If neither exists, ask the user for the missing config or values.

Config schema is tracked in `config.example.toml`. Copy that shape to a `config.toml` at the preferred location, then set `env_file` to the local bootstrap env file. Do **not** commit `config.toml` or the bootstrap env — both paths above are outside the skill's git repo by default.

When calling the Python script, resolve the config path with the same two-location order and pass it via `CF_TOKEN_SKILL_CONFIG`. Example resolution logic:

```bash
if [ -f "$HOME/.config/skills/jz-create-cf-token/config.toml" ]; then
    export CF_TOKEN_SKILL_CONFIG="$HOME/.config/skills/jz-create-cf-token/config.toml"
elif [ -f "<skill-dir>/config.toml" ]; then
    export CF_TOKEN_SKILL_CONFIG="<skill-dir>/config.toml"
else
    echo "No jz-create-cf-token config.toml found" >&2 && exit 1
fi
```

Read the configured account id and bootstrap token only when the project has no usable token, or when the existing project token needs a permission update. If the config file, env file, or variables are missing after checking both locations, ask the user directly.

Use this function to extract values from env files:
```bash
get_env() { awk -F= -v k="$1" '$1==k {sub(/^[^=]*=/, ""); gsub(/^"|"$/, ""); print; exit}' "$2"; }
```

The bootstrap env file must define the variables named by `account_id_var` and `token_var`.

### Step 4: Create or update the project token

Use a Python script to avoid exposing secrets in shell output. The endpoints are:

- List permission groups: `GET https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/tokens/permission_groups`
- Create token: `POST https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/tokens`
- Update token when applicable: `PUT https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/tokens/${TOKEN_ID}`
- Verify token: `GET https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/tokens/verify`

The token name should match the project name. Use `urllib` (stdlib) to avoid external dependencies. Policies should include only the permissions required by the current project.

Permission group ID reference (these are stable across accounts):

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

Always resolve permission group IDs from the live API rather than relying solely on this table, in case Cloudflare adds or renames groups. Use the table only as a fallback mapping from name to expected group.

Script template (adjust project name and permission groups). If updating an existing project token, use the same `body` with `PUT /accounts/${ACCOUNT_ID}/tokens/${TOKEN_ID}` instead of the create request. If the existing token id cannot be confirmed, create a new project token and replace the project token in `.dev.vars`.

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
    # Two-location lookup: ~/.config/skills first, then skill dir
    home_config = os.path.expanduser("~/.config/skills/jz-create-cf-token/config.toml")
    skill_dir_config = os.path.join(os.path.dirname(__file__), "config.toml")
    if os.path.exists(home_config):
        config_path = home_config
    elif os.path.exists(skill_dir_config):
        config_path = skill_dir_config
    else:
        raise SystemExit("No jz-create-cf-token config.toml found at ~/.config/skills/jz-create-cf-token/ or skill directory")

with open(config_path, "rb") as f:
    config = tomllib.load(f)

bootstrap = config["bootstrap"]
env_path = os.path.expanduser(bootstrap["env_file"])
account_id = get_env(bootstrap.get("account_id_var", "CLOUDFLARE_ACCOUNT_ID"), env_path)
bootstrap_token = get_env(bootstrap.get("token_var", "CLOUDFLARE_API_TOKEN"), env_path)

headers = {"Authorization": f"Bearer {bootstrap_token}"}
base = "https://api.cloudflare.com/client/v4"

# 1. Resolve permission group IDs from live API
req = urllib.request.Request(f"{base}/accounts/{account_id}/tokens/permission_groups", headers=headers)
perms = json.loads(urllib.request.urlopen(req).read())

def find_id(name):
    for g in perms["result"]:
        if g["name"] == name:
            return g["id"]
    raise ValueError(f"permission group not found: {name}")

perm_ids = [
    find_id("Workers Scripts Write"),
    find_id("D1 Read"),
    find_id("D1 Write"),
    # ... add more as needed
]

# 2. Create project token
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
    print(f"ERROR: {json.dumps(resp, indent=2)}")
    exit(1)

new_token = resp["result"]["value"]
token_id = resp["result"]["id"]

# 3. Verify
req3 = urllib.request.Request(f"{base}/accounts/{account_id}/tokens/verify",
    headers={"Authorization": f"Bearer {new_token}"})
verify = json.loads(urllib.request.urlopen(req3).read())
status = verify.get("result", {}).get("status", "unknown")
assert verify.get("success") and status == "active", f"verification failed: {status}"

# 4. Write to .dev.vars
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

# 5. Report (never print the token value)
print(f"token_id={token_id}")
print(f"verify_status={status}")
print("updated .dev.vars")
```

### Step 5: Verify the project token works

After writing `.dev.vars`, run a wrangler command to confirm the token is functional:

```bash
source .dev.vars 2>/dev/null; npx wrangler secret list 2>&1 | head -3
```

Or if the project doesn't have secrets yet, a lighter check:

```bash
curl -sS -H "Authorization: Bearer $TOKEN" "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/tokens/verify" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'status={d[\"result\"][\"status\"]}')"
```

## Security rules

- **Never print or display the token value.** Use `[REDACTED]` if a value must be shown.
- **Never hardcode tokens in shell commands.** Always use variables sourced from files.
- **Use the project token for project work.** Do not deploy, create resources, run Wrangler, or write GitHub Secrets with the shared bootstrap token.
- **Only read the bootstrap `CLOUDFLARE_API_TOKEN` from this skill's local config when creating or updating a project token.**
- The project token goes into `.dev.vars`, which must be gitignored. Verify before writing.
- If GitHub Actions deploys the project, write the project token, not the shared token, into GitHub Secrets.
- After creating or updating the project token, report only the token id, source file, and permission boundary.
