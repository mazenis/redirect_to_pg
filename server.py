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
URL_FILE = SCRIPT_DIR / 'tunnel_url.txt'
PORT = int(os.environ.get('PORT', 3000))

CACHE_TTL = 60  # seconds between git pulls
last_pull = 0


def get_tunnel_url():
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
                    print('[*] Pulled latest tunnel_url.txt')
            else:
                print(f'[-] git pull failed: {result.stderr.strip()[:200]}')
        except Exception as e:
            print(f'[-] git pull error: {e}')

    try:
        return URL_FILE.read_text().strip()
    except FileNotFoundError:
        return None


class RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = get_tunnel_url()

        if not url:
            self.send_response(503)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body style="font-family:sans-serif;padding:20px">'
                             b'<h1>Service Unavailable</h1>'
                             b'<p>tunnel_url.txt not found in redirect_to_pg repo.</p>'
                             b'</body></html>')
            return

        print(f'[>] Redirecting to: {url}')
        self.send_response(302)
        self.send_header('Location', url)
        self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), RedirectHandler)
    print(f'Redirect service running on http://localhost:{PORT}')
    print(f'Serving URL from: {URL_FILE}')
    server.serve_forever()
