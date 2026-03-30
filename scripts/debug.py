#!/usr/bin/env python3
"""Debug version — prints everything to terminal so we can see what's wrong."""
import subprocess
import tempfile
import os
from pynput import keyboard

tmp_wav = os.path.join(tempfile.gettempdir(), "ptt_recording.wav")
recording = False
rec_process = None

def start_recording():
    global recording, rec_process
    if recording:
        return
    recording = True
    if os.path.exists(tmp_wav):
        os.remove(tmp_wav)
    print(">>> STARTING RECORDING...")
    rec_process = subprocess.Popen(
        ["rec", "-q", tmp_wav, "rate", "16k", "channels", "1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    print(f">>> rec PID: {rec_process.pid}")

def stop_and_transcribe():
    global recording, rec_process
    if not recording:
        return
    recording = False
    print(">>> STOPPING RECORDING...")
    if rec_process:
        rec_process.terminate()
        rec_process.wait()
        stderr = rec_process.stderr.read().decode() if rec_process.stderr else ""
        if stderr:
            print(f">>> rec stderr: {stderr}")
        rec_process = None

    if not os.path.exists(tmp_wav):
        print(">>> ERROR: No wav file created!")
        return

    size = os.path.getsize(tmp_wav)
    print(f">>> WAV file: {tmp_wav} ({size} bytes)")

    if size < 1000:
        print(">>> ERROR: File too small, mic may not be working")
        return

    print(">>> TRANSCRIBING (mlx-whisper on GPU)...")
    result = subprocess.run(
        ["python3", "-c",
         f"import mlx_whisper; r = mlx_whisper.transcribe('{tmp_wav}', language='en', path_or_hf_repo='mlx-community/whisper-tiny'); print(r['text'])"],
        capture_output=True, text=True, timeout=60,
    )
    text = result.stdout.strip()
    if result.stderr:
        print(f">>> stderr (last 2 lines): {chr(10).join(result.stderr.strip().split(chr(10))[-2:])}")
    if text:
        print(f">>> RESULT: \"{text}\"")
        subprocess.run(["pbcopy"], input=text.encode())
        print(">>> Copied to clipboard!")
    else:
        print(">>> ERROR: No transcription produced")

def on_press(key):
    if key == keyboard.Key.cmd_r:
        start_recording()

def on_release(key):
    if key == keyboard.Key.cmd_r:
        stop_and_transcribe()
    if key == keyboard.Key.esc:
        print("Bye!")
        os._exit(0)

print("Hold RIGHT CMD to record, release to transcribe. ESC to quit.")
with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()
