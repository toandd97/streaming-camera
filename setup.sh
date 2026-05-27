#!/usr/bin/env bash
# =============================================================================
# ORBRO B1 - Camera Monitoring System: One-Command Setup
# =============================================================================
# Usage: bash setup.sh
# Requirements: Docker, Docker Compose, curl
# This script will:
#   1. Create .env from .env.example if not exists
#   2. Download sample video if not exists
#   3. Build and start all Docker services
#   4. Wait for backend to be ready
#   5. Start the bundled-video RTSP publisher service
#   6. Register 4 distinct demo cameras via API
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()    { echo -e "${BLUE}[INFO]${NC}  $1"; }
log_ok()      { echo -e "${GREEN}[OK]${NC}    $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
echo "============================================="
echo "  ORBRO B1 - Camera Monitoring System Setup  "
echo "============================================="
echo ""

# --------------------------------------------------
# Step 1: Prepare .env
# --------------------------------------------------
log_info "Step 1: Preparing environment config..."
bash scripts/init_env.sh
log_ok "Environment config prepared"

# --------------------------------------------------
# Step 2: Check for video file
# --------------------------------------------------
log_info "Step 2: Checking for video file..."

# Use existing resources/videos folder if available
if [ -d resources/videos ] && [ "$(ls -A resources/videos/*.mp4 2>/dev/null)" ]; then
    VIDEO_FILE=$(ls resources/videos/*.mp4 | head -1)
    log_ok "Using existing video: $VIDEO_FILE"
else
    mkdir -p resources/videos resources/images resources/excel
    log_info "Downloading sample video (Big Buck Bunny ~1MB)..."
    curl -L --progress-bar \
        "https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4" \
        -o resources/videos/sample.mp4 \
        || {
            log_warn "Primary download failed. Trying backup source..."
            curl -L --progress-bar \
                "https://www.w3schools.com/html/mov_bbb.mp4" \
                -o resources/videos/sample.mp4
        }
    VIDEO_FILE="resources/videos/sample.mp4"
    log_ok "Sample video downloaded: $VIDEO_FILE"
fi

# --------------------------------------------------
# Step 3: Build and start Docker services
# --------------------------------------------------
log_info "Step 3: Building and starting Docker services..."
docker compose down --remove-orphans 2>/dev/null || true
docker compose up -d --build
log_ok "Docker services started"

# --------------------------------------------------
# Step 4: Wait for backend to be ready
# --------------------------------------------------
log_info "Step 4: Waiting for backend to be ready (up to 120 seconds)..."
TIMEOUT=60
ELAPSED=0
until curl -sf http://localhost:8000/api/v1/cameras > /dev/null 2>&1; do
    if [ $ELAPSED -ge $TIMEOUT ]; then
        log_error "Backend did not start within ${TIMEOUT}s. Check: docker compose logs streaming-camera-app"
        exit 1
    fi
    echo -n "."
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done
echo ""
log_ok "Backend is ready"

# --------------------------------------------------
# Step 5: Start RTSP simulation streams
# --------------------------------------------------
log_info "Step 5: Starting local demo RTSP source library..."
docker compose --profile demo up -d demo-publisher
log_ok "RTSP demo sources started (one RTSP path per bundled video)"
sleep 3

# --------------------------------------------------
# Step 6: Register demo cameras
# --------------------------------------------------
log_info "Step 6: Registering 4 cameras with distinct demo videos..."
bash scripts/register_demo_cameras.sh http://localhost:8000
log_ok "Demo cameras registered"

# --------------------------------------------------
# Done!
# --------------------------------------------------
echo ""
echo "============================================="
echo -e "${GREEN}  Setup Complete!${NC}"
echo "============================================="
echo ""
echo "  Dashboard:  http://localhost:8000"
echo "  API Docs:   http://localhost:8000/docs"
echo "  MongoDB:    mongodb://localhost:27017"
echo ""
echo "  Useful commands:"
echo "    Demo sources:   docker compose --profile demo up -d demo-publisher"
echo "    Stop sources:   docker compose --profile demo stop demo-publisher"
echo "    View logs:      docker compose logs -f streaming-camera-app"
echo "    Stop all:       docker compose down"
echo ""
