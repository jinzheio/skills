#!/usr/bin/env tsx

/**
 * Delete/terminate OVH VPS servers.
 */

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type HttpMethod = "GET" | "POST";

type OvhConfig = {
  endpoint: string;
  applicationKey: string;
  applicationSecret: string;
  consumerKey: string;
};

type OvhVpsSummary = {
  name?: string;
  displayName?: string;
  state?: string;
  zone?: string;
  ipv4?: string;
};

type OvhError = { message?: string; class?: string };

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

function parseArgs(argv: string[]) {
  const out: Record<string, string | boolean> = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith("--")) continue;
    const key = a.slice(2);
    const next = argv[i + 1];
    if (next === undefined || next.startsWith("--")) {
      out[key] = true;
      continue;
    }
    out[key] = next;
    i++;
  }
  return out;
}

function getRequiredEnv(name: string, from: Record<string, string | undefined>) {
  const v = from[name]?.trim();
  if (!v) throw new Error(`${name} is required`);
  return v;
}

function parseEnvFile(filePath: string): Record<string, string> {
  const env: Record<string, string> = {};
  let content: string;
  try { content = fs.readFileSync(filePath, "utf8"); } catch { return env; }
  for (const rawLine of content.split("\n")) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const idx = line.indexOf("=");
    if (idx <= 0) continue;
    const key = line.slice(0, idx).trim();
    let value = line.slice(idx + 1);
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    env[key] = value;
  }
  return env;
}

// ---------------------------------------------------------------------------
// OVH API
// ---------------------------------------------------------------------------

async function getApiTime(endpoint: string) {
  const res = await fetch(`${endpoint}/auth/time`);
  if (!res.ok) throw new Error(`OVH time error: ${res.status}`);
  return String((await res.json()) as number);
}

async function ovhRequest<T>(
  cfg: OvhConfig, method: HttpMethod, pathPart: string, body?: unknown,
): Promise<{ status: number; data: T }> {
  const url = `${cfg.endpoint}${pathPart}`;
  const payload = body === undefined ? "" : JSON.stringify(body);
  const timestamp = await getApiTime(cfg.endpoint);
  const sigInput = [cfg.applicationSecret, cfg.consumerKey, method, url, payload, timestamp].join("+");
  const sig = `$1$${crypto.createHash("sha1").update(sigInput).digest("hex")}`;

  const res = await fetch(url, {
    method,
    headers: {
      "X-Ovh-Application": cfg.applicationKey,
      "X-Ovh-Consumer": cfg.consumerKey,
      "X-Ovh-Timestamp": timestamp,
      "X-Ovh-Signature": sig,
      "Content-Type": "application/json",
    },
    body: payload || undefined,
  });

  const text = await res.text();
  return { status: res.status, data: text ? (JSON.parse(text) as T) : (null as T) };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const dryRun = Boolean(args["dry-run"]);
  const service = typeof args["service"] === "string" ? args["service"] : "";
  const confirm = Boolean(args["confirm"]);
  const listAll = Boolean(args["list"]);

  const envFile = parseEnvFile(path.join(process.cwd(), ".env"));
  const mergedEnv: Record<string, string | undefined> = {
    ...envFile,
    ...Object.fromEntries(Object.entries(process.env).map(([k, v]) => [k, v])),
  };

  const ovhCfg: OvhConfig = {
    endpoint: (mergedEnv.OVH_API_BASE ?? "https://api.us.ovhcloud.com/1.0").replace(/\/+$/, ""),
    applicationKey: getRequiredEnv("OVH_APPLICATION_KEY", mergedEnv),
    applicationSecret: getRequiredEnv("OVH_APPLICATION_SECRET", mergedEnv),
    consumerKey: getRequiredEnv("OVH_CONSUMER_KEY", mergedEnv),
  };

  // List all VPS
  if (listAll || (!service && !dryRun)) {
    const list = await ovhRequest<string[]>(ovhCfg, "GET", "/vps");
    if (list.status >= 300 || !Array.isArray(list.data)) {
      throw new Error(`failed to list VPS: ${list.status}`);
    }

    console.log("VPS services:");
    for (const sn of list.data) {
      try {
        const detail = await ovhRequest<OvhVpsSummary>(ovhCfg, "GET", `/vps/${encodeURIComponent(sn)}`);
        if (detail.status >= 300) { console.log(`  ${sn}`); continue; }
        const d = detail.data;
        console.log(`  ${d.displayName ?? sn}  ${d.state ?? "?"}  ${d.zone ?? "?"}  ${d.ipv4 ?? ""}`);
      } catch {
        console.log(`  ${sn}`);
      }
    }

    if (!service) {
      console.log("\nUse --service <name> to target a VPS for deletion.");
      console.log("Add --confirm to actually delete.");
      return;
    }
  }

  if (!service) {
    throw new Error("--service <name> is required for deletion");
  }

  if (dryRun) {
    console.log(`[dry-run] Would terminate: ${service}`);
    return;
  }

  if (!confirm) {
    throw new Error("Refusing to delete without --confirm. Add --dry-run to preview first.");
  }

  // Terminate
  console.log(`Terminating ${service}...`);
  const res = await ovhRequest<OvhError>(
    ovhCfg, "POST", `/vps/${encodeURIComponent(service)}/terminate`,
  );
  if (res.status >= 300) {
    throw new Error(`terminate failed: ${res.status} - ${res.data?.message ?? "unknown"}`);
  }
  console.log(`✓ ${service} terminated.`);
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
});
