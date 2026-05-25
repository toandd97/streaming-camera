#!/usr/bin/env bash
# benchmark_streams.sh — Monitor system performance while N streams are running
#
# Usage:
#   bash scripts/benchmark_streams.sh [duration_seconds]

DURATION=${1:-30}
API=${2:-http://localhost:8000/api/v1}

echo "=== ORBRO B1 Stream Benchmark ==="
echo "Duration: ${DURATION}s | API: $API"
echo ""
echo "Time        | CPU%  | RAM%  | Streams | Cam1 FPS | Cam2 FPS | Cam3 FPS | Cam4 FPS"
echo "------------|-------|-------|---------|----------|----------|----------|----------"

END_TIME=$(($(date +%s) + DURATION))

while [ "$(date +%s)" -lt "$END_TIME" ]; do
  TIMESTAMP=$(date '+%H:%M:%S')
  
  METRICS=$(curl -sf "$API/system/metrics" 2>/dev/null)
  CAMERAS=$(curl -sf "$API/cameras" 2>/dev/null)

  if [ -n "$METRICS" ] && [ -n "$CAMERAS" ]; then
    CPU=$(echo "$METRICS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['cpu_percent'])" 2>/dev/null || echo "?")
    RAM=$(echo "$METRICS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['memory_percent'])" 2>/dev/null || echo "?")
    STREAMS=$(echo "$METRICS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['active_streams'])" 2>/dev/null || echo "?")
    
    FPS=$(echo "$CAMERAS" | python3 -c "
import sys, json
cams = json.load(sys.stdin)
fps_vals = [str(round(c.get('actual_fps', 0), 1)) for c in cams[:4]]
while len(fps_vals) < 4:
    fps_vals.append('---')
print(' | '.join(fps_vals))
" 2>/dev/null || echo "? | ? | ? | ?")

    printf "%-12s| %-6s| %-6s| %-8s| %s\n" "$TIMESTAMP" "$CPU" "$RAM" "$STREAMS" "$FPS"
  else
    printf "%-12s| API unreachable\n" "$TIMESTAMP"
  fi

  sleep 2
done

echo ""
echo "Benchmark complete."
