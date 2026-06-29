# Cloudflare Cost Guard

## Sources to respect

- Project AGENTS / CLAUDE files may add credential lookup or deployment rules. If present, follow those rules before reading or asking for Cloudflare, Vercel, DNS, GitHub, analytics, or deployment tokens.

## Review checklist

Before deploying Cloudflare paid resources:

- Check whether the project uses Workers, Pages Functions, Durable Objects, D1, KV, R2, Queues, Vectorize, AI Gateway, Workers AI, Browser Rendering, Hyperdrive, or Logpush.
- For Durable Object WebSockets, require WebSocket Hibernation unless the user accepts the estimated duration cost.
- Add or verify a kill switch for any Worker that can create sustained usage.
- Add CPU limits for Workers.
- Check loops, cron jobs, queue consumers, and alarms for maximum batch size, retry behavior, and exit conditions.
- Set Cloudflare Budget Alerts in the dashboard. Use at least `$1`, `$5`, and `$10` for small solo-founder projects.
- Add GraphQL usage monitoring when the project will keep Cloudflare paid resources running after launch.

## Suggested monitor cadence

- Local or hosted monitor: every 1 hour.
- First 24 hours after launch: manually inspect once after 30 minutes and again after 2-3 hours.
- Alert thresholds:
  - Durable Objects duration over `500 GB-s/hour`: warning.
  - Durable Objects duration over `2,000 GB-s/hour`: critical.
  - Durable Objects duration over `5,000 GB-s/day`: critical.
  - Current-cycle Durable Objects projection over `$1`: warning.
  - Current-cycle Durable Objects projection over `$5`: critical.

## GraphQL datasets

- `workersInvocationsAdaptive`
- `durableObjectsPeriodicGroups`
- `durableObjectsInvocationsAdaptiveGroups`
- `durableObjectsStorageGroups`
- `durableObjectsSubrequestsAdaptiveGroups`
