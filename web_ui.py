"""
Vaani web UI server.

This replaces the Tkinter desktop window (ui.py) with a mobile-first web UI.
The voice pipeline in main.py is completely unchanged: this file only consumes
the same ui_queue events (state + transcript) that the Tkinter UI consumed, and
relays them to the browser over Server-Sent Events (SSE).

Why SSE + the standard-library http.server, and not Flask/FastAPI/WebSockets:
- It needs zero new dependencies (our working agreement says ask before adding one).
- The pipeline only ever pushes events one way (server -> browser), which is
  exactly what SSE is for. The single thing the browser sends back (start a
  session) is a plain POST.

Pieces:
- Broadcaster: run_conversation pushes events into this as if it were the
  ui_queue; it fans each event out to every connected browser.
- trigger(): the same entry point the Start button and TWS gesture both use.
- Handler: serves the page, the /events SSE stream, /trigger, and a dev-only
  /simulate that replays a canned turn so the UI can be tested without a mic.
- TWS listener: reused from ui.py so an earbud tap still starts a session.
"""

import os
import sys
import json
import time
import queue
import atexit
import socket
import datetime
import asyncio
import threading
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# The voice pipeline prints Telugu/Hindi transcripts and the rupee sign. On Windows
# the default console encoding is cp1252, which cannot encode those characters, so
# an unconfigured print() raises UnicodeEncodeError and kills the session worker
# thread (the whole conversation silently dies). main.py only fixes this inside its
# own __main__ block, which does NOT run when we import main below. So reconfigure
# stdout/stderr to UTF-8 ourselves; errors="replace" guarantees a stray glyph can
# never crash a live session.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Import the unchanged pipeline. main.py only tees stdout to a log file when run
# as __main__, so importing here leaves our prints going to this server's terminal
# (now safely UTF-8 thanks to the reconfigure above).
from main import run_conversation, create_chat_session, Tee

# WinRT media-button plumbing, identical to ui.py, so a Bluetooth earbud tap can
# start a session hands-free.
from winrt.windows.media import SystemMediaTransportControlsButton
from winrt.windows.media.playback import MediaPlayer

HOST = "0.0.0.0"          # bind on all interfaces so a phone on the same wifi can reach it
PORT = 8765               # deliberately not 8000: that port belongs to the finance tracker API,
                          # which Vaani POSTs transactions to, so both must run side by side in a demo
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


# ── Broadcaster ─────────────────────────────────────────────────────────────
# run_conversation(chat_session, ui_queue) calls ui_queue.put(event). We pass a
# Broadcaster in place of that queue: every .put() fans the event out to one
# queue per connected browser. The SSE handler drains its own queue and writes
# each event to its HTTP response stream.

class Broadcaster:
    def __init__(self):
        self._subscribers = set()
        self._history = []
        self._lock = threading.Lock()

    def subscribe(self):
        # Replay the current session's events into this client first, then register
        # it for live ones, all under one lock so no event slips through the gap.
        # This is what lets a phone taken out of the pocket mid-conversation rebuild
        # the whole conversation so far, not just what happens after it connects.
        q = queue.Queue()
        with self._lock:
            for msg in self._history:
                q.put(msg)
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            self._subscribers.discard(q)

    def put(self, msg):
        # Called from the pipeline thread. Record into the session history and copy
        # the subscriber set under the lock, then deliver outside it.
        with self._lock:
            self._history.append(msg)
            targets = list(self._subscribers)
        for q in targets:
            q.put(msg)

    def reset_history(self):
        # Called at the start of each session so a late-joining client rebuilds the
        # current conversation rather than a previous one.
        with self._lock:
            self._history = []


broadcaster = Broadcaster()
_session_active = threading.Event()  # set while a conversation is running


# ── Session management ──────────────────────────────────────────────────────

def _session_worker():
    # Runs one full conversation on a daemon thread. The try/finally guarantees
    # the session guard clears and the UI returns to Idle even if the pipeline
    # raises unexpectedly.
    broadcaster.reset_history()  # a new conversation starts with a clean history
    broadcaster.put({"type": "session", "event": "start"})  # tells the UI to clear the screen
    cs = create_chat_session()
    try:
        run_conversation(cs, broadcaster)
    finally:
        _session_active.clear()
        broadcaster.put({"type": "state", "value": "Idle"})


def trigger():
    # Shared entry point for the browser mic button and the TWS gesture.
    # No-op if a session is already running (handles accidental double-tap).
    if _session_active.is_set():
        return False
    _session_active.set()
    threading.Thread(target=_session_worker, daemon=True).start()
    return True


# ── Dev-only simulation ─────────────────────────────────────────────────────
# Replays one canned Telugu turn through the broadcaster, in the exact order and
# message shape the real pipeline produces, so the frontend rendering can be
# tested end to end without a microphone or any API calls.

def _simulate():
    TQ = "ఈ రోజు బంగారం ధర ఎంత?"
    TA = "ఈ రోజు బంగారం ధర సుమారు 10 గ్రాములకు ₹71,200."
    seq = [
        (0.0, {"type": "session", "event": "start"}),
        (0.4, {"type": "state", "value": "Listening"}),
        (1.4, {"type": "state", "value": "Translating to English"}),
        (0.6, {"type": "transcript", "speaker": "User", "text": TQ,
               "lang": "te-IN", "translated": "What is the price of gold today?"}),
        (0.5, {"type": "state", "value": "Thinking"}),
        (1.6, {"type": "state", "value": "Translating back"}),
        (0.6, {"type": "transcript", "speaker": "Vaani",
               "text": "Gold is about 71,200 rupees per 10 grams today.", "translated": TA}),
        (0.4, {"type": "state", "value": "Speaking"}),
        (1.5, {"type": "state", "value": "Idle"}),
    ]
    for delay, msg in seq:
        time.sleep(delay)
        broadcaster.put(msg)


# ── HTTP handler ────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # keep the terminal clean; pipeline prints are what we care about

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._serve_file("index.html", "text/html; charset=utf-8")
        elif self.path == "/events":
            self._serve_events()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/trigger":
            started = trigger()
            self._send_json({"started": started})
        elif self.path == "/simulate":
            threading.Thread(target=_simulate, daemon=True).start()
            self._send_json({"ok": True})
        else:
            self.send_error(404)

    def _send_json(self, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, name, ctype):
        try:
            with open(os.path.join(WEB_DIR, name), "rb") as f:
                data = f.read()
        except FileNotFoundError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_events(self):
        # Open a long-lived SSE stream. The browser's EventSource reconnects
        # automatically if this drops.
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        q = broadcaster.subscribe()
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                msg = q.get()
                payload = "data: " + json.dumps(msg, ensure_ascii=False) + "\n\n"
                self.wfile.write(payload.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass  # browser tab closed
        finally:
            broadcaster.unsubscribe(q)


# ── TWS / wired earbud gesture listener (WinRT SMTC via MediaPlayer) ─────────
# Identical approach to ui.py: a Bluetooth earbud's Play/Pause arrives through
# Windows media controls, and we treat either as "start a Vaani session".

async def _listen_for_media_buttons():
    player = MediaPlayer()
    player.command_manager.is_enabled = True

    smtc = player.system_media_transport_controls
    smtc.is_enabled = True
    smtc.is_play_enabled = True
    smtc.is_pause_enabled = True

    def _on_button_pressed(sender, args):
        if args.button in (
            SystemMediaTransportControlsButton.PLAY,
            SystemMediaTransportControlsButton.PAUSE,
        ):
            trigger()

    smtc.add_button_pressed(_on_button_pressed)
    print("TWS Play/Pause listener is ready.")

    while True:
        await asyncio.sleep(1)


def _media_listener_thread():
    try:
        asyncio.run(_listen_for_media_buttons())
    except Exception as error:
        # Non-fatal: the browser mic button still works if SMTC init fails.
        print(f"TWS listener failed: {type(error).__name__}: {error}")


# ── Server lifecycle ─────────────────────────────────────────────────────────

class QuietThreadingHTTPServer(ThreadingHTTPServer):
    # A browser tab closing or an SSE stream reconnecting aborts the socket
    # mid-read, which the base server would dump as an alarming stack trace.
    # Those are normal; swallow them and only surface genuinely unexpected errors.
    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


def _free_port(port):
    # Before binding, make sure no stale Vaani instance is still holding our port.
    # A previous run that was force-quit, or left running in another window, would
    # otherwise make this start fail with "address already in use". We find any
    # process LISTENING on the port via netstat and terminate it with taskkill.
    # Scoped to our own dedicated port (8765), never the finance tracker's 8000.
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "TCP"],
                             capture_output=True, text=True).stdout
    except Exception:
        return
    for line in out.splitlines():
        parts = line.split()
        # netstat TCP rows look like: Proto  LocalAddr  ForeignAddr  State  PID
        if len(parts) >= 5 and parts[3].upper() == "LISTENING" and parts[1].endswith(f":{port}"):
            pid = parts[4]
            if pid in ("0", str(os.getpid())):
                continue
            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, text=True)
            print(f"Freed port {port}: terminated leftover process PID {pid}")


def _lan_ip():
    # Best-effort detection of this machine's LAN IP, so we can print the exact URL
    # a phone should open. Typing the port by hand is easy to get wrong (8765 vs
    # 8675). Connecting a UDP socket to a public address just picks the right
    # outbound interface; nothing is actually sent.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return None
    finally:
        s.close()


def _setup_logging():
    # Tee stdout and stderr to both the terminal and a UTF-8 session log file, the
    # same pattern main.py and ui.py use, so web-mode conversations are debuggable
    # later (exactly how we diagnosed the earlier failures). UTF-8 so Telugu logs.
    os.makedirs("logs", exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # buffering=1 (line-buffered) so each line lands on disk immediately. Without it,
    # a force-quit would lose the buffered tail of the log — the very situation where
    # we most want it.
    logfile = open(os.path.join("logs", f"vaani_web_{ts}.log"), "w", encoding="utf-8", buffering=1)
    sys.stdout = Tee(sys.stdout, logfile)
    sys.stderr = Tee(sys.stderr, logfile)
    atexit.register(logfile.close)


# ── Start ───────────────────────────────────────────────────────────────────

def main():
    _setup_logging()
    _free_port(PORT)  # clear any leftover instance before we try to bind
    threading.Thread(target=_media_listener_thread, daemon=True).start()
    server = QuietThreadingHTTPServer((HOST, PORT), Handler)
    ip = _lan_ip()
    print("Vaani web UI running.")
    print(f"  On this machine:          http://localhost:{PORT}")
    print(f"  From a phone (same wifi): http://{ip}:{PORT}" if ip
          else f"  From a phone (same wifi): http://<this-laptop-ip>:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Vaani web UI.")
    finally:
        # Always release the listening socket so the port is free next time, even
        # when we exit via Ctrl+C.
        server.server_close()


if __name__ == "__main__":
    main()
