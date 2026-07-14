# Cloudflare 成本排查建议

只在已经发现费用、即将上线付费资源，或用户要求排查原因时读取。

## 常见放大路径

| 产品 | 计费单位 | 常见原因 |
|---|---|---|
| Durable Objects | duration (GB-s)、requests、storage | `server.accept()` 让对象不能 hibernate；alarm 循环；storage 写入在循环里 |
| Workers / Pages Functions | requests、CPU time (ms) | SSR 把页面请求变 Worker invocation；无鉴权 endpoint 被爬虫打 |
| D1 | rows read、rows written、storage | 无索引全表扫描；查询扫大量行但只返回少量结果 |
| R2 | storage (GB-month)、Class A ops、Class B ops | 公开文件无 cache；频繁 list/put；误选 Infrequent Access |
| KV | read/write/delete/list ops | 每请求多次读 KV；用 list 做搜索 |
| Queues | operations | consumer 一直失败反复 retry；producer 无限写入 |
| Workers AI | tokens / units / Neurons | endpoint 无鉴权；循环调用 |
| Images | transformations、stored、delivered | 用户输入导致大量 unique transforms；公开 endpoint 无缓存 |
| Browser Rendering | session duration | 批量页面抓取 |
| Cache Reserve | storage、read/write ops | 大文件频繁进入和读取 |
| Stream | storage minutes、delivered minutes | 测试时反复上传；公开播放页无爬虫控制 |

## 处理建议

- Budget Alerts 只通知，不会暂停资源或限制用量。已经有费用增长时，仍要检查资源、限流、鉴权和 kill switch。
- DO + WebSocket 默认使用 `state.acceptWebSocket(server)`。`server.accept()` 会让 Durable Object 在连接期间持续产生 duration 费用。
- 新的付费 Worker 上线后，30 分钟内复查 GraphQL usage，确认没有意外增长的计费单位。
- Cron Triggers 和 Queue Consumers 的耗时最终会体现在 Workers CPU time；不要只看 request count。
- Queue consumer 如果调用自己的公开 API，内部调用必须强制使用 sync/direct 写入模式。不要把用户请求里的 `write_mode: "async"` 传给内部调用。
- DO `storage.put()` 按数据库写入看待。一次业务写入里有多次 job state、ack、mirror 写入时，先确认哪些可以合并、删除或交给 TTL 过期。
- API key 或 legacy fallback 里出现 KV `list()` 时，默认按热路径风险处理。先加 kill switch，再补齐 hash/prefix 索引。
- 同时使用 Queues、Durable Objects 和 KV 的项目，重点检查每条 queue message 会触发多少 KV read/write/list、多少 DO storage write，以及 retry 后是否重复。

## 异常阈值

```text
DO duration 预测 > 免费额度 80%        -> 检查 DO 数量和 hibernation
DO duration 预测 > 免费额度            -> 准备 kill switch
Workers requests 预测 > 免费额度 80%   -> 检查公开 endpoint 和缓存
Workers CPU 预测 > 免费额度 80%        -> 检查 SSR、Cron、Queue consumer
D1 rows read 突增                      -> 检查查询计划和索引
R2 Class A / B ops 突增                -> 检查缓存、list、put、公开访问路径
Queue + DO + KV 同时存在               -> 检查 queue consumer 是否回调公开 API、是否强制 sync
KV list 出现在 auth fallback            -> 先关 legacy scan 或加开关，再回填索引
单文件 DO storage.put() >= 4            -> 检查能否批量写、删掉 redundant mirror/ack
当前账期累计按量费用 > $1              -> 开始关注
当前账期累计按量费用 > $5              -> 排查
当前账期累计按量费用 > $10             -> 立即处理，必要时关停相关入口
```
