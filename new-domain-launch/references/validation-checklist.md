# Domain Validation Checklist

Load this reference before reporting completion.

Do not consider the task complete until all relevant checks pass:

1. Hosting and DNS provider interfaces show the intended domain configuration.
2. For Vercel plus Cloudflare, Vercel project/domain data and Cloudflare zone records agree.
3. `dig +trace NS <domain>` shows the intended delegated nameservers, unless live HTTPS checks already prove the intended site is publicly reachable.
4. Public resolvers return the intended NS, unless live HTTPS checks already prove the intended site is publicly reachable.
5. Authoritative DNS on the chosen provider returns the intended apex and `www` records.
6. For Vercel, `www` is the Vercel-requested `CNAME`, not an `A` record.
7. Hosting provider marks both domains as attached.
8. `https://APEX_HOST` returns the expected page content.
9. `https://www.DOMAIN` returns a `301` to the canonical host if redirect is intended.
10. Cloudflare proxy state and SSL mode match the intended policy.
11. If email forwarding was requested, Cloudflare Email Routing is enabled and catch-all forwarding is verified.

If local `dig` output or public resolver output stays stale or polluted but Vercel and Cloudflare agree on records and the real domain returns the expected page content over HTTPS, treat live access as the completion signal. Report the DNS-output mismatch explicitly.

## Guardrails

- Do not finish when only the dashboard looks correct.
- Do not finish when only the DNS provider is active but registry delegation is stale.
- Do not assume propagation is done without trace or public-resolver checks.
- If local resolver results disagree with provider records or real-world access, verify with Vercel and Cloudflare interfaces plus direct browser or HTTPS access.
- Do not guess provider DNS targets when the official provider can return them.
- Prefer registrar API over browser automation when credentials exist.
- If propagation is the only blocker and live HTTPS is still not working, automate the recheck instead of asking the user to babysit it.
