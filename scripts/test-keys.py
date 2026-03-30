#!/usr/bin/env python3
"""Quick test: does pynput detect any key presses?"""
from pynput import keyboard

def on_press(key):
    print(f"PRESSED: {key}")

def on_release(key):
    print(f"RELEASED: {key}")
    if key == keyboard.Key.esc:
        return False  # stop

print("Press any key (ESC to quit)...")
with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()
