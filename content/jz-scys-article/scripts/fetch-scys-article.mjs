#!/usr/bin/env node

import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { execFile as execFileCallback } from "node:child_process";
import { promisify } from "node:util";

const execFile = promisify(execFileCallback);

const args = process.argv.slice(2);
const url = args.find((arg) => !arg.startsWith("--"));

if (!url) {
  console.error("Usage: fetch-scys-article.mjs <scys-article-url> [--out dir] [--port 9333] [--include-comments] [--no-feishu]");
  process.exit(2);
}

const optionValue = (name, fallback) => {
  const index = args.indexOf(name);
  if (index >= 0 && args[index + 1]) return args[index + 1];
  return fallback;
};

const expandHome = (value) => {
  if (!value) return value;
  if (value === "~") return os.homedir();
  if (value.startsWith("~/")) return path.join(os.homedir(), value.slice(2));
  return value;
};

const readConfig = async () => {
  const configDir = path.join(os.homedir(), ".config", "skills", "jz-scys-article");
  const names = ["config.yml", "config.yaml", "config.toml", "config.json"];
  for (const name of names) {
    const file = path.join(configDir, name);
    try {
      const text = await fs.readFile(file, "utf8");
      if (name.endsWith(".json")) return JSON.parse(text);
      const config = {};
      for (const line of text.split("\n")) {
        const match = line.match(/^\s*([A-Za-z0-9_-]+)\s*[:=]\s*["']?(.+?)["']?\s*$/);
        if (match) config[match[1]] = match[2];
      }
      return config;
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }
  }
  return {};
};

const config = await readConfig();
const port = Number(optionValue("--port", config.port || "9333"));
const outDir = expandHome(optionValue("--out", config.output_dir || "."));
const includeComments = args.includes("--include-comments");
const useFeishu = !args.includes("--no-feishu");

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const fetchJson = async (targetUrl, init) => {
  const res = await fetch(targetUrl, init);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${targetUrl}`);
  return res.json();
};

const getTopicId = (inputUrl) => {
  const match = inputUrl.match(/\/articleDetail\/([^/]+)\/([^/?#]+)/);
  if (!match) return "scys-article";
  return match[2].replace(/[^a-zA-Z0-9_-]/g, "-");
};

const slugify = (text, fallback) => {
  const normalized = text
    .trim()
    .replace(/[\\/:*?"<>|#]+/g, "-")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  return normalized.slice(0, 80) || fallback;
};

const stripMarkdownFrontmatter = (content) => {
  if (!content.startsWith("---\n")) return content.trim();
  const end = content.indexOf("\n---", 4);
  if (end < 0) return content.trim();
  return content.slice(end + 4).trim();
};

const extractMarkdownTitle = (content, fallback) => {
  const htmlTitle = content.match(/^\s*<title>(.*?)<\/title>\s*$/mi)?.[1]?.trim();
  if (htmlTitle) return htmlTitle;
  const titleLine = content.split("\n").find((line) => /^#\s+/.test(line.trim()));
  return titleLine ? titleLine.replace(/^#\s+/, "").trim() : fallback;
};

const normalizeFeishuBody = (content, title) => {
  return content.replace(/^\s*<title>.*?<\/title>\s*\n*/i, `# ${title}\n\n`);
};

const normalizeFeishuUrl = (rawUrl) => rawUrl
  .replace(/[),，。；;]+$/g, "")
  .replace(/\\+$/g, "");

const countMarkdownImages = (content) => {
  const markdownImages = content.match(/!\[[^\]]*\]\([^)]+\)/g) || [];
  const htmlImages = content.match(/<img\b[^>]*>/gi) || [];
  return markdownImages.length + htmlImages.length;
};

class CdpClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.nextId = 1;
    this.pending = new Map();
  }

  async connect() {
    this.ws = new WebSocket(this.wsUrl);
    this.ws.addEventListener("message", (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) reject(new Error(msg.error.message || JSON.stringify(msg.error)));
        else resolve(msg.result);
      }
    });
    await new Promise((resolve, reject) => {
      this.ws.addEventListener("open", resolve, { once: true });
      this.ws.addEventListener("error", reject, { once: true });
    });
  }

  send(method, params = {}) {
    const id = this.nextId++;
    const payload = JSON.stringify({ id, method, params });
    const promise = new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
    });
    this.ws.send(payload);
    return promise;
  }

  close() {
    this.ws?.close();
  }
}

const ensureChrome = async () => {
  try {
    return await fetchJson(`http://127.0.0.1:${port}/json/version`);
  } catch (error) {
    throw new Error(
      `Chrome for Testing is not reachable on port ${port}. Start it with --remote-debugging-port=${port}, then log in to scys.com.`
    );
  }
};

const createBackgroundTarget = async (browserWsUrl) => {
  if (!browserWsUrl) {
    throw new Error("Chrome did not expose a browser-level WebSocket debugger URL.");
  }
  const browserClient = new CdpClient(browserWsUrl);
  await browserClient.connect();
  try {
    const result = await browserClient.send("Target.createTarget", {
      url: "about:blank",
      background: true,
    });
    return result.targetId;
  } finally {
    browserClient.close();
  }
};

const findOrCreateTarget = async (targetUrl, browserWsUrl) => {
  const targets = await fetchJson(`http://127.0.0.1:${port}/json/list`);
  const existing = targets.find((target) => target.type === "page" && target.url.includes(targetUrl));
  if (existing) return existing;

  const sameArticle = targets.find((target) => {
    if (target.type !== "page") return false;
    const wantedId = getTopicId(targetUrl);
    return target.url.includes(`/articleDetail/`) && target.url.includes(wantedId);
  });
  if (sameArticle) return sameArticle;

  const targetId = await createBackgroundTarget(browserWsUrl);
  const refreshedTargets = await fetchJson(`http://127.0.0.1:${port}/json/list`);
  const created = refreshedTargets.find((target) => target.id === targetId);
  if (!created) throw new Error(`Cannot find created Chrome target: ${targetId}`);
  return created;
};

const evaluate = async (client, expression, awaitPromise = false) => {
  const result = await client.send("Runtime.evaluate", {
    expression,
    awaitPromise,
    returnByValue: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text || "Runtime.evaluate failed");
  }
  return result.result?.value;
};

const pageDataExpression = (withComments) => `(() => {
  const clean = (s) => (s || "")
    .replace(/\\u00a0/g, " ")
    .replace(/[ \\t]+\\n/g, "\\n")
    .replace(/\\n{3,}/g, "\\n\\n")
    .trim();
  const norm = (u) => {
    try { return new URL(u, location.href).href; } catch { return ""; }
  };
  const lines = clean(document.body.innerText).split("\\n").map((s) => s.trim()).filter(Boolean);
  const title = document.title || "";
  const dateIndex = lines.findIndex((line) => /^20\\d\\d-\\d\\d-\\d\\d/.test(line));
  const author = dateIndex > 0 ? lines[dateIndex - 1] : "";
  const publishedAt = dateIndex >= 0 ? lines[dateIndex] : "";
  const topicTitleIndex = lines.findIndex((line) => title && line.includes(title.replace(/\\s+50$/, "5000+")));
  const articleStart = topicTitleIndex >= 0 ? topicTitleIndex : lines.findIndex((line) => line.includes("项目复盘") || line.includes("这篇文章"));
  const stopMarkers = ["AI生图", "全部评论", "目录"];
  let articleEnd = lines.length;
  for (const marker of stopMarkers) {
    const idx = lines.findIndex((line, i) => i > articleStart && (line === marker || line.includes(marker)));
    if (idx > 0) articleEnd = Math.min(articleEnd, idx);
  }
  const articleLines = articleStart >= 0 ? lines.slice(articleStart, articleEnd) : [];
  const tocIndex = lines.lastIndexOf("目录");
  const toc = tocIndex >= 0
    ? lines.slice(tocIndex + 1).filter((line) => !["回到顶部", "返回", "查看评论"].includes(line)).slice(0, 120)
    : [];
  const commentsIndex = lines.findIndex((line) => line.includes("全部评论"));
  const comments = ${withComments ? "commentsIndex >= 0 ? lines.slice(commentsIndex, tocIndex >= 0 ? tocIndex : undefined) : []" : "[]"};
  const feishuLinks = [];
  const seenFeishu = new Set();
  const addFeishu = (raw) => {
    const href = norm(raw);
    if (!href || seenFeishu.has(href)) return;
    if (!/^https:\\/\\/[^/]*feishu\\.cn\\//.test(href)) return;
    if (!/\\/(wiki|docx|docs)\\//.test(href)) return;
    seenFeishu.add(href);
    feishuLinks.push(href);
  };
  for (const anchor of Array.from(document.links)) addFeishu(anchor.href);
  for (const line of lines) {
    for (const match of line.matchAll(/https:\\/\\/[^\\s"'<>）)]+feishu\\.cn\\/[^\\s"'<>）)]+/g)) addFeishu(match[0]);
  }
  const imageUrls = [];
  const seen = new Set();
  for (const img of Array.from(document.images)) {
    const src = norm(img.currentSrc || img.src);
    if (!src || seen.has(src)) continue;
    if (!src.includes("sphere-search-mobile.oss-cn-shanghai.aliyuncs.com/upload/doc/blocks/")) continue;
    seen.add(src);
    imageUrls.push(src);
  }
  const commentImageUrls = [];
  const seenComment = new Set();
  for (const img of Array.from(document.images)) {
    const src = norm(img.currentSrc || img.src);
    if (!src || seenComment.has(src)) continue;
    if (!src.includes("/public/upload/")) continue;
    seenComment.add(src);
    commentImageUrls.push(src);
  }
  return {
    url: location.href,
    title,
    author,
    publishedAt,
    articleLines,
    toc,
    comments,
    feishuLinks,
    imageUrls,
    commentImageUrls,
    bodyText: clean(document.body.innerText).slice(0, 500),
  };
})()`;

const markdownEscape = (value) => String(value ?? "").replace(/"/g, '\\"');

const buildMarkdown = (data, sourceUrl, topicId) => {
  const fetchedAt = new Date().toISOString();
  const title = data.articleLines?.[0] || data.title || topicId;
  const parts = [
    "---",
    `title: "${markdownEscape(title)}"`,
    "type: scys-clipping",
    `source_url: "${markdownEscape(sourceUrl)}"`,
    `resolved_url: "${markdownEscape(data.url)}"`,
    `topic_id: "${markdownEscape(topicId)}"`,
    data.author ? `author: "${markdownEscape(data.author)}"` : "",
    data.publishedAt ? `published_at: "${markdownEscape(data.publishedAt)}"` : "",
    `fetched_at: "${fetchedAt}"`,
    `image_count: ${data.imageUrls.length}`,
    `include_comments: ${data.comments.length > 0 ? "true" : "false"}`,
    "---",
    "",
    `# ${title}`,
    "",
  ].filter(Boolean);

  if (data.author || data.publishedAt) {
    parts.push(`> ${[data.author, data.publishedAt].filter(Boolean).join(" | ")}`, "");
  }

  if (data.toc.length) {
    parts.push("## 目录", "");
    for (const item of data.toc) parts.push(`- ${item}`);
    parts.push("");
  }

  parts.push("## 正文", "");
  for (const line of data.articleLines.slice(1)) {
    if (/^\\d+\\.$/.test(line) || line === "•") {
      parts.push(line);
    } else {
      parts.push(line, "");
    }
  }

  if (data.imageUrls.length) {
    parts.push("## 图片", "");
    data.imageUrls.forEach((imageUrl, index) => {
      parts.push(`![图 ${String(index + 1).padStart(2, "0")}](${imageUrl})`, "");
    });
  }

  if (data.comments.length) {
    parts.push("## 评论", "");
    for (const line of data.comments) parts.push(line, "");
    if (data.commentImageUrls.length) {
      parts.push("### 评论图片", "");
      data.commentImageUrls.forEach((imageUrl, index) => {
        parts.push(`![评论图 ${String(index + 1).padStart(2, "0")}](${imageUrl})`, "");
      });
    }
  }

  return parts.join("\n").replace(/\n{3,}/g, "\n\n");
};

const fetchFeishuMarkdown = async (feishuUrl) => {
  const { stdout } = await execFile("lark-cli", [
    "docs",
    "+fetch",
    "--api-version",
    "v2",
    "--as",
    "user",
    "--doc",
    feishuUrl,
    "--doc-format",
    "markdown",
    "--format",
    "json",
  ], {
    maxBuffer: 50 * 1024 * 1024,
  });
  const payload = JSON.parse(stdout);
  const document = payload.data?.document;
  if (!document?.content) throw new Error("lark-cli did not return Markdown content");
  return {
    content: document.content,
    documentId: document.document_id || "",
    revisionId: document.revision_id || "",
    notice: payload._notice,
  };
};

const buildFeishuMarkdown = ({ feishu, feishuUrl, sourceUrl, resolvedUrl, topicId, scysTitle }) => {
  const body = stripMarkdownFrontmatter(feishu.content);
  const title = extractMarkdownTitle(body, scysTitle || topicId);
  const normalizedBody = normalizeFeishuBody(body, title);
  const fetchedAt = new Date().toISOString();
  const imageCount = countMarkdownImages(normalizedBody);
  const frontmatter = [
    "---",
    `title: "${markdownEscape(title)}"`,
    "type: feishu-clipping",
    `source_url: "${markdownEscape(feishuUrl)}"`,
    `scys_source_url: "${markdownEscape(sourceUrl)}"`,
    `scys_resolved_url: "${markdownEscape(resolvedUrl)}"`,
    `topic_id: "${markdownEscape(topicId)}"`,
    feishu.documentId ? `document_id: "${markdownEscape(feishu.documentId)}"` : "",
    feishu.revisionId ? `revision_id: "${markdownEscape(feishu.revisionId)}"` : "",
    `fetched_at: "${fetchedAt}"`,
    `image_count: ${imageCount}`,
    "---",
    "",
  ].filter(Boolean);
  return {
    title,
    imageCount,
    content: `${frontmatter.join("\n")}\n${normalizedBody}\n`,
  };
};

const updateDownloaded = async (recordPath, row) => {
  let lines = [];
  try {
    const existing = await fs.readFile(recordPath, "utf8");
    lines = existing.split("\n").filter(Boolean);
  } catch {}
  const header = "source_url | topic_id | title | clipping_file | image_count | fetched_at | note";
  if (!lines.length) lines.push(header);
  const filtered = lines.filter((line, index) => index === 0 || !line.includes(`| ${row.topicId} |`));
  filtered.push(`${row.sourceUrl} | ${row.topicId} | ${row.title} | ${row.fileName} | ${row.imageCount} | ${row.fetchedAt} | ${row.note}`);
  await fs.writeFile(recordPath, `${filtered.join("\n")}\n`);
};

const browser = await ensureChrome();
const target = await findOrCreateTarget(url, browser.webSocketDebuggerUrl);
const client = new CdpClient(target.webSocketDebuggerUrl);
await client.connect();

await client.send("Page.enable").catch(() => {});
await client.send("Runtime.enable").catch(() => {});

if (!target.url.includes(getTopicId(url))) {
  await client.send("Page.navigate", { url });
}

await sleep(2500);

const data = await evaluate(client, pageDataExpression(includeComments), false);
client.close();

if (!data || !data.articleLines?.length || /即将前往登录页|登录/.test(data.bodyText || "")) {
  console.error("Failed to extract article. The page appears unauthenticated or empty.");
  console.error("Check Chrome for Testing on port 9333, open the target URL there, log in to scys.com, then retry.");
  process.exit(1);
}

const topicId = getTopicId(url);
const title = data.articleLines[0] || data.title || topicId;
await fs.mkdir(outDir, { recursive: true });

let fileName;
let outputTitle = title;
let outputImageCount = data.imageUrls.length;
let outputMode = "scys";
let feishuUrl = "";
let markdown;

if (useFeishu && data.feishuLinks?.length) {
  feishuUrl = normalizeFeishuUrl(data.feishuLinks[0]);
  const feishu = await fetchFeishuMarkdown(feishuUrl);
  const built = buildFeishuMarkdown({
    feishu,
    feishuUrl,
    sourceUrl: url,
    resolvedUrl: data.url,
    topicId,
    scysTitle: title,
  });
  outputTitle = built.title;
  outputImageCount = built.imageCount;
  outputMode = "feishu";
  fileName = `${topicId}-${slugify(outputTitle, topicId)}.md`;
  markdown = built.content;
} else {
  fileName = `${topicId}-${slugify(title, topicId)}.md`;
  markdown = buildMarkdown(data, url, topicId);
}

const outputPath = path.join(outDir, fileName);
await fs.writeFile(outputPath, markdown);

const fetchedAt = new Date().toISOString();
await updateDownloaded(path.join(outDir, "downloaded.md"), {
  sourceUrl: url,
  topicId,
  title: outputTitle,
  fileName,
  imageCount: outputImageCount,
  fetchedAt,
  note: outputMode === "feishu" ? `feishu: ${feishuUrl}` : includeComments ? "with comments" : "article only",
});

console.log(JSON.stringify({
  output: outputPath,
  title: outputTitle,
  mode: outputMode,
  author: data.author,
  publishedAt: data.publishedAt,
  imageCount: outputImageCount,
  commentImageCount: data.commentImageUrls.length,
  feishuUrl: feishuUrl || null,
  includeComments,
  downloadedRecord: path.join(outDir, "downloaded.md"),
}, null, 2));
