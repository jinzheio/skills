---
name: add-indexnow
version: "1.1.0"
description: "当用户想给公开 Web 应用、Next.js 站点或静态站点增加 IndexNow 支持时使用：创建 key 验证文件、URL 收集脚本、URL 提交脚本、文档和验证流程。触发语包括 add IndexNow、submit changed URLs、set up post-push URL submission。不要单独用于 Google Search Console 或 Bing Webmaster onboarding；没有公开 URL 的仓库也不要使用。"
---

# add-indexnow

用于给已有 Web 项目增加 IndexNow 支持，通常是 Next.js 项目。

## 开始

1. 如果目标项目目录不明确，先确认目录。
2. 为该项目生成新的随机 IndexNow key。

不要让用户提前准备 key。不要复用其它项目或域名的 key。每个项目使用独立的新 key。

## 目标

增加一套轻量 IndexNow 流程：

- 生成项目专用随机 key
- 暴露 `public/<key>.txt` 用于所有权验证
- 基于项目公开路由创建 URL 收集脚本
- 创建批量提交 URL 的脚本
- 在 `package.json` 增加 collect / submit 命令
- 写明运行方式
- 用 dry run 和 lint 验证

## 交付物

创建或更新：

- `scripts/indexnow-submit.ts`
- `scripts/indexnow-collect-urls.ts`
- `docs/indexnow.md`
- `package.json`
- `public/<INDEXNOW_KEY>.txt`

## 流程

1. 改动前检查目标仓库：
   - `package.json`
   - 公开路由文件
   - sitemap / robots 文件
   - 域名配置

2. 确认 canonical base URL。
   优先使用项目已有域名配置。如果同时存在 env 和硬编码域名逻辑，沿用项目现有模式。

3. 将变更文件映射到公开 URL。
   收集器必须贴合目标 app 的真实路由结构。跳过：
   - API routes
   - admin 或需要登录的路由
   - scripts 和数据库文件
   - 内部页面

4. 为项目生成新 key。
   优先使用 `openssl rand -hex 16` 或等价安全随机字符串。

5. 生成文件。
   以 `assets/` 里的模板为起点，再按目标项目调整路由、base URL 默认值和排除规则。不要不加修改地复制模板。

6. 增加 key 验证文件。
   创建 `public/<key>.txt`，文件内容必须是 key 本身。

7. 验证：
   - 对近期 git diff 跑 URL collector
   - 用 `--dry-run` 跑 submit
   - 跑项目 lint

8. 汇报：
   - 包含哪些路由
   - 跳过哪些路由
   - lint 是否只有既有 warning，还是产生了新问题
   - 在总结里给出生成的 key，方便用户保存

## 验证清单

- collector 只输出目标 host 下的公开站点 URL。
- submit 脚本接受 `--urls-file`。
- submit 脚本支持 `INDEXNOW_KEY` 或读取 `public/<key>.txt`。
- submit 脚本过滤其它 host 的 URL。
- dry run 不发真实请求。
- 文档包含常用命令、环境变量和排查方法。
- lint 通过，或仅有与本次无关的既有问题。
