# Stage 5: Rendering — recipes and troubleshooting

## Normal case (user's machine, CI)

```bash
npx remotion render <CompositionId> video/promo.mp4
```

Remotion downloads its own headless Chrome on first run. Verify the output with sampled frames (see SKILL.md Stage 5) — never ship a render you haven't looked at.

## Constrained / sandboxed environments

Symptoms and fixes, in the order you'll hit them:

### Chrome download blocked (storage.googleapis.com unreachable)

Playwright's CDN is often reachable when Chrome-for-Testing's isn't:

```bash
npm i playwright-core && npx playwright-core install chromium-headless-shell
npx remotion render <Id> out.mp4 \
  --browser-executable="$(find ~/.cache/ms-playwright -name headless_shell -type f | head -1)"
```

### Missing shared libraries, no root (e.g. `libXdamage.so.1: cannot open shared object file`)

Check what's missing: `ldd <headless_shell> | grep "not found"`. If it's only X11 damage/fixes-type libs (never called in headless mode), compile a stub:

```bash
cat > xd.c <<'EOF'
typedef unsigned long XID; typedef XID Damage; typedef void Display;
int XDamageQueryExtension(Display*d,int*e,int*err){return 0;}
int XDamageQueryVersion(Display*d,int*a,int*b){return 0;}
Damage XDamageCreate(Display*d,XID w,int l){return 0;}
void XDamageDestroy(Display*d,Damage m){}
void XDamageSubtract(Display*d,Damage m,XID r,XID p){}
void XDamageAdd(Display*d,XID w,XID r){}
EOF
cc -shared -fPIC -Wl,-soname,libXdamage.so.1 -o /tmp/stublibs/libXdamage.so.1 xd.c
LD_LIBRARY_PATH=/tmp/stublibs npx remotion render ...
```

Only stub libs whose functionality headless rendering genuinely never uses; if core libs (glib, nss) are missing, stubs won't save you — ask the user to render locally instead.

### npm installs stall forever

Slow/flaky proxies hang npm's keep-alive sockets. Remedies: run installs in the background and poll; add `--prefer-offline --fetch-timeout=30000 --fetch-retries=10 --fetch-retry-mintimeout=1000`; if one tarball refuses to arrive, `curl` it from the registry directly and untar into `node_modules/<pkg>` yourself.

### Renders die partway (OOM or watchdog-killed background processes)

Render in resumable chunks — each invocation is short-lived and bounded:

```bash
for range in 0-289 290-579 580-869 870-1159; do
  [ -f "out/chunk-$range.mp4" ] && continue
  npx remotion render <Id> "out/chunk-$range.mp4" --frames=$range --concurrency=1
done
printf "file 'chunk-0-289.mp4'\nfile 'chunk-290-579.mp4'\n..." > out/list.txt
ffmpeg -f concat -safe 0 -i out/list.txt -c copy out/full.mp4
```

Chunks concat losslessly (`-c copy`) because each starts at a keyframe. This also gives cheap partial re-renders after edits: re-render only the chunks covering the frames you changed, then re-concat.

### Fonts render as fallback

You forgot `delayRender` in the font loader, or the woff2 path is wrong. Fix the loader (see remotion-build.md) — don't paper over it with `--timeout` increases. If a render intermittently times out with "delayRender was called but not cleared", raise `--timeout` to 120000 and drop `--concurrency` to 1.

### If all sandbox routes fail

Deliver the Remotion source + render scripts into the repo, verify the composition in chunks you *can* render (even a few frames via `--frames=0-30`), and hand the final full render to the user: `pnpm video:promo:render`.
