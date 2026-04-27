# IndexNow Integration

This project can submit changed public URLs to IndexNow after a push or deploy.

## Required setup

- Generate a new random IndexNow key for this project and host.
- Add a verification file to `public/`:
  - filename: `<INDEXNOW_KEY>.txt`
  - file content: `<INDEXNOW_KEY>`

Do not reuse a shared key from another project by default. Prefer one unique key per host or project.

## Optional environment variables

- `INDEXNOW_KEY`: override key used by the submit script
- `INDEXNOW_ENDPOINT`: custom endpoint override. Defaults to `https://api.indexnow.org/indexnow`

## Collect changed URLs

```bash
tmp_file="$(mktemp)"
pnpm indexnow:collect --base-url https://example.com --from <old-ref> --to <new-ref> --out-file "$tmp_file"
```

## Submit URLs

```bash
pnpm indexnow:submit --base-url https://example.com --urls-file "$tmp_file"
```

## Typical flow

```bash
tmp_file="$(mktemp)"
pnpm indexnow:collect --base-url https://example.com --from <old-ref> --to <new-ref> --out-file "$tmp_file"
pnpm indexnow:submit --base-url https://example.com --urls-file "$tmp_file"
```
