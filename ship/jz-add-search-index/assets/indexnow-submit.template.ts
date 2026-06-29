import { readFile } from 'node:fs/promises';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';

const DEFAULT_BASE_URL = 'https://example.com';
const DEFAULT_ENDPOINT = 'https://api.indexnow.org/indexnow';
const MAX_URLS_PER_REQUEST = 10_000;

type Args = {
  urlsFile: string;
  baseUrl: string;
  endpoint: string;
  key?: string;
  dryRun: boolean;
};

function parseArgs(argv: string[]): Args {
  let urlsFile = '';
  let baseUrl = DEFAULT_BASE_URL;
  let endpoint = process.env.INDEXNOW_ENDPOINT?.trim() || DEFAULT_ENDPOINT;
  let key = process.env.INDEXNOW_KEY?.trim() || '';
  let dryRun = false;

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];

    if (arg === '--urls-file') {
      urlsFile = argv[i + 1] ?? '';
      i += 1;
      continue;
    }

    if (arg === '--base-url') {
      baseUrl = argv[i + 1] ?? baseUrl;
      i += 1;
      continue;
    }

    if (arg === '--endpoint') {
      endpoint = argv[i + 1] ?? endpoint;
      i += 1;
      continue;
    }

    if (arg === '--key') {
      key = argv[i + 1] ?? key;
      i += 1;
      continue;
    }

    if (arg === '--dry-run') {
      dryRun = true;
    }
  }

  if (!urlsFile) {
    throw new Error('Missing required arg: --urls-file <path>');
  }

  return { urlsFile, baseUrl, endpoint, key: key || undefined, dryRun };
}

function resolveKeyFromPublic(rootDir: string): string {
  const publicDir = path.join(rootDir, 'public');

  if (!existsSync(publicDir)) {
    return '';
  }

  for (const name of readdirSync(publicDir)) {
    if (!name.endsWith('.txt')) continue;

    const key = name.slice(0, -4).trim();
    if (key.length < 8) continue;

    try {
      const content = readFileSync(path.join(publicDir, name), 'utf8').trim();
      if (content === key) {
        return key;
      }
    } catch {
      // Ignore unreadable files while scanning for the verification key.
    }
  }

  return '';
}

function normalizeUrls(input: string[], expectedHost: string) {
  const valid = new Set<string>();
  const skipped: string[] = [];

  for (const raw of input) {
    const value = raw.trim();
    if (!value) continue;

    try {
      const parsed = new URL(value);
      if (!['http:', 'https:'].includes(parsed.protocol)) {
        skipped.push(value);
        continue;
      }
      if (parsed.host !== expectedHost) {
        skipped.push(value);
        continue;
      }
      valid.add(parsed.toString());
    } catch {
      skipped.push(value);
    }
  }

  return { valid: Array.from(valid), skipped };
}

function chunk<T>(items: T[], size: number): T[][] {
  const batches: T[][] = [];

  for (let i = 0; i < items.length; i += size) {
    batches.push(items.slice(i, i + size));
  }

  return batches;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const host = new URL(args.baseUrl).host;
  const key = args.key || resolveKeyFromPublic(process.cwd());

  if (!key) {
    throw new Error(
      'IndexNow key not found. Set INDEXNOW_KEY, pass --key, or add public/<key>.txt with matching content.',
    );
  }

  const raw = await readFile(args.urlsFile, 'utf8');
  const inputUrls = raw.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const { valid, skipped } = normalizeUrls(inputUrls, host);

  if (valid.length === 0) {
    console.log(JSON.stringify({ ok: true, submitted: 0, skipped: skipped.length }, null, 2));
    return;
  }

  const batches = chunk(valid, MAX_URLS_PER_REQUEST);
  let successBatches = 0;
  const errors: string[] = [];

  for (let i = 0; i < batches.length; i += 1) {
    const urlList = batches[i];

    if (args.dryRun) {
      successBatches += 1;
      continue;
    }

    const response = await fetch(args.endpoint, {
      method: 'POST',
      headers: {
        'content-type': 'application/json; charset=utf-8',
      },
      body: JSON.stringify({
        host,
        key,
        urlList,
      }),
    });

    if (!response.ok) {
      const text = (await response.text()).slice(0, 500);
      errors.push(`batch ${i + 1}/${batches.length} failed: HTTP ${response.status} ${text}`.trim());
      continue;
    }

    successBatches += 1;
  }

  console.log(
    JSON.stringify(
      {
        ok: errors.length === 0,
        endpoint: args.endpoint,
        host,
        totalInput: inputUrls.length,
        submitted: valid.length,
        skipped: skipped.length,
        batchCount: batches.length,
        successBatches,
        failedBatches: batches.length - successBatches,
        errors,
      },
      null,
      2,
    ),
  );

  if (errors.length > 0) {
    process.exitCode = 1;
  }
}

void main().catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(message);
  process.exit(1);
});
