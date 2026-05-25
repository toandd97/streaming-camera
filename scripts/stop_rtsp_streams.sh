#!/usr/bin/env bash
# stop_rtsp_streams.sh — Stop all FFmpeg RTSP simulation processes
#
# Usage:
#   bash scripts/stop_rtsp_streams.sh
#
# Use this to test stream disconnection and auto-reconnect behavior.

PID_FILE="/tmp/orbro_ffmpeg_pids"

if [ -f "$PID_FILE" ]; then
  echo "Stopping FFmpeg processes (from PID file)..."
  while IFS= read -r pid; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid"
      echo "  [✓] Stopped PID $pid"
    fi
  done < "$PID_FILE"
  rm -f "$PID_FILE"
else
  echo "No PID file found. Trying to kill all ffmpeg rtsp processes..."
  pkill -f "ffmpeg.*rtsp://" && echo "  [✓] Stopped all FFmpeg RTSP processes" || echo "  [!] No FFmpeg RTSP processes found"
fi

echo "Done. Cameras will enter DISCONNECTED → RECONNECTING state."
