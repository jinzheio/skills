#!/usr/bin/env node
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

async function loadPlaywright() {
  try {
    return await import("playwright");
  } catch {
    const require = createRequire(import.meta.url);
    const resolved = require.resolve("playwright", { paths: [process.cwd()] });
    return await import(pathToFileURL(resolved).href);
  }
}

function parseArgs(argv) {
  const args = { profileUrl: "", cdp: "http://127.0.0.1:9333", limit: 30, maxRounds: 120 };
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === "--profile-url") args.profileUrl = argv[++i];
    else if (argv[i] === "--cdp") args.cdp = argv[++i];
    else if (argv[i] === "--limit") args.limit = Number(argv[++i]);
    else if (argv[i] === "--max-rounds") args.maxRounds = Number(argv[++i]);
  }
  if (!args.profileUrl) throw new Error("--profile-url is required");
  return args;
}

async function sourceCookies(cdp) {
  let browser;
  try {
    browser = await chromium.connectOverCDP(cdp);
    const context = browser.contexts()[0];
    return context ? await context.cookies("https://www.douyin.com") : [];
  } finally {
    await browser?.close().catch(() => {});
  }
}

async function dismiss(page) {
  for (const text of ["取消", "稍后", "我知道了"]) {
    const loc = page.getByText(text, { exact: true }).first();
    try {
      if (await loc.count()) {
        await loc.click({ timeout: 3000 });
        await page.waitForTimeout(1200);
        return;
      }
    } catch {}
  }
}

async function extract(page) {
  return page.evaluate(() => {
    const out = [];
    const seen = new Set();
    const add = (id, href, text) => {
      if (!id || seen.has(id)) return;
      seen.add(id);
      const clean = (text || "").replace(/\s+/g, " ").trim();
      if (clean.startsWith("置顶")) return;
      out.push({
        id,
        kind: "video",
        url: `https://www.douyin.com/video/${id}`,
        href,
        title: clean.slice(0, 240),
      });
    };
    for (const node of document.querySelectorAll("a[href]")) {
      const href = new URL(node.getAttribute("href"), location.href).href;
      const text = node.innerText || node.getAttribute("aria-label") || node.title || "";
      const match = href.match(/\/video\/(\d{10,25})/);
      if (match) add(match[1], href, text);
    }
    return out;
  });
}

async function scroll(page) {
  return page.evaluate(() => {
    const candidates = [document.scrollingElement, document.documentElement, document.body, ...document.querySelectorAll("*")]
      .filter(Boolean)
      .map((el) => ({ el, room: Math.max(0, (el.scrollHeight || 0) - (el.clientHeight || 0)) }))
      .filter((entry) => entry.room > 50)
      .sort((a, b) => b.room - a.room);
    const target = candidates[0]?.el || document.scrollingElement || document.documentElement;
    const before = target.scrollTop || window.scrollY || 0;
    const delta = Math.max((target.clientHeight || window.innerHeight) * 0.85, 900);
    if (target === document.scrollingElement || target === document.documentElement || target === document.body) window.scrollBy(0, delta);
    else target.scrollTop = before + delta;
    const after = target.scrollTop || window.scrollY || 0;
    return after !== before;
  });
}

const args = parseArgs(process.argv.slice(2));
const playwright = await loadPlaywright();
const chromium = playwright.chromium ?? playwright.default?.chromium;
if (!chromium) throw new Error("Playwright chromium export not found");
const cookies = await sourceCookies(args.cdp);
const browser = await chromium.launch({ headless: true, args: ["--disable-blink-features=AutomationControlled"] });
try {
  const context = await browser.newContext({
    locale: "zh-CN",
    viewport: { width: 1440, height: 1200 },
    userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
  });
  if (cookies.length) await context.addCookies(cookies);
  const page = await context.newPage();
  await page.goto(args.profileUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(4000);
  await dismiss(page);
  const seen = new Map();
  let idle = 0;
  for (let round = 0; round < args.maxRounds && seen.size < args.limit; round += 1) {
    for (const item of await extract(page)) {
      if (!seen.has(item.id)) seen.set(item.id, item);
    }
    const moved = await scroll(page);
    idle = moved ? 0 : idle + 1;
    if (idle > 10) break;
    await page.waitForTimeout(2200 + Math.floor(Math.random() * 800));
  }
  process.stdout.write(JSON.stringify(Array.from(seen.values()).slice(0, args.limit)));
} finally {
  await browser.close().catch(() => {});
}
