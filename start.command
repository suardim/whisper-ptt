#!/bin/bash
cd "$(dirname "$0")"
nohup python3 push-to-talk.py &>/dev/null &
sleep 1
osascript -e 'tell application "Terminal" to close front window' &>/dev/null
