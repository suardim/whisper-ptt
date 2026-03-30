# whisper-ptt

Push-to-talk voice dictation for macOS. Hold a key, speak, release — your speech is transcribed and pasted wherever your cursor is.

Runs as a lightweight menu bar app with native SF Symbol icons.

## Features

- **Push-to-talk** — hold Right Command, speak, release to transcribe
- **Auto-paste** — transcription is copied to clipboard and typed into the active window
- **Menu bar app** — mic icon with recording/transcribing states
- **Auto-detects language** — English, Portuguese, and 90+ other languages
- **Smart context** — learns from your vocabulary file and recent transcriptions
- **Sound feedback** — beeps on start/stop recording
- **History log** — searchable log of all transcriptions with timestamps
- **Fast on Apple Silicon** — uses MLX Whisper for GPU-accelerated transcription

## Requirements

- macOS (Apple Silicon recommended)
- Python 3.10+
- Homebrew

## Install

```bash
# Install dependencies
brew install sox
pip3 install mlx-whisper pynput rumps

# Clone
git clone https://github.com/suardim/whisper-ptt.git
cd whisper-ptt

# Generate menu bar icons
python3 scripts/generate-icons.py

# Run
python3 push-to-talk.py
```

## Usage

```bash
# Run with defaults (Right Command key, small model)
python3 push-to-talk.py

# Use a different key
python3 push-to-talk.py --key option_r

# Use a smaller/faster model
python3 push-to-talk.py --model tiny

# Clipboard only, no auto-typing
python3 push-to-talk.py --no-type
```

### Available keys

`cmd_r`, `option_r`, `option_l`, `ctrl_r`, `f8`, `f18`, `f19`

### Available models

`tiny` (fastest), `base`, `small` (default, best balance), `medium`, `large` (most accurate)

## Menu bar options

Click the mic icon in the menu bar to:

- Toggle auto-type on/off
- Edit your vocabulary file (improves accuracy for names, jargon, etc.)
- View transcription history
- Open the app folder

## Auto-start on login

Double-click `start.command` or add it to **System Settings > General > Login Items**.

Or add an alias to your shell:

```bash
echo 'alias ptt="python3 /path/to/whisper-ptt/push-to-talk.py"' >> ~/.zshrc
```

## macOS Permissions

The app needs these permissions (System Settings > Privacy & Security):

- **Input Monitoring** — to detect the hotkey globally
- **Accessibility** — to type into other apps
- **Microphone** — to record audio

Add your terminal app (or Python binary) to each.

## Project structure

```
whisper-ptt/
  push-to-talk.py      # main app
  start.command         # double-click launcher
  vocabulary.txt        # custom words for better accuracy
  icons/                # SF Symbol menu bar icons
  scripts/
    generate-icons.py   # regenerate icons
    debug.py            # verbose debug version
    test-keys.py        # test keyboard detection
```

## License

MIT
