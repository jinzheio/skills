# Skill 命名规范

单一任务 skill 使用：

```text
jz-<method>-<resource>[-<qualifier>]
```

按产品域合并、由顶层 router 分发多个 action 的大 skill 使用：

```text
jz-<product-or-domain>
```

例如 `jz-cloudflare`、`jz-github`、`jz-site-observability`。只有当多个 action 共享主要认证、配置、用户意图和发布生命周期时才使用这种名称；action 名仍使用动作词。目录名、`SKILL.md` frontmatter 的 `name`、`agents/openai.yaml` 的 `default_prompt` 必须一致。

## Method

| Method | 使用场景 | 默认副作用 |
| --- | --- | --- |
| `get` | 获取、下载或导出已有内容和数据 | 无远端副作用 |
| `check` | 读取数据后诊断、核对或判断 | 无 |
| `create` | 创建新资源或新产物 | 创建 |
| `setup` | 把配置、集成或环境设到目标状态 | 幂等写入 |
| `update` | 修改已有资源的一部分 | 更新 |
| `delete` | 删除资源 | 删除 |
| `manage` | 同一系统内包含查询、创建、更新和删除等多种操作 | 可能写入 |
| `sync` | 增量同步两个位置的状态 | 目标端或双方写入 |
| `deploy` | 把代码或产物发布到运行环境 | 发布 |
| `launch` | 完成公开上线，包括部署、域名和上线后接入 | 多阶段写入 |
| `migrate` | 把运行环境或数据从来源移到目标 | 多阶段写入 |

允许使用已有明确含义的领域动作：

- Git：`commit`、`push`
- 内容：`transcribe`、`edit`、`review`
- 操作：`send`、`connect`

产品域 router 内的 action 可以保留已有方法含义，但不再为每个方法创建一个公开 skill 名。

## Resource

- 写用户要处理的资源或拿到的结果，少写内部实现。
- 单项资源用单数，集合用复数，例如 `get-feishu-doc`、`get-x-posts`。
- 迁移名称同时写来源和目标，例如 `migrate-vercel-to-cloudflare`。
- 使用产品全名，例如 `cloudflare`、`github`。保留 `api`、`pr`、`x`、`ovh` 等正式缩写。
- `jz-` 后通常不超过四段。

不要新增 `ops`、`add`、`init`、`fetch`、`download`、`audit` 等同义写法。`build` 只用于明确产出可运行项目的 builder，例如 `jz-build-tanstack`。确实需要新 method 时，先更新本文档并说明现有 method 为什么不适用。

## 修改检查

改名、移动或删除 skill 后检查：

1. 目录名与 frontmatter `name` 一致。
2. `agents/openai.yaml` 存在，`default_prompt` 使用新的 `$jz-*` 名称。
3. README 中英文列表、安装示例、调用示例和凭证表已更新。
4. skill 间调用、脚本路径、配置目录和 eval metadata 已更新。
5. `~/.agents/skills/`、`~/.claude/skills/`、`~/.codex/skills/` 中没有旧链接、断链或遗漏。
