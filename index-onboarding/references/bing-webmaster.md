# Bing Webmaster Tools

Load this reference for Bing Webmaster Tools onboarding.

IndexNow URL submission does not by itself make the site appear in Bing Webmaster Tools.

## Rules

- If `BING_WEBMASTER_API_KEY` is available, prefer the API route over manual browser import.
- Importing from Google Search Console is valid when explicitly requested, but optional.
- If Bing credentials and browser access are missing, report Bing Webmaster Tools as `skipped` and continue to Clarity.

## Preferred API Flow

1. Check `GetUserSites` to see whether the final domain is already present.
2. If missing, call `AddSite` for the final canonical URL, for example `https://example.com/`.
3. Read returned site metadata, especially:
   - `AuthenticationCode`
   - `DnsVerificationCode`
   - `IsVerified`
4. Prefer HTML meta verification for static or repo-controlled sites:
   - add `<meta name="msvalidate.01" content="<AuthenticationCode>" />` to the live homepage head
   - deploy the repo if code changed and deployment credentials exist
5. Once the verification token is live, call `VerifySite`.
6. Recheck `GetUserSites` until the site appears with `IsVerified = true`, or report a refresh delay if `VerifySite` succeeded but site state has not caught up.
7. Submit the sitemap through `SubmitFeed`.
8. Optionally submit the homepage or changed URLs through `SubmitUrl`.

## Minimum Goal

- site appears in Bing Webmaster Tools for the owning account
- verification state is known
- sitemap submission state is known

Verify against the final canonical URL with trailing slash consistency.
