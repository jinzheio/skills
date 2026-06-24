# Cloudflare D1 全表扫描审计

用于检查 D1 查询是否会造成 rows read 异常、公开页面变慢，或在流量上来后带来不必要成本。

## 审计目标

输出时区分三类结论：

| 类型 | 含义 | 处理 |
|---|---|---|
| 裸表扫描 | 查询计划显示 `SCAN <table>`，且表会增长 | 优先补索引、改查询或预聚合 |
| 索引扫描 | 查询计划显示 `SCAN <table> USING INDEX` 或 `SEARCH ... USING INDEX`，但仍要读大量索引项 | 判断数据量和访问频率，必要时预聚合 |
| 可接受扫描 | 小表、离线任务、低频后台查询，或聚合表规模有上限 | 在报告中说明边界 |

不要把“用了索引”直接写成“没有风险”。`GROUP BY`、`AVG()`、`COUNT()`、`ORDER BY computed_value LIMIT 10` 通常仍要读大量行或大量索引项。

## 执行步骤

### 1. 找到所有 D1 查询

在项目根目录运行：

```bash
rg -n "DB\\.prepare|\\.prepare\\(|SELECT|INSERT|UPDATE|DELETE|CREATE INDEX|CREATE TABLE|ALTER TABLE" \
  src app pages server workers functions migrations wrangler* package.json 2>/dev/null
```

如果项目不是这些目录结构，先用 `rg --files` 找源码、migration 和 worker 入口。

把查询按触发路径分类：

- 用户请求热路径：公开页面、API、登录、checkout、webhook、unlock、dashboard。
- 后台路径：Cron、Queue consumer、admin job、一次性脚本。
- 统计路径：aggregate、analytics、report、history。
- 写入路径：`INSERT`、`UPDATE`、`ON CONFLICT`。

### 2. 建表和索引清单

从 migrations 和当前 schema 整理：

- 表名、主键、唯一约束。
- 二级索引。
- 会持续增长的表。
- 有上限或自然很小的表，例如每日聚合表、配置表。

SQLite/D1 会为 `PRIMARY KEY` 和 `UNIQUE` 自动建索引。报告里可以写“由主键/唯一约束覆盖”，不要误判为缺索引。

### 3. 对照查询和索引

逐条检查：

- `WHERE` 中的等值条件是否是复合索引的左前缀。
- `ORDER BY ... LIMIT` 是否能被同一个索引顺序覆盖。
- `GROUP BY` 是否能按索引顺序读取，是否仍需扫描大量行。
- `HAVING` 是否在聚合后才过滤，不能当成减少 rows read 的条件。
- `OR`、`LIKE '%keyword%'`、表达式函数、JSON 字段过滤是否会让普通索引失效。
- `WHERE column IS NOT NULL` 只能减少空值部分；如果大多数行都有值，仍可能读很多行。

常见索引模式：

```sql
-- 去重/最近一条
CREATE INDEX IF NOT EXISTS idx_results_dedup
ON assessment_results(client_hash, answer_hash, occupation_soc, created_at DESC);

-- owner + plan + 最新记录
CREATE INDEX IF NOT EXISTS idx_comparisons_owner_plan_created
ON comparisons(owner_result_id, plan_tier, created_at DESC);

-- 邮箱历史
CREATE INDEX IF NOT EXISTS idx_paid_results_email_created
ON paid_results(email_hash, created_at DESC);
```

### 4. 用查询计划验证

优先在本地临时 SQLite 库或 D1 本地库验证 schema：

```bash
sqlite3 <tmp-db> < migrations/0001_initial.sql
sqlite3 <tmp-db> < migrations/0002_next.sql
sqlite3 <tmp-db> \
  "EXPLAIN QUERY PLAN SELECT id FROM table_name WHERE indexed_col = 'x' LIMIT 1;"
```

如果需要验证远端 D1，使用 Wrangler 的 SQL command。不要把真实 database id、account id 或 token 写进报告：

```bash
pnpm exec wrangler d1 execute <database-name> --remote \
  --command "EXPLAIN QUERY PLAN SELECT id FROM table_name WHERE indexed_col = 'x' LIMIT 1;"
```

判断输出：

```text
SEARCH table USING INDEX idx_name (...)      -> 走索引查找
SEARCH table USING COVERING INDEX idx_name   -> 走覆盖索引，不回表
SCAN table                                   -> 裸表扫描
SCAN table USING INDEX idx_name              -> 扫索引，不是裸扫，但可能仍读很多项
USE TEMP B-TREE FOR ORDER BY/GROUP BY        -> 排序或分组需要临时结构
```

### 5. 判断是否需要预聚合

以下查询即使加索引，也经常不适合放在公开页面实时跑：

```sql
SELECT occupation_title, AVG(doom_score) AS avg_d, COUNT(*) AS cnt
FROM assessment_events
WHERE occupation_title IS NOT NULL AND occupation_title != ''
GROUP BY occupation_title
HAVING cnt >= 3
ORDER BY avg_d DESC
LIMIT 10;
```

原因：

- `AVG()` 和 `COUNT()` 必须先算完每个 group。
- `ORDER BY avg_d` 按计算结果排序，普通索引不能直接取前 10。
- `HAVING cnt >= 3` 是聚合后过滤，不能减少前面的扫描量。

更稳妥的做法是写入时维护聚合表：

```sql
CREATE TABLE IF NOT EXISTS occupation_aggregate (
  occupation_title TEXT PRIMARY KEY,
  count INTEGER NOT NULL DEFAULT 0,
  avg_doom REAL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_occupation_aggregate_avg_doom
ON occupation_aggregate(avg_doom DESC);
```

写入结果时同步更新：

```sql
INSERT INTO occupation_aggregate (occupation_title, count, avg_doom, updated_at)
VALUES (?, 1, ?, ?)
ON CONFLICT(occupation_title) DO UPDATE SET
  avg_doom = (avg_doom * count + excluded.avg_doom) / (count + 1),
  count = count + 1,
  updated_at = excluded.updated_at;
```

公开页面读取聚合表：

```sql
SELECT occupation_title, avg_doom, count
FROM occupation_aggregate
WHERE count >= 3
ORDER BY avg_doom DESC
LIMIT 10;
```

如果 `count >= 3` 过滤很重要，可以改建更贴近查询的索引，或维护一个只包含可展示行的物化表。

### 6. 输出格式

报告每个问题时包含：

- 查询位置：文件和行号。
- 查询用途：热路径、后台、统计页或 webhook。
- 当前查询计划：贴关键一行，不贴完整敏感输出。
- 风险判断：裸表扫描、索引扫描但可能很重、或可接受。
- 建议：新增索引、改查询、预聚合、缓存、移到后台任务。
- 验证方式：需要跑的 `EXPLAIN QUERY PLAN` 或测试。

示例：

```text
问题：duo 成功页按 owner_result_id 查询 comparisons 没有索引。
位置：src/pages/api/unlock.ts:33
路径：用户支付成功页，公开请求热路径。
查询计划：SCAN comparisons
风险：comparisons 每个 duo 购买一行，会随收入增长。
建议：添加 (owner_result_id, plan_tier, created_at DESC)。
验证：EXPLAIN QUERY PLAN 应显示 SEARCH comparisons USING INDEX idx_comparisons_owner_plan_created。
```

## 结论边界

- `EXPLAIN QUERY PLAN` 证明访问路径，不证明实际 rows read 数字。
- 数据量小的时候，全表扫描可能暂时便宜；报告要说明“现在能用”和“增长后会出问题”的分界。
- D1 rows read 异常要结合 Cloudflare usage、请求量、缓存命中和页面访问频率判断。
- 迁移里新增索引前，确认生产表大小和写入频率。大表建索引可能需要安排低峰期。
