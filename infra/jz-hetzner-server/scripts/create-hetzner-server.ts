#!/usr/bin/env tsx

/**
 * Create Hetzner Cloud servers.
 *
 * Workflow:
 * 1. Validate env/token
 * 2. Create server(s) via Hetzner Cloud API
 * 3. Wait for server(s) to reach "running" state
 * 4. Optionally wait for SSH to be reachable
 * 5. Print server info (IP, root password, login command)
 */

import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { randomBytes } from "node:crypto";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type HetznerServer = {
  id: number;
  name: string;
  status: string;
  created: string;
  public_net: {
    ipv4?: { ip: string };
    ipv6?: { ip: string };
  };
  server_type?: { name: string; cores: number; memory: number; disk: number };
  location?: { name: string };
  image?: { name: string };
};

type CreateResponse = {
  server: HetznerServer;
  root_password?: string;
  action?: { id: number };
  error?: { message: string; code: string };
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

function expandHome(p: string) {
  const os = require("node:os");
  if (p.startsWith("~/")) return path.join(os.homedir(), p.slice(2));
  return p;
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

function randomName(prefix: string): string {
  return `${prefix}-${randomBytes(4).toString("hex")}`;
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

// ---------------------------------------------------------------------------
// Hetzner API
// ---------------------------------------------------------------------------

const HCLOUD_API = "https://api.hetzner.cloud/v1";

async function createServer(
  token: string,
  params: {
    name: string;
    serverType: string;
    location: string;
    image: string;
    sshKeyName?: string;
  },
): Promise<CreateResponse> {
  const body: Record<string, unknown> = {
    name: params.name,
    server_type: params.serverType,
    location: params.location,
    image: params.image,
  };
  if (params.sshKeyName) {
    body.ssh_keys = [params.sshKeyName];
  }

  const res = await fetch(`${HCLOUD_API}/servers`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  const payload = (await res.json()) as CreateResponse;
  return payload;
}

async function getServer(token: string, serverId: number): Promise<{ server: HetznerServer }> {
  const res = await fetch(`${HCLOUD_API}/servers/${serverId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return res.json() as Promise<{ server: HetznerServer }>;
}

async function listServers(token: string): Promise<HetznerServer[]> {
  const all: HetznerServer[] = [];
  let page = 1;
  while (true) {
    const res = await fetch(`${HCLOUD_API}/servers?page=${page}&per_page=50`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = (await res.json()) as ServersListResponse;
    all.push(...(data.servers ?? []));
    const lastPage = data.meta?.pagination?.last_page ?? 1;
    if (page >= lastPage) break;
    page++;
  }
  return all;
}

// ---------------------------------------------------------------------------
// SSH
// ---------------------------------------------------------------------------

function sshKeygenRemoveHost(ip: string) {
  try { execFileSync("ssh-keygen", ["-R", ip], { stdio: "ignore" }); } catch { /* ok */ }
}

function canSsh(ip: string, user: string, keyPath: string) {
  try {
    const out = execFileSync("ssh", [
      "-i", keyPath,
      "-o", "BatchMode=yes",
      "-o", "ConnectTimeout=10",
      "-o", "StrictHostKeyChecking=accept-new",
      `${user}@${ip}`,
      "whoami && hostname && uptime",
    ], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
    return { ok: true, out };
  } catch (e: unknown) {
    const err = e as { stderr?: string; message?: string };
    return { ok: false, err: String(err?.stderr ?? err?.message ?? err) };
  }
}

function canSshPassword(ip: string, user: string, password: string) {
  try {
    const out = execFileSync("sshpass", [
      "-p", password,
      "ssh",
      "-o", "PreferredAuthentications=password",
      "-o", "PubkeyAuthentication=no",
      "-o", "ConnectTimeout=10",
      "-o", "StrictHostKeyChecking=accept-new",
      `${user}@${ip}`,
      "whoami && hostname && uptime",
    ], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
    return { ok: true, out };
  } catch {
    return { ok: false };
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const dryRun = Boolean(args["dry-run"]);
  const name = typeof args["name"] === "string" ? args["name"] : "";
  const namePrefix = typeof args["name-prefix"] === "string" ? args["name-prefix"] : "server";
  const serverType = typeof args["server-type"] === "string" ? args["server-type"] :
    (process.env.HCLOUD_SERVER_TYPE ?? "cx22");
  const location = typeof args["location"] === "string" ? args["location"] :
    (process.env.HCLOUD_LOCATION ?? "nbg1");
  const image = typeof args["image"] === "string" ? args["image"] :
    (process.env.HCLOUD_IMAGE ?? "ubuntu-24.04");
  const sshKeyName = typeof args["ssh-key-name"] === "string" ? args["ssh-key-name"] : "";
  const timeoutMin = Number(typeof args["timeout-min"] === "string" ? args["timeout-min"] : "5");
  const count = Math.min(
    Number(typeof args["count"] === "string" ? args["count"] : "1"),
    10,
  );
  const waitSsh = Boolean(args["wait-ssh"]);
  const sshUser = typeof args["ssh-user"] === "string" ? args["ssh-user"] : "root";
  const sshKeyPath = expandHome(
    typeof args["ssh-key"] === "string" ? args["ssh-key"] : "~/.ssh/id_ed25519_hetz_01",
  );

  // Load env
  const envFile = parseEnvFile(path.join(process.cwd(), ".env"));
  const mergedEnv: Record<string, string | undefined> = {
    ...envFile,
    ...Object.fromEntries(Object.entries(process.env).map(([k, v]) => [k, v])),
  };

  const token = mergedEnv.HETZNER_API_TOKEN?.trim();
  if (!token) {
    throw new Error("HETZNER_API_TOKEN is required. Set it in .env or environment.");
  }

  if (dryRun) {
    console.log("[dry-run] Would create servers:");
    for (let i = 0; i < count; i++) {
      const n = name || (count > 1 ? `${namePrefix}-${i + 1}` : randomName(namePrefix));
      console.log(`  ${i + 1}. name=${n} type=${serverType} location=${location} image=${image} ssh_key=${sshKeyName || "(none)"}`);
    }
    console.log(`[dry-run] Total: ${count}`);
    return;
  }

  const results: { name: string; id: number; ipv4: string | null; rootPassword: string | null; status: string; error?: string }[] = [];

  for (let i = 0; i < count; i++) {
    const serverName = name || (count > 1 ? `${namePrefix}-${i + 1}` : randomName(namePrefix));

    console.log(`\n--- Creating ${i + 1}/${count}: ${serverName} ---`);

    try {
      const result = await createServer(token, {
        name: serverName,
        serverType,
        location,
        image,
        sshKeyName: sshKeyName || undefined,
      });

      if (result.error) {
        throw new Error(`Hetzner API error: ${result.error.message} (${result.error.code})`);
      }

      const server = result.server;
      const serverId = server.id;
      const rootPassword = result.root_password ?? null;
      const ipv4 = server.public_net?.ipv4?.ip ?? null;
      const ipv6 = server.public_net?.ipv6?.ip ?? null;

      // Wait for server to be running
      console.log(`Server ${serverId} created. Waiting for "running" state...`);
      const deadline = Date.now() + timeoutMin * 60_000;
      let currentStatus = server.status;
      while (currentStatus !== "running" && Date.now() < deadline) {
        await sleep(10_000);
        const { server: updated } = await getServer(token, serverId);
        currentStatus = updated.status;
        if (currentStatus !== "running" && currentStatus !== "initializing") {
          throw new Error(`Server entered unexpected state: ${currentStatus}`);
        }
        process.stdout.write(".");
      }
      process.stdout.write("\n");

      if (currentStatus !== "running") {
        throw new Error(`Server did not reach "running" within ${timeoutMin} min. Current: ${currentStatus}`);
      }

      // Optionally wait for SSH
      if (waitSsh && ipv4) {
        console.log(`Waiting for SSH on ${sshUser}@${ipv4} ...`);
        const sshDeadline = Date.now() + 5 * 60_000;
        let sshOk = false;
        while (Date.now() < sshDeadline) {
          sshKeygenRemoveHost(ipv4);
          let result;
          if (rootPassword) {
            result = canSshPassword(ipv4, sshUser, rootPassword);
          } else {
            result = canSsh(ipv4, sshUser, sshKeyPath);
          }
          if (result.ok) {
            console.log(`SSH OK: ${sshUser}@${ipv4}`);
            sshOk = true;
            break;
          }
          process.stdout.write(".");
          await sleep(15_000);
        }
        process.stdout.write("\n");
        if (!sshOk) {
          console.warn("SSH not yet reachable; server may still be booting. Try again shortly.");
        }
      }

      // Print info
      console.log(`\n✓ Server ready: ${serverName}`);
      console.log(`  ID:         ${serverId}`);
      console.log(`  IPv4:       ${ipv4 ?? "(none)"}`);
      console.log(`  IPv6:       ${ipv6 ?? "(none)"}`);
      console.log(`  Type:       ${server.server_type?.name ?? serverType}`);
      console.log(`  Location:   ${server.location?.name ?? location}`);
      if (rootPassword) {
        console.log(`  Root pass:  ${rootPassword}`);
        console.log(`  Login:      ssh root@${ipv4}`);
      }
      if (sshKeyName) {
        console.log(`  Login (key): ssh -i <key> root@${ipv4}`);
      }

      results.push({ name: serverName, id: serverId, ipv4, rootPassword, status: "created" });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(`✗ Failed: ${msg}`);
      results.push({ name: serverName, id: 0, ipv4: null, rootPassword: null, status: "failed", error: msg });
    }
  }

  // Report
  const created = results.filter((r) => r.status === "created");
  const failed = results.filter((r) => r.status === "failed");
  console.log(`\n=== Report ===`);
  console.log(`Total: ${results.length} | Created: ${created.length} | Failed: ${failed.length}`);
  created.forEach((r) => console.log(`  - ${r.name}: ${r.ipv4} (root password saved above)`));
  failed.forEach((r) => console.log(`  - ${r.name}: ${r.error}`));
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
});
