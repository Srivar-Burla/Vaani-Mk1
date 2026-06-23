import asyncio
from winrt.windows.media import SystemMediaTransportControls
from winrt.windows.media.playback import MediaPlayer

def my_custom_action():
    """Your custom logic goes here."""
    print("🚀 SUCCESS: TWS Play/Pause interaction successfully detected!")

def on_button_pressed(sender, args):
    """Callback event triggered when Windows forwards the TWS media button command."""
    from winrt.windows.media import SystemMediaTransportControlsButton
    
    # Check if the pressed button is specifically Play or Pause
    if (args.button == SystemMediaTransportControlsButton.PLAY or 
        args.button == SystemMediaTransportControlsButton.PAUSE):
        my_custom_action()

async def main():
    # 1. Initialize a background media player instance to catch system focus
    player = MediaPlayer()
    player.command_manager.is_enabled = True # Allow system to map commands
    
    # 2. Get the System Media Transport Controls reference
    smtc = player.system_media_transport_controls
    smtc.is_enabled = True
    
    # 3. Inform Windows this script handles Play and Pause events
    smtc.is_play_enabled = True
    smtc.is_pause_enabled = True
    
    # 4. Bind our custom listener function to the button press event
    smtc.add_button_pressed(on_button_pressed)
    
    print("Listening for TWS earbud Play/Pause via WinRT... Press Ctrl+C to exit.")
    
    # Keep the async loop running indefinitely to listen for events
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nScript exited successfully.")
