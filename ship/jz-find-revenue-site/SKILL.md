---
name: jz-find-revenue-site
description: 获取与某个网站业务类型/服务对象相似的高收入网站，或获取最近出现的高收入网站。用于用户说"获取与 xxx 相似的高收入网站""找 xxx 的相似站点里收入高的网站""查看 Similarweb 相似站点""查看 TrustMRR 同类型站点""获取最新的高收入网站""找最近赚钱的网站""按流量/收入阈值筛网站"时。默认结合 Similarweb、Semrush、TrustMRR、域名注册时间和公开页面证据。相似网站按业务类型/服务对象相似判定（参考 Similarweb similar sites、Semrush 竞品、TrustMRR 同 category），而不是域名结构/子域名模式相似。
---

# 高收入网站发现

## 目标

找出已经有流量或收入证据的网站，输出可核验的候选表。这个 skill 只负责发现、补数、筛选和判断。

## 配置与路径

本 skill 的配置文件在：

```bash
~/.config/skills/jz-find-revenue-site/config.toml
```

凭据文件在：

```bash
~/.config/skills/jz-find-revenue-site/.env
```

首次使用时，将 skill 目录下的 `config.example.toml` 和 `.env.example` 复制到上述路径并填入实际值。

也支持将配置文件放在 skill 本地目录（`config.toml` 和 `.env`），作为未配置全局文件时的回退。优先级：`~/.config/skills/jz-find-revenue-site/` > skill 目录本地。

运行前先读取 config.toml。`paths.skill_root` 是 `ptr` CLI 代码所在的目录，所有 `uv run python -m ptr.cli` 命令都在这个目录下执行。`paths.data_root` 是主数据目录，sqlite、csv、raw/cache 和 reports 都在这里。配置中的路径允许使用 `~`，读取后必须展开成用户 home 目录。

运行项目命令前加载凭据，但不要输出凭据：

```bash
cd <paths.skill_root>   # 展开 ~/.claude/skills/jz-find-revenue-site
set -a; source <credentials.env_file>; set +a   # 展开 ~/.config/skills/jz-find-revenue-site/.env
uv run --with requests python -m ptr.cli <subcommand> ...
```

paths 展开规则：
- `paths.skill_root` → skill 代码目录，cd 到这里
- `paths.sqlite` → `--db` 参数
- `paths.trustmrr_csv` → `--trustmrr-csv` / `--export` 参数
- `paths.reports` → `--output` 的报告目录
- `paths.similarweb_raw` → `--raw-dir` 的父级（实际 raw 数据会按月份/子目录组织）

## 触发模式

### 与某站相似的高收入网站

用户给出 `example.com` 或产品名时，**"相似"指业务类型/服务对象相似**（如 husky-app 是无代码 App 构建器，则相似站是 appmaker、Convertio、Adalo、Glide、Bubble 等同类产品），不是域名结构/子域名模式/后缀相似。判定顺序：

1. 归一化域名，查本地库和历史报告是否已有该站、同类站或相似站：
   - `paths.sqlite`（`paid_traction_radar.sqlite3`）
   - `paths.trustmrr_csv`（`trustmrr-latest.csv`）
2. **Similarweb similar sites**（业务相似）— 优先用 dash API，不用 Similarweb 公网页摘要代替：
   - endpoint 读取 `dash_api.similar_sites_url`
   - 常用参数读取 `dash_api.defaults`，并传入 `key=<domain>`
   - 原始 JSON 保存到 `paths.similarweb_raw/similar-sites/`
3. **Semrush 竞品**（业务相似）— organic competitors：
   - 先读配置中的 `semrush` / `semrush_dash` 段。默认只使用 `3ue.co` dash API，不访问 Semrush 官方网站。
   - Semrush MCP 当前不可用，不作为数据源。不要调用 Semrush MCP 来补流量、关键词、竞品或来源分布。
   - 如果需要选择 Semrush 节点，使用 `semrush.preferred_node` / `semrush_dash.preferred_node_index`，不要使用 `semrush.avoid_node`。
   - 如果 `3ue.co` dash API 暂时不可用，复用 `paths.reports/*semrush*.csv`，缺口写 `unknown`，不要编数字。
4. **TrustMRR 同类型站点**（业务相似）— 按 `category` 字段匹配：
   - 优先使用最新本地快照；快照过旧或用户要当前数据时运行 `fetch-trustmrr`。
   - 同 category 站点列表 + 同 title/description 关键词。
5. 兜底：本地数据库按 `category_guess` 字段查询相同一级类目下的站点。
6. 对候选站逐个补：
   - 月访问总量。
   - TrustMRR 30 日收入、MRR、总收入、30 日增长。
   - Semrush organic traffic、paid traffic、主要关键词或竞品关系。
   - 支付网关跳出访问。
   - 注册时间。
   - 首页 title、description、H1/H2 或公开页面说明。

**判定方法**：
- 必须先确认目标站的产品定位（用 agent 拉取首页、读 `domains.title` / `domains.description` / `domains.h1`），不能从域名/后缀推断
- 业务相似以 Similarweb similar sites、Semrush organic competitors、TrustMRR category 为权威来源
- 不要因为 "都是 admin.* 子域名" 或 "都是 .ai 后缀" 把不同业务的站归为相似

### 最新高收入网站

用户要求"最新""最近出现""新站""本月/本周"时：

1. 刷新或导出 TrustMRR：

```bash
# 刷新（从 API 拉取）
uv run --with requests python -m ptr.cli fetch-trustmrr \
  --db <paths.sqlite> \
  --export <paths.trustmrr_csv>

# 或仅导出已有快照
uv run --with requests python -m ptr.cli export-trustmrr \
  --db <paths.sqlite> \
  --output <paths.trustmrr_csv>
```

2. 从 TrustMRR 取最近出现、30 日收入高、MRR 高或增长快的网站。
3. 从 payment referral 结果补充 TrustMRR 没覆盖的网站：

```bash
uv run --with requests python -m ptr.cli keyword-radar \
  --db <paths.sqlite> \
  --keyword "<category-or-task>" \
  --trustmrr-csv <paths.trustmrr_csv> \
  --min-trustmrr-revenue 5000 \
  --min-referral-visits 5000 \
  --limit 100 \
  --output <paths.reports>/high-revenue-site-candidates.csv
```

4. 用 Similarweb 和 Semrush 补流量，不要只因为 TrustMRR 未命中就删除候选。
5. 注册时间缺失时补 RDAP/WHOIS：

```bash
uv run --with requests python -m ptr.cli enrich-domain-age \
  --db <paths.sqlite> \
  --domains <comma-separated-domains> \
  --limit 200
```

## 默认阈值

用户指定阈值时使用用户阈值。用户没有指定时，用这些默认值：

- `trustmrr_revenue_30d >= 5000`
- 或 `mrr >= 1000`
- 或 `total_revenue >= 10000`
- 或 `monthly_total_visits >= 10000`
- 或 `similarweb_paid_referral_visits >= 5000`

如果是"最新高收入网站"，优先保留最近 90 天首次出现在 TrustMRR、本地报告或 Similarweb 缓存里的站点；注册时间可作为辅助，不要求必须是新域名。

## Similarweb 口径

Similarweb 只用 dash API、ptr CLI 或已保存 raw/cache。不要访问 `similarweb.com/website/<domain>` 公网页来补数。

查某个站的 outgoing referral，用：

- endpoint 读取 `dash_api.outgoing_table_url`
- 常用参数读取 `dash_api.defaults`，并传入 `key=<domain>`
- 默认先看 `3m`，再按需要查 `1m`、`6m`、`12m`

支付目标包括但不限于：

- `checkout.stripe.com`
- `buy.stripe.com`
- `billing.stripe.com`
- `checkout.paddle.com`
- `paypal.com`
- `creem.io`
- `polar.sh`

查主站 referral 或 payment target referral 时，先 dry-run 查看缓存：

```bash
uv run --with requests python -m ptr.cli fetch-similarweb \
  --db <paths.sqlite> \
  --period 1m \
  --targets <domain-or-payment-target> \
  --country 999 \
  --web-source Total \
  --all-pages \
  --max-pages 16 \
  --dry-run
```

缓存缺失且任务需要当前数据时，去掉 `--dry-run`。刷新支付目标前先确认用户确实需要，Similarweb 查询会消耗账号额度。

如果 Similarweb 返回 HTML 登录页、403 或设备数量限制：

1. 确认凭据已加载（`source <credentials.env_file>`）。
2. 使用 `dash_api.login_url` 重新登录后重试同一个接口。
3. 仍失败时记录失败源和错误类型。不要改用公网页估算。

## TrustMRR 口径

TrustMRR 是收入优先来源。默认字段：

- `trustmrr_revenue_30d`
- `mrr`
- `total_revenue`
- `growth_30d`
- `visitors_30d`
- `trustmrr_url`

`not_found` 表示查过但未命中，不表示没有收入。`unknown` 表示数据源没有稳定结果。

## Semrush 口径

Semrush 用来补：

- `semrush_organic_traffic`
- `semrush_paid_traffic`
- `organic_keywords`
- `paid_keywords`
- `referring_domains`
- `organic_competitors`
- `keyword_themes`

默认只使用 `3ue.co` Semrush dash API。不要访问 Semrush 官方网站，不要使用官方 API、Semrush MCP 或套餐外接口。Semrush MCP 当前不可用；即使工具列表里出现 Semrush MCP，也不要调用它补数。

### 认证与节点选择

配置中的 `semrush_dash` 段提供了 `3ue.co` Semrush dash API 所需的所有连接参数，包括代理地址、节点 API、配置 cookie 名、节点选择策略和 API/页面 URL 模板。不要把这些值写死在 prompt 或回复中。运行前必须读取 config.toml 的 `semrush_dash` 段。

认证流程：

1. 用 `dash_api.login_url` 和 `credentials` 段配置的凭据登录。登录成功后会写入认证 cookie。
2. 请求 `semrush_dash.nodes_url` 获取节点列表。
3. 从列表中选择一个可用节点：`note` 必须包含 `semrush_dash.preferred_plan_label` 和 `semrush_dash.preferred_health_marker`，不能包含 `semrush_dash.avoid_plan_label`。优先选 `semrush_dash.preferred_node_index`（节点数组下标字符串），但如果对应节点状态为不可用标记则换下一个可用节点。
4. 把节点选择写入 config 中指定的 cookie，格式为 `{"<service_code>":{"node":"<index>","lang":"<default_language>"}}`。
5. 节点激活后前端会写入一个额外的激活 cookie（config 中的 `semrush_dash.activation_cookie`），Semrush 页面还需要带页面级 token 参数（config 中的 `semrush_dash.gmitm_param`）。这些值在 browser session 期间有效。

### 访问方式

#### 方式一：用户当前 Chrome + CDP（优先）

如果用户已经在 Chrome 中登录并打开 `3ue.co` Semrush dash，必须复用这一个 Chrome 会话。`3ue.co`/Semrush 可能限制同一账号多设备使用；不要另开 headless Chromium、不要用新的浏览器 profile 登录，也不要访问 `semrush.com` 官方页面。

先读取 config 中的 `semrush_dash.cdp`。默认 CDP bridge 为 `http://localhost:3456`。

```bash
# 列出当前 Chrome tabs，找到 sem.3ue.co tab
curl -s "<cdp_bridge>/targets"
```

如果用户已经给了 Semrush 页面，优先使用该 tab。需要新查 Traffic Analytics 时，优先在同一个 Chrome 会话中新开 `semrush_dash.routes.traffic_landing`，再在页面输入域名并点击“分析”。不要直接假设 `overview/?q=<domain>` 一定能返回报表；Traffic Analytics 常见稳定落点是带 `lid` 的 `traffic-overview` 页面。

```bash
# 在当前 Chrome 会话中新开 Traffic Analytics 入口
curl -s "<cdp_bridge>/new?url=<urlencoded semrush_dash.routes.traffic_landing>"

# 在页面中输入域名并点击“分析”
curl -s -X POST "<cdp_bridge>/eval?target=<TAB_ID>" --data-binary @- <<'JS'
(() => {
  const domain = '<domain>';
  const input = document.querySelector('input[name="competitors.0"], input[placeholder*="域名"], input');
  if (!input) return JSON.stringify({ok:false, reason:'no input'});
  input.focus();
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  setter.call(input, domain);
  input.dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertText', data:domain}));
  input.dispatchEvent(new Event('change', {bubbles:true}));
  const button = [...document.querySelectorAll('button,[role=button]')]
    .find(el => /分析|Analyze/i.test(el.innerText || el.getAttribute('aria-label') || ''));
  if (!button) return JSON.stringify({ok:false, reason:'no analyze button', value:input.value});
  button.click();
  return JSON.stringify({ok:true, value:input.value});
})()
JS

# 等待跳转到 traffic-overview，再提取页面文本和资源列表
curl -s -X POST "<cdp_bridge>/eval?target=<TAB_ID>" --data-binary @- <<'JS'
JSON.stringify({
  href: location.href,
  title: document.title,
  text: document.body.innerText,
  resources: performance.getEntriesByType('resource')
    .map(r => ({name:r.name, initiatorType:r.initiatorType, duration:r.duration, transferSize:r.transferSize}))
    .filter(r => /api|rpc|dpa|backlink|analytics|traffic|quazar|trend|engine-web/i.test(r.name))
})
JS
```

在 tab 内可用 `fetch()` 调页面实际加载过的 API。浏览器 session 会带认证 cookie 和页面级参数：

```js
var resp = await fetch('<api-url>', {credentials: 'include'});
```

Traffic Analytics 页面使用的接口可能来自 Semrush 前端的 Quazar / `engine-web` 服务，不一定是 `semrush_dash.rpc_url`。先用 `performance.getEntriesByType('resource')` 或 DevTools 网络记录确认真实接口，再复用当前 tab 的 `fetch()`。不要把官方 Semrush API 当作兜底。

Traffic Analytics 来源字段按 config `semrush_dash.traffic_channels` 映射。页面如果只显示柱状图、不显示数值，允许从 SVG 坐标反算访问量，但必须在结果中标注为估算，并确认各来源合计接近总 visits。缺口写 `unknown`。

Backlinks 页面可直接从当前 tab 的 DOM 提取 overview 数字、反向链接类型、follow/nofollow、TLD、国家、锚文本、top pages 和 competitors。发现 `analytics/backlinks/webapi2/...` 或 `analytics/competitors/rpc` 等资源时，可用当前 tab 内 `fetch()` 复用。

#### 方式二：Python requests（需完整 cookie）

从用户当前 `3ue.co` Chrome 会话复制完整 cookie 集合到 requests session，**不要调用 Semrush 官方 login 接口**。认证 cookie 名和域参见 config 中的 `semrush_dash` 段。

只有在确认不会触发多设备限制时才用 requests。requests 能打开页面 HTML 不代表报表数据已经可用；Traffic Analytics 数据常由前端异步接口加载，优先回到方式一。

### 关键页面路径

URL 模板参见 config `semrush_dash` 段，host 必须是 `3ue.co` 或配置中指定的 dash host。从 dash API / dash 页面可提取的数据字段包括但不限于：自然流量、付费流量、关键词数、引荐域名、反向链接、每月访问量、流量来源分布、AI 可见度、竞品列表、关键词主题、锚文本分布、外链国家/TLD 分布等。

提取时保留原始页面数值格式（如 `4.9M`、`317.9K`），缺口写 `unknown`，不要编数字。

## 输出字段

默认输出 Markdown 表；用户需要后续处理时同时写 CSV。字段至少包含：

- `domain`
- `product_name`
- `category_or_task`
- `why_matched`
- `registration_date`
- `first_seen_source`
- `monthly_total_visits`
- `monthly_total_visits_source`
- `trustmrr_revenue_30d`
- `mrr`
- `total_revenue`
- `growth_30d`
- `similarweb_paid_referral_visits`
- `semrush_organic_traffic`
- `semrush_paid_traffic`
- `source_urls`
- `data_status`
- `notes`

排序优先级：

1. 明确收入高。
2. 月访问高。
3. 近期出现或注册时间新。
4. 支付网关跳出访问高。
5. Semrush 关键词和外链能解释获客来源。

## 过滤

公开推荐或给用户做产品判断前，过滤：

- 成人内容。
- 赌博、博彩。
- 加密交易、杠杆、自动交易。
- 受管制药品、大麻、违禁品。
- 仿冒、账号黑产、明显规避平台规则的服务。
- 页面信息不足、无法确认卖什么的网站。

如果只是内部候选表，可以保留但标记 `excluded_reason`，不要放进推荐列表。

## "相似" 的定义

在本 skill 中，"相似网站" / "同类网站" / "竞品" 全部指**业务类型或服务对象相似**（例如 husky-app 是无代码 App 构建器，则相似站是 Bubble、Glide、Adalo、Convertio、AppSheet 等同类产品），**不**指以下任何一种：

- 域名结构相似（如都是 `admin.*` / `app.*` / `dashboard.*` 子域名）
- TLD 相似（如都是 `.ai` / `.co` / `.io`）
- Similarweb 分类相似（仅 `Search_Engines` 这一级粗分类意义不大，不能作为相似判定）
- 流量来源相似（如都是 Direct 流量大）
- 商业模式相似（如都是 SaaS）

判定相似以以下权威来源为准，**优先级从高到低**：

1. **Similarweb similar sites**（产品功能定位）
2. **Semrush organic competitors**（搜索流量竞品）
3. **TrustMRR 同 category**（业务分类）
4. **本库 `domains.category_guess` + title/description 关键词匹配**

做相似判定前必须先确认目标站的产品定位（用 agent 拉取首页 + 读 `domains.title` / `domains.description` / `domains.h1`），不能从域名/后缀/分类大类推断。

## 输出完整性（review 规则）

**严禁自作主张采样。** 除非用户明确说"给几个例子""top N""代表性的"等限定词，否则必须输出完整列表。不能因为"表太长""太多不重要的"而截断、合并或只选"最具代表性的"。

**严禁加入非 filter 的排除策略。** 只使用 `config/filters.toml` 中定义的过滤规则。不要自行判断某个站"太知名""没有参考价值"而删除。如果用户要加过滤，由用户明确指示或通过修改 filters.toml 实现。当前 filters.toml 包含以下过滤组：

- `mature_company_domains`：成熟大公司和支付平台
- `generic_channels`：Similarweb 通用渠道名（不是真实域名）

**filters.toml 是 skill 的 reference 文件，非明确要求不得擅自修改。**

用户没有指定输出格式时，默认输出完整的 Markdown 表，不分页、不截断。

## 缺失数据补全策略

输出报告前，按以下优先级补全每个候选站的描述和流量来源。先查数据库已有字段，缺失时再获取。

### 网站功能/内容（并行）

`domains` 表的 `title`、`description`、`h1`、`category_guess` 等字段可能已有数据。缺失时用 agents 并行获取：

- 每个 agent 负责一个域名，访问其首页，提取 title、meta description、H1/H2、明显的产品说明文字
- 可并行派发多个 agent（无外部 API 限制），但单批控制在 10 个以内避免资源争抢
- 获取到的数据通过 `ptr.cli` 的 domain enrichment 命令或直接 INSERT/UPDATE 写回 sqlite：

```bash
uv run --with requests python -m ptr.cli enrich-domain-info \
  --db <paths.sqlite> \
  --domain <domain> \
  --title "<title>" \
  --description "<description>" \
  --h1 "<h1>"
```

- 如果 agent 访问失败（超时、blocked），标记 `notes` 字段并跳过，不要反复重试

### 补查结果写回数据库

补查不是只改报告。只要得到新的、可复用的数据，必须写回 `paths.sqlite`：

- traffic sources：写入或更新 `traffic_sources`，保留 `domain`、`source_name`、`share`、`estimated_visits`、`month`、`country`、`web_source`、`source_type`、`raw_json`。
- 首页/定位信息：写入或更新 `domains.title`、`domains.description`、`domains.h1`、`domains.category_guess`、`notes`。
- TrustMRR 命中：通过 `trustmrr_startups` / `trustmrr_metrics` 或 `export-trustmrr` 对应流程入库，不要只写 Markdown。
- 公开收入证据：如果本地库没有专门表，创建 `revenue_evidence` 表写入 `domain`、`status`、`revenue_numbers`、`source_urls`、`evidence_quote`、`confidence`、`checked_at`、`notes`。`status` 只能用 `confirmed`、`likely`、`not_found`、`unknown`。
- 报告中的派生说明（如 `partial cache`、root domain 兜底、来源覆盖率）可写入 `report_enrichments` 或同等用途表，字段至少包含 `report_name`、`domain`、`matched_domain`、`metric_month`、`traffic_source_summary`、`traffic_source_coverage`、`coverage_status`、`updated_at`。

写库后再生成或更新 Markdown/CSV。Markdown/CSV 是读数结果，不是唯一存档。

### 流量来源（串行）

流量来源查 Similarweb traffic sources，已有缓存直接取 `traffic_sources` 表。缓存缺失时串行查询：

- Similarweb dash API 有并发限制，**必须逐域名串行**，不能并行派发
- 使用 `fetch-similarweb` 获取 traffic sources：

```bash
uv run --with requests python -m ptr.cli fetch-similarweb \
  --db <paths.sqlite> \
  --period 1m \
  --targets <domain> \
  --country 999 \
  --web-source Total \
  --all-pages \
  --max-pages 16
```

- Semrush 流量数据同理，只使用 `3ue.co` Semrush dash API 串行补充。优先用 CDP 浏览器方式，其次用 Python requests + 完整 `3ue.co` cookie。不要访问 Semrush 官方网站，不要调用 Semrush MCP。
- 每查完一个域名的 Similarweb 后间隔 2-3 秒再查下一个，避免触发速率限制
- 不需要实时数据的域名（缓存已有且月份新鲜）直接跳过，不要浪费配额

### 注册时间（串行）

注册时间缺失时用 RDAP/WHOIS 补：

```bash
uv run --with requests python -m ptr.cli enrich-domain-age \
  --db <paths.sqlite> \
  --domains <comma-separated-domains> \
  --limit 200
```

可批量传多个域名，内部会串行处理。

### 优先级

1. 先查数据库已有的 description / title / category
2. 缺失的 description 用 agents 并行补
3. 再查数据库已有的 traffic_sources
4. 缺失的流量用 Similarweb/Semrush **串行**补
5. 最后补注册时间和 TrustMRR

## 汇报规则

结论要区分"已确认""未命中""未知"：

- 已确认：给出来源、日期和数值。
- 未命中：说明查过哪个来源。
- 未知：说明缺哪个认证、接口或数据字段。

不要把 payment referral 访问写成网站总访问量。它只能证明从该站跳到支付目标的访问下限，不代表收入、用户数或总流量。

不要把流量或收入估算写成确定事实。没有来源时用 `unknown`，不要留空。
