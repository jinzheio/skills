#!/usr/bin/env node
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { basename, join } from "node:path";
import { spawnSync } from "node:child_process";

function run(cmd, args) {
  const result = spawnSync(cmd, args, { encoding: "utf8" });
  return {
    ok: result.status === 0,
    stdout: result.stdout.trim(),
    stderr: result.stderr.trim(),
  };
}

function has(path) {
  return existsSync(path);
}

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return null;
  }
}

function listWorkflows() {
  const dir = ".github/workflows";
  if (!has(dir)) return [];
  return readdirSync(dir)
    .filter((file) => /\.(ya?ml)$/.test(file))
    .map((file) => {
      const path = join(dir, file);
      const text = readFileSync(path, "utf8");
      return {
        file: path,
        cloudflare: /cloudflare|wrangler|pages/i.test(text),
        pull_request: /pull_request/.test(text),
        push: /\bpush\b/.test(text),
        deploy: /deploy/i.test(text),
      };
    });
}

const pkg = readJson("package.json");
const workflows = listWorkflows();
const gitStatus = run("git", ["status", "--short", "--branch"]);
const branch = run("git", ["branch", "--show-current"]);
const remote = run("git", ["remote", "-v"]);

const envFiles = [".env", ".env.local", ".env.production", ".env.development", ".dev.vars", ".env.example"]
  .filter(has)
  .map((file) => {
    const text = readFileSync(file, "utf8");
    const vars = text
      .split(/\r?\n/)
      .map((line) => line.match(/^([A-Za-z_][A-Za-z0-9_]*)=/)?.[1])
      .filter(Boolean);
    return { file, vars };
  });

const state = {
  project: basename(process.cwd()),
  git: {
    is_repo: gitStatus.ok,
    branch: branch.stdout || null,
    status: gitStatus.stdout || gitStatus.stderr || null,
    remotes: remote.stdout ? remote.stdout.split(/\r?\n/) : [],
  },
  package: pkg
    ? {
        package_manager: has("pnpm-lock.yaml")
          ? "pnpm"
          : has("yarn.lock")
            ? "yarn"
            : has("package-lock.json")
              ? "npm"
              : has("bun.lockb") || has("bun.lock")
                ? "bun"
                : null,
        scripts: pkg.scripts ? Object.keys(pkg.scripts).sort() : [],
        cloudflare_dependencies: Object.keys({ ...(pkg.dependencies || {}), ...(pkg.devDependencies || {}) })
          .filter((name) => /wrangler|cloudflare|opennext/i.test(name))
          .sort(),
      }
    : null,
  cloudflare: {
    wrangler_jsonc: has("wrangler.jsonc"),
    wrangler_json: has("wrangler.json"),
    wrangler_toml: has("wrangler.toml"),
    open_next_config: has("open-next.config.ts") || has("open-next.config.js") || has("open-next.config.mjs"),
  },
  github_actions: {
    workflows,
    has_cloudflare_production_deploy: workflows.some((wf) => wf.cloudflare && wf.push && wf.deploy),
    has_pr_preview: workflows.some((wf) => wf.cloudflare && wf.pull_request),
  },
  public_site: {
    robots: has("public/robots.txt") || has("app/robots.ts") || has("src/app/robots.ts"),
    sitemap: has("public/sitemap.xml") || has("app/sitemap.ts") || has("src/app/sitemap.ts"),
  },
  env_files: envFiles,
};

console.log(JSON.stringify(state, null, 2));
