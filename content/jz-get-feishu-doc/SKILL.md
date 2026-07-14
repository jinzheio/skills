---
name: jz-get-feishu-doc
description: "下载飞书云文档、飞书 wiki 或 docx 链接为本地 Markdown clipping，并下载正文图片到本地 assets 后回写图片路径。用户给出飞书文档 URL/token，要求下载文章、保存到 raw/clippings/feishu、下载图片、让文章本地显示图片、避免重复抓取，或处理 lark-cli docs +fetch/+media-preview/+media-download 输出时使用。"
---

# 飞书文档下载

用于把飞书 wiki/docx 文档保存成本地 Markdown，并把正文图片下载到本地，让 clipping 离线可读。

## 前置检查

- 使用 `lark-cli`，默认身份 `--as user`。
- 执行文档命令前先读 CLI 自带说明，确保参数与当前版本一致：

```bash
lark-cli skills read lark-shared
lark-cli skills read lark-doc
lark-cli skills read lark-doc references/lark-doc-fetch.md
lark-cli skills read lark-doc references/lark-doc-media-download.md
lark-cli skills read lark-doc references/lark-doc-media-preview.md
```

- 检查登录状态：

```bash
lark-cli auth status --json
```

如果 user 身份需要授权，按 `lark-shared` 的 split-flow 处理。不要把授权链接、device code 或 token 写入项目文件。

## 默认输出

在目标项目根目录执行。除非用户指定其它目录，按这个约定保存：

```text
raw/clippings/feishu/<slug>.md
raw/clippings/feishu/assets/<slug>/
raw/clippings/feishu/downloaded.md
```

`raw/` 已经是原始素材区的项目里，可以直接改 clipping 中的图片链接为本地 `assets/...` 路径。不要额外创建 `rendered/` 显示版，除非用户明确要求保留原文件不动。

## 去重记录

下载前可选读取目标目录里的记录文件。默认目标目录是 `raw/clippings/feishu/`；如果用户指定其它下载目录，就读 `<target-dir>/downloaded.md`。

```text
<target-dir>/downloaded.md
```

如果记录文件存在，先在里面查：

- 完整 `source_url`
- URL 最后的 wiki/docx token
- `document_id`

命中后再确认 `clipping_file` 指向的文件存在。`clipping_file` 和 `assets_dir` 都相对记录文件所在目录。文件存在时，默认不要重新抓取；直接汇报已存在的 clipping 和 assets 目录。只有用户明确说刷新、覆盖、重新下载或补图片时，才继续执行抓取。

记录文件不存在时继续下载，不要因此中断。

建议记录表字段：

```text
source_url | document_id | revision_id | title | clipping_file | assets_dir | image_count | fetched_at | note
```

下载或刷新完成后，新增或更新对应行。相同 `source_url` 或相同 token 只保留一行。

## 下载文档

优先抓取 Markdown：

```bash
lark-cli docs +fetch \
  --api-version v2 \
  --as user \
  --doc "<feishu-wiki-or-docx-url>" \
  --doc-format markdown \
  --format json > .tmp/feishu-fetch.json
```

从 JSON 中读取：

- `.data.document.content`
- `.data.document.document_id`
- `.data.document.revision_id`

用第一行 Markdown 标题生成文件名。frontmatter 至少包含：

```yaml
---
title: "<title>"
date: YYYY-MM-DD
type: feishu-clipping
source_url: "<source-url>"
document_id: "<document-id>"
revision_id: <revision-id>
fetched_at: "YYYY-MM-DD <timezone>"
---
```

写入前先检查目标文件是否存在，也要检查 `downloaded.md`。已有文件不要覆盖，除非用户明确要求刷新。

## 下载图片

从 clipping 中提取两类图片 token：

- Markdown 图片：`![](https://feishu.cn/file/<token>)`
- HTML 图片：`<img ... src="<token>" ...>`

不要默认下载 `<source mime="video/mp4" token="...">` 视频；用户明确要视频时再处理。

每张图片按出现顺序命名，保存到：

```text
raw/clippings/feishu/assets/<slug>/<NN>-<kind>-<token>.<ext>
```

`kind` 用 `markdown` 或 `inline-img`。

先试下载接口：

```bash
lark-cli docs +media-download --as user --token "<token>" --output "<asset-path-no-ext>" --format json
```

如果返回 `HTTP 403`，改用预览接口：

```bash
lark-cli docs +media-preview --as user --token "<token>" --output "<asset-path-no-ext>" --format json
```

`--output` 不带扩展名，让 CLI 根据 `Content-Type` 自动补扩展名。下载后用 `file` 或等价命令确认是图片，不是错误页。

## 回写 clipping

下载成功后，直接修改原 clipping：

- `https://feishu.cn/file/<token>` -> `assets/<slug>/<filename>`
- `<img ... src="<token>" ...>` -> `<img ... src="assets/<slug>/<filename>" ...>`

回写后检查：

```bash
rg -n 'https://feishu\.cn/file/|src="[A-Za-z0-9]+"' raw/clippings/feishu/<slug>.md
find raw/clippings/feishu/assets/<slug> -type f | wc -l
```

如果 `rg` 仍有命中，说明还有图片没有替换，或有视频/source token。只在用户要求下载视频时处理视频。

## 汇报

完成后说明：

1. Markdown 文件路径。
2. 图片目录。
3. 文档图片数量、成功下载数量、失败数量。
4. 是否命中 `downloaded.md` 记录。
5. 是否改写了原 clipping。
6. 是否新增或更新 `downloaded.md`。
7. 如果 `lark-cli` 输出 `_notice.update`，提示可运行 `lark-cli update`。

不要输出密钥、授权链接、个人账号信息或本机私有配置路径。
