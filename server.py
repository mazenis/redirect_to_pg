#!/usr/bin/env python3
"""Redirect service — reads tunnel_url.txt from this repo and redirects to it.

The photo-gallery's update-tunnel-url.sh pushes the new URL to this repo,
so a `git pull` here is enough to stay current (this repo is tiny, pull is fast).
"""
import os
import subprocess
import time
import urllib.request
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

SCRIPT_DIR = Path(__file__).parent
# prod → the stable public link (also used by the APK / GitHub Pages);
# dev  → a separate URL so dev tunnels never overwrite production.
# files → File Drop service (Dropbox-like file hosting)
URL_FILES = {
    'prod': SCRIPT_DIR / 'tunnel_url.txt',
    'dev': SCRIPT_DIR / 'tunnel_url_dev.txt',
    # File Drop mirrors its URL into THIS repo (like the gallery), so a git pull
    # here keeps it current — no reaching into the separate file-drop repo.
    'files': SCRIPT_DIR / 'tunnel_url_filedrop.txt',
}
PORT = int(os.environ.get('PORT', 3000))

CACHE_TTL = 60  # seconds between git pulls
last_pull = 0


def _git_pull():
    global last_pull
    now = time.time()
    if now - last_pull >= CACHE_TTL:
        last_pull = now
        try:
            result = subprocess.run(
                ['git', '-C', str(SCRIPT_DIR), 'pull', '--ff-only'],
                capture_output=True, text=True, timeout=20)
            if result.returncode == 0:
                if 'Already up to date' not in result.stdout:
                    print('[*] Pulled latest tunnel URLs')
            else:
                print(f'[-] git pull failed: {result.stderr.strip()[:200]}')
        except Exception as e:
            print(f'[-] git pull error: {e}')


def get_tunnel_url(env='prod'):
    _git_pull()
    url_file = URL_FILES.get(env, URL_FILES['prod'])
    try:
        return url_file.read_text().strip()
    except FileNotFoundError:
        return None


def env_from_path(path):
    # /dev (or /dev/…) → dev; everything else → prod.
    first = path.strip('/').split('/', 1)[0].lower()
    return 'dev' if first == 'dev' else 'prod'


def check_reachable(url, timeout=4):
    """Return True if the tunnel URL answers with any HTTP status (not a network error)."""
    if not url:
        return False
    try:
        req = urllib.request.Request(url, method='HEAD')
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True  # a 4xx/5xx still means the tunnel + app are reachable
    except Exception:
        return False


def build_panel():
    """Control panel showing BOTH environments: live URL, reachability, open link."""
    rows = []
    for env, label, route in (('prod', 'Production', '/prod'), ('dev', 'Development', '/dev')):
        url = get_tunnel_url(env)
        up = check_reachable(url)
        badge = ('#16a34a', 'ONLINE') if up else (('#dc2626', 'OFFLINE') if url else ('#9ca3af', 'NO URL'))
        url_html = (f'<a href="{url}">{url}</a>' if url else '<i>not published yet</i>')
        rows.append(f'''
        <div class="card">
          <div class="head">
            <span class="env {env}">{label}</span>
            <span class="badge" style="background:{badge[0]}">{badge[1]}</span>
          </div>
          <div class="url">{url_html}</div>
          <div class="actions">
            <a class="btn primary" href="{route}">Open {label} →</a>
            <a class="btn" href="{route}" onclick="navigator.clipboard&&navigator.clipboard.writeText('{url or ''}');return false;">Copy URL</a>
          </div>
          <div class="file">{URL_FILES[env].name}</div>
        </div>''')
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Photo Gallery — Control</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="30">
<style>
  body{{font-family:system-ui,sans-serif;background:#f6f7f9;color:#1f2937;margin:0;padding:24px}}
  h1{{font-size:20px;margin:0 0 4px}} .sub{{color:#6b7280;font-size:13px;margin-bottom:20px}}
  .grid{{display:grid;gap:16px;max-width:520px}}
  .card{{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;box-shadow:0 1px 2px rgba(0,0,0,.04)}}
  .head{{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}}
  .env{{font-weight:700;font-size:15px}} .env.dev{{color:#b45309}} .env.prod{{color:#065f46}}
  .badge{{color:#fff;font-size:11px;font-weight:700;padding:3px 9px;border-radius:20px;letter-spacing:.03em}}
  .url{{font-size:13px;word-break:break-all;margin-bottom:12px}} .url a{{color:#0969da}}
  .actions{{display:flex;gap:8px}}
  .btn{{flex:1;text-align:center;text-decoration:none;padding:8px 10px;border-radius:8px;font-size:13px;
        border:1px solid #d1d5db;color:#374151;background:#fff}}
  .btn.primary{{background:#0969da;border-color:#0969da;color:#fff;font-weight:600}}
  .file{{color:#9ca3af;font-size:11px;margin-top:8px;font-family:monospace}}
</style></head>
<body>
  <h1>⚡ Photo Gallery — Control</h1>
  <div class="sub">Both environments · auto-refreshes every 30s</div>
  <div class="grid">{''.join(rows)}</div>
</body></html>'''


class RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._handle(head=False)

    def do_HEAD(self):
        # Reachability probes (e.g. the File Drop bookmark) use HEAD — mirror GET
        # but send no body, so we don't 501 on it.
        self._handle(head=True)

    def _handle(self, head=False):
        path = self.path.split('?', 1)[0].strip('/').lower()

        # File Drop launcher page — served over http so it's same-origin with
        # /files (no file:// unique-origin blocks; the reachability dot works).
        if path in ('open', 'launcher', 'filedrop'):
            launcher = SCRIPT_DIR.parent / 'file-drop' / 'file-drop.html'
            try:
                body = launcher.read_bytes()
            except FileNotFoundError:
                body = b'<h1>Launcher not found</h1>'
                self.send_response(404)
            else:
                self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            if not head:
                self.wfile.write(body)
            return

        # Control panel: shows BOTH envs (does not redirect).
        if path in ('panel', 'control'):
            body = build_panel().encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            if not head:
                self.wfile.write(body)
            return

        # /files → File Drop service
        if path.split('/')[0] == 'files':
            env = 'files'
        else:
            env = env_from_path(self.path)
        url = get_tunnel_url(env)

        if not url:
            body = (f'<html><body style="font-family:sans-serif;padding:20px">'
                    f'<h1>Service Unavailable</h1>'
                    f'<p>No URL published yet for <b>{env}</b> '
                    f'({URL_FILES[env].name}). '
                    f'<a href="/panel">Open control panel</a></p>'
                    f'</body></html>').encode()
            self.send_response(503)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            if not head:
                self.wfile.write(body)
            return

        print(f'[>] ({env}) {"HEAD" if head else "Redirecting"} to: {url}')
        self.send_response(302)
        self.send_header('Location', url)
        self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), RedirectHandler)
    print(f'Redirect service running on http://localhost:{PORT}')
    print(f'  /       → prod redirect ({URL_FILES["prod"].name})')
    print(f'  /dev    → dev redirect  ({URL_FILES["dev"].name})')
    print(f'  /panel  → control panel (both envs, live status)')
    server.serve_forever()
