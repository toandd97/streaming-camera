#!/usr/bin/env bash
# register_demo_cameras.sh — Register 4 distinct demo-video RTSP cameras via API
#
# Usage:
#   bash scripts/register_demo_cameras.sh [base_url]
#
# Examples:
#   bash scripts/register_demo_cameras.sh                    # default http://localhost:8000
#   bash scripts/register_demo_cameras.sh http://localhost:8000

BASE_URL=${1:-http://localhost:8000}
API="$BASE_URL/api/v1"

declare -a NAMES=("Main Gate (Garden)" "Parking (Office)" "Warehouse (Door)" "Outdoor (Fire)")
declare -a PATHS=("demo/garden" "demo/office" "demo/door" "demo/fire")

# When backend runs in Docker: use mediamtx hostname
# When backend runs on host: use localhost
RTSP_HOST="mediamtx"

echo "Registering 4 distinct demo-video cameras to $API"
echo ""

for i in 0 1 2 3; do
  NAME="${NAMES[$i]}"
  PATH_SUFFIX="${PATHS[$i]}"
  RTSP_URL="rtsp://$RTSP_HOST:8554/$PATH_SUFFIX"

  echo "Registering: $NAME → $RTSP_URL"

  RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API/cameras" \
    -H "Content-Type: application/json" \
    -d "{
      \"name\": \"$NAME\",
      \"rtsp_url\": \"$RTSP_URL\",
      \"resolution\": \"640x360\",
      \"target_fps\": 10,
      \"display_fps\": 5,
      \"enabled\": true,
      \"description\": \"Demo camera $((i+1))\"
    }")

  HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
  BODY=$(echo "$RESPONSE" | head -n-1)

  if [ "$HTTP_CODE" = "201" ]; then
    ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id','?'))" 2>/dev/null || echo "?")
    echo "  [✓] Created (ID: $ID)"
  else
    echo "  [!] Failed (HTTP $HTTP_CODE): $BODY"
  fi
  echo ""
done

echo "Done! Run: curl $API/cameras | python3 -m json.tool"
