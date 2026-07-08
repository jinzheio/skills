#!/usr/bin/env node
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const SKILL_NAME = "jz-cron-job";
const DEFAULT_API_BASE = "https://api.cron-job.org";
const METHOD_CODES = {
  GET: 0,
  POST: 1,
  OPTIONS: 2,
  HEAD: 3,
  PUT: 4,
  DELETE: 5,
  TRACE: 6,
  CONNECT: 7,
  PATCH: 8,
};
const METHOD_NAMES = Object.fromEntries(Object.entries(METHOD_CODES).map(([k, v]) => [v, k]));
const STATUS_NAMES = {
  0: "Unknown / not executed yet",
  1: "OK",
  2: "Failed (DNS error)",
  3: "Failed (could not connect)",
  4: "Failed (HTTP error)",
  5: "Failed (timeout)",
  6: "Failed (too much response data)",
  7: "Failed (invalid URL)",
  8: "Failed (internal errors)",
  9: "Failed (unknown reason)",
};
const SENSITIVE_HEADER_RE = /^(authorization|cookie|set-cookie|x-cron-secret|x-api-key|api-key|token|secret)$/i;

function usage() {
  console.log(`Usage:
  cron_job.mjs check
  cron_job.mjs list
  cron_job.mjs get <jobId>
  cron_job.mjs history <jobId>
  cron_job.mjs history-detail <jobId> <identifier>
  cron_job.mjs create --title <title> --url <url> [options]
  cron_job.mjs update <jobId> [options]
  cron_job.mjs enable <jobId>
  cron_job.mjs disable <jobId>
  cron_job.mjs delete <jobId>
  cron_job.mjs folders
  cron_job.mjs folder-get <folderId>
  cron_job.mjs folder-create <title>
  cron_job.mjs folder-update <folderId> <title>
  cron_job.mjs folder-delete <folderId>

Options for create/update:
  --title <title>
  --url <url>
  --enabled true|false
  --method GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS
  --timeout <seconds>
  --folder-id <id>
  --save-responses true|false
  --redirect-success true|false
  --timezone <tz>
  --every-hour
  --every-minute
  --daily-at HH:MM
  --schedule-json <json>
  --header "Name:Value"
  --body <string>
  --auth-user <user> --auth-password <password>
`);
}

function readEnvFile(file) {
  if (!fs.existsSync(file)) return {};
  const env = {};
  for (const rawLine of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const match = line.match(/^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!match) continue;
    let value = match[2].trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    env[match[1]] = value;
  }
  return env;
}

function loadConfig() {
  const defaultEnvDisplay = `~/.config/skills/${SKILL_NAME}/.env`;
  const envPath =
    process.env.JZ_CRON_JOB_ENV ||
    path.join(os.homedir(), ".config", "skills", SKILL_NAME, ".env");
  const fileEnv = readEnvFile(envPath);
  const apiKey = process.env.CRON_JOB_API_KEY || fileEnv.CRON_JOB_API_KEY;
  const apiBase = (process.env.CRON_JOB_API_BASE || fileEnv.CRON_JOB_API_BASE || DEFAULT_API_BASE)
    .replace(/\/+$/, "");
  if (!apiKey) {
    const envDisplay = process.env.JZ_CRON_JOB_ENV ? "the file pointed to by JZ_CRON_JOB_ENV" : defaultEnvDisplay;
    throw new Error(`Missing CRON_JOB_API_KEY. Put it in ${envDisplay} or export it in the shell.`);
  }
  return { apiKey, apiBase };
}

function parseArgs(argv) {
  const options = {};
  const positionals = [];
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (!arg.startsWith("--")) {
      positionals.push(arg);
      continue;
    }
    const key = arg.slice(2);
    if (key === "every-hour" || key === "every-minute") {
      options[key] = true;
      continue;
    }
    const value = argv[i + 1];
    if (value === undefined || value.startsWith("--")) {
      throw new Error(`Missing value for --${key}`);
    }
    i += 1;
    if (key === "header") {
      options.header = options.header || [];
      options.header.push(value);
    } else {
      options[key] = value;
    }
  }
  return { options, positionals };
}

function boolValue(value, name) {
  if (value === undefined) return undefined;
  if (value === true || value === "true" || value === "1" || value === "yes") return true;
  if (value === false || value === "false" || value === "0" || value === "no") return false;
  throw new Error(`${name} must be true or false`);
}

function intValue(value, name) {
  if (value === undefined) return undefined;
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) throw new Error(`${name} must be an integer`);
  return parsed;
}

function parseMethod(value) {
  if (!value) return undefined;
  const method = value.toUpperCase();
  if (!(method in METHOD_CODES)) {
    throw new Error(`Unsupported request method: ${value}`);
  }
  return METHOD_CODES[method];
}

function defaultSchedule(timezone = "UTC") {
  return {
    timezone,
    expiresAt: 0,
    hours: [-1],
    mdays: [-1],
    minutes: [0],
    months: [-1],
    wdays: [-1],
  };
}

function parseDailyAt(value, timezone = "UTC") {
  const match = value.match(/^([01]?\d|2[0-3]):([0-5]\d)$/);
  if (!match) throw new Error("--daily-at must be HH:MM");
  return {
    timezone,
    expiresAt: 0,
    hours: [Number.parseInt(match[1], 10)],
    mdays: [-1],
    minutes: [Number.parseInt(match[2], 10)],
    months: [-1],
    wdays: [-1],
  };
}

function parseHeaders(values = []) {
  const headers = {};
  for (const item of values) {
    const sep = item.indexOf(":");
    if (sep <= 0) throw new Error(`Header must be "Name:Value": ${item}`);
    const key = item.slice(0, sep).trim();
    const value = item.slice(sep + 1).trim();
    if (!key) throw new Error(`Header name is empty: ${item}`);
    headers[key] = value;
  }
  return headers;
}

function buildSchedule(options) {
  const timezone = options.timezone || "UTC";
  if (options["schedule-json"]) {
    return JSON.parse(options["schedule-json"]);
  }
  if (options["every-minute"]) {
    return {
      timezone,
      expiresAt: 0,
      hours: [-1],
      mdays: [-1],
      minutes: [-1],
      months: [-1],
      wdays: [-1],
    };
  }
  if (options["every-hour"]) return defaultSchedule(timezone);
  if (options["daily-at"]) return parseDailyAt(options["daily-at"], timezone);
  return undefined;
}

function buildJobPatch(options, { requireUrl = false } = {}) {
  const job = {};
  if (options.title !== undefined) job.title = options.title;
  if (options.url !== undefined) job.url = options.url;
  if (requireUrl && !job.url) throw new Error("--url is required");

  const enabled = boolValue(options.enabled, "--enabled");
  if (enabled !== undefined) job.enabled = enabled;
  const saveResponses = boolValue(options["save-responses"], "--save-responses");
  if (saveResponses !== undefined) job.saveResponses = saveResponses;
  const redirectSuccess = boolValue(options["redirect-success"], "--redirect-success");
  if (redirectSuccess !== undefined) job.redirectSuccess = redirectSuccess;

  const requestMethod = parseMethod(options.method);
  if (requestMethod !== undefined) job.requestMethod = requestMethod;
  const timeout = intValue(options.timeout, "--timeout");
  if (timeout !== undefined) job.requestTimeout = timeout;
  const folderId = intValue(options["folder-id"], "--folder-id");
  if (folderId !== undefined) job.folderId = folderId;

  const schedule = buildSchedule(options);
  if (schedule) job.schedule = schedule;

  const headers = parseHeaders(options.header);
  if (Object.keys(headers).length > 0 || options.body !== undefined) {
    job.extendedData = {};
    if (Object.keys(headers).length > 0) job.extendedData.headers = headers;
    if (options.body !== undefined) job.extendedData.body = options.body;
  }

  if (options["auth-user"] !== undefined || options["auth-password"] !== undefined) {
    if (!options["auth-user"] || !options["auth-password"]) {
      throw new Error("--auth-user and --auth-password must be provided together");
    }
    job.auth = {
      enable: true,
      user: options["auth-user"],
      password: options["auth-password"],
    };
  }
  return job;
}

function redactUrl(value) {
  if (!value || typeof value !== "string") return value;
  try {
    const url = new URL(value);
    url.search = "";
    url.hash = "";
    return url.toString();
  } catch {
    return value.replace(/\?.*$/, "");
  }
}

function redactHeaders(headers) {
  if (!headers || typeof headers !== "object") return headers;
  const output = {};
  for (const [key, value] of Object.entries(headers)) {
    output[key] = SENSITIVE_HEADER_RE.test(key) ? "[redacted]" : value;
  }
  return output;
}

function redactJob(job) {
  if (!job || typeof job !== "object") return job;
  const output = { ...job };
  if (output.url) output.url = redactUrl(output.url);
  if (output.requestMethod !== undefined) {
    output.requestMethodName = METHOD_NAMES[output.requestMethod] || output.requestMethod;
  }
  if (output.lastStatus !== undefined) {
    output.lastStatusText = STATUS_NAMES[output.lastStatus] || output.lastStatus;
  }
  if (output.extendedData) {
    output.extendedData = {
      ...output.extendedData,
      headers: redactHeaders(output.extendedData.headers),
    };
    if (output.extendedData.body !== undefined) output.extendedData.body = "[redacted]";
  }
  if (output.auth?.password !== undefined) {
    output.auth = { ...output.auth, password: "[redacted]" };
  }
  return output;
}

function redactHistory(item) {
  if (!item || typeof item !== "object") return item;
  const output = { ...item };
  if (output.url) output.url = redactUrl(output.url);
  if (output.headers !== undefined && output.headers !== null) output.headers = "[redacted]";
  if (output.body !== undefined && output.body !== null) output.body = "[redacted]";
  if (output.status !== undefined) output.statusName = STATUS_NAMES[output.status] || output.status;
  return output;
}

function printJson(value) {
  console.log(JSON.stringify(value, null, 2));
}

async function request(method, route, payload) {
  const { apiKey, apiBase } = loadConfig();
  const response = await fetch(`${apiBase}${route}`, {
    method,
    headers: {
      "Authorization": `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  const text = await response.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { raw: text };
    }
  }
  if (!response.ok) {
    const message = data?.message || data?.error || response.statusText;
    throw new Error(`cron-job.org API ${response.status}: ${message}`);
  }
  return data;
}

async function main() {
  const [command, ...rest] = process.argv.slice(2);
  if (!command || command === "-h" || command === "--help") {
    usage();
    return;
  }

  const { options, positionals } = parseArgs(rest);
  switch (command) {
    case "check": {
      const data = await request("GET", "/jobs");
      printJson({ ok: true, jobCount: data.jobs?.length ?? 0, someFailed: Boolean(data.someFailed) });
      break;
    }
    case "list": {
      const data = await request("GET", "/jobs");
      printJson({ ...data, jobs: (data.jobs || []).map(redactJob) });
      break;
    }
    case "get": {
      const [jobId] = positionals;
      if (!jobId) throw new Error("get requires <jobId>");
      const data = await request("GET", `/jobs/${encodeURIComponent(jobId)}`);
      printJson({ ...data, jobDetails: redactJob(data.jobDetails) });
      break;
    }
    case "history": {
      const [jobId] = positionals;
      if (!jobId) throw new Error("history requires <jobId>");
      const data = await request("GET", `/jobs/${encodeURIComponent(jobId)}/history`);
      printJson({ ...data, history: (data.history || []).map(redactHistory) });
      break;
    }
    case "history-detail": {
      const [jobId, identifier] = positionals;
      if (!jobId || !identifier) throw new Error("history-detail requires <jobId> <identifier>");
      const data = await request(
        "GET",
        `/jobs/${encodeURIComponent(jobId)}/history/${encodeURIComponent(identifier)}`,
      );
      printJson({ ...data, jobHistoryDetails: redactHistory(data.jobHistoryDetails) });
      break;
    }
    case "create": {
      const job = buildJobPatch(options, { requireUrl: true });
      if (!job.schedule) job.schedule = defaultSchedule(options.timezone || "UTC");
      if (job.enabled === undefined) job.enabled = false;
      const data = await request("PUT", "/jobs", { job });
      printJson(data);
      break;
    }
    case "update": {
      const [jobId] = positionals;
      if (!jobId) throw new Error("update requires <jobId>");
      const job = buildJobPatch(options);
      if (Object.keys(job).length === 0) throw new Error("update requires at least one option");
      const data = await request("PATCH", `/jobs/${encodeURIComponent(jobId)}`, { job });
      printJson(data);
      break;
    }
    case "enable":
    case "disable": {
      const [jobId] = positionals;
      if (!jobId) throw new Error(`${command} requires <jobId>`);
      const data = await request("PATCH", `/jobs/${encodeURIComponent(jobId)}`, {
        job: { enabled: command === "enable" },
      });
      printJson(data);
      break;
    }
    case "delete": {
      const [jobId] = positionals;
      if (!jobId) throw new Error("delete requires <jobId>");
      const data = await request("DELETE", `/jobs/${encodeURIComponent(jobId)}`);
      printJson(data);
      break;
    }
    case "folders": {
      printJson(await request("GET", "/folders"));
      break;
    }
    case "folder-get": {
      const [folderId] = positionals;
      if (!folderId) throw new Error("folder-get requires <folderId>");
      printJson(await request("GET", `/folders/${encodeURIComponent(folderId)}`));
      break;
    }
    case "folder-create": {
      const [title] = positionals;
      if (!title) throw new Error("folder-create requires <title>");
      printJson(await request("PUT", "/folders", { folder: { title } }));
      break;
    }
    case "folder-update": {
      const [folderId, title] = positionals;
      if (!folderId || !title) throw new Error("folder-update requires <folderId> <title>");
      printJson(await request("PATCH", `/folders/${encodeURIComponent(folderId)}`, { folder: { title } }));
      break;
    }
    case "folder-delete": {
      const [folderId] = positionals;
      if (!folderId) throw new Error("folder-delete requires <folderId>");
      printJson(await request("DELETE", `/folders/${encodeURIComponent(folderId)}`));
      break;
    }
    default:
      throw new Error(`Unknown command: ${command}`);
  }
}

main().catch((error) => {
  console.error(`error: ${error.message}`);
  process.exit(1);
});
