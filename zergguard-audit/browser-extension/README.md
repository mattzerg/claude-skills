# ZergGuard URL Shield (browser extension)

Real-time URL check. Blocks navigation to domains on the local ZergGuard IOC list.

## Install (Chrome / Brave / Edge)

1. `chrome://extensions` → enable Developer Mode.
2. "Load unpacked" → select this folder.

## IOC list source

The extension expects a local HTTP server serving the IOC cache at `http://127.0.0.1:54321/ioc.json`.

The simplest way to run this locally:

```bash
cd ~/.config/zerg-guard
python3 -m http.server 54321 --bind 127.0.0.1 &
# now http://127.0.0.1:54321/ioc_cache.json is reachable
```

Or set up a tiny LaunchAgent for it (TODO: ship `com.matteisner.zergguard-iocserver.plist`).

## Whatever you do

The extension defaults are sensible — if it can't reach the IOC server, it just won't block anything. You won't lose browsing capability.
