# redirect_to_pg

A tiny redirect service for the photo-gallery. Visitors hit this service at a
stable address and get redirected (HTTP 302) to the current Cloudflare tunnel URL.

## How it works

1. `tunnel_url.txt` in this repo holds the current tunnel URL.
2. The photo-gallery's `update-tunnel-url.sh` pushes the new URL here whenever
   the tunnel restarts.
3. `server.py` serves a 302 redirect to that URL, doing a `git pull` at most
   once per minute to pick up changes.

## Run

```bash
python3 server.py            # serves on port 3000
PORT=8000 python3 server.py  # custom port
```

No dependencies — just Python 3 and git.

## Files

| File | Purpose |
|------|---------|
| `server.py` | The redirect HTTP server |
| `tunnel_url.txt` | Current tunnel URL (auto-updated by photo-gallery) |
| `.env.local` | Local secrets (not committed) |
