import os
import sys
import datetime
import atexit
import asyncio
import threading
import queue
import tkinter as tk
from tkinter import scrolledtext
from dotenv import load_dotenv

load_dotenv()

# GUI mode: redirect all print() and tracebacks to the log file only — no terminal shown.
# The Tee in main.py only activates when main.py is run directly (__main__), so
# importing from main here does not redirect stdout again.
os.makedirs("logs", exist_ok=True)
_session_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
_log_file = open(os.path.join("logs", f"vaani_{_session_ts}.log"), "w", encoding="utf-8")
sys.stdout = _log_file
sys.stderr = _log_file
atexit.register(_log_file.close)

# Import after redirecting stdout so any init-time output also lands in the log.
from main import run_conversation, create_chat_session
from winrt.windows.media import SystemMediaTransportControlsButton
from winrt.windows.media.playback import MediaPlayer

# ── Queue & session state ──────────────────────────────────────────────────────
# Background thread puts state/transcript dicts here; the main thread drains it
# every 100ms via root.after(). Never call Tkinter methods from the background thread.

ui_queue = queue.Queue()
_session_active = threading.Event()  # set while a session is running; cleared on exit

# ── Tkinter window ─────────────────────────────────────────────────────────────
root = tk.Tk()
root.title("Vaani")
root.resizable(False, False)

STATE_COLORS = {
    "Idle":      "#888888",
    "Listening": "#2ecc71",
    "Thinking":  "#e67e22",
    "Speaking":  "#3498db",
}

# State indicator row
_state_row = tk.Frame(root, padx=12, pady=8)
_state_row.pack(fill=tk.X)
tk.Label(_state_row, text="State:", font=("Helvetica", 11)).pack(side=tk.LEFT)
state_label = tk.Label(_state_row, text="Idle", font=("Helvetica", 11, "bold"),
                       fg=STATE_COLORS["Idle"])
state_label.pack(side=tk.LEFT, padx=6)

# Transcript pane (read-only; written only via _append_transcript on the main thread)
transcript = scrolledtext.ScrolledText(
    root, state=tk.DISABLED, wrap=tk.WORD,
    width=62, height=22, font=("Helvetica", 10), padx=8, pady=8
)
transcript.pack(padx=12, pady=(0, 8))

# Colour tags for different transcript line types
transcript.tag_config("user",             foreground="#2c3e50")
transcript.tag_config("user_translated",  foreground="#7f8c8d",
                       font=("Helvetica", 10, "italic"))
transcript.tag_config("vaani",            foreground="#1a5276",
                       font=("Helvetica", 10, "bold"))
transcript.tag_config("vaani_translated", foreground="#7f8c8d",
                       font=("Helvetica", 10, "italic"))

# Start button — disabled while a session is active
start_btn = tk.Button(
    root, text="Start Listening", font=("Helvetica", 11),
    bg="#2ecc71", fg="white", padx=16, pady=6,
    command=lambda: trigger_listen()
)
start_btn.pack(pady=(0, 12))


# ── Transcript helper ──────────────────────────────────────────────────────────

def _append_transcript(text, tag):
    # Always called on the main thread (from poll_queue). Appends one line to the pane.
    transcript.config(state=tk.NORMAL)
    transcript.insert(tk.END, text + "\n", tag)
    transcript.config(state=tk.DISABLED)
    transcript.see(tk.END)


# ── Queue poller ───────────────────────────────────────────────────────────────

def poll_queue():
    # Drains ui_queue on the Tkinter main thread every 100ms.
    # Handles two message types:
    #   {"type": "state", "value": "Listening"|"Thinking"|"Speaking"|"Idle"}
    #   {"type": "transcript", "speaker": "User"|"Vaani", "text": ...,
    #    "translated": ...|None, "lang": ...}
    #   {"type": "trigger"} from the WinRT earbud listener
    try:
        while True:
            msg = ui_queue.get_nowait()

            if msg["type"] == "state":
                val = msg["value"]
                state_label.config(text=val, fg=STATE_COLORS.get(val, "#888888"))
                if val == "Idle":
                    # Session ended — re-enable the Start button
                    start_btn.config(state=tk.NORMAL)

            elif msg["type"] == "trigger":
                # The WinRT callback runs on its own thread. The queue brings the
                # gesture back to Tkinter's main thread, then uses the same entry
                # point as the Start button. Active sessions remain a safe no-op.
                trigger_listen()

            elif msg["type"] == "transcript":
                if msg["speaker"] == "User":
                    _append_transcript(f"You: {msg['text']}", "user")
                    if msg.get("translated"):
                        # Non-English turn: show the English translation Gemini receives
                        _append_transcript(f"  (English): {msg['translated']}", "user_translated")

                elif msg["speaker"] == "Vaani":
                    if msg.get("translated"):
                        # Non-English turn: show Gemini's English reply, then what was spoken
                        _append_transcript(f"Vaani (English): {msg['text']}", "vaani_translated")
                        _append_transcript(f"Vaani: {msg['translated']}", "vaani")
                    else:
                        _append_transcript(f"Vaani: {msg['text']}", "vaani")

    except queue.Empty:
        pass

    root.after(100, poll_queue)


# ── Session management ─────────────────────────────────────────────────────────

def _session_worker():
    # Runs on a daemon background thread. try/finally guarantees the session guard
    # clears and the UI returns to Idle even if run_conversation raises unexpectedly.
    cs = create_chat_session()
    try:
        run_conversation(cs, ui_queue)
    finally:
        _session_active.clear()
        ui_queue.put({"type": "state", "value": "Idle"})


def trigger_listen():
    # Shared entry point for the Start button and the TWS gesture.
    # No-op if a session is already running (handles accidental double-tap).
    if _session_active.is_set():
        return
    _session_active.set()
    start_btn.config(state=tk.DISABLED)
    transcript.config(state=tk.NORMAL)
    transcript.delete("1.0", tk.END)
    transcript.config(state=tk.DISABLED)
    threading.Thread(target=_session_worker, daemon=True).start()


# ── TWS / wired earbud gesture listener (WinRT SMTC via MediaPlayer) ───────────
# Bluetooth earbuds send Play/Pause through AVRCP into Windows media controls.
# MediaPlayer gives this Win32 Python app a valid SMTC session without requiring
# a UWP view. While Vaani is open, that session may receive the gesture instead
# of Spotify or YouTube Music, which is the accepted Mk1 hands-free tradeoff.

async def _listen_for_media_buttons():
    # MediaPlayer creates the Windows media session used by Bluetooth AVRCP.
    # This is the same route proven by TWS_inter_ID.py, and it bypasses the
    # keyboard, shell-hook, and raw-input paths that failed with these earbuds.
    player = MediaPlayer()
    player.command_manager.is_enabled = True

    # Tell Windows that Vaani accepts Play and Pause while the GUI is open.
    # Windows can then forward a single earbud tap to this SMTC session.
    smtc = player.system_media_transport_controls
    smtc.is_enabled = True
    smtc.is_play_enabled = True
    smtc.is_pause_enabled = True

    def _on_button_pressed(sender, args):
        # Both PLAY and PAUSE mean "invoke Vaani" for Mk1. Queue the trigger so
        # the Tkinter main thread starts the normal STT-to-TTS pipeline safely.
        if args.button in (
            SystemMediaTransportControlsButton.PLAY,
            SystemMediaTransportControlsButton.PAUSE,
        ):
            ui_queue.put({"type": "trigger"})

    # Keep the player, SMTC object, and callback alive for the entire coroutine.
    # If MediaPlayer is collected, Windows removes Vaani's media session.
    smtc.add_button_pressed(_on_button_pressed)
    print("TWS Play/Pause listener is ready.")

    while True:
        await asyncio.sleep(1)


def _media_listener_thread():
    # WinRT callbacks need a persistent asyncio loop. A daemon thread keeps that
    # loop separate while Tkinter owns the main thread and conversation audio
    # continues on its existing worker thread.
    try:
        asyncio.run(_listen_for_media_buttons())
    except Exception as error:
        # GUI stderr is redirected to the session log. The Start button remains
        # available even if SMTC initialization fails on a particular machine.
        print(f"TWS listener failed: {type(error).__name__}: {error}")


threading.Thread(target=_media_listener_thread, daemon=True).start()

# ── Start ──────────────────────────────────────────────────────────────────────
root.after(100, poll_queue)
root.mainloop()
