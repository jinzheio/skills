# Facade Protocol Switching

Use this reference when a Worker facade needs to switch upstream LLM requests between OpenAI-compatible mode and Anthropic native mode.

Do not add private deployment details to this file. Use placeholders such as `<client-base-url>`, `<account-id>`, `<gateway-id>`, `<worker-name>`, `<client-model>`, `<provider-model>`, and `<custom-provider-slug>`.

## Modes

OpenAI-compatible mode:

```text
client /v1/messages
  -> facade converts Anthropic Messages to OpenAI chat completions
  -> AI Gateway /compat/chat/completions or provider-specific /chat/completions
  -> provider OpenAI-compatible endpoint
```

Anthropic native mode:

```text
client /v1/messages
  -> facade forwards Anthropic Messages body
  -> AI Gateway provider-specific /anthropic/v1/messages
  -> provider Anthropic-compatible endpoint
```

Use OpenAI-compatible mode when cost accounting is more important than avoiding conversion, or when the provider does not support Anthropic Messages reliably.

Use Anthropic native mode when the client already speaks Anthropic Messages and the provider supports that format. This avoids request/response conversion in the facade.

## Endpoint Patterns

OpenAI-compatible unified endpoint:

```text
https://gateway.ai.cloudflare.com/v1/<account-id>/<gateway-id>/compat/chat/completions
```

Provider-specific OpenAI-compatible endpoint:

```text
https://gateway.ai.cloudflare.com/v1/<account-id>/<gateway-id>/<provider>/chat/completions
https://gateway.ai.cloudflare.com/v1/<account-id>/<gateway-id>/custom-<custom-provider-slug>/chat/completions
```

Provider-specific Anthropic native endpoint:

```text
https://gateway.ai.cloudflare.com/v1/<account-id>/<gateway-id>/<provider>/anthropic/v1/messages
https://gateway.ai.cloudflare.com/v1/<account-id>/<gateway-id>/custom-<custom-provider-slug>/anthropic/v1/messages
```

For custom providers, AI Gateway appends everything after `custom-<custom-provider-slug>/` to the configured `base_url`.

Example:

```text
Gateway URL:
https://gateway.ai.cloudflare.com/v1/<account-id>/<gateway-id>/custom-<custom-provider-slug>/anthropic/v1/messages

Upstream URL:
<custom-provider-base-url>/anthropic/v1/messages
```

## Worker Controls

Keep the protocol decision explicit. A common pattern is an allowlist of upstream model prefixes:

```text
ANTHROPIC_NATIVE_UPSTREAM_PREFIXES=<provider-a>/,custom-<custom-provider-slug>/
```

If a prefix is in the allowlist, route `/v1/messages` to Anthropic native. Otherwise convert to OpenAI chat completions.

The facade should tag requests with metadata:

```json
{
  "course_model": "<client-model>",
  "upstream_model": "<provider>/<provider-model>",
  "pricing_model": "<pricing-model>",
  "upstream_format": "anthropic"
}
```

Use `"upstream_format": "openai"` for conversion fallback.

## Headers

Always strip the client credential before calling AI Gateway:

```text
Authorization
x-api-key
```

When AI Gateway authentication is enabled, use:

```http
cf-aig-authorization: Bearer <ai-gateway-token>
```

For Anthropic native mode, preserve Anthropic request headers that the provider needs:

```text
anthropic-version
anthropic-beta
```

For OpenAI-compatible mode, remove Anthropic-only headers unless the upstream endpoint explicitly accepts them.

Set custom cost when the project has its own price table:

```http
cf-aig-custom-cost: {"per_token_in":0.000001,"per_token_out":0.000002}
cf-aig-metadata: {"upstream_format":"anthropic", "...":"..."}
```

## Provider Notes

Kimi code models:

- Force `temperature=1` when the provider requires it.
- Anthropic native mode may require `thinking: {"type":"enabled"}`.
- If health checks use very small `max_tokens`, raise Kimi Anthropic native requests to a minimum such as `120`, otherwise the response may contain thinking but no text.
- Confirm AI Gateway logs show nonzero `tokens_in`, `tokens_out`, and `cost`.

DeepSeek:

- Anthropic native mode can remove facade-side conversion for clients that already use Anthropic Messages.
- Verify AI Gateway cost accounting before relying on spend limits. Some provider paths may return usage in the body while AI Gateway logs still show `tokens_in=0`, `tokens_out=0`, and `cost=0`.
- If spend limits must be enforced by AI Gateway, consider OpenAI-compatible mode until logs confirm token parsing.

Providers without Anthropic-compatible endpoints:

- Keep them on OpenAI-compatible mode.
- Return provider errors without hiding the status code.
- Add native mode only after a real request proves that the provider path, headers, model id, and usage accounting work.

## Verification

Send an Anthropic Messages request through the facade:

```bash
curl -sS <client-base-url>/v1/messages \
  -H "x-api-key: <client-key>" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  --data '{
    "model": "<client-model>",
    "max_tokens": 120,
    "messages": [{"role": "user", "content": "Reply OK only"}]
  }'
```

Then query AI Gateway logs:

```bash
./scripts/cf_ai_gateway_ops.sh logs 10
```

Check:

```text
provider
model
path
status_code
duration
tokens_in
tokens_out
cost
custom_cost
metadata.upstream_format
response_content_type
```

Interpretation:

- `metadata.upstream_format=anthropic` and `path=anthropic/v1/messages`: native mode is active.
- `metadata.upstream_format=openai` and `path=chat/completions`: OpenAI-compatible fallback is active.
- `custom_cost=true` with nonzero tokens: AI Gateway can calculate custom cost for that path.
- `custom_cost=true` with zero tokens: custom price is present, but AI Gateway did not parse usage for that request.

Also query Worker analytics when latency is the reason for switching:

```bash
./scripts/cf_ai_gateway_ops.sh worker <start-utc> <end-utc> <worker-version>
```

Compare Worker `cpuTimeUs`, Worker `requestDuration`, and AI Gateway `duration`.

If Worker CPU is only a few milliseconds and request duration is close to AI Gateway duration, the facade is not the bottleneck.
