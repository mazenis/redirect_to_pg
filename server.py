#!/usr/bin/env python3
"""Redirect service — reads tunnel_url.txt from this repo and redirects to it.

The photo-gallery's update-tunnel-url.sh pushes the new URL to this repo,
so a `git pull` here is enough to stay current (this repo is tiny, pull is fast).
"""
import os
import subprocess
import time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

SCRIPT_DIR = Path(__file__).parent
# prod → the stable public link (also used by the APK / GitHub Pages);
# dev  → a separate URL so dev tunnels never overwrite production.
URL_FILES = {
    'prod': SCRIPT_DIR / 'tunnel_url.txt',
    'dev': SCRIPT_DIR / 'tunnel_url_dev.txt',
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


class RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        env = env_from_path(self.path)
        url = get_tunnel_url(env)

        if not url:
            self.send_response(503)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(f'<html><body style="font-family:sans-serif;padding:20px">'
                             f'<h1>Service Unavailable</h1>'
                             f'<p>No URL published yet for <b>{env}</b> '
                             f'({URL_FILES[env].name}).</p>'
                             f'</body></html>'.encode())
            return

        print(f'[>] ({env}) Redirecting to: {url}')
        self.send_response(302)
        self.send_header('Location', url)
        self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), RedirectHandler)
    print(f'Redirect service running on http://localhost:{PORT}')
    print(f'  /     → prod ({URL_FILES["prod"].name})')
    print(f'  /dev  → dev  ({URL_FILES["dev"].name})')
    server.serve_forever()
