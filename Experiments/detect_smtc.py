"""
SMTC / WinRT detection diagnostic for Vaani TWS gesture invocation.

Tests two approaches:
  Path A — Register as SMTC media app and receive ButtonPressed events directly.
           This is the goal: if it works, every earbud tap is caught here
           before it reaches any other app.
  Path B — Monitor the active media session via GlobalSystemMediaTransportControls.
           Fallback: fires on playback state changes (earbud tap OR manual pause).

Install:  pip install winsdk
Run:      python detect_smtc.py
Then tap your earbuds and look for [SMTC] or [GSMTC] lines.
Ctrl+C to stop.

What to report back:
  - Did you see "[OK] Path A" or "[FAIL] Path A"?
  - If Path A OK: did tapping your earbuds print a [SMTC] BUTTON PRESSED line?
  - If Path A failed: did tapping earbuds print a [GSMTC] Playback status line?
"""

import asyncio
import sys


async def _main():
    smtc_ok = False

    # ── Path A: direct SMTC registration (ButtonPressed events) ──────────────
    # get_for_current_view() is the UWP path.  On Windows 11 it sometimes works
    # from an unpackaged Win32 process too — worth testing.
    try:
        from winrt.windows.media import (
            SystemMediaTransportControls,
            SystemMediaTransportControlsButton,
            MediaPlaybackStatus,
        )

        smtc = SystemMediaTransportControls.get_for_current_view()
        smtc.is_enabled       = True
        smtc.is_play_enabled  = True
        smtc.is_pause_enabled = True
        # Set PLAYING so Windows treats this as the "current" session and routes
        # media key presses here instead of Spotify/YouTube Music.
        smtc.playback_status  = MediaPlaybackStatus.PLAYING

        _BTN_NAMES = {
            SystemMediaTransportControlsButton.PLAY_PAUSE: "PLAY_PAUSE",
            SystemMediaTransportControlsButton.PLAY:       "PLAY",
            SystemMediaTransportControlsButton.PAUSE:      "PAUSE",
            SystemMediaTransportControlsButton.STOP:       "STOP",
            SystemMediaTransportControlsButton.NEXT:       "NEXT",
            SystemMediaTransportControlsButton.PREVIOUS:   "PREVIOUS",
        }

        def _on_button(sender, args):
            name = _BTN_NAMES.get(args.button, str(args.button))
            print(f"[SMTC] BUTTON PRESSED: {name}", flush=True)
            if args.button == SystemMediaTransportControlsButton.PLAY_PAUSE:
                print("       *** PLAY_PAUSE — this is your earbud tap! ***", flush=True)

        smtc.button_pressed += _on_button
        smtc_ok = True
        print("[OK] Path A: SMTC registered as media app — earbud taps should appear as [SMTC] lines.")

    except Exception as exc:
        print(f"[FAIL] Path A: SMTC registration failed — {exc}")
        print("        (Common on unpackaged Win32 Python; will try Path B.)")

    # ── Path B: GSMTC playback monitoring (state-change proxy) ───────────────
    # Watches the currently active media app's playback status.
    # Cannot distinguish earbud taps from manual pauses, but useful as a signal.
    try:
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as _GsmtcMgr,
        )

        mgr     = await _GsmtcMgr.request_async()
        session = mgr.get_current_session()

        if session is None:
            print("[INFO] Path B: no active media session found.  Open Spotify or YouTube Music first.")
        else:
            # MediaPlaybackStatus enum values (integer)
            _STATUS = {0: "Closed", 1: "Changing", 2: "Stopped", 3: "Playing", 4: "Paused"}

            def _on_playback(sender, args):
                info   = sender.get_playback_info()
                status = info.playback_status
                label  = _STATUS.get(int(status), str(status))
                print(f"[GSMTC] Playback status → {label}", flush=True)

            session.playback_info_changed += _on_playback
            print("[OK] Path B: GSMTC monitoring active — playback changes logged as [GSMTC] lines.")

    except Exception as exc:
        print(f"[FAIL] Path B: GSMTC monitoring failed — {exc}")

    if not smtc_ok:
        print()
        print("Path A failed.  If Path B shows [GSMTC] lines when you tap,")
        print("we have a usable (proxy) signal and can discuss next steps.")

    print("\nTap your earbuds now.  Ctrl+C to stop.\n")

    try:
        await asyncio.sleep(600)   # keep running up to 10 min
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        print("\nStopped.")
