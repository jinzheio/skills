#!/usr/bin/env tsx

/**
 * Delete Hetzner Cloud servers.
 */

import fs from "node:fs";
import path from "node:path";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type HetznerServer = {
  id: number;
  name: string;
  status: string;
  created: string;
  public_net: { ipv4?: { ip: string }; ipv6?: { ip: string } };
  server_type?: { name: string };
  location?: { name: string };
};

type ServersListResponse = {
  servers: HetznerServer[];
  meta?: { pagination?: { last_page: number } };
};

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
// Hetzner API
// ---------------------------------------------------------------------------

const HCLOUD_API = "https://api.hetzner.cloud/v1";

async function listServers(token: string): Promise<HetznerServer[]> {
  const all: HetznerServer[] = [];
  let page = 1;
  while (true) {
    const res = await fetch(`${HCLOUD_API}/servers?page=${page}&per_page=50`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      const err = (await res.json().catch(() => ({}))) as { error?: { message: string } };
      throw new Error(`Failed to list servers: ${res.status} - ${err.error?.message ?? "unknown"}`);
    }
    const data = (await res.json()) as ServersListResponse;
    all.push(...(data.servers ?? []));
    const lastPage = data.meta?.pagination?.last_page ?? 1;
    if (page >= lastPage) break;
    page++;
  }
  return all;
}

async function deleteServer(token: string, serverId: number): Promise<void> {
  const res = await fetch(`${HCLOUD_API}/servers/${serverId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok && res.status !== 404) {
    const err = (await res.json().catch(() => ({}))) as { error?: { message: string } };
    throw new Error(`Delete failed: ${res.status} - ${err.error?.message ?? "unknown"}`);
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const dryRun = Boolean(args["dry-run"]);
  const serverId = typeof args["server-id"] === "string" ? Number(args["server-id"]) : 0;
  const serverName = typeof args["server-name"] === "string" ? args["server-name"] : "";
  const confirm = Boolean(args["confirm"]);
  const listOnly = Boolean(args["list"]);

  const envFile = parseEnvFile(path.join(process.cwd(), ".env"));
  const mergedEnv: Record<string, string | undefined> = {
    ...envFile,
    ...Object.fromEntries(Object.entries(process.env).map(([k, v]) => [k, v])),
  };

  const token = mergedEnv.HETZNER_API_TOKEN?.trim();
  if (!token) throw new Error("HETZNER_API_TOKEN is required. Set it in .env or environment.");

  const servers = await listServers(token);

  if (listOnly || !serverId && !serverName) {
    console.log("Servers:");
    for (const s of servers) {
      const ip = s.public_net?.ipv4?.ip ?? "(no ipv4)";
      console.log(`  id=${s.id}  name=${s.name}  status=${s.status}  type=${s.server_type?.name ?? "?"}  location=${s.location?.name ?? "?"}  ip=${ip}  created=${s.created}`);
    }
    console.log(`Total: ${servers.length}`);
    if (!listOnly) console.log("\nUse --server-id <id> or --server-name <name>. Add --confirm to delete.");
    return;
  }

  let targetId = serverId;
  if (!targetId && serverName) {
    const match = servers.find((s) => s.name === serverName);
    if (!match) throw new Error(`Server not found by name: ${serverName}`);
    targetId = match.id;
    console.log(`Matched: id=${match.id} name=${match.name} ip=${match.public_net?.ipv4?.ip ?? ""}`);
  }
  if (!targetId) throw new Error("No target server identified.");

  if (dryRun) {
    const s = servers.find((sv) => sv.id === targetId);
    console.log(`[dry-run] Would delete: id=${targetId} name=${s?.name ?? "?"} ip=${s?.public_net?.ipv4?.ip ?? "?"}`);
    return;
  }

  if (!confirm) throw new Error("Refusing to delete without --confirm.");

  console.log(`Deleting server ${targetId}...`);
  await deleteServer(token, targetId);
  console.log(`✓ Server ${targetId} deleted.`);
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
});
