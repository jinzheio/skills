# Hermes 原生模型 Fallback

用户要求配置、验证或排查 Hermes 主模型 fallback 时读取本文。普通云端 agent 状态检查不需要加载。

官方文档：

- <https://hermes-agent.nousresearch.com/docs/user-guide/features/fallback-providers>
- <https://hermes-agent.nousresearch.com/docs/integrations/providers>

## 目录

- 配置结论
- 修改前检查
- 判断 Kimi Key 区域
- 先做 Provider 直连测试
- 写入原生 Fallback 链
- 验证自动切换
- 已知现象

## 配置结论

使用 Hermes 原生顶层 `fallback_providers`。列表按顺序尝试；每项必须有 `provider` 和 `model`。

```yaml
fallback_providers:
  - provider: deepseek
    model: deepseek-chat
  - provider: kimi-coding-cn
    model: kimi-k2.6
```

常用 provider 与环境变量：

| Provider | 环境变量 | 常用模型 |
| --- | --- | --- |
| `deepseek` | `DEEPSEEK_API_KEY` | `deepseek-chat` |
| `kimi-coding` | `KIMI_API_KEY` | `kimi-for-coding`、`kimi-k2.6` |
| `kimi-coding-cn` | `KIMI_CN_API_KEY` | `kimi-k2.6` |

`fallback_model` 是旧的单项配置。新增或修改时使用 `fallback_providers`，并删除旧的 `fallback_model`，避免两个来源并存。

## 修改前检查

1. 从 deployment 配置读取 `install_dir`、`hermes.home_dir`、`hermes.agent_dir` 和 `hermes.gateway_service`。
2. 检查当前主模型、fallback 链和标准 key 是否存在，不输出 key 原文。
3. 备份 `config.yaml` 和 `.env`。
4. 修改前记录 owner/group/mode，修改后恢复。

```bash
stat -c "%U:%G %a %n" \
  {{ config.hermes.home_dir }}/config.yaml \
  {{ config.hermes.home_dir }}/.env

sudo -u clawsimple env \
  HOME={{ config.server.install_dir }} \
  HERMES_HOME={{ config.hermes.home_dir }} \
  PATH={{ config.hermes.agent_dir }}/venv/bin:/usr/bin \
  VIRTUAL_ENV={{ config.hermes.agent_dir }}/venv \
  {{ config.hermes.agent_dir }}/venv/bin/python -m hermes_cli.main fallback list
```

若 key 来自本地管理仓库，只把它映射成 Hermes 识别的标准变量名写入远端 `.env`。不要把本地管理变量名写进 Hermes 配置，也不要输出 key。

## 判断 Kimi Key 区域

不要按变量名或 key 长度判断区域。对同一个 key 测试 models endpoint，只输出 HTTP 状态：

```text
https://api.moonshot.ai/v1/models
https://api.moonshot.cn/v1/models
https://api.kimi.com/coding/v1/models
```

- `api.moonshot.cn` 返回 200：使用 `KIMI_CN_API_KEY` 和 `kimi-coding-cn`。
- `api.moonshot.ai` 返回 200：使用 `KIMI_API_KEY` 和 `kimi-coding`。
- `api.kimi.com/coding` 返回 200：使用 `KIMI_API_KEY` 和 `kimi-coding`；Kimi Coding key 通常会被 Hermes 自动路由到 coding endpoint。
- 所有 endpoint 都失败：不要加入 fallback 链，先报告 key 不可用。

## 先做 Provider 直连测试

在写入生产 fallback 链前，分别验证 provider。使用最小请求，避免工具调用：

```bash
cd {{ config.server.install_dir }}
timeout 180 sudo -u clawsimple env \
  HOME={{ config.server.install_dir }} \
  HERMES_HOME={{ config.hermes.home_dir }} \
  PATH={{ config.hermes.agent_dir }}/venv/bin:{{ config.hermes.agent_dir }}/node_modules/.bin:/usr/bin:{{ config.server.install_dir }}/.local/bin:/usr/local/bin \
  VIRTUAL_ENV={{ config.hermes.agent_dir }}/venv \
  {{ config.hermes.agent_dir }}/venv/bin/python -m hermes_cli.main chat \
    -Q --ignore-rules --max-turns 1 \
    --provider deepseek --model deepseek-chat \
    -q "Reply exactly: DEEPSEEK_OK"
```

Kimi 中国区测试把 provider/model 改成：

```text
--provider kimi-coding-cn --model kimi-k2.6
```

只有直连测试通过的 provider 才能进入 fallback 链。

## 写入原生 Fallback 链

优先调用 Hermes 自身的配置读写函数，避免手工 YAML 字符串替换：

```python
from hermes_cli.config import load_config, save_config

cfg = load_config()
cfg["fallback_providers"] = [
    {"provider": "deepseek", "model": "deepseek-chat"},
    {"provider": "kimi-coding-cn", "model": "kimi-k2.6"},
]
cfg.pop("fallback_model", None)
save_config(cfg)
```

写入后：

```bash
chown clawsimple:clawsimple {{ config.hermes.home_dir }}/config.yaml {{ config.hermes.home_dir }}/.env
chmod 600 {{ config.hermes.home_dir }}/config.yaml {{ config.hermes.home_dir }}/.env
systemctl restart {{ config.hermes.gateway_service }}
systemctl is-active {{ config.hermes.gateway_service }}
```

再运行：

```bash
sudo -u clawsimple env \
  HOME={{ config.server.install_dir }} \
  HERMES_HOME={{ config.hermes.home_dir }} \
  PATH={{ config.hermes.agent_dir }}/venv/bin:/usr/bin \
  VIRTUAL_ENV={{ config.hermes.agent_dir }}/venv \
  {{ config.hermes.agent_dir }}/venv/bin/python -m hermes_cli.main fallback list
```

## 验证自动切换

不要破坏生产 Codex OAuth 或生产 key。创建临时 `HERMES_HOME`：

1. 主 provider 配成一个无效 key。
2. fallback 只放一个已直连通过的 provider。
3. 运行最小请求并检查返回。
4. 删除临时目录。

例如：临时主模型使用无效 DeepSeek key，fallback 使用 Kimi。若请求返回指定文本，证明 Hermes 原生 fallback 已触发。

生产验证还要确认：

- `hermes fallback list` 显示正确顺序。
- 日志出现主模型失败时，包含 `trying fallback` 或 fallback provider 切换记录。
- 主模型恢复后仍能完成最小请求。
- gateway 为 `active`，重启后没有持续 traceback。
- `.env` 和 `config.yaml` 为 `clawsimple:clawsimple 600`。

## 已知现象

- fallback 是按 turn 生效；下一条用户消息会重新尝试主模型。
- 主模型的 429、401/403、404、5xx、连接失败和重复无效响应可触发 fallback。
- `hermes status` 的 API Keys 摘要可能只显示 `Kimi` 国际区状态，不代表 `KIMI_CN_API_KEY` 不可用。用 `config check`、直连请求和 `fallback list` 判断。
- gateway 重启交接期间，旧进程可能记录一次失败并退出。以重启后的当前 service 状态和新日志为准。
- SSH 偶发关闭时，等待几秒后重试；不要因此重启服务器。
