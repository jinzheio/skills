---
name: new-domain-launch
version: "1.1.0"
description: "Use when the user has an already deployed site and wants a custom domain connected, including 'connect this domain', '绑定域名', 'set up DNS', 'make www redirect', or 'enable HTTPS'. Covers registrar nameservers, DNS provider records, hosting-platform domain binding, TLS, apex/www redirects, and email forwarding only when requested. Do not use before the site has a working deployment; use upstart-site first."
---

# new-domain-launch

Use this skill when the site is already deployed, but the user now wants a new custom domain to work on the public internet.

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
- optional inbound email forwarding works if requested

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

## Source of truth

Use platform APIs and dashboards as the source of truth for configuration:

- DNS record intent comes from the hosting provider and DNS provider. For Vercel plus Cloudflare, trust Vercel domain/project inspection and Cloudflare DNS zone records over local resolver output.
- Connectivity is proven by loading the public URL and receiving the expected page content. A bare DNS answer is only supporting evidence.
- Local DNS output, including `dig`, can be stale or polluted by the local network. Do not let a polluted local DNS answer block completion when Vercel and Cloudflare records are correct and the public page returns the intended content.

## Workflow

### 1. Plan

Before changing registrar, DNS, hosting, TLS, or email settings, produce a plan:

- domain and intended canonical host
- registrar, DNS provider, and hosting provider
- current nameserver state
- hosting-provider domain binding targets
- DNS records to create or update
- proxy and TLS policy
- redirect policy
- validation commands and live URL checks
- rollback or correction path for wrong DNS records
- whether email forwarding was requested

Ask for user confirmation before external changes unless the user already explicitly authorized the domain launch.

### 2. Create or inspect the DNS zone

If the domain will use Cloudflare DNS:

1. Create the zone in Cloudflare first.
2. Record the assigned nameservers.
3. If the registrar is separate, update the registrar nameservers to the Cloudflare nameservers.
4. Prefer the registrar's official API when credentials are available.
5. Only fall back to browser automation when the registrar API is unavailable or blocked.

For Spaceship specifically:

- prefer the official external API rather than the web app when API key and secret are available
- use the domain API to inspect current nameservers and update them to `provider=custom` with the Cloudflare hosts

### 3. Wait for nameserver delegation

Do not rush past this step. Run `scripts/check-dns-propagation.sh <domain> <ns-keyword>` to poll propagation state automatically.

The script checks public resolvers (`1.1.1.1`, `8.8.8.8`) and then makes a live HTTPS request on each attempt. **The live HTTPS page load is the authoritative completion signal — not a clean DNS answer.**

DNS results from local resolvers and public resolvers can be stale or polluted by the local network for many minutes after delegation has actually changed. The script will tell you when this is happening and will not block on stale resolver output once the site is reachable.

If the script times out:

1. Open the live URL directly in a browser.
2. Check Cloudflare and Vercel dashboards — if both show the records as active and correct, the configuration is done regardless of what `dig` returns locally.
3. If the page loads in a browser, treat that as the completion signal and proceed.

If delegation is still propagating and live HTTPS is not yet working, re-run the script or set a heartbeat automation and come back later.

### 4. Bind the domain on the hosting provider

Add both the apex and `www` domains to the hosting platform if the user wants both.

For Vercel-like platforms:

1. Add the apex domain to the project.
2. Add the `www` domain to the project.
3. Query the provider for the exact required DNS targets.
4. Configure project-level redirect rules if `www -> apex` or `apex -> www` is desired.

Do not guess DNS targets from memory if the provider can return them directly.

For Vercel, treat the apex and `www` records as separate provider instructions:

- apex uses the record type and value Vercel shows for the apex host
- `www` uses the record type and value Vercel shows for the `www` host
- when Vercel asks for a `CNAME` on `www`, create a `CNAME`; do not create an `A` record
- do not copy the apex `A` value into `www`

Examples of acceptable sources:

- official CLI output
- official domain inspect/config API
- provider dashboard

### 5. Create DNS records

After the hosting provider returns the exact target values:

1. Create the apex record.
2. Create the `www` record.
3. Match the provider's recommended record type and target.

For Vercel-like setups:

- apex: use the provider-recommended record type and value, often `A`
- `www`: use the provider-recommended record type and value, normally `CNAME`

For Vercel specifically, `www` should be a `CNAME` when Vercel returns a CNAME target such as `cname.vercel-dns.com`. Do not create an `A` record for `www`, and do not assume the `www` record should copy the apex target.

### 6. Enable proxy and TLS settings when applicable

If Cloudflare is the DNS provider and the user wants Cloudflare in front:

1. Turn on orange-cloud proxy for the live records.
2. Set SSL/TLS mode to `Full (strict)` when the origin has a valid certificate.
3. Only use weaker TLS modes if the origin cannot support strict validation.

Do not leave the zone at `Full` if `Strict` is available.

### 7. Configure the redirect

Prefer putting host redirects on the hosting platform when supported.

For the default policy:

- apex serves the site
- `www` returns `301` to the apex

After configuring the redirect, verify both HTTP and HTTPS behavior if needed, but final acceptance should focus on HTTPS.

### 8. Optional email forwarding

If and only if the user asks for inbound domain email forwarding, read `references/email-routing.md`.

## Validation checklist

Before reporting completion, read `references/validation-checklist.md` and verify every relevant item.

## Good final report

Report these items clearly:

- registrar nameserver state
- DNS provider zone state
- apex record
- `www` record
- proxy state
- TLS mode
- canonical host and redirect rule
- email forwarding state, if requested
- remaining blocker, if any

If propagation is still pending and live HTTPS is still not working, say that explicitly and separate:

- already applied configuration
- still waiting on public delegation

If live HTTPS works while nameserver checks still look stale, say that the site is reachable and note the stale DNS check as non-blocking.
