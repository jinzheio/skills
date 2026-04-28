---
name: new-domain-launch
description: "Connect a newly bought domain to an already deployed site so it is publicly reachable on the intended host. Use after the site/repo/deployment already exists, often right after an upstart-site style workflow. Covers registrar nameservers, DNS provider setup, hosting-platform domain binding, HTTPS, and apex/www redirect verification."
---

# new-domain-launch

Use this skill when the site is already deployed, but the user now wants a new domain to work on the public internet.

Typical sequence:

1. Site already exists on a temporary host or platform URL.
2. User provides a new domain.
3. This skill connects the registrar, DNS provider, and hosting platform until the domain is actually reachable.

Do not stop at "record created" or "platform says verified". The finish line is public reachability.

## Goal

Make the new domain work end to end:

- apex host resolves correctly
- `www` follows the intended redirect policy
- HTTPS works
- the live site is reachable from the public internet

## Default policy

Unless the user says otherwise:

- make the apex domain canonical, for example `example.com`
- make `www.example.com` redirect to the apex with `301`
- if Cloudflare is used, enable orange-cloud proxy only after the target records are known
- if Cloudflare fronts a valid HTTPS origin such as Vercel, use `Full (strict)`

## Preconditions

Before touching DNS:

1. Confirm the project already has a working deployment on the hosting provider.
2. Identify the intended canonical host:
   - apex only
   - `www` only
   - apex canonical with `www` redirect
3. Identify the three systems involved:
   - registrar, such as Spaceship
   - DNS provider, often Cloudflare
   - hosting provider, often Vercel

If the site itself is not yet deployed, stop and use the deployment workflow first.

## Workflow

### 1. Create or inspect the DNS zone

If the domain will use Cloudflare DNS:

1. Create the zone in Cloudflare first.
2. Record the assigned nameservers.
3. If the registrar is separate, update the registrar nameservers to the Cloudflare nameservers.
4. Prefer the registrar's official API when credentials are available.
5. Only fall back to browser automation when the registrar API is unavailable or blocked.

For Spaceship specifically:

- prefer the official external API rather than the web app when API key and secret are available
- use the domain API to inspect current nameservers and update them to `provider=custom` with the Cloudflare hosts

### 2. Wait for nameserver delegation

Do not rush past this step.

Check:

- registry or trace output, for example `dig +trace NS <domain>`
- public resolvers such as `1.1.1.1` and `8.8.8.8`
- DNS provider zone status, for example Cloudflare `active`

Important:

- registrar UI success is not enough
- DNS provider zone activation is not enough
- the registry delegation must actually point to the intended nameservers
- local `dig` results can lag or reflect the current network environment, so do not treat one stale local result as absolute truth
- in some local or network environments, `dig` and public-resolver checks can keep showing the old nameservers even after the public HTTPS site is already serving the correct page; when live HTTPS access returns the intended site content and the `www` redirect policy works, do not keep waiting only because nameserver output is stale

If delegation is still propagating and live HTTPS access does not yet return the intended site, set a heartbeat automation and come back later.

### 3. Bind the domain on the hosting provider

Add both the apex and `www` domains to the hosting platform if the user wants both.

For Vercel-like platforms:

1. Add the apex domain to the project.
2. Add the `www` domain to the project.
3. Query the provider for the exact required DNS targets.
4. Configure project-level redirect rules if `www -> apex` or `apex -> www` is desired.

Do not guess DNS targets from memory if the provider can return them directly.

Examples of acceptable sources:

- official CLI output
- official domain inspect/config API
- provider dashboard

### 4. Create DNS records

After the hosting provider returns the exact target values:

1. Create the apex record.
2. Create the `www` record.
3. Match the provider's recommended record type and target.

For Vercel-like setups, this commonly means:

- apex: provider-recommended `A`
- `www`: provider-recommended `CNAME`

Do not assume the `www` record should copy the apex target.

### 5. Enable proxy and TLS settings when applicable

If Cloudflare is the DNS provider and the user wants Cloudflare in front:

1. Turn on orange-cloud proxy for the live records.
2. Set SSL/TLS mode to `Full (strict)` when the origin has a valid certificate.
3. Only use weaker TLS modes if the origin cannot support strict validation.

Do not leave the zone at `Full` if `Strict` is available.

### 6. Configure the redirect

Prefer putting host redirects on the hosting platform when supported.

For the default policy:

- apex serves the site
- `www` returns `301` to the apex

After configuring the redirect, verify both HTTP and HTTPS behavior if needed, but final acceptance should focus on HTTPS.

## Validation checklist

Do not consider the task complete until all relevant checks pass:

1. `dig +trace NS <domain>` shows the intended delegated nameservers, unless live HTTPS checks already prove the intended site is publicly reachable.
2. Public resolvers return the intended NS, unless live HTTPS checks already prove the intended site is publicly reachable.
3. Authoritative DNS on the chosen provider returns the intended apex and `www` records.
4. Hosting provider marks both domains as attached.
5. `https://APEX_HOST` returns the site successfully.
6. `https://www.DOMAIN` returns a `301` to the canonical host if redirect is intended.
7. Cloudflare proxy state and SSL mode match the intended policy.

If local `dig` output or public resolver output stays stale but the real domain is already reachable on public HTTPS, treat successful live access as the completion signal and report the DNS-output mismatch explicitly instead of blocking on propagation.

## Guardrails

- Do not finish when only the dashboard looks correct.
- Do not finish when only the DNS provider is active but registry delegation is stale.
- Do not assume propagation is done without trace or public-resolver checks.
- If local resolver results disagree with real-world access, verify with direct browser or HTTPS access; if the domain serves the intended page and redirect behavior is correct, finish instead of continuing to wait on stale nameserver output.
- Do not guess provider DNS targets when the official provider can return them.
- Prefer registrar API over browser automation when credentials exist.
- If propagation is the only blocker and live HTTPS is still not working, automate the recheck instead of asking the user to babysit it.

## Good final report

Report these items clearly:

- registrar nameserver state
- DNS provider zone state
- apex record
- `www` record
- proxy state
- TLS mode
- canonical host and redirect rule
- remaining blocker, if any

If propagation is still pending and live HTTPS is still not working, say that explicitly and separate:

- already applied configuration
- still waiting on public delegation

If live HTTPS works while nameserver checks still look stale, say that the site is reachable and note the stale DNS check as non-blocking.
