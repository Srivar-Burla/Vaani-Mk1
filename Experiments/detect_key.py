from pynput import keyboard

# Run this script, tap your earbuds, and read what prints.
# It logs both key-press and key-release events for every key pynput sees.
# Press Ctrl+C to exit when done.

def on_press(key):
    print(f"PRESS:   {key!r}")

def on_release(key):
    print(f"RELEASE: {key!r}")

print("Listening for key events. Tap your earbuds now. Press Ctrl+C to stop.\n")

with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()
