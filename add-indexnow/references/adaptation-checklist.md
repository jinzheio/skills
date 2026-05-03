# Collector 适配清单

把 `indexnow-collect-urls.ts` 适配到新项目时使用这份清单。

## Key 设置

- 为当前项目生成新的随机 IndexNow key。
- 创建 `public/<key>.txt`，内容必须与 key 完全一致。
- 除非用户明确要求共享运维配置，不要跨项目或 host 复用 key。

## 路由盘点

- 从 `src/app`、`app`、router config 或 CMS 内容目录列出所有公开页面。
- 标出内部页面，例如 admin、profile、auth、dashboard、settings 和 API routes。
- 检查是否有 locale 前缀、blog slug 或生成内容路由。

## 全局文件

这些文件变化时，通常需要提交多个或全部公开页面：

- root layout
- sitemap
- robots
- site config 或 domain config
- shared navigation
- homepage shared sections

## 文件到路由映射

- 直接 page 文件映射到直接 URL。
- content 文件映射到渲染后的 URL。
- shared components 映射到它实际影响的页面。
- assets 和 backend-only 变更默认跳过，除非影响可抓取页面。

## 验证

- 对近期 diff 运行 collector，并检查输出文件。
- 确认没有 API、auth、admin 或其它 host 的 URL。
- 先用 `--dry-run` 运行 submit。
- 创建文件后运行仓库 lint。
