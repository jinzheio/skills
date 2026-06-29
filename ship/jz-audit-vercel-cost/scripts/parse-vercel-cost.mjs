#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import process from "node:process";

function parseArgs(argv) {
  const args = {
    platformFee: 20,
    cycleDay: 3,
    scope: process.env.VERCEL_SCOPE || "",
    token: process.env.VERCEL_TOKEN || "",
  };
  for (let index = 2; index < argv.length; index += 1) {
    const arg = argv[index];
    const next = argv[index + 1];
    if (arg === "--from") args.from = next, index += 1;
    else if (arg === "--to") args.to = next, index += 1;
    else if (arg === "--platform-fee") args.platformFee = Number(next), index += 1;
    else if (arg === "--cycle-day") args.cycleDay = Number(next), index += 1;
    else if (arg === "--scope") args.scope = next, index += 1;
    else if (arg === "--token") args.token = next, index += 1;
    else if (arg === "--help" || arg === "-h") args.help = true;
  }
  return args;
}

function usage() {
  console.log(`Usage:
  node scripts/parse-vercel-cost.mjs --from YYYY-MM-DD --to YYYY-MM-DD [--cycle-day 3] [--platform-fee 20]

Output:
  JSON with effective usage, non-Pro billed usage, and projected receipt amount.`);
}

function roundMoney(value) {
  return Number(Number(value || 0).toFixed(6));
}

function runVercelUsage(args) {
  const cliArgs = ["usage", "--format", "json", "--from", args.from, "--to", args.to];
  if (args.scope) cliArgs.push("--scope", args.scope);
  if (args.token) cliArgs.push("--token", args.token);
  const stdout = execFileSync("vercel", cliArgs, {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  const start = stdout.indexOf("{");
  const end = stdout.lastIndexOf("}");
  if (start < 0 || end < start) {
    throw new Error("vercel usage did not return JSON");
  }
  return JSON.parse(stdout.slice(start, end + 1));
}

function summarize(args, usageJson) {
  const services = usageJson.services || [];
  const nonProServices = services.filter((service) => service.name !== "Pro");
  const nonProBilled = nonProServices.reduce((sum, service) => sum + Number(service.billedCost || 0), 0);
  const proratedProBilled = services
    .filter((service) => service.name === "Pro")
    .reduce((sum, service) => sum + Number(service.billedCost || 0), 0);
  const topNonProBilledServices = nonProServices
    .filter((service) => Number(service.billedCost || 0) > 0)
    .sort((left, right) => Number(right.billedCost || 0) - Number(left.billedCost || 0))
    .slice(0, 12)
    .map((service) => ({
      name: service.name,
      billedCostUsd: roundMoney(service.billedCost),
      effectiveCostUsd: roundMoney(service.effectiveCost),
      pricingQuantity: service.pricingQuantity,
      pricingUnit: service.pricingUnit,
    }));
  const topEffectiveServices = services
    .filter((service) => Number(service.effectiveCost || 0) > 0)
    .sort((left, right) => Number(right.effectiveCost || 0) - Number(left.effectiveCost || 0))
    .slice(0, 12)
    .map((service) => ({
      name: service.name,
      effectiveCostUsd: roundMoney(service.effectiveCost),
      billedCostUsd: roundMoney(service.billedCost),
      pricingQuantity: service.pricingQuantity,
      pricingUnit: service.pricingUnit,
    }));

  return {
    input: {
      from: args.from,
      to: args.to,
      cycleDay: args.cycleDay,
      platformFeeUsd: args.platformFee,
    },
    vercelPeriod: usageJson.period,
    context: usageJson.context,
    pricingUnit: usageJson.pricingUnit,
    effectiveUsageCostUsd: roundMoney(usageJson.totals?.effectiveCost),
    totalBilledCostUsd: roundMoney(usageJson.totals?.billedCost),
    proratedProBilledInUsageQueryUsd: roundMoney(proratedProBilled),
    nonProBilledUsageUsd: roundMoney(nonProBilled),
    projectedReceiptAmountUsd: roundMoney(Number(args.platformFee || 0) + nonProBilled),
    topNonProBilledServices,
    topEffectiveServices,
  };
}

const args = parseArgs(process.argv);
if (args.help || !args.from || !args.to) {
  usage();
  process.exit(args.help ? 0 : 1);
}

try {
  const usageJson = runVercelUsage(args);
  console.log(JSON.stringify(summarize(args, usageJson), null, 2));
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}
