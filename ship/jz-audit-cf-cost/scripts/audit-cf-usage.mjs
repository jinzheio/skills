#!/usr/bin/env node

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const GRAPHQL_ENDPOINT = "https://api.cloudflare.com/client/v4/graphql";
const API_BASE = "https://api.cloudflare.com/client/v4";

const PRODUCT_DATASETS = {
  workers: [
    "workersInvocationsAdaptiveGroups",
    "workersInvocationsAdaptive",
    "workersTraceEventsAdaptiveGroups",
  ],
  kv: ["kvOperationsAdaptiveGroups", "kvStorageAdaptiveGroups"],
  d1: ["d1AnalyticsAdaptiveGroups", "d1StorageAdaptiveGroups"],
  r2: ["r2OperationsAdaptiveGroups", "r2StorageAdaptiveGroups"],
  images: [
    "imageResizingRequestsAdaptiveGroups",
    "imagesRequestsAdaptiveGroups",
    "imagesTransformationsAdaptiveGroups",
  ],
  workersAi: [
    "workersAiInferenceAdaptiveGroups",
    "workersAIInferenceAdaptiveGroups",
    "aiInferenceAdaptiveGroups",
  ],
  queues: ["queueOperationsAdaptiveGroups", "queuesOperationsAdaptiveGroups"],
  durableObjects: [],
  cron: [
    "workersScheduledEventsAdaptiveGroups",
    "workersInvocationsAdaptiveGroups",
  ],
};

const WRANGLER_FILES = ["wrangler.jsonc", "wrangler.json", "wrangler.toml"];
const DEFAULT_ENV_FILES = [".dev.vars", ".env", ".env.local"];
const ACCOUNT_ID_KEYS = ["CLOUDFLARE_ACCOUNT_ID", "CF_ACCOUNT_ID"];
const API_TOKEN_KEYS = ["CLOUDFLARE_API_TOKEN", "CF_API_TOKEN"];
const CURRENT_SCRIPT_PATH = fileURLToPath(import.meta.url);
const MS_PER_DAY = 24 * 60 * 60 * 1000;

function parseArgs(argv) {
  const args = {
    project: ".",
    dryRun: false,
    json: false,
    discoverOnly: false,
    includePaygo: true,
    quotaInputs: [],
  };

  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--dry-run") args.dryRun = true;
    else if (arg === "--json") args.json = true;
    else if (arg === "--discover-only") args.discoverOnly = true;
    else if (arg === "--self-test") args.selfTest = true;
    else if (arg === "--no-paygo") args.includePaygo = false;
    else if (arg === "--project") args.project = argv[++i];
    else if (arg === "--env-file") args.envFile = argv[++i];
    else if (arg === "--from") args.from = argv[++i];
    else if (arg === "--to") args.to = argv[++i];
    else if (arg === "--account-id") args.accountId = argv[++i];
    else if (arg === "--token") {
      i += 1;
      throw new Error("Do not pass Cloudflare API tokens with --token. Put CLOUDFLARE_API_TOKEN or CF_API_TOKEN in .dev.vars, .env, or the process environment.");
    }
    else if (arg === "--estimate-do") args.estimateDo = true;
    else if (arg === "--do-objects") args.doObjects = Number(argv[++i]);
    else if (arg === "--do-hours-per-day") args.doHoursPerDay = Number(argv[++i]);
    else if (arg === "--do-days") args.doDays = Number(argv[++i]);
    else if (arg === "--do-memory-mb") args.doMemoryMb = Number(argv[++i]);
    else if (arg === "--do-free-gbs") args.doFreeGbs = Number(argv[++i]);
    else if (arg === "--do-rate") args.doRate = Number(argv[++i]);
    else if (arg === "--quota-json") args.quotaInputs.push(...readQuotaJson(argv[++i]));
    else if (arg === "--quota") args.quotaInputs.push(parseQuotaArg(argv[++i]));
    else if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  const now = new Date();
  const start = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
  args.usingDefaultPeriod = !args.from && !args.to;
  args.from ??= start.toISOString().slice(0, 10);
  args.to ??= new Date(now.getTime() + MS_PER_DAY).toISOString().slice(0, 10);
  args.doObjects ??= 1;
  args.doHoursPerDay ??= 24;
  args.doDays ??= daysBetween(args.from, args.to);
  args.doMemoryMb ??= 128;
  args.doFreeGbs ??= 400000;
  args.doRate ??= 0.0001;
  return args;
}

function printHelp() {
  console.log(`Usage:
  node <skill-dir>/scripts/audit-cf-usage.mjs --project <repo> [--from YYYY-MM-DD] [--to YYYY-MM-DD]

Options:
  --dry-run          Only parse wrangler config and show datasets that would be queried.
  --discover-only    Query GraphQL schema and list matching datasets.
  --json             Print JSON.
  --env-file PATH    Read Cloudflare credentials from a specific env file before project defaults.
  --no-paygo         Skip Cloudflare Billing PayGo usage endpoint.
  --account-id ID    Override Cloudflare account id. Prefer env files for routine use.
  --self-test        Run local script tests without calling Cloudflare APIs.
  --estimate-do      Estimate Durable Objects duration cost.
  --do-objects N     Durable Objects count for --estimate-do. Defaults to 1.
  --do-hours-per-day N
                    Online hours per object per day. Defaults to 24.
  --do-days N        Days to estimate. Defaults to the analytics date window.
  --do-memory-mb N   Durable Object memory size. Defaults to 128.
  --quota-json PATH  Calculate plan usage ratios from a JSON file.
  --quota SPEC       Calculate one quota row.

Quota SPEC format:
  name=KV reads,used=120000,included=1000000,period=monthly,elapsedDays=10,cycleDays=30
  name=KV reads,used=70000,included=100000,period=daily,last3=60000|70000|80000

Required token permissions for API mode:
  Account: Analytics: Read. PayGo usage is alpha and may also need account billing access.

Credential lookup:
  Account id keys: CLOUDFLARE_ACCOUNT_ID, CF_ACCOUNT_ID.
  API token keys:  CLOUDFLARE_API_TOKEN, CF_API_TOKEN.
  Lookup order: --env-file, .dev.vars, .env, .env.local, process environment.`);
}

function loadCredentialContext(projectDir, explicitEnvFile) {
  const values = {};
  const sources = {};
  const envFiles = explicitEnvFile
    ? [path.resolve(projectDir, explicitEnvFile)]
    : DEFAULT_ENV_FILES.map((file) => path.join(projectDir, file));

  for (const filePath of envFiles) {
    if (!fs.existsSync(filePath)) {
      if (explicitEnvFile) throw new Error(`Env file not found: ${redactPath(filePath)}`);
      continue;
    }
    const parsed = parseEnvFile(fs.readFileSync(filePath, "utf8"));
    const source = explicitEnvFile ? "--env-file" : path.basename(filePath);
    for (const [key, value] of Object.entries(parsed)) {
      if (value !== "" && values[key] === undefined) {
        values[key] = value;
        sources[key] = source;
      }
    }
  }

  for (const key of [...ACCOUNT_ID_KEYS, ...API_TOKEN_KEYS]) {
    if (values[key] === undefined && process.env[key]) {
      values[key] = process.env[key];
      sources[key] = "process.env";
    }
  }

  const accountIdKey = ACCOUNT_ID_KEYS.find((key) => values[key]);
  const tokenKey = API_TOKEN_KEYS.find((key) => values[key]);
  return {
    accountId: values[accountIdKey] ?? null,
    token: values[tokenKey] ?? null,
    accountIdKey: accountIdKey ?? null,
    tokenKey: tokenKey ?? null,
    accountIdSource: accountIdKey ? sources[accountIdKey] : null,
    tokenSource: tokenKey ? sources[tokenKey] : null,
  };
}

function parseEnvFile(input) {
  const values = {};
  for (const rawLine of input.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const normalized = line.startsWith("export ") ? line.slice("export ".length).trim() : line;
    const index = normalized.indexOf("=");
    if (index === -1) continue;
    const key = normalized.slice(0, index).trim();
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) continue;
    values[key] = parseEnvValue(normalized.slice(index + 1).trim());
  }
  return values;
}

function parseEnvValue(value) {
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    const unquoted = value.slice(1, -1);
    return value.startsWith('"')
      ? unquoted.replace(/\\n/g, "\n").replace(/\\"/g, '"').replace(/\\\\/g, "\\")
      : unquoted;
  }
  const commentIndex = value.search(/\s#/);
  return (commentIndex === -1 ? value : value.slice(0, commentIndex)).trim();
}

function redactPath(filePath) {
  return path.basename(filePath);
}

function readQuotaJson(filePath) {
  const raw = fs.readFileSync(filePath, "utf8");
  const parsed = JSON.parse(raw);
  return Array.isArray(parsed) ? parsed : parsed.items ?? [];
}

function parseQuotaArg(spec) {
  const item = {};
  for (const part of spec.split(",")) {
    const index = part.indexOf("=");
    if (index === -1) continue;
    const key = part.slice(0, index).trim();
    const value = part.slice(index + 1).trim();
    if (["used", "included", "elapsedDays", "cycleDays", "rate"].includes(key)) {
      item[key] = Number(value);
    } else if (key === "last3") {
      item.last3 = value.split("|").map(Number).filter((number) => !Number.isNaN(number));
    } else {
      item[key] = value;
    }
  }
  return item;
}

function daysBetween(from, to) {
  const start = new Date(`${from}T00:00:00.000Z`);
  const end = new Date(`${to}T00:00:00.000Z`);
  return Math.max(1, Math.ceil((end.getTime() - start.getTime()) / MS_PER_DAY));
}

function findWranglerConfig(projectDir) {
  for (const file of WRANGLER_FILES) {
    const fullPath = path.join(projectDir, file);
    if (fs.existsSync(fullPath)) return fullPath;
  }
  return null;
}

function resolveProjectDir(projectArg) {
  let current = path.resolve(projectArg);
  if (fs.existsSync(current) && !fs.statSync(current).isDirectory()) {
    current = path.dirname(current);
  }
  while (true) {
    if (hasProjectMarker(current)) return current;
    const parent = path.dirname(current);
    if (parent === current) return path.resolve(projectArg);
    current = parent;
  }
}

function hasProjectMarker(dir) {
  return Boolean(findWranglerConfig(dir) || fs.existsSync(path.join(dir, "package.json")));
}

function stripJsonc(input) {
  return input
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1")
    .replace(/,\s*([}\]])/g, "$1");
}

function parseTomlSubset(input) {
  const root = {};
  let current = root;
  for (const rawLine of input.split(/\r?\n/)) {
    const line = rawLine.replace(/#.*$/, "").trim();
    if (!line) continue;
    const arrayTableMatch = line.match(/^\[\[([^\]]+)\]\]$/);
    if (arrayTableMatch) {
      current = ensureTomlArrayTable(root, arrayTableMatch[1]);
      continue;
    }
    const objectTableMatch = line.match(/^\[([^\]]+)\]$/);
    if (objectTableMatch) {
      current = ensureTomlObjectTable(root, objectTableMatch[1]);
      continue;
    }
    const pair = line.match(/^([A-Za-z0-9_."-]+)\s*=\s*(.+)$/);
    if (!pair) continue;
    const key = pair[1].replaceAll('"', "");
    const value = pair[2].trim();
    current[key] = parseTomlValue(value);
  }
  return root;
}

function ensureTomlObjectTable(root, tableName) {
  let current = root;
  for (const part of tomlPath(tableName)) {
    if (!current[part] || typeof current[part] !== "object" || Array.isArray(current[part])) {
      current[part] = {};
    }
    current = current[part];
  }
  return current;
}

function ensureTomlArrayTable(root, tableName) {
  const parts = tomlPath(tableName);
  let current = root;
  for (const part of parts.slice(0, -1)) {
    if (!current[part] || typeof current[part] !== "object" || Array.isArray(current[part])) {
      current[part] = {};
    }
    current = current[part];
  }
  const last = parts.at(-1);
  if (!Array.isArray(current[last])) current[last] = [];
  const item = {};
  current[last].push(item);
  return item;
}

function tomlPath(tableName) {
  return tableName.split(".").map((part) => part.trim().replace(/^"|"$/g, ""));
}

function parseTomlValue(value) {
  if (value.startsWith("[") && value.endsWith("]")) {
    return value
      .slice(1, -1)
      .split(",")
      .map((item) => item.trim().replace(/^"|"$/g, ""))
      .filter(Boolean);
  }
  if (value === "true") return true;
  if (value === "false") return false;
  return value.replace(/^"|"$/g, "");
}

function readWranglerConfig(configPath) {
  if (!configPath) return { config: {}, parseWarning: "No wrangler config found." };
  const raw = fs.readFileSync(configPath, "utf8");
  try {
    if (configPath.endsWith(".toml")) return { config: parseTomlSubset(raw) };
    return { config: JSON.parse(stripJsonc(raw)) };
  } catch (error) {
    return { config: {}, parseWarning: `Could not parse wrangler config: ${error.message}` };
  }
}

function asArray(value) {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

function detectResources(config, projectDir) {
  const resources = [];
  const push = (type, name, detail = {}) => resources.push({ type, name, ...detail });

  collectConfiguredResources(config, push);
  for (const [environment, envConfig] of Object.entries(config.env ?? {})) {
    if (envConfig && typeof envConfig === "object" && !Array.isArray(envConfig)) {
      collectConfiguredResources(envConfig, push, environment);
    }
  }

  const packageHint = readPackageHint(projectDir);
  if (!resources.some((resource) => resource.type === "workers") && packageHint.isCloudflareProject) {
    push("workers", packageHint.name ?? "(package hint)", {
      source: "package.json",
      framework: packageHint.framework,
    });
  }

  const codeHints = scanCodeHints(projectDir);
  if (codeHints.workersAi) {
    push("workersAi", "(code reference)", {
      source: "code-scan",
      sourceFiles: codeHints.workersAiFiles,
    });
  }
  if (codeHints.imageTransforms) {
    push("images", "(code reference)", {
      source: "code-scan",
      sourceFiles: codeHints.imageTransformFiles,
    });
  }
  if (codeHints.externalImageHosts.length > 0) {
    push("images", "(external image hosts)", {
      source: "code-scan",
      hosts: codeHints.externalImageHosts.slice(0, 8),
      sourceFiles: codeHints.externalImageHostFiles,
      note: "Host reference only. Confirm whether these zones or R2 buckets are in the same account.",
    });
  }

  return dedupeResources(resources);
}

function collectConfiguredResources(config, push, environment = null) {
  const withEnvironment = (detail = {}) => (environment ? { ...detail, environment } : detail);
  if (config.name || config.main || config.assets) {
    push("workers", config.name ?? "(unnamed worker)", withEnvironment({
      hasAssets: Boolean(config.assets),
      observability: Boolean(config.observability?.enabled),
    }));
  }

  for (const item of asArray(config.kv_namespaces)) {
    push("kv", item.binding, withEnvironment({
      idPresent: Boolean(item.id),
      previewIdPresent: Boolean(item.preview_id),
    }));
  }
  for (const item of asArray(config.d1_databases)) {
    push("d1", item.binding, withEnvironment({
      databaseName: item.database_name,
      databaseIdPresent: Boolean(item.database_id),
    }));
  }
  for (const item of asArray(config.r2_buckets)) {
    push("r2", item.binding, withEnvironment({ bucketName: item.bucket_name }));
  }
  for (const item of asArray(config.durable_objects?.bindings)) {
    push("durableObjects", item.name, withEnvironment({ className: item.class_name }));
  }
  for (const item of asArray(config.queues?.producers)) {
    push("queues", item.binding, withEnvironment({ queue: item.queue }));
  }
  for (const item of asArray(config.queues?.consumers)) {
    push("queues", item.queue, withEnvironment({ consumer: true }));
  }
  for (const cron of asArray(config.triggers?.crons)) {
    push("cron", cron, withEnvironment());
  }
  for (const item of asArray(config.ai)) {
    push("workersAi", item.binding ?? "AI", withEnvironment());
  }
}

function readPackageHint(projectDir) {
  const packagePath = path.join(projectDir, "package.json");
  if (!fs.existsSync(packagePath)) return { isCloudflareProject: false };
  try {
    const pkg = JSON.parse(fs.readFileSync(packagePath, "utf8"));
    const allDeps = {
      ...(pkg.dependencies ?? {}),
      ...(pkg.devDependencies ?? {}),
    };
    const scripts = Object.values(pkg.scripts ?? {}).join("\n");
    const isCloudflareProject = Boolean(
      allDeps["@astrojs/cloudflare"] ||
        allDeps["@cloudflare/next-on-pages"] ||
        allDeps["@cloudflare/vite-plugin"] ||
        allDeps["@opennextjs/cloudflare"] ||
        allDeps["@sveltejs/adapter-cloudflare"] ||
        allDeps.wrangler ||
        /wrangler\s+(deploy|pages\s+deploy)/.test(scripts),
    );
    const framework =
      (allDeps["@astrojs/cloudflare"] && "astro-cloudflare") ||
      (allDeps["@cloudflare/next-on-pages"] && "next-on-pages") ||
      (allDeps["@opennextjs/cloudflare"] && "opennext-cloudflare") ||
      (allDeps["@sveltejs/adapter-cloudflare"] && "sveltekit-cloudflare") ||
      (allDeps["@cloudflare/vite-plugin"] && "cloudflare-vite") ||
      undefined;
    return {
      isCloudflareProject,
      name: pkg.name,
      framework,
    };
  } catch {
    return { isCloudflareProject: false };
  }
}

function scanCodeHints(projectDir) {
  const hints = {
    workersAi: false,
    imageTransforms: false,
    externalImageHosts: [],
    workersAiFiles: [],
    imageTransformFiles: [],
    externalImageHostFiles: [],
  };
  const files = [];
  collectFiles(projectDir, files, 0);
  const hostSet = new Set();
  const hostFiles = new Set();

  for (const file of files) {
    const text = fs.readFileSync(file, "utf8");
    const relativeFile = path.relative(projectDir, file);
    if (/\bAI\.run\b|\benv\.AI\b/.test(text)) {
      hints.workersAi = true;
      hints.workersAiFiles.push(relativeFile);
    }
    if (/\/cdn-cgi\/image\/|cf:\s*{\s*image|image\s*:\s*{\s*(width|height|quality|fit)/.test(text)) {
      hints.imageTransforms = true;
      hints.imageTransformFiles.push(relativeFile);
    }
    for (const match of text.matchAll(/https:\/\/(images\.[A-Za-z0-9.-]+)/g)) {
      hostSet.add(match[1]);
      hostFiles.add(relativeFile);
    }
  }

  hints.externalImageHosts = [...hostSet].sort();
  hints.workersAiFiles = hints.workersAiFiles.slice(0, 8);
  hints.imageTransformFiles = hints.imageTransformFiles.slice(0, 8);
  hints.externalImageHostFiles = [...hostFiles].sort().slice(0, 8);
  return hints;
}

function scanCostRiskFindings(projectDir) {
  const files = [];
  collectFiles(projectDir, files, 0);
  const findings = [];
  for (const file of files) {
    const text = fs.readFileSync(file, "utf8");
    const relativeFile = path.relative(projectDir, file);
    findings.push(...detectQueueLoopRisks(text, relativeFile));
    findings.push(...detectDurableObjectWriteRisks(text, relativeFile));
    findings.push(...detectKvListRisks(text, relativeFile));
  }
  return dedupeFindings(findings);
}

function detectQueueLoopRisks(text, file) {
  const findings = [];
  const hasQueueConsumer =
    /\bqueue\s*\(|\bMessageBatch\b|\bQueue\b|\.sendBatch\s*\(|\.send\s*\(/.test(text) &&
    /\bfetch\s*\(|\bwrite_mode\b|\bwriteMode\b|\bmode\b/.test(text);
  const forwardsAsyncMode =
    /write_mode\s*:\s*[^,\n]*(message|msg|body|payload|request|data)\.[A-Za-z0-9_.-]+/.test(text) ||
    /writeMode\s*:\s*[^,\n]*(message|msg|body|payload|request|data)\.[A-Za-z0-9_.-]+/.test(text);
  const internalFetch =
    /\bfetch\s*\(\s*([`'"]\/|new URL\s*\(|[A-Za-z0-9_]+\.url|request\.url)/.test(text) ||
    /\bfetch\s*\([^)]*\/v[0-9]\//s.test(text);
  const forcesSync =
    /write_mode\s*:\s*["']sync["']|writeMode\s*:\s*["']sync["']|mode\s*:\s*["']sync["']/.test(text);

  if (hasQueueConsumer && internalFetch && forwardsAsyncMode && !forcesSync) {
    findings.push({
      id: "queue-internal-call-may-requeue",
      severity: "high",
      file,
      evidence: "Queue-like code makes an internal fetch and appears to forward write_mode/writeMode from the message.",
      whyItMatters: "A queue consumer that calls the public async path can requeue the same work and multiply Queue, KV, and DO operations.",
      recommendation: "Force sync/direct mode on internal queue-consumer calls, or call the write function directly instead of the public async endpoint.",
    });
  }
  return findings;
}

function detectDurableObjectWriteRisks(text, file) {
  const findings = [];
  const storagePutMatches = [...text.matchAll(/\b(state\.)?storage\.put\s*\(/g)];
  const hasDurableObjectShape = /\bDurableObject\b|state\.storage|ctx\.storage|constructor\s*\(\s*state\s*,\s*env\s*\)/.test(text);
  if (hasDurableObjectShape && storagePutMatches.length >= 4) {
    findings.push({
      id: "many-durable-object-storage-puts",
      severity: storagePutMatches.length >= 8 ? "high" : "medium",
      file,
      evidence: `${storagePutMatches.length} storage.put() call sites in one file.`,
      whyItMatters: "Unbatched Durable Object writes can turn one logical user write into many billable storage row writes.",
      recommendation: "Batch related state updates, remove redundant job-state mirrors, and prefer TTL expiry over explicit ack/delete writes when possible.",
    });
  }
  if (/storage\.put\s*\([^)]*\)\s*;?\s*[\r\n]+\s*storage\.put\s*\(/s.test(text)) {
    findings.push({
      id: "adjacent-durable-object-storage-puts",
      severity: "medium",
      file,
      evidence: "Adjacent storage.put() calls found.",
      whyItMatters: "Adjacent writes are often batchable and can double or triple DO write volume.",
      recommendation: "Combine related values into one object or use a single batched write where the API allows it.",
    });
  }
  return findings;
}

function detectKvListRisks(text, file) {
  const findings = [];
  const listMatches = [
    ...text.matchAll(/\b(?:env|context\.env|ctx\.env|this\.env)\.[A-Z0-9_]+\.list\s*\(/g),
    ...text.matchAll(/\b[A-Z0-9_]*(?:KV|KEYS|CACHE|NAMESPACE)[A-Z0-9_]*\.list\s*\(/g),
  ];
  if (listMatches.length === 0) return findings;

  const hasAuthContext = /api[_-]?key|authorization|bearer|auth|token/i.test(text);
  const hasFallbackContext = /fallback|legacy|miss|not\s+found|if\s*\(|catch\s*\(/i.test(text);
  findings.push({
    id: hasAuthContext ? "kv-list-in-auth-path" : "kv-list-in-request-path",
    severity: hasAuthContext ? "high" : "medium",
    file,
    evidence: `${listMatches.length} KV-like list() call site(s)${hasAuthContext ? " in auth/API-key context" : ""}.`,
    whyItMatters: "KV list operations are billable and become expensive when used as a per-request fallback.",
    recommendation: hasFallbackContext
      ? "Gate legacy scans behind a kill switch, backfill lookup indexes, and log/count every fallback hit."
      : "Confirm list() is not on the hot request path; prefer direct key lookup or an indexed mapping.",
  });
  return findings;
}

function dedupeFindings(findings) {
  const seen = new Set();
  return findings.filter((finding) => {
    const key = `${finding.id}:${finding.file}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function collectFiles(dir, files, depth) {
  if (depth > 4 || files.length > 400) return;
  const skip = new Set([
    ".agents",
    ".astro",
    ".git",
    ".next",
    ".open-next",
    ".svelte-kit",
    ".turbo",
    ".vercel",
    ".wrangler",
    ".wrangler-dry-run",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "out",
  ]);
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (skip.has(entry.name)) continue;
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) collectFiles(fullPath, files, depth + 1);
    else if (fullPath !== CURRENT_SCRIPT_PATH && /\.(js|jsx|mjs|cjs|ts|tsx|astro|vue|svelte)$/.test(entry.name)) files.push(fullPath);
  }
}

function dedupeResources(resources) {
  const seen = new Set();
  return resources.filter((resource) => {
    const key = `${resource.type}:${resource.name}:${resource.environment ?? ""}:${resource.source ?? ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function productsForResources(resources) {
  const products = new Set();
  for (const resource of resources) {
    if (resource.type === "durableObjects") products.add("durableObjects");
    else if (resource.type === "cron") products.add("workers");
    else products.add(resource.type);
  }
  return [...products];
}

function detectResourceCombinationRisks(resources) {
  const types = new Set(resources.map((resource) => resource.type));
  const findings = [];
  if (types.has("queues") && types.has("durableObjects") && types.has("kv")) {
    findings.push({
      id: "queue-do-kv-amplification-combo",
      severity: "medium",
      file: "wrangler config",
      evidence: "Project uses Queues, Durable Objects, and KV together.",
      whyItMatters: "Queue retries or internal requeue loops can multiply both DO storage writes and KV read/write/list operations.",
      recommendation: "Audit queue consumers for idempotency, forced sync internal writes, bounded retries, and per-message operation counts.",
    });
  }
  return findings;
}

async function cloudflareFetch(url, token, init = {}) {
  const response = await fetch(url, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  const json = await response.json().catch(() => ({}));
  if (!response.ok || json.success === false) {
    const message = json.errors?.map((error) => error.message).join("; ") || response.statusText;
    throw new Error(message);
  }
  return json;
}

async function discoverAccountDatasets(token) {
  const query = `query {
    __type(name: "Account") {
      fields {
        name
        args {
          name
          type {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
              }
            }
          }
        }
      }
    }
  }`;
  const json = await cloudflareFetch(GRAPHQL_ENDPOINT, token, {
    method: "POST",
    body: JSON.stringify({ query }),
  });
  return json.data?.__type?.fields?.sort((a, b) => a.name.localeCompare(b.name)) ?? [];
}

async function discoverInputFieldNames(token, typeName) {
  const query = `query ($typeName: String!) {
    __type(name: $typeName) {
      inputFields {
        name
      }
    }
  }`;
  const json = await cloudflareFetch(GRAPHQL_ENDPOINT, token, {
    method: "POST",
    body: JSON.stringify({ query, variables: { typeName } }),
  });
  return json.data?.__type?.inputFields?.map((field) => field.name).sort() ?? [];
}

function matchDatasets(products, accountFields) {
  const fieldMap = new Map(accountFields.map((field) => [field.name, field]));
  const matched = {};
  for (const product of products) {
    matched[product] = (PRODUCT_DATASETS[product] ?? [])
      .filter((name) => fieldMap.has(name))
      .map((name) => {
        const field = fieldMap.get(name);
        return {
          name,
          filterType: unwrapType(field.args?.find((arg) => arg.name === "filter")?.type),
        };
      });
  }
  return matched;
}

function unwrapType(type) {
  let current = type;
  while (current?.ofType) current = current.ofType;
  return current?.name ?? null;
}

async function queryDatasetProbe({ accountId, token, dataset, filterType, filter }) {
  if (!filterType) throw new Error("No filter argument found in schema.");
  const query = `query ($accountTag: String, $filter: ${filterType}) {
    viewer {
      accounts(filter: { accountTag: $accountTag }) {
        ${dataset}(filter: $filter, limit: 1) {
          __typename
        }
      }
    }
  }`;
  const variables = {
    accountTag: accountId,
    filter,
  };
  return cloudflareFetch(GRAPHQL_ENDPOINT, token, {
    method: "POST",
    body: JSON.stringify({ query, variables }),
  });
}

function buildDateFilter(filterFieldNames, from, to) {
  const fields = new Set(filterFieldNames);
  if (fields.has("date_geq") && fields.has("date_lt")) {
    return { date_geq: from, date_lt: to };
  }
  if (fields.has("datetime_geq") && fields.has("datetime_lt")) {
    return { datetime_geq: `${from}T00:00:00Z`, datetime_lt: `${to}T00:00:00Z` };
  }
  if (fields.has("datetime_geq") && fields.has("datetime_leq")) {
    return { datetime_geq: `${from}T00:00:00Z`, datetime_leq: `${to}T00:00:00Z` };
  }
  return { date_geq: from, date_lt: to };
}

async function fetchPaygoUsage({ accountId, token, from, to, usingDefaultPeriod }) {
  const url = new URL(`${API_BASE}/accounts/${accountId}/paygo-usage`);
  if (!usingDefaultPeriod) {
    if (from) url.searchParams.set("from", from);
    if (to) url.searchParams.set("to", to);
  }
  return cloudflareFetch(url, token);
}

function estimateDurableObjects(args) {
  const memoryGb = args.doMemoryMb / 1024;
  const seconds = args.doObjects * args.doHoursPerDay * 3600 * args.doDays;
  const durationGbs = seconds * memoryGb;
  const billableGbs = Math.max(0, durationGbs - args.doFreeGbs);
  const estimatedUsd = billableGbs * args.doRate;
  const elapsedDays = args.doDays;
  const cycleDays = daysInUtcMonth(args.from);
  const projectedDurationGbs = (durationGbs / elapsedDays) * cycleDays;
  const projectedBillableGbs = Math.max(0, projectedDurationGbs - args.doFreeGbs);
  const usedPlanRatio = ratio(durationGbs, args.doFreeGbs);
  const projectedPlanRatio = ratio(projectedDurationGbs, args.doFreeGbs);
  return {
    objects: args.doObjects,
    hoursPerDay: args.doHoursPerDay,
    days: args.doDays,
    memoryMb: args.doMemoryMb,
    durationGbs,
    projectedDurationGbs,
    freeGbs: args.doFreeGbs,
    billableGbs,
    projectedBillableGbs,
    rateUsdPerGbs: args.doRate,
    estimatedUsd,
    projectedUsd: projectedBillableGbs * args.doRate,
    usedPlanRatio,
    projectedPlanRatio,
  };
}

function calculateQuotaRows(items, defaults) {
  return items.map((item) => calculateQuotaRow(item, defaults));
}

function calculateQuotaRow(item, defaults) {
  const period = item.period ?? "monthly";
  const included = Number(item.included);
  const used = Number(item.used);
  const elapsedDays = Number(item.elapsedDays ?? defaults.elapsedDays);
  const cycleDays = Number(item.cycleDays ?? defaults.cycleDays);
  const last3 = Array.isArray(item.last3) ? item.last3.map(Number).filter((value) => !Number.isNaN(value)) : [];
  const recentAverage = last3.length > 0 ? sum(last3.slice(-3)) / Math.min(3, last3.length) : null;
  const projectedUsed =
    period === "daily"
      ? recentAverage
      : (used / Math.max(1, elapsedDays)) * cycleDays;
  const billableUsed =
    period === "daily"
      ? Math.max(0, used - included)
      : Math.max(0, used - included);
  const projectedBillableUsed =
    period === "daily"
      ? (recentAverage === null ? null : Math.max(0, recentAverage - included))
      : Math.max(0, projectedUsed - included);
  const rate = item.rate === undefined ? null : Number(item.rate);
  return {
    name: item.name,
    product: item.product ?? null,
    metric: item.metric ?? null,
    unit: item.unit ?? null,
    period,
    used,
    included,
    elapsedDays,
    cycleDays,
    last3,
    recent3DayAverage: recentAverage,
    usedPlanRatio: ratio(used, included),
    projectedUsed,
    projectedPlanRatio: ratio(projectedUsed, included),
    billableUsed,
    projectedBillableUsed,
    estimatedCost: rate === null ? null : billableUsed * rate,
    projectedCost: rate === null || projectedBillableUsed === null ? null : projectedBillableUsed * rate,
  };
}

function sum(values) {
  return values.reduce((total, value) => total + value, 0);
}

function daysInUtcMonth(dateText) {
  const date = new Date(`${dateText}T00:00:00.000Z`);
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0)).getUTCDate();
}

function ratio(used, included) {
  if (used === null || used === undefined || Number.isNaN(used)) return null;
  if (!included || included <= 0) return null;
  return used / included;
}

function buildUsageRows(result) {
  const rows = [];
  if (result.quotaRows?.length) {
    rows.push(...result.quotaRows.map(usageRowFromQuotaRow));
  }
  if (result.estimates?.durableObjects) {
    rows.push(usageRowFromDurableObjectEstimate(result.estimates.durableObjects));
  }
  if (result.paygoUsage) {
    rows.push(...extractPaygoUsageRows(result.paygoUsage));
  }
  return rows;
}

function usageRowFromQuotaRow(row) {
  return {
    product: row.product ?? null,
    metric: row.metric ?? row.name ?? null,
    source: "manual-quota",
    sourceDetail: row.name ?? null,
    period: row.period,
    used: finiteOrNull(row.used),
    unit: row.unit ?? null,
    included: finiteOrNull(row.included),
    billableUsed: finiteOrNull(row.billableUsed),
    projectedUsed: finiteOrNull(row.projectedUsed),
    usedPlanRatio: finiteOrNull(row.usedPlanRatio),
    projectedPlanRatio: finiteOrNull(row.projectedPlanRatio),
    estimatedCostUsd: finiteOrNull(row.estimatedCost),
    projectedCostUsd: finiteOrNull(row.projectedCost),
    confidence: "high",
    note: null,
  };
}

function usageRowFromDurableObjectEstimate(estimate) {
  return {
    product: "Durable Objects",
    metric: "duration",
    source: "local-estimate",
    sourceDetail: `${estimate.objects} objects, ${estimate.hoursPerDay} hours/day, ${estimate.memoryMb} MB`,
    period: "monthly",
    used: estimate.durationGbs,
    unit: "GB-s",
    included: estimate.freeGbs,
    billableUsed: estimate.billableGbs,
    projectedUsed: estimate.projectedDurationGbs,
    usedPlanRatio: estimate.usedPlanRatio,
    projectedPlanRatio: estimate.projectedPlanRatio,
    estimatedCostUsd: estimate.estimatedUsd,
    projectedCostUsd: estimate.projectedUsd,
    confidence: "medium",
    note: "Estimated from object count, online hours, days, and memory size.",
  };
}

function extractPaygoUsageRows(paygoUsage) {
  const candidates = [];
  collectObjects(paygoUsage, candidates, []);
  const rows = [];
  for (const candidate of candidates) {
    const row = usageRowFromPaygoObject(candidate.object, candidate.path);
    if (row) rows.push(row);
  }
  return dedupeUsageRows(rows);
}

function collectObjects(value, output, pathParts) {
  if (!value || typeof value !== "object") return;
  if (Array.isArray(value)) {
    value.forEach((item, index) => collectObjects(item, output, [...pathParts, String(index)]));
    return;
  }
  output.push({ object: value, path: pathParts.join(".") || "$" });
  for (const [key, child] of Object.entries(value)) {
    collectObjects(child, output, [...pathParts, key]);
  }
}

function usageRowFromPaygoObject(object, sourcePath) {
  const used = firstNumber(object, ["usage", "used", "quantity", "value", "count", "requests", "units"]);
  const estimatedCostUsd = firstNumber(object, ["cost", "amount", "total", "subtotal", "price", "estimatedCost"]);
  const product = firstString(object, ["product", "service", "serviceName", "name", "resource", "resourceType"]);
  const metric = firstString(object, ["metric", "usageType", "unit", "billingMetric", "measure", "sku"]);
  if (used === null && estimatedCostUsd === null) return null;
  if (!product && !metric) return null;
  return {
    product,
    metric,
    source: "paygo-usage",
    sourceDetail: sourcePath,
    period: null,
    used,
    unit: firstString(object, ["unit", "unitName", "usageUnit"]),
    included: firstNumber(object, ["included", "free", "allowance"]),
    billableUsed: firstNumber(object, ["billable", "billableUsage", "billableQuantity"]),
    projectedUsed: null,
    usedPlanRatio: null,
    projectedPlanRatio: null,
    estimatedCostUsd,
    projectedCostUsd: null,
    confidence: "low",
    note: "Extracted from PayGo raw response. Confirm field meanings before using as invoice data.",
  };
}

function firstNumber(object, keys) {
  for (const key of keys) {
    const value = object[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value))) {
      return Number(value);
    }
  }
  return null;
}

function firstString(object, keys) {
  for (const key of keys) {
    const value = object[key];
    if (typeof value === "string" && value.trim() !== "") return value.trim();
  }
  return null;
}

function finiteOrNull(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function dedupeUsageRows(rows) {
  const seen = new Set();
  return rows.filter((row) => {
    const key = [
      row.product,
      row.metric,
      row.source,
      row.sourceDetail,
      row.used,
      row.estimatedCostUsd,
    ].join("|");
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function buildDryRun({ projectDir, configPath, config, parseWarning, resources, products, from, to, usingDefaultPeriod }) {
  return {
    project: path.basename(projectDir),
    wranglerConfig: configPath ? path.basename(configPath) : null,
    workerName: config.name ?? null,
    dateRange: {
      from,
      to,
      timezone: "UTC",
      note: usingDefaultPeriod
        ? "GraphQL analytics defaults to current UTC month through tomorrow; PayGo defaults to Cloudflare current billing period."
        : "Explicit date range.",
    },
    parseWarning,
    resources,
    riskFindings: dedupeFindings([
      ...scanCostRiskFindings(projectDir),
      ...detectResourceCombinationRisks(resources),
    ]),
    products,
    plannedDatasets: Object.fromEntries(
      products.map((product) => [product, PRODUCT_DATASETS[product] ?? []]),
    ),
  };
}

function printText(result) {
  console.log(`Project: ${result.project}`);
  console.log(`Wrangler config: ${result.wranglerConfig ?? "not found"}`);
  console.log(`Range: ${result.dateRange.from} to ${result.dateRange.to} (UTC date_lt)`);
  if (result.credentials) {
    console.log(`Credentials: account id ${result.credentials.accountId}${formatSource(result.credentials.accountIdSource)}, API token ${result.credentials.apiToken}${formatSource(result.credentials.apiTokenSource)}`);
  }
  if (result.parseWarning) console.log(`Warning: ${result.parseWarning}`);

  console.log("\nDetected resources:");
  for (const resource of result.resources) {
    const details = [resource.environment ? `env: ${resource.environment}` : null, resource.note].filter(Boolean);
    const suffix = details.length ? ` (${details.join("; ")})` : "";
    console.log(`- ${resource.type}: ${resource.name}${suffix}`);
    if (resource.sourceFiles?.length) {
      console.log(`  source files: ${resource.sourceFiles.join(", ")}`);
    }
  }
  if (result.resources.length === 0) console.log("- none");

  console.log("\nProducts to monitor:");
  for (const product of result.products) console.log(`- ${product}`);
  if (result.products.length === 0) console.log("- none");

  if (result.plannedDatasets) {
    console.log("\nGraphQL datasets to try:");
    if (Object.keys(result.plannedDatasets).length === 0) console.log("- none");
    for (const [product, datasets] of Object.entries(result.plannedDatasets)) {
      console.log(`- ${product}: ${datasets.join(", ") || "none"}`);
    }
  }

  if (result.riskFindings?.length) {
    console.log("\nCost risk findings:");
    for (const finding of result.riskFindings) {
      console.log(`- [${finding.severity}] ${finding.id}: ${finding.file}`);
      console.log(`  evidence: ${finding.evidence}`);
      console.log(`  why: ${finding.whyItMatters}`);
      console.log(`  fix: ${finding.recommendation}`);
    }
  }

  if (result.matchedDatasets) {
    console.log("\nDatasets found in this account schema:");
    for (const [product, datasets] of Object.entries(result.matchedDatasets)) {
      const names = datasets.map((dataset) => dataset.name);
      console.log(`- ${product}: ${names.join(", ") || "not found"}`);
    }
  }

  if (result.datasetProbes?.length) {
    console.log("\nDataset probes:");
    for (const probe of result.datasetProbes) {
      console.log(`- ${probe.dataset}: ${probe.status}, filter ${JSON.stringify(probe.filter)}`);
    }
  }

  if (result.paygoUsage) {
    console.log("\nPayGo usage endpoint:");
    console.log(JSON.stringify(result.paygoUsage, null, 2));
  }
  if (result.paygoError) {
    console.log("\nPayGo usage endpoint:");
    console.log(`- unavailable: ${result.paygoError}`);
  }

  if (result.usageRows?.length) {
    console.log("\nUsage rows:");
    for (const row of result.usageRows) {
      const label = [row.product, row.metric].filter(Boolean).join(" / ") || "(unknown)";
      console.log(`- ${label}`);
      console.log(`  source: ${row.source}${row.sourceDetail ? ` (${row.sourceDetail})` : ""}`);
      console.log(`  used: ${formatNumber(row.used)}${row.unit ? ` ${row.unit}` : ""}`);
      console.log(`  included: ${formatNumber(row.included)}${row.unit ? ` ${row.unit}` : ""}`);
      console.log(`  billable: ${formatNumber(row.billableUsed)}${row.unit ? ` ${row.unit}` : ""}`);
      console.log(`  projected: ${formatNumber(row.projectedUsed)}${row.unit ? ` ${row.unit}` : ""}`);
      console.log(`  used / plan included: ${formatPercent(row.usedPlanRatio)}`);
      console.log(`  projected / plan included: ${formatPercent(row.projectedPlanRatio)}`);
      console.log(`  estimated cost: ${formatUsd(row.estimatedCostUsd)}`);
      console.log(`  projected cost: ${formatUsd(row.projectedCostUsd)}`);
      console.log(`  confidence: ${row.confidence}`);
      if (row.note) console.log(`  note: ${row.note}`);
    }
  }

  if (result.queryErrors?.length) {
    console.log("\nQuery errors:");
    for (const error of result.queryErrors) console.log(`- ${error.dataset}: ${error.message}`);
  }
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "unknown";
  return `${(value * 100).toFixed(1)}%`;
}

function formatSource(source) {
  return source ? ` from ${source}` : "";
}

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "unknown";
  return Number(value).toLocaleString("en-US", { maximumFractionDigits: 2 });
}

function formatUsd(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "unknown";
  return `$${Number(value).toFixed(2)}`;
}

function runSelfTest() {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "cf-cost-audit-"));
  try {
    const envProject = path.join(tempRoot, "env-project");
    fs.mkdirSync(envProject, { recursive: true });
    fs.writeFileSync(
      path.join(envProject, ".dev.vars"),
      "CF_ACCOUNT_ID=dummy-account-id\nCF_API_TOKEN=\"dummy-api-key-value\"\n",
    );
    const credentials = loadCredentialContext(envProject);
    assertEqual(credentials.accountId, "dummy-account-id", "loads account id from .dev.vars");
    assertEqual(credentials.token, "dummy-api-key-value", "loads API token from .dev.vars");
    assertEqual(credentials.accountIdSource, ".dev.vars", "records account id source");

    const docsOnlyProject = path.join(tempRoot, "docs-only");
    fs.mkdirSync(docsOnlyProject, { recursive: true });
    fs.writeFileSync(path.join(docsOnlyProject, "README.md"), "env.AI and /cdn-cgi/image/ are only docs.");
    const docsOnlyResources = detectResources({}, docsOnlyProject);
    assertEqual(docsOnlyResources.length, 0, "ignores documentation-only Cloudflare references");
    fs.mkdirSync(path.join(docsOnlyProject, ".next", "server"), { recursive: true });
    fs.writeFileSync(path.join(docsOnlyProject, ".next", "server", "compiled.js"), "env.API_KEYS.list({ prefix: 'legacy:' })");
    assertEqual(scanCostRiskFindings(docsOnlyProject).length, 0, "ignores generated build directories");

    const codeProject = path.join(tempRoot, "code-project");
    fs.mkdirSync(path.join(codeProject, "src"), { recursive: true });
    fs.writeFileSync(
      path.join(codeProject, "src", "worker.ts"),
      "export default { async fetch(request, env) { await env.AI.run('model'); return fetch('/cdn-cgi/image/width=100/a.png'); } };",
    );
    const codeResources = detectResources({}, codeProject);
    assertTruthy(codeResources.some((resource) => resource.type === "workersAi"), "detects Workers AI code references");
    assertTruthy(codeResources.some((resource) => resource.type === "images"), "detects image transform code references");
    assertTruthy(
      codeResources.every((resource) => !resource.sourceFiles || resource.sourceFiles.every((file) => !path.isAbsolute(file))),
      "reports source files as relative paths",
    );

    const riskyProject = path.join(tempRoot, "risky-project");
    fs.mkdirSync(path.join(riskyProject, "src"), { recursive: true });
    fs.writeFileSync(
      path.join(riskyProject, "src", "consumer.ts"),
      `
export default {
  async queue(batch, env) {
    for (const message of batch.messages) {
      await fetch("/v1/memory", {
        method: "POST",
        body: JSON.stringify({ write_mode: message.body.write_mode || "async" })
      });
    }
  }
}
`,
    );
    fs.writeFileSync(
      path.join(riskyProject, "src", "room.ts"),
      `
export class Room extends DurableObject {
  async write(state) {
    await this.ctx.storage.put("a", state.a);
    await this.ctx.storage.put("b", state.b);
    await this.ctx.storage.put("c", state.c);
    await this.ctx.storage.put("d", state.d);
  }
}
`,
    );
    fs.writeFileSync(
      path.join(riskyProject, "src", "auth.ts"),
      `
export async function authenticate(env, token) {
  const found = await env.API_KEYS.get(token);
  if (!found) {
    const keys = await env.API_KEYS.list({ prefix: "legacy:" });
    return keys.keys.find((key) => key.name === token);
  }
  return found;
}
`,
    );
    const riskFindings = scanCostRiskFindings(riskyProject);
    assertTruthy(riskFindings.some((finding) => finding.id === "queue-internal-call-may-requeue"), "detects queue internal requeue risk");
    assertTruthy(riskFindings.some((finding) => finding.id === "many-durable-object-storage-puts"), "detects repeated DO storage.put risk");
    assertTruthy(riskFindings.some((finding) => finding.id === "kv-list-in-auth-path"), "detects KV list auth fallback risk");
    assertTruthy(
      detectResourceCombinationRisks([
        { type: "queues", name: "Q" },
        { type: "durableObjects", name: "DO" },
        { type: "kv", name: "KV" },
      ]).some((finding) => finding.id === "queue-do-kv-amplification-combo"),
      "detects Queue + DO + KV resource combination risk",
    );

    const tomlProject = path.join(tempRoot, "toml-project");
    fs.mkdirSync(tomlProject, { recursive: true });
    fs.writeFileSync(
      path.join(tomlProject, "wrangler.toml"),
      [
        'name = "cost-test-worker"',
        'account_id = "dummy-account-id"',
        'main = "src/index.ts"',
        "",
        "[triggers]",
        'crons = ["*/30 * * * *"]',
        "",
        "[[durable_objects.bindings]]",
        'name = "ROOM"',
        'class_name = "RoomObject"',
        "",
        "[[queues.producers]]",
        'binding = "JOBS"',
        'queue = "jobs"',
        "",
        "[[queues.consumers]]",
        'queue = "jobs"',
        "",
        "[[env.production.d1_databases]]",
        'binding = "PROD_DB"',
        'database_name = "prod-db"',
        'database_id = "example-database-id"',
      ].join("\n"),
    );
    const tomlConfig = readWranglerConfig(path.join(tomlProject, "wrangler.toml")).config;
    assertEqual(tomlConfig.account_id, "dummy-account-id", "reads account id from TOML");
    const tomlResources = detectResources(tomlConfig, tomlProject);
    assertTruthy(tomlResources.some((resource) => resource.type === "workers"), "detects worker from TOML");
    assertTruthy(tomlResources.some((resource) => resource.type === "durableObjects"), "detects durable objects from nested TOML tables");
    assertTruthy(tomlResources.some((resource) => resource.type === "queues"), "detects queues from nested TOML tables");
    assertTruthy(tomlResources.some((resource) => resource.type === "cron"), "detects cron triggers from TOML object table");
    assertTruthy(
      tomlResources.some((resource) => resource.type === "d1" && resource.environment === "production"),
      "detects resources from TOML env tables",
    );
    assertTruthy(
      tomlResources.every((resource) => !Object.prototype.hasOwnProperty.call(resource, "database_id")),
      "does not expose raw D1 database ids",
    );
    assertTruthy(
      tomlResources.some((resource) => resource.type === "d1" && resource.databaseIdPresent === true),
      "keeps D1 database id presence flag",
    );
    fs.mkdirSync(path.join(tomlProject, "src", "nested"), { recursive: true });
    assertEqual(resolveProjectDir(path.join(tomlProject, "src", "nested")), tomlProject, "resolves project root from subdirectory");
    assertTruthy(
      productsForResources(tomlResources).includes("durableObjects"),
      "keeps durable objects in products to monitor",
    );

    const packageProject = path.join(tempRoot, "package-project");
    fs.mkdirSync(packageProject, { recursive: true });
    fs.writeFileSync(
      path.join(packageProject, "package.json"),
      JSON.stringify({
        name: "package-cloudflare-project",
        dependencies: { "@opennextjs/cloudflare": "1.0.0" },
      }),
    );
    const packageResources = detectResources({}, packageProject);
    assertTruthy(packageResources.some((resource) => resource.type === "workers"), "detects Cloudflare project from package dependencies");

    const monthly = calculateQuotaRow(
      { product: "KV", metric: "reads", used: 120, included: 1000, period: "monthly", elapsedDays: 10, cycleDays: 30 },
      {},
    );
    assertClose(monthly.usedPlanRatio, 0.12, "monthly used ratio");
    assertClose(monthly.projectedPlanRatio, 0.36, "monthly projected ratio");

    const daily = calculateQuotaRow(
      { product: "Workers", metric: "requests", used: 100, included: 200, period: "daily", last3: [50, 100, 150] },
      {},
    );
    assertClose(daily.usedPlanRatio, 0.5, "daily used ratio");
    assertClose(daily.projectedPlanRatio, 0.5, "daily projected ratio uses recent average");

    const usageRows = buildUsageRows({
      quotaRows: [monthly],
      estimates: {
        durableObjects: estimateDurableObjects({
          doObjects: 5,
          doHoursPerDay: 24,
          doDays: 30,
          doMemoryMb: 128,
          doFreeGbs: 400000,
          doRate: 0.0001,
          from: "2026-06-01",
        }),
      },
      paygoUsage: {
        result: {
          items: [
            { product: "Workers", metric: "requests", usage: 1234, unit: "requests", cost: 0.12 },
          ],
        },
      },
    });
    assertTruthy(usageRows.some((row) => row.source === "manual-quota"), "usageRows include manual quota rows");
    assertTruthy(usageRows.some((row) => row.source === "local-estimate"), "usageRows include local estimate rows");
    assertTruthy(usageRows.some((row) => row.source === "paygo-usage"), "usageRows include PayGo rows");
    assertTruthy(
      usageRows.every((row) => Object.prototype.hasOwnProperty.call(row, "projectedPlanRatio")),
      "usageRows keep projectedPlanRatio field",
    );
    assertEqual(
      JSON.stringify(buildDateFilter(["date_geq", "date_lt"], "2026-06-01", "2026-06-16")),
      JSON.stringify({ date_geq: "2026-06-01", date_lt: "2026-06-16" }),
      "builds date filter for date fields",
    );
    assertEqual(
      JSON.stringify(buildDateFilter(["datetime_geq", "datetime_lt"], "2026-06-01", "2026-06-16")),
      JSON.stringify({ datetime_geq: "2026-06-01T00:00:00Z", datetime_lt: "2026-06-16T00:00:00Z" }),
      "builds datetime filter for datetime fields",
    );

    let tokenRejected = false;
    try {
      parseArgs(["node", "audit-cf-usage.mjs", "--token", "dummy-api-key-value"]);
    } catch {
      tokenRejected = true;
    }
    assertTruthy(tokenRejected, "rejects --token argument");

    console.log("Self-test passed.");
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
}

function assertEqual(actual, expected, label) {
  if (actual !== expected) {
    throw new Error(`${label}: expected ${expected}, got ${actual}`);
  }
}

function assertClose(actual, expected, label) {
  if (Math.abs(actual - expected) > 1e-9) {
    throw new Error(`${label}: expected ${expected}, got ${actual}`);
  }
}

function assertTruthy(value, label) {
  if (!value) throw new Error(`${label}: expected truthy value`);
}

async function main() {
  const args = parseArgs(process.argv);
  if (args.selfTest) {
    runSelfTest();
    return;
  }
  const projectDir = resolveProjectDir(args.project);
  const credentials = loadCredentialContext(projectDir, args.envFile);
  const configPath = findWranglerConfig(projectDir);
  const { config, parseWarning } = readWranglerConfig(configPath);
  const configAccountId = config.account_id ?? config.accountId ?? null;
  const accountId = args.accountId ?? credentials.accountId ?? configAccountId;
  const token = credentials.token;
  const resources = detectResources(config, projectDir);
  const products = productsForResources(resources);
  const result = buildDryRun({
    projectDir,
    configPath,
    config,
    parseWarning,
    resources,
    products,
    from: args.from,
    to: args.to,
    usingDefaultPeriod: args.usingDefaultPeriod,
  });
  result.credentials = {
    accountId: accountId ? "found" : "missing",
    accountIdSource: args.accountId ? "--account-id" : credentials.accountIdSource ?? (configAccountId ? "wrangler config" : null),
    apiToken: token ? "found" : "missing",
    apiTokenSource: credentials.tokenSource,
  };
  if (args.estimateDo) {
    result.estimates = {
      ...(result.estimates ?? {}),
      durableObjects: estimateDurableObjects(args),
    };
  }
  if (args.quotaInputs.length > 0) {
    result.quotaRows = calculateQuotaRows(args.quotaInputs, {
      elapsedDays: daysBetween(args.from, args.to),
      cycleDays: daysInUtcMonth(args.from),
    });
  }

  if (!args.dryRun) {
    if (!accountId || !token) {
      result.apiWarning = "Missing Cloudflare account id or API token. Put CLOUDFLARE_ACCOUNT_ID/CLOUDFLARE_API_TOKEN or CF_ACCOUNT_ID/CF_API_TOKEN in .dev.vars, .env, or the process environment; re-run with --dry-run for local-only detection.";
    } else {
      const accountFields = await discoverAccountDatasets(token);
      result.matchedDatasets = matchDatasets(products, accountFields);
      if (!args.discoverOnly) {
        result.queryErrors = [];
        result.datasetProbes = [];
        const filterFieldCache = new Map();
        for (const datasets of Object.values(result.matchedDatasets)) {
          for (const dataset of datasets) {
            try {
              if (dataset.filterType && !filterFieldCache.has(dataset.filterType)) {
                filterFieldCache.set(dataset.filterType, await discoverInputFieldNames(token, dataset.filterType));
              }
              const filterFieldNames = filterFieldCache.get(dataset.filterType) ?? [];
              const filter = buildDateFilter(filterFieldNames, args.from, args.to);
              await queryDatasetProbe({
                accountId,
                token,
                dataset: dataset.name,
                filterType: dataset.filterType,
                filter,
              });
              result.datasetProbes.push({
                dataset: dataset.name,
                filterType: dataset.filterType,
                filterFields: filterFieldNames,
                filter,
                status: "ok",
              });
            } catch (error) {
              result.queryErrors.push({ dataset: dataset.name, message: error.message });
            }
          }
        }
        if (args.includePaygo) {
          try {
            result.paygoUsage = await fetchPaygoUsage({
              accountId,
              token,
              from: args.from,
              to: args.to,
              usingDefaultPeriod: args.usingDefaultPeriod,
            });
          } catch (error) {
            result.paygoError = error.message;
          }
        }
      }
    }
  }

  result.usageRows = buildUsageRows(result);
  if (args.json) console.log(JSON.stringify(result, null, 2));
  else printText(result);
  if (result.apiWarning) console.error(`\n${result.apiWarning}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
