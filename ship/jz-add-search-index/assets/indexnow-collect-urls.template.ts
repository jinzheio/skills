import { execFileSync } from 'node:child_process';
import { writeFile } from 'node:fs/promises';
import path from 'node:path';

const DEFAULT_BASE_URL = 'https://example.com';

type Args = {
  baseUrl: string;
  from: string;
  to: string;
  outFile: string;
};

const STATIC_ROUTE_MAP = new Map<string, string>([
  ['src/app/page.tsx', '/'],
  ['src/app/about/page.tsx', '/about'],
]);

const GLOBAL_ROUTE_FILES = new Set([
  'src/app/layout.tsx',
  'src/app/sitemap.ts',
  'src/app/robots.ts',
]);

function parseArgs(argv: string[]): Args {
  let baseUrl = DEFAULT_BASE_URL;
  let from = '';
  let to = 'HEAD';
  let outFile = '';

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];

    if (arg === '--base-url') {
      baseUrl = argv[i + 1] ?? baseUrl;
      i += 1;
      continue;
    }

    if (arg === '--from') {
      from = argv[i + 1] ?? '';
      i += 1;
      continue;
    }

    if (arg === '--to') {
      to = argv[i + 1] ?? to;
      i += 1;
      continue;
    }

    if (arg === '--out-file') {
      outFile = argv[i + 1] ?? '';
      i += 1;
      continue;
    }
  }

  if (!from) {
    throw new Error('Missing required arg: --from <git-ref>');
  }

  if (!outFile) {
    throw new Error('Missing required arg: --out-file <path>');
  }

  return { baseUrl, from, to, outFile };
}

function listChangedFiles(from: string, to: string): string[] {
  const output = execFileSync('git', ['diff', '--name-only', `${from}..${to}`], {
    cwd: process.cwd(),
    encoding: 'utf8',
  });

  return output
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function addUrl(urls: Set<string>, baseUrl: string, route: string) {
  const normalizedBase = baseUrl.replace(/\/+$/, '');
  urls.add(route === '/' ? `${normalizedBase}/` : `${normalizedBase}${route}`);
}

function collectUrls(baseUrl: string, changedFiles: string[]): string[] {
  const urls = new Set<string>();

  for (const filePath of changedFiles) {
    if (filePath.startsWith('src/app/api/')) continue;
    if (filePath.startsWith('scripts/')) continue;
    if (filePath.startsWith('src/db/')) continue;

    const staticRoute = STATIC_ROUTE_MAP.get(filePath);
    if (staticRoute) {
      addUrl(urls, baseUrl, staticRoute);
      continue;
    }

    if (GLOBAL_ROUTE_FILES.has(filePath)) {
      for (const route of STATIC_ROUTE_MAP.values()) {
        addUrl(urls, baseUrl, route);
      }
      continue;
    }

    // Add project-specific component-to-route mappings here.
  }

  return Array.from(urls).sort();
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const changedFiles = listChangedFiles(args.from, args.to);
  const urls = collectUrls(args.baseUrl, changedFiles);
  const outPath = path.resolve(args.outFile);

  await writeFile(outPath, urls.join('\n') + (urls.length > 0 ? '\n' : ''), 'utf8');

  console.log(
    JSON.stringify(
      {
        ok: true,
        from: args.from,
        to: args.to,
        changedFiles: changedFiles.length,
        submittedUrls: urls.length,
        outFile: outPath,
        urls,
      },
      null,
      2,
    ),
  );
}

void main().catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(message);
  process.exit(1);
});
