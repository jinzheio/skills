import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';

const envPath = process.env.CLOUDFLARE_ENV_FILE || '.env.local';

if (!existsSync(envPath)) {
  console.error(`Missing ${envPath}`);
  process.exit(1);
}

const envText = readFileSync(envPath, 'utf8');
const requiredKeys = ['CLOUDFLARE_API_TOKEN', 'CLOUDFLARE_ACCOUNT_ID'];
const extra = {};

for (const line of envText.split(/\r?\n/)) {
  const match = line.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
  if (!match) {
    continue;
  }

  let value = match[2].trim();
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    value = value.slice(1, -1);
  }
  if (requiredKeys.includes(match[1])) {
    extra[match[1]] = value;
  }
}

for (const key of requiredKeys) {
  if (!extra[key]) {
    console.error(`Missing ${key} in ${envPath}`);
    process.exit(1);
  }
}

const args = process.argv.slice(2);
if (!args.length) {
  console.error('Usage: node with-cloudflare-env.mjs <command> [...args]');
  process.exit(1);
}

const result = spawnSync(args[0], args.slice(1), {
  stdio: 'inherit',
  env: { ...process.env, ...extra },
});

process.exit(result.status ?? 1);
