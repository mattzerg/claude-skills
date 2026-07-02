# V0 — Slack tunnel setup (Matt-action required)

Auto-mode classifier (sensibly) declined to expose `localhost:8788` publicly without your explicit consent + the Slack signing secret in place. Three steps; each takes ~2 minutes.

## Step 1 — Get your Slack signing secret

1. Open <https://api.slack.com/apps>
2. Click the app that owns the token `xapp-1-A0B0BFYGV3R-...` (find it via your existing config at `~/.claude/skills/slack-skill/config.json` → `app_token`)
3. **Basic Information** → **App Credentials** → **Signing Secret** → **Show**
4. Copy it.

## Step 2 — Add the secret to slack-skill config

```bash
/usr/bin/python3 -c "
import json, sys
SECRET = input('Paste Slack signing secret: ').strip()
path = '/Users/mattheweisner/.claude/skills/slack-skill/config.json'
cfg = json.load(open(path))
cfg['default']['signing_secret'] = SECRET
import tempfile, os
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
with os.fdopen(fd, 'w') as fh: json.dump(cfg, fh, indent=2)
os.replace(tmp, path)
print('OK secret stored')
"
```

This adds the `signing_secret` field that `serve.py /slack/action` reads. From that point, the HMAC verification (added in Phase 2 Q0.4) will accept legitimate Slack requests and reject anything else.

## Step 3 — Start the Cloudflare Quick Tunnel + configure Slack

Quick Tunnel (ephemeral; URL changes on restart, fine for first-test):

```bash
# In a separate terminal so it stays running:
cloudflared tunnel --url http://localhost:8788
```

Within ~5 seconds the output will print a URL like `https://abc-def-ghi.trycloudflare.com`. Copy it.

Then in your Slack app dashboard:

1. <https://api.slack.com/apps> → your app
2. **Features** → **Interactivity & Shortcuts** → toggle ON
3. **Request URL** → paste `https://<tunnel-host>/slack/action`
4. **Save Changes**

## Step 4 — Verify end-to-end

```bash
# Post a fresh card:
/usr/bin/python3 ~/.claude/skills/decision-queue/tools/slack_card.py digest --limit 1

# Tap a button in FM-DM.
# Confirm a new row landed:
tail -1 ~/.claude/state/decisions_log.jsonl
```

Expected: a row with `"channel": "slack"`, `"answer": "<button-action-id>"`, and `"slack_user": "<your-name>"`.

## Step 5 — Make the tunnel persistent (optional)

Quick tunnels die when the process dies. For a stable URL, use a **named tunnel** (one-time setup, no domain needed):

```bash
cloudflared login              # opens browser; pick your Cloudflare account
cloudflared tunnel create zerg-decision-queue
# Note the tunnel UUID printed
cloudflared tunnel route dns zerg-decision-queue decisions.<your-cf-zone>
# Or use a generated *.cfargotunnel.com hostname for free
```

Then create `~/.cloudflared/config.yml`:

```yaml
tunnel: <UUID-from-create>
credentials-file: /Users/mattheweisner/.cloudflared/<UUID>.json
ingress:
  - hostname: decisions.<your-cf-zone>
    service: http://localhost:8788
  - service: http_status:404
```

And a LaunchAgent `com.zerg.decision-queue-tunnel.plist` to run `cloudflared tunnel run zerg-decision-queue` at login. Stable URL → set it in the Slack app once and forget.

If you want, I can prepare the LaunchAgent .plist file as a follow-up when you have the named tunnel UUID. Or just stay on Quick Tunnel and re-paste the URL into Slack each time it changes (annoying but zero-setup).
