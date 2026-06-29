# 项目协作规则

## Skill 目录同步

本仓库是 skill 源码仓库。全局 skill 目录通过软链接指向本仓库里的各个 skill 目录：

- `~/.agents/skills/`
- `~/.claude/skills/`
- `~/.codex/skills/`

当 skill 发生以下变动时，必须同步维护三个全局目录里的软链接：

- 新增 skill：在三个全局目录中创建同名软链接，指向本仓库对应 skill 目录。
- 改名或移动 skill：删除旧同名软链接，创建新同名软链接，并确认目标路径存在。
- 删除 skill：删除三个全局目录中的对应软链接。

同步后必须检查：

- `SKILL.md` frontmatter 的 `name:` 与目录名一致，且都有 `jz-` 前缀。
- README 中英文列表、安装示例、调用示例、凭证表已同步。
- `agents/openai.yaml` 存在且 `default_prompt` 使用 `$jz-*`。
- 三个全局目录里的软链接没有断链、旧名残留或指向已删除目录。

## Skill 本机配置

- 新建或修改 skill 时，本机配置目录统一使用 `~/.config/skills/<skill-name>/`。
- 环境变量放在 `~/.config/skills/<skill-name>/.env`。
- 结构化配置放在 `~/.config/skills/<skill-name>/config.yml`、`config.yaml`、`config.toml` 或 skill 自己说明的格式。
- 如果为了兼容旧安装需要读取其它位置，必须把 `~/.config/skills/<skill-name>/` 作为首选位置，并在文档中说明旧位置只是 fallback。

不要把本机绝对路径写进文档或提交内容。需要举例时使用 `<repo-root>/<skill-name>`、`<skill-dir>` 这类占位符。

## Review 硬性要求

提交、推送或发布前，必须检查新增和修改内容是否包含本地目录、个人隐私或真实账号信息。

禁止提交：

- 本机绝对路径，例如用户目录、临时目录中的个人路径、机器专属工作区路径。
- 真实账号、邮箱、手机号、联系人、群名、客户名、项目私有代号。
- token、secret、password、cookie、session、private key、含密钥的 API 响应。
- 本机配置文件、密钥缓存、数据库缓存的具体路径。
- 服务器内部目录结构，除非它是公开文档的一部分且已经确认可公开。

写法要求：

- 路径用相对路径或占位符，例如 `./skill-name/scripts/tool.mjs`、`<repo-root>`、`<skill-dir>`。
- 账号用占位符，例如 `<github-owner>`、`<account-id>`、`<email>`。
- 群名、联系人、客户名用 `<群名>`、`<联系人>`、`<客户>`。
- 配置和密钥位置只写“本机未跟踪配置”“本机缓存”“用户指定的配置文件”，不要写具体路径。

如果发现上述内容，先修正再提交；不能确认是否可公开时，按不可公开处理。
