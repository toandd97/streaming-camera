#!/usr/bin/env bash
# start_rtsp_streams.sh — Publish a video file as N RTSP streams via MediaMTX
#
# Usage:
#   bash scripts/start_rtsp_streams.sh <video_file> <num_streams>
#
# Examples:
#   bash scripts/start_rtsp_streams.sh videos/sample.mp4 4
#   bash scripts/start_rtsp_streams.sh videos/sample.mp4 4  (from inside Docker container)
#
# RTSP URLs published:
#   rtsp://localhost:8554/cam1 ... camN  (from host)
#   rtsp://mediamtx:8554/cam1  ... camN  (from inside Docker backend container)

set -e

VIDEO=${1:-videos/sample.mp4}
NUM=${2:-4}
RTSP_HOST=${3:-localhost}
RTSP_PORT=${4:-8554}

if [ ! -f "$VIDEO" ]; then
  echo "[ERROR] Video file not found: $VIDEO"
  echo "Usage: bash scripts/start_rtsp_streams.sh <video_file> <num_streams>"
  exit 1
fi

echo "Starting $NUM RTSP streams from: $VIDEO"
echo "RTSP server: rtsp://$RTSP_HOST:$RTSP_PORT"
echo ""

PID_FILE="/tmp/orbro_ffmpeg_pids"
> "$PID_FILE"

for i in $(seq 1 "$NUM"); do
  RTSP_URL="rtsp://$RTSP_HOST:$RTSP_PORT/cam$i"
  
  ffmpeg -re -stream_loop -1 \
    -i "$VIDEO" \
    -c:v libx264 \
    -preset ultrafast \
    -tune zerolatency \
    -b:v 500k \
    -an \
    -f rtsp \
    "$RTSP_URL" \
    -loglevel warning \
    &
  
  PID=$!
  echo "$PID" >> "$PID_FILE"
  echo "  [✓] Started cam$i → $RTSP_URL (PID: $PID)"
done

echo ""
echo "All $NUM streams started. PIDs saved to $PID_FILE"
echo "To stop: bash scripts/stop_rtsp_streams.sh"
