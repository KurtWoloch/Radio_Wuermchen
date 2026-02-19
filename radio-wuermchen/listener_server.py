"""
Radio Würmchen - Listener Web Server
Serves the station page with embedded player and a request form.
Writes listener requests to listener_request.txt for the DJ orchestrator.
Uses ThreadingHTTPServer so the stream proxy doesn't block other requests.
"""

import http.server
import socketserver
import urllib.parse
import urllib.request
import json
import os
import re
import html
import time
import base64
import threading
from pathlib import Path
from datetime import datetime

PORT = 8001
# Icecast local address for stream proxying
ICECAST_URL = "http://localhost:8000/stream"

BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
LISTENER_REQUEST_FILE = BASE_DIR / "listener_request.txt"
LISTENER_LOG_FILE = BASE_DIR / "listener_requests.log"
STREAMER_LOG_FILE = BASE_DIR / "streamer.log"
SHOWS_SCHEDULE_FILE = BASE_DIR / "shows_schedule.json"
LOGO_FILE = BASE_DIR / "logo.png"

# Rate limit: one request per IP per 2 minutes
request_timestamps = {}
RATE_LIMIT_SECONDS = 120


def get_current_show():
    """Get the currently active show name from the schedule."""
    try:
        with open(SHOWS_SCHEDULE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        now = datetime.now()
        current_minutes = now.hour * 60 + now.minute
        for show in data.get("shows", []):
            start = show["schedule"]["start"]
            end = show["schedule"]["end"]
            sh, sm = map(int, start.split(":"))
            eh, em = map(int, end.split(":"))
            start_min = sh * 60 + sm
            end_min = eh * 60 + em
            if end_min <= start_min:  # overnight show
                if current_minutes >= start_min or current_minutes < end_min:
                    return show["name"]
            else:
                if start_min <= current_minutes < end_min:
                    return show["name"]
        return None
    except:
        return None


def get_recent_tracks(n=5):
    """Get the last N tracks from streamer.log by parsing 'Streaming:' lines,
    filtering out announcements (temp_announcement*.mp3)."""
    try:
        tracks = []
        with open(STREAMER_LOG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                m = re.search(r'Streaming: (.+)$', line.strip())
                if m:
                    filename = m.group(1).strip()
                    # Skip announcements
                    if filename.startswith('temp_announcement'):
                        continue
                    # Extract artist - title from filename
                    name = Path(filename).stem  # remove .mp3
                    tracks.append(name)
        # Return last N, most recent first
        return list(reversed(tracks[-n:]))
    except:
        return []


def get_logo_data_uri():
    """Return the logo as a base64 data URI, or empty string if not found."""
    try:
        with open(LOGO_FILE, 'rb') as f:
            data = base64.b64encode(f.read()).decode('ascii')
        return f"data:image/png;base64,{data}"
    except:
        return ""


def get_station_page(message=None, error=None):
    show = get_current_show()
    tracks = get_recent_tracks(5)
    logo_uri = get_logo_data_uri()

    show_html = f'<div id="showname" class="show-name">Now: {html.escape(show)}</div>' if show else ''

    tracks_html = ""
    if tracks:
        tracks_html = '<div class="recent"><h3>Recently Played</h3><ul>'
        for i, t in enumerate(tracks):
            cls = ' class="now"' if i == 0 else ''
            tracks_html += f'<li{cls}>{html.escape(t)}</li>'
        tracks_html += '</ul></div>'

    msg_html = ""
    if message:
        msg_html = f'<div class="msg success">{html.escape(message)}</div>'
    if error:
        msg_html = f'<div class="msg error">{html.escape(error)}</div>'

    logo_html = f'<img src="{logo_uri}" alt="Radio Würmchen" class="logo">' if logo_uri else ''

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Radio W&uuml;rmchen</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: #0a0a14; color: #eee;
    min-height: 100vh; display: flex; justify-content: center; align-items: center;
  }}
  .container {{
    max-width: 480px; width: 90%; padding: 2rem;
    background: #0f1a0f; border-radius: 16px;
    box-shadow: 0 8px 32px rgba(0,255,0,0.08);
    border: 1px solid #1a3a1a;
  }}
  .logo {{ display: block; margin: 0 auto 1rem; max-width: 120px; border-radius: 12px; }}
  h1 {{ text-align: center; font-size: 1.8rem; margin-bottom: 0.3rem; }}
  h1 span {{ color: #00ff00; }}
  .subtitle {{ text-align: center; color: #888; font-size: 0.85rem; margin-bottom: 1.2rem; }}
  .show-name {{
    text-align: center; color: #00ff00; font-weight: 600;
    margin-bottom: 1rem; font-size: 1.1rem;
  }}
  audio {{ width: 100%; margin-bottom: 1.2rem; border-radius: 8px; }}
  .recent {{ margin-bottom: 1.5rem; }}
  .recent h3 {{ color: #aaa; font-size: 0.8rem; text-transform: uppercase; margin-bottom: 0.5rem; }}
  .recent ul {{ list-style: none; }}
  .recent li {{
    padding: 0.4rem 0; border-bottom: 1px solid #1a1a0a;
    font-size: 0.9rem; color: #ccc;
  }}
  .recent li.now {{ color: #00ff00; font-weight: 600; }}
  h2 {{ font-size: 1rem; margin-bottom: 0.8rem; color: #ccc; }}
  form {{ display: flex; flex-direction: column; gap: 0.6rem; }}
  input[type=text] {{
    padding: 0.7rem; border-radius: 8px; border: 1px solid #1a3a1a;
    background: #0a1f0a; color: #eee; font-size: 1rem;
  }}
  input[type=text]::placeholder {{ color: #555; }}
  input[type=text]:focus {{ outline: none; border-color: #00ff00; box-shadow: 0 0 8px rgba(0,255,0,0.2); }}
  button {{
    padding: 0.7rem; border-radius: 8px; border: none;
    background: #00aa00; color: white; font-size: 1rem;
    cursor: pointer; font-weight: 600; transition: background 0.2s;
  }}
  button:hover {{ background: #00cc00; }}
  .msg {{ padding: 0.7rem; border-radius: 8px; margin-bottom: 1rem; text-align: center; }}
  .msg.success {{ background: #1b4332; color: #95d5b2; }}
  .msg.error {{ background: #461220; color: #f5a6a6; }}
  .listeners {{ text-align: center; color: #666; font-size: 0.8rem; margin-bottom: 1rem; }}
  .listeners span {{ color: #00ff00; font-weight: 600; }}
  .footer {{ text-align: center; color: #555; font-size: 0.75rem; margin-top: 1.5rem; }}
</style>
</head>
<body>
<div class="container">
  {logo_html}
  <h1>Radio <span>W&uuml;rmchen</span></h1>
  <p class="subtitle">AI-powered radio &mdash; Vienna, Austria</p>
  {show_html}
  <audio controls autoplay>
    <source src="/stream" type="audio/mpeg">
    Your browser does not support the audio element.
  </audio>
  {tracks_html}
  {msg_html}
  <h2>Send a request to the DJ</h2>
  <form id="reqform" onsubmit="return sendRequest(event)">
    <input type="text" id="reqinput" name="request" placeholder="e.g. Play something by Daft Punk!" maxlength="200" required>
    <button type="submit" id="reqbtn">Send Request</button>
  </form>
  <div id="reqmsg"></div>
  <script>
  function sendRequest(e) {{
    e.preventDefault();
    var inp = document.getElementById('reqinput');
    var btn = document.getElementById('reqbtn');
    var msg = document.getElementById('reqmsg');
    var text = inp.value.trim();
    if (!text) return false;
    btn.disabled = true;
    btn.textContent = 'Sending...';
    fetch('/request', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
      body: 'request=' + encodeURIComponent(text)
    }})
    .then(function(r) {{ return r.json(); }})
    .then(function(data) {{
      if (data.ok) {{
        msg.className = 'msg success';
        msg.textContent = data.message;
        inp.value = '';
      }} else {{
        msg.className = 'msg error';
        msg.textContent = data.message;
      }}
      btn.disabled = false;
      btn.textContent = 'Send Request';
    }})
    .catch(function() {{
      msg.className = 'msg error';
      msg.textContent = 'Connection error. Please try again.';
      btn.disabled = false;
      btn.textContent = 'Send Request';
    }});
    return false;
  }}
  function updateNowPlaying() {{
    fetch('/nowplaying')
    .then(function(r) {{ return r.json(); }})
    .then(function(data) {{
      var showEl = document.getElementById('showname');
      if (data.show) {{
        if (!showEl) {{
          showEl = document.createElement('div');
          showEl.id = 'showname';
          showEl.className = 'show-name';
          var audio = document.querySelector('audio');
          audio.parentNode.insertBefore(showEl, audio);
        }}
        showEl.textContent = 'Now: ' + data.show;
      }} else if (showEl) {{
        showEl.remove();
      }}
      var lEl = document.getElementById('listeners');
      if (lEl && data.listeners >= 0) {{
        lEl.innerHTML = '<span>' + data.listeners + '</span> listener' + (data.listeners !== 1 ? 's' : '') + ' tuned in';
      }}
      var ul = document.querySelector('.recent ul');
      if (ul && data.tracks && data.tracks.length) {{
        ul.innerHTML = data.tracks.map(function(t, i) {{
          return '<li' + (i === 0 ? ' class="now"' : '') + '>' + t.replace(/&/g,'&amp;').replace(/</g,'&lt;') + '</li>';
        }}).join('');
      }}
    }})
    .catch(function() {{}});
  }}
  setInterval(updateNowPlaying, 60000);
  </script>
  <div id="listeners" class="listeners"></div>
  <p class="footer">Powered by Icecast &amp; OpenClaw</p>
</div>
</body>
</html>"""


class RadioHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(get_station_page().encode("utf-8"))
        elif self.path == "/nowplaying":
            # JSON endpoint for live updates
            listeners = -1
            try:
                r = urllib.request.urlopen("http://localhost:8000/status-json.xsl", timeout=3)
                icecast = json.loads(r.read().decode('utf-8'))
                source = icecast.get("icestats", {}).get("source", {})
                if isinstance(source, list):
                    listeners = sum(s.get("listeners", 0) for s in source)
                else:
                    listeners = source.get("listeners", 0)
            except:
                pass
            data = {
                "show": get_current_show(),
                "tracks": get_recent_tracks(5),
                "listeners": listeners
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        elif self.path == "/stream":
            # Proxy the Icecast stream
            try:
                req = urllib.request.Request(ICECAST_URL)
                resp = urllib.request.urlopen(req)
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()
                while True:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        break
            except Exception:
                self.send_response(502)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/request":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            params = urllib.parse.parse_qs(body)
            request_text = params.get("request", [""])[0].strip()

            client_ip = self.client_address[0]
            now = time.time()

            if not request_text or len(request_text) > 200:
                resp = {"ok": False, "message": "Please enter a request (max 200 characters)."}
            elif client_ip in request_timestamps and (now - request_timestamps[client_ip]) < RATE_LIMIT_SECONDS:
                remaining = int(RATE_LIMIT_SECONDS - (now - request_timestamps[client_ip]))
                resp = {"ok": False, "message": f"Please wait {remaining} seconds before sending another request."}
            else:
                try:
                    with open(LISTENER_REQUEST_FILE, 'w', encoding='utf-8') as f:
                        f.write(request_text)
                    with open(LISTENER_LOG_FILE, 'a', encoding='utf-8') as f:
                        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {client_ip}: {request_text}\n")
                    request_timestamps[client_ip] = now
                    resp = {"ok": True, "message": "Your request has been sent to the DJ! \U0001f3b5"}
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Request from {client_ip}: {request_text}")
                except Exception:
                    resp = {"ok": False, "message": "Something went wrong. Please try again."}

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), RadioHandler)
    print(f"Radio Würmchen listener server running on http://localhost:{PORT}")
    print(f"Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
