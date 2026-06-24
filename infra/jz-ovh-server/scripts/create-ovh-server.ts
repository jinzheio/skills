#!/usr/bin/env tsx

/**
 * Create OVH VPS servers.
 *
 * Workflow:
 * 1. (optional) List available plans / datacenters
 * 2. Create order via OVH API cart workflow
 * 3. Wait for VPS delivery
 * 4. Rebuild with explicit SSH public key injection
 * 5. Wait until SSH is reachable
 * 6. Print server info (IP, login command)
 */

import crypto from "node:crypto";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type HttpMethod = "GET" | "POST" | "PUT" | "DELETE";

type OvhConfig = {
  endpoint: string;
  applicationKey: string;
  applicationSecret: string;
  consumerKey: string;
};

type VpsPlan = {
  planCode: string;
  description?: string;
  vcore?: number;
  memoryMb?: number;
  diskGb?: number;
};

type OvhError = { message?: string; class?: string };

// ---------------------------------------------------------------------------
// CLI args
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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getRequiredEnv(name: string, from: Record<string, string | undefined>) {
  const v = from[name]?.trim();
  if (!v) throw new Error(`${name} is required`);
  return v;
}

function expandHome(p: string) {
  if (p.startsWith("~/")) return path.join(os.homedir(), p.slice(2));
  return p;
}

function parseEnvFile(filePath: string): Record<string, string> {
  const env: Record<string, string> = {};
  let content: string;
  try {
    content = fs.readFileSync(filePath, "utf8");
  } catch {
    return env;
  }
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

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

// ---------------------------------------------------------------------------
// OVH API
// ---------------------------------------------------------------------------

async function getApiTime(endpoint: string) {
  const response = await fetch(`${endpoint}/auth/time`);
  if (!response.ok) throw new Error(`failed to get OVH API time: ${response.status}`);
  const payload = (await response.json()) as number;
  return String(payload);
}

async function ovhRequest<T>(
  cfg: OvhConfig,
  method: HttpMethod,
  pathPart: string,
  body?: unknown,
): Promise<{ status: number; data: T }> {
  const url = `${cfg.endpoint}${pathPart}`;
  const payload = body === undefined ? "" : JSON.stringify(body);
  const timestamp = await getApiTime(cfg.endpoint);
  const signatureInput = [
    cfg.applicationSecret,
    cfg.consumerKey,
    method,
    url,
    payload,
    timestamp,
  ].join("+");
  const signature = `$1$${crypto.createHash("sha1").update(signatureInput).digest("hex")}`;

  const response = await fetch(url, {
    method,
    headers: {
      "X-Ovh-Application": cfg.applicationKey,
      "X-Ovh-Consumer": cfg.consumerKey,
      "X-Ovh-Timestamp": timestamp,
      "X-Ovh-Signature": signature,
      "Content-Type": "application/json",
    },
    body: payload || undefined,
  });

  const text = await response.text();
  const data = text ? (JSON.parse(text) as T) : (null as T);
  return { status: response.status, data };
}

// ---------------------------------------------------------------------------
// SSH
// ---------------------------------------------------------------------------

function sshKeygenRemoveHost(ip: string) {
  try {
    execFileSync("ssh-keygen", ["-R", ip], { stdio: "ignore" });
  } catch {
    // ignore
  }
}

function canSsh(
  ip: string,
  sshUser: string,
  sshKeyPath: string,
): { ok: boolean; out?: string; err?: string } {
  try {
    const out = execFileSync(
      "ssh",
      [
        "-i", sshKeyPath,
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
        "-o", "StrictHostKeyChecking=accept-new",
        `${sshUser}@${ip}`,
        "whoami && hostname && uptime",
      ],
      { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
    );
    return { ok: true, out };
  } catch (e: unknown) {
    const err = e as { stderr?: string; message?: string };
    return { ok: false, err: String(err?.stderr ?? err?.message ?? err) };
  }
}

// ---------------------------------------------------------------------------
// VPS helpers
// ---------------------------------------------------------------------------

function normalize(value: string) {
  return value.trim().toLowerCase();
}

type OvhImage = {
  id: number;
  name?: string;
  distribution?: string;
  version?: string;
  description?: string;
};

function matchImage(image: OvhImage, osName: string) {
  const target = normalize(osName);
  const candidates = [
    image.name,
    image.distribution,
    image.version ? `${image.distribution ?? ""} ${image.version}` : "",
    image.description,
  ]
    .filter(Boolean)
    .map((v) => normalize(String(v)));
  return candidates.some((v) => v.includes(target));
}

async function resolveImageId(cfg: OvhConfig, serviceName: string, osName: string, imageIdOverride?: string) {
  if (imageIdOverride) return imageIdOverride;

  const list = await ovhRequest<number[]>(
    cfg, "GET", `/vps/${encodeURIComponent(serviceName)}/images/available`,
  );
  if (list.status >= 300 || !Array.isArray(list.data)) {
    throw new Error(`failed to list images for ${serviceName} (status ${list.status})`);
  }

  for (const id of list.data) {
    const detail = await ovhRequest<OvhImage>(
      cfg, "GET", `/vps/${encodeURIComponent(serviceName)}/images/available/${id}`,
    );
    if (detail.status >= 300) continue;
    if (matchImage(detail.data, osName)) {
      return String(id);
    }
  }
  throw new Error(`no imageId matched ${osName} for ${serviceName}`);
}

function pickIp(ips: string[], kind: "v4" | "v6") {
  if (kind === "v4") return ips.find((ip) => ip.includes(".")) ?? null;
  return ips.find((ip) => ip.includes(":")) ?? null;
}

// ---------------------------------------------------------------------------
// Order via OVH cart
// ---------------------------------------------------------------------------

async function createVpsOrder(
  cfg: OvhConfig,
  planCode: string,
  duration: string,
  pricingMode: string,
  datacenter: string,
  displayName: string,
) {
  // 1. Create a cart
  const cart = await ovhRequest<{ cartId: string }>(cfg, "POST", "/order/cart", {
    ovhSubsidiary: "US",
  });
  if (cart.status >= 300) {
    throw new Error(`failed to create cart: ${cart.status}`);
  }
  const cartId = cart.data.cartId;
  console.log(`Cart created: ${cartId}`);

  // 2. Assign cart to self
  const assign = await ovhRequest<unknown>(cfg, "POST", `/order/cart/${cartId}/assign`);
  if (assign.status >= 300) {
    throw new Error(`failed to assign cart: ${assign.status}`);
  }

  // 3. Add VPS plan item to cart
  const item = await ovhRequest<{ itemId: number }>(cfg, "POST", `/order/cart/${cartId}/vps`, {
    duration,
    planCode,
    pricingMode,
    quantity: 1,
  });
  if (item.status >= 300) {
    const err = item.data as OvhError | null;
    throw new Error(`failed to add VPS to cart: ${item.status} - ${err?.message ?? "unknown"}`);
  }

  // 4. Configure the item
  const itemId = item.data.itemId;
  const config = await ovhRequest<unknown>(
    cfg,
    "POST",
    `/order/cart/${cartId}/item/${itemId}/configuration`,
    { label: "vps_os", value: "_none_" },
  );
  if (config.status >= 300) {
    console.warn(`Note: configuration set returned ${config.status} (may be ok)`);
  }

  // 5. Set datacenter
  if (datacenter) {
    const dcConf = await ovhRequest<unknown>(
      cfg,
      "POST",
      `/order/cart/${cartId}/item/${itemId}/configuration`,
      { label: "datacenter", value: datacenter.toLowerCase() },
    );
    if (dcConf.status >= 300) {
      console.warn(`Note: datacenter config returned ${dcConf.status} (may be ok)`);
    }
  }

  // 6. Set displayName
  if (displayName) {
    const nameConf = await ovhRequest<unknown>(
      cfg,
      "POST",
      `/order/cart/${cartId}/item/${itemId}/configuration`,
      { label: "displayName", value: displayName },
    );
    if (nameConf.status >= 300) {
      console.warn(`Note: displayName config returned ${nameConf.status} (may be ok)`);
    }
  }

  return { cartId, itemId };
}

type OvhContract = { id: string; url: string; name?: string };

async function checkoutCart(cfg: OvhConfig, cartId: string) {
  // Get contracts that need signing
  const contracts = await ovhRequest<OvhContract[]>(
    cfg, "GET", `/order/cart/${cartId}/checkout`,
  );

  if (contracts.status >= 300 || !Array.isArray(contracts.data)) {
    return { orderId: null as number | null, contracts: [] };
  }

  // Sign each contract
  for (const c of contracts.data) {
    const sign = await ovhRequest<unknown>(
      cfg,
      "POST",
      `/order/cart/${cartId}/contract/${c.id}/sign`,
    );
    if (sign.status >= 300) {
      throw new Error(`failed to sign contract ${c.id}: ${sign.status}`);
    }
  }

  // Place the order
  const order = await ovhRequest<{ orderId: number }>(
    cfg, "POST", `/order/cart/${cartId}/checkout`,
  );
  if (order.status >= 300) {
    const err = order.data as OvhError | null;
    throw new Error(`failed to checkout: ${order.status} - ${err?.message ?? "unknown"}`);
  }

  const orderId = order.data?.orderId ?? null;
  if (orderId) {
    // Pay with default payment method
    const pay = await ovhRequest<unknown>(
      cfg,
      "POST",
      `/me/order/${orderId}/payWithRegisteredPaymentMean`,
      { paymentMean: "default-payment-mean" },
    );
    if (pay.status >= 300) {
      console.warn(`Order ${orderId} placed but payment may need manual action.`);
    } else {
      console.log(`Order ${orderId} paid.`);
    }
  }

  return { orderId, contracts: contracts.data };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const dryRun = Boolean(args["dry-run"]);
  const listPlans = Boolean(args["list-plans"]);
  const plan = typeof args["plan"] === "string" ? args["plan"] : "essential";
  const osName = typeof args["os"] === "string" ? args["os"] : "Ubuntu 24.04";
  const sshKeyPath = expandHome(
    typeof args["ssh-key"] === "string" ? args["ssh-key"] : "~/.ssh/id_ed25519_ovh",
  );
  const sshPubKeyPath = sshKeyPath.endsWith(".pub") ? sshKeyPath : `${sshKeyPath}.pub`;
  const sshUser = typeof args["ssh-user"] === "string" ? args["ssh-user"] : "ubuntu";
  const datacenter = typeof args["datacenter"] === "string" ? args["datacenter"] : "";
  const timeoutMin = Number(typeof args["timeout-min"] === "string" ? args["timeout-min"] : "60");
  const count = Math.min(
    Number(typeof args["count"] === "string" ? args["count"] : "1"),
    10,
  );
  const namePrefix = typeof args["name-prefix"] === "string" ? args["name-prefix"] : "ovh-vps";
  const imageIdOverride = typeof args["image-id"] === "string" ? args["image-id"] : undefined;
  const skipRebuild = Boolean(args["skip-rebuild"]);
  const skipSsh = Boolean(args["skip-ssh"]);

  // Load env
  const envFile = parseEnvFile(path.join(process.cwd(), ".env"));
  const mergedEnv: Record<string, string | undefined> = {
    ...envFile,
    ...Object.fromEntries(
      Object.entries(process.env).map(([k, v]) => [k, v]),
    ),
  };

  const ovhCfg: OvhConfig = {
    endpoint: (mergedEnv.OVH_API_BASE ?? "https://api.us.ovhcloud.com/1.0").replace(/\/+$/, ""),
    applicationKey: getRequiredEnv("OVH_APPLICATION_KEY", mergedEnv),
    applicationSecret: getRequiredEnv("OVH_APPLICATION_SECRET", mergedEnv),
    consumerKey: getRequiredEnv("OVH_CONSUMER_KEY", mergedEnv),
  };

  const publicSshKey = getRequiredEnv("OVH_SSH_PUBLIC_KEY", mergedEnv);
  const doNotSendPassword =
    (mergedEnv.OVH_VPS_DO_NOT_SEND_PASSWORD ?? "true").trim().toLowerCase() !== "false";

  const duration = (mergedEnv.OVH_VPS_DURATION ?? "P1M").trim();
  const pricingMode = (mergedEnv.OVH_VPS_PRICING_MODE ?? "default").trim();
  const planCodesStr = mergedEnv.OVH_VPS_PLAN_CODES?.trim();
  const datacentersStr = mergedEnv.OVH_VPS_DATACENTERS?.trim();

  // Validate SSH key
  if (!fs.existsSync(sshPubKeyPath)) {
    throw new Error(`SSH public key not found: ${sshPubKeyPath}`);
  }
  if (!skipRebuild && !fs.existsSync(sshKeyPath)) {
    throw new Error(`SSH private key not found: ${sshKeyPath}`);
  }

  // List plans (informational)
  if (listPlans) {
    console.log("Plan codes (from OVH_VPS_PLAN_CODES):", planCodesStr || "(not set)");
    console.log("Datacenters (from OVH_VPS_DATACENTERS):", datacentersStr || "(not set)");
    console.log("Use these env vars to set available plans and datacenters.");
    return;
  }

  // Build plan code: try env var mapping first, fallback to raw `--plan` value
  const planMap = new Map<string, string>();
  if (planCodesStr) {
    for (const entry of planCodesStr.split(",")) {
      const trimmed = entry.trim();
      if (!trimmed) continue;
      const idx = trimmed.indexOf(":");
      if (idx > 0) {
        planMap.set(trimmed.slice(0, idx).trim().toLowerCase(), trimmed.slice(idx + 1).trim());
      } else {
        // Bare code — use directly
        planMap.set(trimmed.toLowerCase(), trimmed);
      }
    }
  }
  const planCode = planMap.get(plan.toLowerCase()) ?? plan;

  // Build datacenter list
  let datacenters: string[] = [];
  if (datacentersStr) {
    datacenters = datacentersStr.split(",").map((s) => s.trim()).filter(Boolean);
  }

  if (dryRun) {
    console.log("[dry-run] Would create VPS:");
    for (let i = 0; i < count; i++) {
      const dc = datacenter || (datacenters.length > 0 ? datacenters[i % datacenters.length] : "auto");
      console.log(`  ${i + 1}. plan=${plan} (code=${planCode}) os=${osName} dc=${dc} name=${namePrefix}-${i + 1}`);
    }
    console.log(`[dry-run] SSH key: ${sshPubKeyPath}`);
    console.log(`[dry-run] Total: ${count} VPS`);
    return;
  }

  // -----------------------------------------------------------------------
  // Create servers
  // -----------------------------------------------------------------------

  const results: { name: string; ipv4: string | null; status: string; message: string }[] = [];

  for (let i = 0; i < count; i++) {
    const dc = datacenter || (datacenters.length > 0 ? datacenters[i % datacenters.length] : "BHS");
    const displayName = count > 1 ? `${namePrefix}-${i + 1}` : namePrefix;

    console.log(`\n--- Creating VPS ${i + 1}/${count}: ${displayName} ---`);

    try {
      // Step 1: Order and pay
      console.log("Creating order...");
      const { cartId, itemId } = await createVpsOrder(ovhCfg, planCode, duration, pricingMode, dc, displayName);
      console.log(`Cart item: ${itemId}`);

      const { orderId } = await checkoutCart(ovhCfg, cartId);
      console.log(`Order placed: ${orderId ?? "see OVH control panel"}`);

      // Step 2: Wait for VPS to appear in service list
      console.log("Waiting for VPS delivery (this may take 2-10 minutes)...");
      const deadline = Date.now() + 20 * 60_000; // 20 min delivery timeout
      let serviceName = "";
      while (Date.now() < deadline) {
        const list = await ovhRequest<string[]>(ovhCfg, "GET", "/vps");
        if (Array.isArray(list.data)) {
          // Find a VPS with matching displayName or newest unknown
          for (const sn of list.data) {
            try {
              const detail = await ovhRequest<{ displayName?: string; state?: string }>(
                ovhCfg, "GET", `/vps/${encodeURIComponent(sn)}`,
              );
              if (detail.status < 300 && detail.data?.displayName === displayName) {
                serviceName = sn;
                break;
              }
            } catch { /* continue */ }
          }
          if (serviceName) break;
          // If we have services and count is low, the new one might be visible
          // Fallback: any service not previously known would work (tracked externally)
        }
        process.stdout.write(".");
        await sleep(30_000);
      }
      process.stdout.write("\n");

      if (!serviceName) {
        throw new Error("Timed out waiting for VPS to appear. Check OVH control panel.");
      }
      console.log(`VPS delivered: ${serviceName}`);

      // Step 3: Get VPS detail and IPs
      const detail = await ovhRequest<{
        displayName?: string;
        state?: string;
        zone?: string;
        vcore?: number;
        memoryLimit?: number;
        model?: { name?: string; offer?: string; disk?: number };
      }>(ovhCfg, "GET", `/vps/${encodeURIComponent(serviceName)}`);
      if (detail.status >= 300) {
        throw new Error(`failed to get VPS detail: ${detail.status}`);
      }

      const ipsResp = await ovhRequest<string[]>(
        ovhCfg, "GET", `/vps/${encodeURIComponent(serviceName)}/ips`,
      );
      const ips = Array.isArray(ipsResp.data) ? ipsResp.data : [];
      let ipv4 = pickIp(ips, "v4");
      const ipv6 = pickIp(ips, "v6");

      // Step 4: Rebuild with SSH key
      if (!skipRebuild) {
        console.log("Rebuilding with SSH key injection...");
        const imageId = await resolveImageId(ovhCfg, serviceName, osName, imageIdOverride);

        const rebuild = await ovhRequest<unknown>(
          ovhCfg,
          "POST",
          `/vps/${encodeURIComponent(serviceName)}/rebuild`,
          { imageId, publicSshKey, doNotSendPassword },
        );
        if (rebuild.status >= 300) {
          const err = rebuild.data as OvhError | null;
          throw new Error(`rebuild failed: ${rebuild.status} - ${err?.message ?? "unknown"}`);
        }
        console.log("Rebuild started. Waiting for SSH...");

        // Refresh IPs after rebuild (may change)
        await sleep(15_000);
        const ips2 = await ovhRequest<string[]>(
          ovhCfg, "GET", `/vps/${encodeURIComponent(serviceName)}/ips`,
        );
        const ips2Arr = Array.isArray(ips2.data) ? ips2.data : ips;
        ipv4 = pickIp(ips2Arr, "v4");
      }

      if (!ipv4) {
        throw new Error(`No IPv4 found for ${serviceName}`);
      }

      // Step 5: Wait for SSH
      if (!skipSsh) {
        console.log(`Waiting for SSH on ${sshUser}@${ipv4} ...`);
        const sshDeadline = Date.now() + timeoutMin * 60_000;
        let lastErr = "";
        while (Date.now() < sshDeadline) {
          sshKeygenRemoveHost(ipv4);
          const res = canSsh(ipv4, sshUser, sshKeyPath);
          if (res.ok) {
            console.log(`SSH OK: ${sshUser}@${ipv4}`);
            break;
          }
          lastErr = res.err ?? "";
          process.stdout.write(".");
          await sleep(15_000);
        }
        process.stdout.write("\n");
        if (Date.now() >= sshDeadline) {
          throw new Error(`Timed out waiting for SSH. Last error: ${lastErr}`);
        }
      }

      // Step 6: Print info
      const meta = detail.data ?? {};
      const planName = meta.model?.name ?? meta.model?.offer ?? plan;
      console.log(`\n✓ VPS ready: ${displayName}`);
      console.log(`  Service:    ${serviceName}`);
      console.log(`  IPv4:       ${ipv4}`);
      console.log(`  IPv6:       ${ipv6 ?? "(none)"}`);
      console.log(`  Plan:       ${planName}`);
      console.log(`  vCPU:       ${meta.vcore ?? "?"}`);
      console.log(`  Memory:     ${meta.memoryLimit ? `${meta.memoryLimit}MB` : "?"}`);
      console.log(`  Disk:       ${meta.model?.disk ? `${meta.model.disk}GB` : "?"}`);
      console.log(`  Region:     ${meta.zone ?? "?"}`);
      console.log(`  Login:      ssh -i ${sshKeyPath} ${sshUser}@${ipv4}`);

      results.push({ name: displayName, ipv4, status: "created", message: "OK" });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(`✗ Failed: ${msg}`);
      results.push({ name: displayName, ipv4: null, status: "failed", message: msg });
    }
  }

  // Final report
  const created = results.filter((r) => r.status === "created");
  const failed = results.filter((r) => r.status === "failed");
  console.log(`\n=== Report ===`);
  console.log(`Total: ${results.length} | Created: ${created.length} | Failed: ${failed.length}`);
  if (created.length > 0) {
    console.log("Created:");
    created.forEach((r) => console.log(`  - ${r.name}: ${r.ipv4}`));
  }
  if (failed.length > 0) {
    console.log("Failed:");
    failed.forEach((r) => console.log(`  - ${r.name}: ${r.message}`));
  }
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
});
