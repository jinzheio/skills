---
name: jz-scys-article
description: "获取生财有术 scys.com 文章内容并保存为 Markdown。用户给出生财 articleDetail/xq_topic 链接，要求抓取正文、评论、目录、图片 URL、生成 clipping、处理登录态、复用 Chrome for Testing、排查 token 鉴权失败，或识别文章中的飞书/wiki 全文链接并下载飞书正文时使用。图片默认只保留远程 URL，不下载到本地；如果全文在飞书中，输出飞书内容并在 metadata 记录 scys 原始链接。"
---

# 生财文章获取

用于把 `scys.com/articleDetail/xq_topic/...` 文章保存为 Markdown clipping。默认保留正文图片远程 URL，不下载图片。

如果生财正文只放摘要，完整文章在飞书/wiki 链接中，优先下载飞书内容作为输出，并在 frontmatter 里保留生财原始链接。

## 默认原则

- 默认后台执行，不切换到浏览器前台，不影响用户正常工作。
- 优先复用已登录的 Chrome for Testing，调试端口 `9333`。
- 如果 Chrome for Testing 不可用，再考虑用户指定的自用浏览器登录态。
- 不要把 cookie、token、授权链接、账号信息写入项目文件或最终回复。
- 不要只因为接口返回 `token鉴权参数异常` 就停止。先排查登录态复用路径。

## 登录态优先级

1. **Chrome for Testing（默认）**
   - 端口：`9333`
   - 用户数据目录：`$HOME/.chrome-codex-automation`
   - 用法：通过 CDP 连接已登录浏览器，直接读取页面 DOM。

2. **自用 Chrome（fallback）**
   - 用户常用 profile：`$HOME/Library/Application Support/Google/Chrome/Profile 6`
   - 只有在用户明确同意或该 Chrome 已经开放远程调试端口时使用。
   - 不要直接启动这个 profile 做自动化，避免抢占用户窗口或锁 profile。

## 快速执行

在目标项目根目录运行：

```bash
node <skill-dir>/scripts/fetch-scys-article.mjs \
  "https://scys.com/articleDetail/xq_topic/<topic-id>"
```

默认输出：

```text
./<topic-id>.md
./downloaded.md
```

如果本机未跟踪配置里设置了 `output_dir`，默认输出目录用配置值覆盖当前目录。配置文件按顺序读取：

```text
~/.config/skills/jz-scys-article/config.yml
~/.config/skills/jz-scys-article/config.yaml
~/.config/skills/jz-scys-article/config.toml
~/.config/skills/jz-scys-article/config.json
```

配置示例：

```yaml
output_dir: "<clipping-dir>"
port: 9333
```

可选参数：

```bash
node <skill-dir>/scripts/fetch-scys-article.mjs "<url>" \
  --out <clipping-dir> \
  --port 9333 \
  --include-comments
```

`--include-comments` 会把当前页面已加载的评论写入 Markdown。默认不写评论，只写正文、目录和图片 URL。
`--no-feishu` 会跳过飞书全文链接，直接保存生财页面内容。

## 飞书全文链接

如果页面里出现 `feishu.cn/wiki/...`、`feishu.cn/docx/...` 或 `feishu.cn/docs/...` 链接，按这个顺序处理：

1. 优先调用 `$jz-feishu-doc-download` 下载对应飞书链接。这样可以复用飞书 skill 的去重、图片下载和媒体处理。
2. 输出内容使用飞书下载结果，而不是生财摘要。
3. 在飞书结果的 frontmatter/metadata 里追加：
   - `scys_source_url`：用户给出的生财原始链接。
   - `scys_resolved_url`：Chrome 实际打开后的生财链接。
   - `topic_id`：生财 topic id。
4. 如果用脚本自动执行，脚本会用 `lark-cli docs +fetch` 获取飞书 Markdown，并写入同样的 SCYS metadata。脚本路径不下载飞书图片；需要离线图片时，改用 `$jz-feishu-doc-download` 的完整流程。

## 脚本做什么

脚本通过 Chrome DevTools Protocol 执行：

1. 检查 `http://127.0.0.1:<port>/json/version` 是否可用。
2. 查找已打开的目标页；找不到则在后台新建 target 并导航到目标 URL。
3. 等页面加载，读取 DOM 文本、目录、飞书全文链接、正文图片 URL 和评论区图片 URL。
4. 如果页面只显示登录跳转或接口鉴权失败，输出诊断，不生成错误 clipping。
5. 如果发现飞书全文链接，下载飞书 Markdown，写入飞书正文，并在 frontmatter 记录生财原始链接。
6. 如果没有飞书全文链接，写入生财 Markdown：
   - frontmatter：标题、来源、作者、时间、topic id、抓取时间。
   - 正文文本。
   - 图片区：按页面顺序写 `![图 NN](url)`。
   - 可选评论区。
7. 更新 `downloaded.md`，避免重复抓同一篇。

## 如果 Chrome for Testing 没开

先后台启动专用浏览器：

```bash
CFT_APP="$(find "$HOME/Library/Caches/ms-playwright" "$HOME/Library/Caches/puppeteer" "$HOME/.cache/puppeteer" \
  -path '*/Google Chrome for Testing.app' -type d 2>/dev/null | head -n 1)"

open -n -g "$CFT_APP" --args \
  --user-data-dir="$HOME/.chrome-codex-automation" \
  --remote-debugging-port=9333 \
  --no-first-run \
  --no-default-browser-check \
  --new-window "about:blank"
```

`-g` 表示后台打开，不抢用户焦点。

如果找不到 Chrome for Testing，先说明缺少浏览器运行环境，不要改用用户日常 Chrome 硬跑。

## 鉴权失败处理

出现这些情况时，先诊断：

- 页面文本是 `即将前往登录页`
- 接口返回 `token鉴权参数异常`
- 标题是登录页或空页面

诊断顺序：

1. `curl -s http://127.0.0.1:9333/json/list`，确认目标页是否在 Chrome for Testing 中打开。
2. 如果目标页已打开，直接连这个 target 读 DOM，不要重新导入 cookie。
3. 如果目标页未打开，后台新建 target 导航，检查是否仍跳登录。
4. 如果仍跳登录，请用户在 Chrome for Testing 窗口手动登录生财后重试。
5. 只有 Chrome for Testing 确认不可用时，才考虑用户自用浏览器。

## 图片策略

- 正文图片只保留远程 URL。
- 不下载图片，除非用户明确要求离线归档。
- 跳过头像、锚点头像、二维码、站点图标。
- 远程 URL 不视为永久归档。需要长期保存时，再按用户要求单独下载。

## 汇报

完成后说明：

1. Markdown 文件路径。
2. 文章标题、作者、发布时间。
3. 输出模式：`scys` 或 `feishu`。
4. 如果命中飞书，说明飞书链接和 frontmatter 是否包含 `scys_source_url`。
5. 正文图片 URL 数量。
6. 是否包含评论。
7. 是否命中或更新 `downloaded.md`。
8. 如果失败，说明卡在哪一步，以及已尝试的登录态路径。
