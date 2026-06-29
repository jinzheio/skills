#!/usr/bin/env node

import { existsSync, mkdirSync, readFileSync, writeFileSync, copyFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const REQUIRED_FILES = ['about.md', 'voice.md', 'anti-style.md'];
const ALL_TARGETS = ['codex', 'chatgpt', 'claude', 'claude-code'];
const BLOCK_ID = 'build-personal-context';
const DEFAULT_PROFILE_DIR = path.join(os.homedir(), 'Projects', 'aboutme');

function usage() {
  return `Usage:
  node scripts/install-profile.mjs [--source <dir>] [--profile-dir <dir>] [--targets codex,chatgpt,claude,claude-code]
  node scripts/install-profile.mjs -g

Options:
  --source <dir>       Directory containing about.md, voice.md, anti-style.md. Default: ~/Projects/aboutme
  --profile-dir <dir>  Shared profile directory. Default: ~/Projects/aboutme
  --targets <list>     Comma-separated targets
  -g, --global         Enable all targets
  --dry-run            Print planned writes without changing files
`;
}

function parseArgs(argv) {
  const args = {
    source: '',
    profileDir: DEFAULT_PROFILE_DIR,
    targets: [],
    global: false,
    dryRun: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--source') {
      args.source = argv[++i] ?? '';
    } else if (arg === '--profile-dir') {
      args.profileDir = argv[++i] ?? args.profileDir;
    } else if (arg === '--targets') {
      args.targets = (argv[++i] ?? '').split(',').map((item) => item.trim()).filter(Boolean);
    } else if (arg === '-g' || arg === '--global') {
      args.global = true;
    } else if (arg === '--dry-run') {
      args.dryRun = true;
    } else if (arg === '-h' || arg === '--help') {
      console.log(usage());
      process.exit(0);
    } else {
      throw new Error(`Unknown option: ${arg}`);
    }
  }

  args.source ||= args.profileDir;

  if (args.global) {
    args.targets = ALL_TARGETS;
  }

  if (args.targets.length === 0) {
    throw new Error('Choose --targets <list> or use -g.');
  }

  const unknownTargets = args.targets.filter((target) => !ALL_TARGETS.includes(target));
  if (unknownTargets.length > 0) {
    throw new Error(`Unknown target(s): ${unknownTargets.join(', ')}`);
  }

  return {
    ...args,
    source: expandHome(args.source),
    profileDir: expandHome(args.profileDir),
    targets: Array.from(new Set(args.targets)),
  };
}

function expandHome(value) {
  if (value === '~') return os.homedir();
  if (value.startsWith('~/')) return path.join(os.homedir(), value.slice(2));
  return path.resolve(value);
}

function validateSource(sourceDir) {
  if (!existsSync(sourceDir)) {
    throw new Error(`Source directory does not exist: ${sourceDir}`);
  }

  const missing = REQUIRED_FILES.filter((name) => !existsSync(path.join(sourceDir, name)));
  if (missing.length > 0) {
    throw new Error(`Missing required file(s): ${missing.join(', ')}.`);
  }
}

function readProfile(profileDir) {
  return Object.fromEntries(
    REQUIRED_FILES.map((name) => [name, readFileSync(path.join(profileDir, name), 'utf8').trim()])
  );
}

function writeFilePlanned(filePath, content, dryRun, writes) {
  writes.push(filePath);
  if (dryRun) return;
  mkdirSync(path.dirname(filePath), { recursive: true });
  writeFileSync(filePath, content, 'utf8');
}

function copyProfileFiles(sourceDir, profileDir, dryRun, writes) {
  if (!dryRun) {
    mkdirSync(profileDir, { recursive: true });
  }

  for (const name of REQUIRED_FILES) {
    const from = path.join(sourceDir, name);
    const to = path.join(profileDir, name);
    writes.push(to);
    if (!dryRun) {
      copyFileSync(from, to);
    }
  }
}

function managedBlock(content) {
  const about = path.join(content.profileDir, 'about.md');
  const voice = path.join(content.profileDir, 'voice.md');
  const antiStyle = path.join(content.profileDir, 'anti-style.md');

  return [
    `<!-- ${BLOCK_ID}:start -->`,
    `## 个人上下文`,
    ``,
    `当运行环境可以读取本机文件时，按任务类型读取这些文件：`,
    ``,
    `- 代我完成任何任务前，读取 ${about}。`,
    `- 写作、编辑、消息、发布、命名、UX 文案、文档、README、prompt 或对外文本任务，读取 ${voice}。`,
    `- 写作或编辑任务，还要读取 ${antiStyle}，并把它作为排除清单。`,
    ``,
    `如果文件不可用，继续处理当前请求。只有当缺失文件会影响结果时，才说明缺失情况。`,
    ``,
    `除非我明确要求，不要把这些文件原文贴回给我。把它们作为偏好和约束使用。`,
    `<!-- ${BLOCK_ID}:end -->`,
  ].join('\n');
}

function upsertManagedBlock(filePath, block, dryRun, writes) {
  const start = `<!-- ${BLOCK_ID}:start -->`;
  const end = `<!-- ${BLOCK_ID}:end -->`;
  const current = existsSync(filePath) ? readFileSync(filePath, 'utf8') : '';
  const pattern = new RegExp(`${escapeRegExp(start)}[\\s\\S]*?${escapeRegExp(end)}`);
  const next = pattern.test(current)
    ? current.replace(pattern, block)
    : [current.trimEnd(), block].filter(Boolean).join('\n\n') + '\n';

  writeFilePlanned(filePath, next, dryRun, writes);
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function chatgptInstructions(profile) {
  return `# ChatGPT Custom Instructions

Use the following profile when writing, planning, or making recommendations for me.

## About Me

${profile['about.md']}

## Voice Profile

${profile['voice.md']}

## Anti AI Writing Style

${profile['anti-style.md']}
`;
}

function claudeInstructions(profile) {
  return `# Claude Project Instructions

Read this as persistent user context before producing drafts, strategy, analysis, or code-facing prose.

## About Me

${profile['about.md']}

## Voice Profile

${profile['voice.md']}

## Anti AI Writing Style

${profile['anti-style.md']}
`;
}

function installTargets(args, writes) {
  const profile = readProfile(args.dryRun ? args.source : args.profileDir);

  for (const target of args.targets) {
    if (target === 'codex') {
      upsertManagedBlock(
        path.join(os.homedir(), '.codex', 'AGENTS.md'),
        managedBlock({ profileDir: args.profileDir }),
        args.dryRun,
        writes
      );
    }

    if (target === 'claude-code') {
      upsertManagedBlock(
        path.join(os.homedir(), '.claude', 'CLAUDE.md'),
        managedBlock({ profileDir: args.profileDir }),
        args.dryRun,
        writes
      );
    }

    if (target === 'chatgpt') {
      writeFilePlanned(
        path.join(args.profileDir, 'chatgpt-custom-instructions.md'),
        chatgptInstructions(profile),
        args.dryRun,
        writes
      );
    }

    if (target === 'claude') {
      writeFilePlanned(
        path.join(args.profileDir, 'claude-project-instructions.md'),
        claudeInstructions(profile),
        args.dryRun,
        writes
      );
    }
  }
}

function main() {
  try {
    const args = parseArgs(process.argv.slice(2));
    validateSource(args.source);

    const writes = [];
    copyProfileFiles(args.source, args.profileDir, args.dryRun, writes);
    installTargets(args, writes);

    console.log(args.dryRun ? 'Dry run complete. Planned writes:' : 'Install complete. Written files:');
    for (const filePath of writes) {
      console.log(`- ${filePath}`);
    }

    if (args.targets.includes('chatgpt')) {
      console.log('ChatGPT: paste or upload chatgpt-custom-instructions.md where your ChatGPT workspace can use it.');
    }
    if (args.targets.includes('claude')) {
      console.log('Claude: paste or upload claude-project-instructions.md into Claude Project, Chat, or Cowork instructions.');
    }
  } catch (error) {
    console.error(error.message);
    console.error('');
    console.error(usage());
    process.exit(1);
  }
}

main();
