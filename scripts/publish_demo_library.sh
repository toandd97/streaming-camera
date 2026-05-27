#!/usr/bin/env bash
# Publish each bundled H.264 video as its own RTSP camera source.
#
# These publishers are deliberately separate from the camera CRUD API. The API
# registers RTSP sources; this service supplies reproducible local RTSP inputs.

set -euo pipefail

SOURCE_VIDEO_DIR="${VIDEO_DIR:-/app/resources/videos}"
DEMO_CACHE_DIR="${DEMO_CACHE_DIR:-}"
RTSP_HOST="${RTSP_HOST:-mediamtx}"
RTSP_PORT="${RTSP_PORT:-8554}"
PATH_PREFIX="${PATH_PREFIX:-demo}"
MAX_STREAMS="${MAX_STREAMS:-80}"

if [ ! -d "$SOURCE_VIDEO_DIR" ]; then
  echo "[ERROR] Demo video directory does not exist: $SOURCE_VIDEO_DIR" >&2
  exit 1
fi

mapfile -d '' SOURCE_VIDEOS < <(find "$SOURCE_VIDEO_DIR" -maxdepth 1 -type f -name '*.mp4' -print0 | sort -z)
if [ "${#SOURCE_VIDEOS[@]}" -eq 0 ]; then
  echo "[ERROR] No .mp4 demo videos found in $SOURCE_VIDEO_DIR" >&2
  exit 1
fi

if [ -n "$DEMO_CACHE_DIR" ]; then
  mkdir -p "$DEMO_CACHE_DIR"
  for source in "${SOURCE_VIDEOS[@]}"; do
    output="$DEMO_CACHE_DIR/$(basename "$source")"
    if [ ! -f "$output" ] || [ "$source" -nt "$output" ]; then
      tmp="$output.tmp"
      echo "[INFO] Preparing low-bandwidth demo asset: $(basename "$source")"
      ffmpeg -nostdin -hide_banner -loglevel error -y -i "$source" \
        -map 0:v:0 -vf "scale=-2:360,fps=10" -an \
        -c:v libx264 -preset veryfast -profile:v baseline \
        -b:v 350k -maxrate 450k -bufsize 900k \
        -g 20 -keyint_min 20 -sc_threshold 0 \
        -movflags +faststart -f mp4 "$tmp"
      mv "$tmp" "$output"
    fi
  done
  VIDEO_DIR="$DEMO_CACHE_DIR"
else
  VIDEO_DIR="$SOURCE_VIDEO_DIR"
fi

mapfile -d '' VIDEOS < <(find "$VIDEO_DIR" -maxdepth 1 -type f -name '*.mp4' -print0 | sort -z)
if [ "${#VIDEOS[@]}" -eq 0 ]; then
  echo "[ERROR] No .mp4 demo videos found in $VIDEO_DIR" >&2
  exit 1
fi

PIDS=()
cleanup() {
  if [ "${#PIDS[@]}" -gt 0 ]; then
    kill "${PIDS[@]}" 2>/dev/null || true
    wait "${PIDS[@]}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

count=0
for video in "${VIDEOS[@]}"; do
  if [ "$count" -ge "$MAX_STREAMS" ]; then
    break
  fi

  stem="$(basename "${video%.mp4}")"
  path="${PATH_PREFIX}/${stem}"
  url="rtsp://${RTSP_HOST}:${RTSP_PORT}/${path}"

  # Prepared assets are H.264 at dashboard-friendly bitrate. Stream-copy avoids
  # keeping one active encoder per demo camera while streams are running.
  ffmpeg -nostdin -hide_banner -loglevel warning \
    -re -stream_loop -1 -i "$video" -map 0:v:0 -an \
    -c:v copy -f rtsp -rtsp_transport tcp "$url" &
  PIDS+=("$!")
  count=$((count + 1))
  echo "[OK] $stem -> $url"
done

echo "[INFO] Published $count demo RTSP sources from $VIDEO_DIR"
echo "[INFO] Register cameras with rtsp://${RTSP_HOST}:${RTSP_PORT}/${PATH_PREFIX}/<video-name>"

# Treat any unexpected publisher exit as a service failure; Docker will restart
# the service and restore the complete set of demo streams.
set +e
wait -n "${PIDS[@]}"
status=$?
echo "[ERROR] A demo publisher exited (status=$status); restarting all sources" >&2
exit 1
