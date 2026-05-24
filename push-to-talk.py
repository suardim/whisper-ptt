#!/usr/bin/env python3
"""
Push-to-Talk Whisper Dictation — macOS Menu Bar App
Hold Right ⌘ to record. Release to transcribe.
Result is copied to clipboard and typed into active window.

Usage: python3 push-to-talk.py [--model small] [--key cmd_r] [--no-type]

Requires: mlx-whisper, sox, pynput, rumps
"""

import argparse
import subprocess
import tempfile
import threading
import os
import re
import time
import datetime
import rumps
import objc
from AppKit import NSImage, NSImageSymbolConfiguration, NSStatusBar, NSMakeSize
from PyObjCTools import AppHelper
from pynput import keyboard

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(SCRIPT_DIR, "history.txt")
VOCAB_FILE = os.path.join(SCRIPT_DIR, "vocabulary.txt")
def sf_symbol(name, size=13):
    """Create an NSImage from an SF Symbol, sized for the menu bar."""
    config = NSImageSymbolConfiguration.configurationWithPointSize_weight_(size, 0)
    img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
    if img:
        img = img.imageWithSymbolConfiguration_(config)
        img.setTemplate_(True)
        img.setSize_(NSMakeSize(size, size))
    return img
tmp_wav = os.path.join(tempfile.gettempdir(), "ptt_recording.wav")

# Model repo mapping
MODEL_REPOS = {
    "tiny": "mlx-community/whisper-tiny",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large": "mlx-community/whisper-large-v3-turbo",
}

# Whisper hallucination phrases to strip
HALLUCINATIONS = [
    "thank you.", "thanks for watching.", "thank you for watching.",
    "subscribe.", "like and subscribe.", "so.", "you.",
    "the end.", "bye.", "goodbye.",
]


def collapse_repetitions(text, run_limit=4):
    """Drop runs of the same word repeated run_limit+ times in a row.

    Whisper hallucinates degenerate output like "de de de de ..." (often when
    the audio is silent/truncated). Such a run is removed entirely while any
    surrounding real speech is preserved. Legitimate short repeats (e.g.
    "no no no") are kept.
    """
    words = text.split()
    out, i, n = [], 0, len(words)
    while i < n:
        key = words[i].lower().strip(".,!?;:¿¡\"'()[]…")
        j = i
        while j < n and words[j].lower().strip(".,!?;:¿¡\"'()[]…") == key:
            j += 1
        # Drop the run only if it's a real word repeated past the limit.
        if not (key and (j - i) >= run_limit):
            out.extend(words[i:j])
        i = j
    return " ".join(out)


def clean_text(text):
    """Remove Whisper hallucinations and clean up output."""
    text = text.strip()
    lower = text.lower().strip()
    if lower in HALLUCINATIONS:
        return ""
    for phrase in HALLUCINATIONS:
        if lower.endswith(phrase):
            text = text[:len(text) - len(phrase)].strip()
    text = collapse_repetitions(text)
    text = re.sub(r' +', ' ', text)
    return text.strip()


def beep(sound="Tink"):
    """Play a macOS system sound."""
    subprocess.Popen(
        ["afplay", f"/System/Library/Sounds/{sound}.aiff"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def load_vocabulary():
    """Load vocabulary words from file (skip comments and blanks)."""
    if not os.path.exists(VOCAB_FILE):
        return ""
    words = []
    with open(VOCAB_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                words.append(line)
    return ", ".join(words)


def get_recent_history(n=5):
    """Get last N *clean* transcriptions as context.

    Repetition hallucinations are stripped and degenerate/empty entries are
    skipped so they can never feed back into the Whisper prompt (which would
    prime even more repetition — a self-poisoning loop).
    """
    if not os.path.exists(HISTORY_FILE):
        return ""
    with open(HISTORY_FILE) as f:
        lines = f.readlines()
    texts = []
    for line in lines:
        match = re.match(r'\[.*?\] (.+)', line.strip())
        if not match:
            continue
        cleaned = collapse_repetitions(match.group(1)).strip()
        # Skip anything that collapsed to nothing or has no real content.
        if len(cleaned.split()) < 2:
            continue
        if not texts or texts[-1] != cleaned:  # drop consecutive duplicates
            texts.append(cleaned)
    return " ".join(texts[-n:])


def build_initial_prompt():
    """Build Whisper initial_prompt from vocabulary + recent history."""
    parts = []
    vocab = load_vocabulary()
    if vocab:
        parts.append(vocab)
    history = get_recent_history(5)
    if history:
        parts.append(history)
    prompt = ". ".join(parts)
    # Whisper initial_prompt has a ~224 token limit, keep it reasonable
    return prompt[:500] if prompt else ""


class PushToTalkApp(rumps.App):
    def __init__(self, model="small", hotkey=keyboard.Key.cmd_r, auto_type=True):
        super().__init__("", quit_button=None)
        # Set SF Symbol icon directly on the NSStatusItem
        self._set_sf_icon("mic")
        self.model = model
        self.model_repo = MODEL_REPOS.get(model, MODEL_REPOS["small"])
        self.hotkey = hotkey
        self.auto_type = auto_type
        self.recording = False
        self.rec_process = None
        self.transcribing = False

        # Menu items
        self.status_item = rumps.MenuItem("Ready — Hold Right ⌘ to record")
        self.status_item.set_callback(None)
        self.last_text_item = rumps.MenuItem("Last: (nothing yet)")
        self.last_text_item.set_callback(None)
        self.type_toggle = rumps.MenuItem(
            f"Auto-Type: {'On' if self.auto_type else 'Off'}",
            callback=self.toggle_type,
        )
        self.model_item = rumps.MenuItem(f"Model: {self.model}")
        self.model_item.set_callback(None)
        self.edit_vocab_item = rumps.MenuItem(
            "Edit Vocabulary...",
            callback=self.edit_vocabulary,
        )
        self.view_history_item = rumps.MenuItem(
            "View History...",
            callback=self.view_history,
        )
        self.open_folder_item = rumps.MenuItem(
            "Open App Folder...",
            callback=self.open_folder,
        )
        self.quit_item = rumps.MenuItem("Quit", callback=self.quit_app)

        self.menu = [
            self.status_item,
            self.last_text_item,
            None,
            self.type_toggle,
            self.model_item,
            None,
            self.edit_vocab_item,
            self.view_history_item,
            self.open_folder_item,
            None,
            self.quit_item,
        ]

        # Start keyboard listener
        self.listener = keyboard.Listener(
            on_press=self.on_press, on_release=self.on_release
        )
        self.listener.daemon = True
        self.listener.start()

    def on_press(self, key):
        if key == self.hotkey and not self.recording and not self.transcribing:
            self.start_recording()

    def on_release(self, key):
        if key == self.hotkey and self.recording:
            self.stop_and_transcribe()

    def start_recording(self):
        self.recording = True
        if os.path.exists(tmp_wav):
            os.remove(tmp_wav)
        self.rec_process = subprocess.Popen(
            ["/opt/homebrew/bin/rec", "-q", tmp_wav, "rate", "16k", "channels", "1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        beep("Tink")
        self._ui(icon="mic.fill", status="Recording... release to stop")

    def stop_and_transcribe(self):
        self.recording = False
        self.transcribing = True
        if self.rec_process:
            self.rec_process.terminate()
            self.rec_process.wait()
            self.rec_process = None
        beep("Pop")
        self._ui(icon="ellipsis.circle", status="Transcribing...")
        threading.Thread(target=self.transcribe, daemon=True).start()

    def transcribe(self):
        if not os.path.exists(tmp_wav):
            self.finish("No audio recorded")
            return
        try:
            prompt = build_initial_prompt()
            # Escape single quotes for the inline python command
            safe_prompt = prompt.replace("'", "\\'")

            # condition_on_previous_text=False stops Whisper from looping on
            # its own output within a clip (another repetition source).
            if safe_prompt:
                whisper_cmd = f"import mlx_whisper; r = mlx_whisper.transcribe('{tmp_wav}', initial_prompt='{safe_prompt}', condition_on_previous_text=False, path_or_hf_repo='{self.model_repo}'); print(r['text'])"
            else:
                whisper_cmd = f"import mlx_whisper; r = mlx_whisper.transcribe('{tmp_wav}', condition_on_previous_text=False, path_or_hf_repo='{self.model_repo}'); print(r['text'])"

            result = subprocess.run(
                ["/Users/user/.pyenv/versions/3.11.9/bin/python3", "-c", whisper_cmd],
                capture_output=True, text=True, timeout=60,
            )
            text = clean_text(result.stdout)

            if not text:
                self.finish("No speech detected")
                return

            # Copy to clipboard
            subprocess.run(["pbcopy"], input=text.encode(), check=True)

            # Auto-type (Quartz CGEvents are thread-safe; OK off the main thread)
            if self.auto_type:
                self.type_text(text)

            # Save to history
            self.save_history(text)

            # All AppKit UI updates must happen on the main thread.
            AppHelper.callAfter(self._on_transcribed, text)

        except subprocess.TimeoutExpired:
            self.finish("Transcription timed out")
        except Exception as e:
            self.finish(f"Error: {e}")

    def _on_transcribed(self, text):
        """Main-thread UI updates after a successful transcription."""
        rumps.notification(
            "Transcribed",
            f"{'Typed + ' if self.auto_type else ''}Copied to clipboard",
            text,
        )
        self.last_text_item.title = (
            f"Last: {text[:60]}{'...' if len(text) > 60 else ''}"
        )
        self.finish("Ready — Hold Right ⌘ to record")

    def type_text(self, text):
        """Simulate Cmd+V using Quartz CGEvents (no osascript needed)."""
        time.sleep(0.2)
        try:
            from Quartz import (
                CGEventCreateKeyboardEvent, CGEventSetFlags,
                CGEventPost, kCGHIDEventTap, kCGEventFlagMaskCommand,
            )
            # Key code 9 = 'v'
            cmd_down = CGEventCreateKeyboardEvent(None, 9, True)
            cmd_up = CGEventCreateKeyboardEvent(None, 9, False)
            CGEventSetFlags(cmd_down, kCGEventFlagMaskCommand)
            CGEventSetFlags(cmd_up, kCGEventFlagMaskCommand)
            CGEventPost(kCGHIDEventTap, cmd_down)
            CGEventPost(kCGHIDEventTap, cmd_up)
        except Exception:
            # Fallback to osascript
            subprocess.run(
                ["/usr/bin/osascript", "-e",
                 'tell application "System Events" to keystroke "v" using command down'],
                capture_output=True, timeout=5,
            )

    def save_history(self, text):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(HISTORY_FILE, "a") as f:
            f.write(f"[{timestamp}] {text}\n")

    def finish(self, status):
        self.transcribing = False
        self._ui(icon="mic", status=status)

    def _ui(self, icon=None, status=None):
        """Schedule a UI update on the main thread.

        AppKit objects (the status item, its button/image) may only be touched
        from the main thread. on_press/on_release run on the pynput listener
        thread and transcribe() runs on a worker thread, so every UI mutation
        is marshalled here via the main run loop.
        """
        AppHelper.callAfter(self._apply_ui, icon, status)

    def _apply_ui(self, icon, status):
        if icon is not None:
            self._set_sf_icon(icon)
        if status is not None:
            self.status_item.title = status

    def _set_sf_icon(self, symbol_name):
        """Set menu bar icon to an SF Symbol."""
        img = sf_symbol(symbol_name)
        if img:
            try:
                self._nsapp.nsstatusitem.button().setImage_(img)
            except Exception:
                # App not fully initialized yet, use title fallback
                self.title = symbol_name

    def toggle_type(self, sender):
        self.auto_type = not self.auto_type
        sender.title = f"Auto-Type: {'On' if self.auto_type else 'Off'}"

    def edit_vocabulary(self, _):
        """Open vocabulary file in default text editor."""
        subprocess.Popen(["open", "-e", VOCAB_FILE])

    def view_history(self, _):
        """Open history file in default text editor."""
        # Create if doesn't exist
        if not os.path.exists(HISTORY_FILE):
            open(HISTORY_FILE, "w").close()
        subprocess.Popen(["open", "-e", HISTORY_FILE])

    def open_folder(self, _):
        """Open the app folder in Finder."""
        subprocess.Popen(["open", SCRIPT_DIR])

    def quit_app(self, _):
        rumps.quit_application()


def main():
    parser = argparse.ArgumentParser(description="Push-to-Talk Whisper Dictation")
    parser.add_argument("--model", default="small",
                        help="Whisper model: tiny, base, small, medium, large")
    parser.add_argument("--key", default="cmd_r",
                        help="Hotkey: cmd_r, f8, option_r, option_l, ctrl_r")
    parser.add_argument("--no-type", action="store_true",
                        help="Only copy to clipboard, don't auto-type")
    args = parser.parse_args()

    key_map = {
        "option_r": keyboard.Key.alt_r,
        "option_l": keyboard.Key.alt_l,
        "ctrl_r": keyboard.Key.ctrl_r,
        "cmd_r": keyboard.Key.cmd_r,
        "f8": keyboard.Key.f8,
        "f18": keyboard.Key.f18,
        "f19": keyboard.Key.f19,
    }
    hotkey = key_map.get(args.key, keyboard.Key.cmd_r)

    app = PushToTalkApp(
        model=args.model,
        hotkey=hotkey,
        auto_type=not args.no_type,
    )
    app.run()


if __name__ == "__main__":
    main()
