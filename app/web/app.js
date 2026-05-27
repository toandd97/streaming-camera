/**
 * ORBRO VMS Dashboard — app.js
 *
 * Architecture (scaled for 80+ cameras):
 *  - WebSocket to /api/v1/ws/dashboard for real-time status updates
 *  - Falls back to polling GET /api/v1/cameras every 5s if WS fails
 *  - HLS video via hls.js (MediaMTX serves segments, Python NOT in video path)
 *  - IntersectionObserver: only load HLS streams for visible camera tiles
 *    → 80 cameras but only 4-8 load at once (viewport lazy loading)
 */

const API = '/api/v1';
const POLL_INTERVAL_MS = 5000;
const EVENT_LIMIT = 80;
const ALLOWED_FPS = [1, 5, 10, 15, 30, 60, 75, 120];

// ─── State ───────────────────────────────────────────────────────────────────
let cameras = [];        // [{id, name, rtsp_url, hls_url, status, actual_fps, ...}]
let events = [];         // [{id, time, type, message}]
let ws = null;
let wsConnected = false;
let pollingTimers = [];
let editingCameraId = null;
let maximizedCameraId = null;
let maximizedHls = null;

// HLS player instances: camera_id → Hls instance
const hlsPlayers = {};

// Canvas throttle: camera_id → { rafId, lastDrawTime, displayFps }
const canvasThrottles = {};

// IntersectionObserver for lazy-loading HLS streams
let tileObserver = null;

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  lucide.createIcons();
  setupModal();
  setupStreamModal();
  setupSimulationPanel();
  setupTelegramPanel();
  initTileObserver();
  connectWebSocket();
  startPolling();
  addEvent('INFO', 'Dashboard initialized. Connecting to backend...');
});

// ─── IntersectionObserver — Lazy HLS loading ──────────────────────────────────
function initTileObserver() {
  tileObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      const tile = entry.target;
      const cameraId = tile.dataset.cameraId;
      if (!cameraId) return;

      if (entry.isIntersecting) {
        // Tile is visible — start HLS if camera is connected
        const cam = cameras.find(c => c.id === cameraId);
        if (cam && cam.status === 'CONNECTED' && cam.hls_url) {
          startHLS(cameraId, cam.hls_url, cam.display_fps ?? 5);
        }
      } else {
        // Tile scrolled out of view — destroy HLS to free resources
        destroyHLS(cameraId);
      }
    });
  }, {
    root: null,       // viewport
    rootMargin: '50px',
    threshold: 0.1,
  });
}

// ─── HLS Player Management ────────────────────────────────────────────────────
function startHLS(cameraId, hlsUrl, displayFps) {
  if (hlsPlayers[cameraId]) return; // already playing

  const video = document.getElementById(`video-${cameraId}`);
  const canvas = document.getElementById(`canvas-${cameraId}`);
  const placeholder = document.getElementById(`placeholder-${cameraId}`);
  if (!video || !hlsUrl) return;

  if (Hls.isSupported()) {
    const hls = new Hls({
      enableWorker: true,
      lowLatencyMode: false,
      backBufferLength: 10,
      maxBufferLength: 15,
      startLevel: -1, // auto quality
    });
    hls.loadSource(hlsUrl);
    hls.attachMedia(video);

    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      video.play().catch(() => {});
      // Show canvas (throttled draw), keep video hidden
      if (canvas) {
        canvas.style.display = 'block';
        startCanvasThrottle(cameraId, video, canvas, displayFps ?? 5);
      } else {
        // Fallback: show video directly
        video.style.display = 'block';
      }
      if (placeholder) placeholder.style.display = 'none';
    });

    hls.on(Hls.Events.ERROR, (event, data) => {
      if (data.fatal) {
        console.warn(`HLS fatal error for ${cameraId}:`, data.type);
        destroyHLS(cameraId);
        showPlaceholder(cameraId, false);
      }
    });

    hlsPlayers[cameraId] = hls;

  } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
    // Safari: native HLS support
    video.src = hlsUrl;
    video.play().catch(() => {});
    if (canvas) {
      canvas.style.display = 'block';
      startCanvasThrottle(cameraId, video, canvas, displayFps ?? 5);
    } else {
      video.style.display = 'block';
    }
    if (placeholder) placeholder.style.display = 'none';
    hlsPlayers[cameraId] = { native: true };
  }
}

function destroyHLS(cameraId) {
  stopCanvasThrottle(cameraId);
  const hls = hlsPlayers[cameraId];
  if (!hls) return;

  if (hls.native) {
    const video = document.getElementById(`video-${cameraId}`);
    if (video) { video.src = ''; video.load(); }
  } else if (typeof hls.destroy === 'function') {
    hls.destroy();
  }
  delete hlsPlayers[cameraId];

  const video = document.getElementById(`video-${cameraId}`);
  if (video) video.style.display = 'none';
  const canvas = document.getElementById(`canvas-${cameraId}`);
  if (canvas) canvas.style.display = 'none';
}

function showPlaceholder(cameraId, isError) {
  stopCanvasThrottle(cameraId);
  const video = document.getElementById(`video-${cameraId}`);
  const canvas = document.getElementById(`canvas-${cameraId}`);
  const placeholder = document.getElementById(`placeholder-${cameraId}`);
  if (video) { video.style.display = 'none'; video.src = ''; }
  if (canvas) canvas.style.display = 'none';
  if (placeholder) {
    placeholder.style.display = 'flex';
    const icon = placeholder.querySelector('[data-lucide]');
    const label = placeholder.querySelector('.placeholder-label');
    if (icon) icon.setAttribute('data-lucide', isError ? 'server-crash' : 'wifi-off');
    if (label) label.textContent = isError ? 'SERVER UNREACHABLE' : 'NO SIGNAL';
    lucide.createIcons({ nodes: [placeholder] });
  }
}

// ─── Canvas FPS Throttle ─────────────────────────────────────────────────────────────────────
/**
 * startCanvasThrottle(id, videoEl, canvasEl, fps)
 *
 * Uses requestAnimationFrame to read the hidden <video> and draw onto <canvas>
 * at most `fps` frames per second. This makes the display FPS setting
 * visually apparent: low FPS = choppy, high FPS = smooth.
 */
function startCanvasThrottle(id, videoEl, canvasEl, fps) {
  stopCanvasThrottle(id); // stop any previous loop for this camera

  const ctx = canvasEl.getContext('2d');
  const interval = 1000 / Math.max(fps, 1);
  let lastDraw = 0;

  function loop(ts) {
    if (!canvasThrottles[id]) return; // stopped externally
    canvasThrottles[id].rafId = requestAnimationFrame(loop);
    if (ts - lastDraw < interval) return;
    lastDraw = ts;
    if (videoEl.readyState >= 2) { // HAVE_CURRENT_DATA
      // Match canvas resolution to video intrinsic size for crisp image
      if (canvasEl.width !== videoEl.videoWidth || canvasEl.height !== videoEl.videoHeight) {
        canvasEl.width = videoEl.videoWidth || 640;
        canvasEl.height = videoEl.videoHeight || 360;
      }
      ctx.drawImage(videoEl, 0, 0, canvasEl.width, canvasEl.height);
    }
  }

  canvasThrottles[id] = { rafId: requestAnimationFrame(loop), displayFps: fps };
}

function stopCanvasThrottle(id) {
  const t = canvasThrottles[id];
  if (t) {
    cancelAnimationFrame(t.rafId);
    delete canvasThrottles[id];
  }
}

function updateCanvasFps(id, fps) {
  const t = canvasThrottles[id];
  if (t) {
    // Simply update the FPS — the loop reads interval dynamically
    // Easiest: restart the throttle with the new FPS
    const video = document.getElementById(`video-${id}`);
    const canvas = document.getElementById(`canvas-${id}`);
    if (video && canvas && canvas.style.display !== 'none') {
      startCanvasThrottle(id, video, canvas, fps);
    }
  }
}

// ─── WebSocket ────────────────────────────────────────────────────────────────
function connectWebSocket() {
  const wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}${API}/ws/dashboard`;
  try {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      wsConnected = true;
      updateWsBadge(true);
      addEvent('SUCCESS', 'WebSocket connected. Real-time updates active.');
      stopPolling();
    };

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        handleWsMessage(msg);
      } catch (e) { /* ignore malformed */ }
    };

    ws.onclose = () => {
      wsConnected = false;
      updateWsBadge(false);
      addEvent('WARNING', 'WebSocket disconnected. Falling back to polling...');
      startPolling();
      setTimeout(connectWebSocket, 5000);
    };

    ws.onerror = () => {
      wsConnected = false;
      updateWsBadge(false);
      startPolling();
    };
  } catch (e) {
    wsConnected = false;
    updateWsBadge(false);
  }
}

function handleWsMessage(msg) {
  switch (msg.type) {
    case 'camera_status_snapshot':
      if (Array.isArray(msg.data)) {
        msg.data.forEach(runtime => {
          const cam = cameras.find(c => c.id === runtime.camera_id);
          if (cam) {
            const prevHlsUrl = cam.hls_url; // WS payload has no hls_url — preserve it
            Object.assign(cam, runtime);
            if (!cam.hls_url) cam.hls_url = prevHlsUrl;
          }
        });
        renderCameras();
      }
      break;
    case 'system_metrics':
      updateMetrics(msg.data);
      break;
    case 'stream_event':
      addEventFromApi(msg.data);
      break;
  }
}

function updateWsBadge(connected) {
  const badge = document.getElementById('ws-badge');
  if (connected) {
    badge.textContent = 'Live';
    badge.className = 'live-badge connected';
  } else {
    badge.textContent = 'Polling';
    badge.className = 'live-badge';
  }
}

// ─── Polling ──────────────────────────────────────────────────────────────────
function startPolling() {
  stopPolling();
  fetchCameras();
  fetchMetrics();
  fetchEvents();
  pollingTimers.push(setInterval(fetchCameras, POLL_INTERVAL_MS));
  pollingTimers.push(setInterval(fetchMetrics, POLL_INTERVAL_MS));
  pollingTimers.push(setInterval(fetchEvents, 6000));
}

function stopPolling() {
  pollingTimers.forEach(timer => clearInterval(timer));
  pollingTimers = [];
}

async function fetchCameras() {
  try {
    const res = await fetch(`${API}/cameras`);
    if (!res.ok) return;
    cameras = await res.json();
    renderCameras();
  } catch (e) { /* network error */ }
}

async function fetchMetrics() {
  try {
    const res = await fetch(`${API}/system/metrics`);
    if (!res.ok) return;
    updateMetrics(await res.json());
  } catch (e) { /* network error */ }
}

async function fetchEvents() {
  try {
    const res = await fetch(`${API}/stream-events?limit=30`);
    if (!res.ok) return;
    const data = await res.json();
    data.reverse().forEach(evt => {
      if (!events.find(e => e.id === evt.id)) addEventFromApi(evt);
    });
  } catch (e) { /* network error */ }
}

// ─── Metrics ──────────────────────────────────────────────────────────────────
function updateMetrics(data) {
  const cpuVal = document.getElementById('cpu-val');
  const ramVal = document.getElementById('ram-val');
  const cpuBadge = document.getElementById('cpu-badge');
  const ramBadge = document.getElementById('ram-badge');

  if (cpuVal) {
    cpuVal.textContent = data.cpu_percent ?? '--';
    const high = data.cpu_percent > 80;
    cpuVal.className = high ? 'metric-value-alert' : '';
    cpuBadge.className = 'metric-badge' + (high ? ' alert' : '');
  }
  if (ramVal) {
    ramVal.textContent = data.memory_percent ?? '--';
    const high = data.memory_percent > 85;
    ramVal.className = high ? 'metric-value-alert' : '';
    ramBadge.className = 'metric-badge' + (high ? ' alert' : '');
  }
  const streamsVal = document.getElementById('streams-val');
  if (streamsVal && data.active_streams !== undefined) {
    streamsVal.textContent = data.active_streams;
  }
  const gpuBadge = document.getElementById('gpu-badge');
  const gpuVal = document.getElementById('gpu-val');
  if (data.gpu_available && gpuBadge) {
    gpuBadge.style.display = 'flex';
    if (gpuVal) gpuVal.textContent = data.gpu_percent ?? '--';
  }
}

// ─── Camera Rendering ─────────────────────────────────────────────────────────
function renderCameras() {
  const grid = document.getElementById('camera-grid');
  if (!grid) return;

  if (cameras.length === 0) {
    grid.innerHTML = `
      <div style="grid-column:1/-1; text-align:center; color:var(--slate-600); padding:60px 0;">
        <p style="font-family:var(--font-mono)">No cameras registered.</p>
        <p style="font-size:0.8rem; margin-top:6px;">Click "Register Camera" to add one.</p>
      </div>`;
    lucide.createIcons();
    return;
  }

  // Remove any placeholder/loading/no-camera elements that are not tiles
  Array.from(grid.children).forEach(child => {
    if (!child.id || !child.id.startsWith('tile-')) {
      grid.removeChild(child);
    }
  });

  cameras.forEach(cam => {
    let tile = document.getElementById(`tile-${cam.id}`);
    if (!tile) {
      tile = document.createElement('div');
      tile.id = `tile-${cam.id}`;
      tile.className = 'camera-tile';
      tile.dataset.cameraId = cam.id;
      tile.innerHTML = buildTileHTML(cam);
      grid.appendChild(tile);
      lucide.createIcons({ nodes: [tile] });
      attachTileListeners(tile, cam);
      // Start observing for lazy HLS loading
      if (tileObserver) tileObserver.observe(tile);
    } else {
      updateTile(tile, cam);
    }
  });

  // Remove tiles for deleted cameras
  const ids = cameras.map(c => `tile-${c.id}`);
  Array.from(grid.children).forEach(child => {
    if (!ids.includes(child.id) && child.id.startsWith('tile-')) {
      const cId = child.dataset.cameraId;
      if (cId) {
        if (tileObserver) tileObserver.unobserve(child);
        destroyHLS(cId);
      }
      grid.removeChild(child);
    }
  });
}

function buildTileHTML(cam) {
  const statusClass = cam.status?.toLowerCase() || 'created';
  const isOnline = cam.status === 'CONNECTED';
  const isError = cam.status === 'ERROR';

  return `
    <div class="video-area">
      <video class="video-feed" id="video-${cam.id}"
             autoplay muted playsinline
             style="display:none;"
             poster=""></video>
      <canvas id="canvas-${cam.id}" style="display:none; width:100%; height:100%; object-fit:contain;"></canvas>
      <div class="video-placeholder ${isError ? 'error' : ''}" id="placeholder-${cam.id}"
           style="display:flex">
        <i data-lucide="${isError ? 'server-crash' : 'wifi-off'}"></i>
        <span class="placeholder-label">${isError ? 'SERVER UNREACHABLE' : 'NO SIGNAL'}</span>
      </div>

      <div class="badge-status" id="badge-${cam.id}">
        <span class="status-dot ${statusClass}" id="dot-${cam.id}"></span>
        <span id="status-text-${cam.id}">${cam.status ?? 'CREATED'}</span>
      </div>

      <div class="badge-fps" id="fps-badge-${cam.id}">
        <span class="badge-fps-label" id="fps-label-${cam.id}">${cam.display_fps ?? 5} FPS</span>
      </div>
    </div>

    <div class="tile-controls">
      <div class="tile-header">
        <span class="tile-name" title="${cam.rtsp_url}">${cam.name}</span>
        <div class="tile-actions">
          <button class="btn-tile ${cam.simulated_offline ? 'btn-sim-on' : 'btn-sim-off'}" id="sim-${cam.id}"
                  title="${cam.simulated_offline ? 'Restore now (simulation automatically restores after 15 seconds)' : 'Simulate offline for 15 seconds; alert is raised after 10 seconds'}">
            <i data-lucide="${cam.simulated_offline ? 'play' : 'zap-off'}"></i> ${cam.simulated_offline ? 'Sim On' : 'Sim Off'}
          </button>
          <button class="btn-tile btn-edit" id="edit-${cam.id}"
                  title="Edit camera name or stream URL">
            <i data-lucide="pencil"></i> Edit
          </button>
          <button class="btn-tile btn-delete" id="delete-${cam.id}"
                  title="Delete camera config and stop stream">
            <i data-lucide="trash-2"></i> Delete
          </button>
        </div>
      </div>

      <div class="tile-metrics">
        <div class="tile-metric-row">
          <span>Status:</span>
          <span class="metric-val" id="uptime-${cam.id}">
            ${cam.status === 'CONNECTED' ? formatUptime(cam.uptime_seconds ?? 0) : (cam.last_error || cam.status || 'CREATED')}
          </span>
        </div>
        <div class="tile-metric-row">
          <span>Reconnects:</span>
          <span class="metric-val reconnects" id="reconn-${cam.id}">${cam.reconnect_count ?? 0}</span>
        </div>
        <div class="tile-metric-row">
          <span>Display FPS:</span>
          <span class="metric-val" id="dfps-${cam.id}">${cam.display_fps ?? 5}</span>
        </div>
        <div class="tile-metric-row">
          <span>HLS Stream:</span>
          <span class="metric-val" style="font-size:0.7rem; color:var(--slate-500);">
            ${cam.hls_url ? cam.hls_url.split('/').slice(-3).join('/') : 'N/A'}
          </span>
        </div>
      </div>
    </div>`;
}

function updateTile(tile, cam) {
  const isOnline = cam.status === 'CONNECTED';
  const isError = cam.status === 'ERROR';

  // Status dot and text
  const dot = tile.querySelector(`#dot-${cam.id}`);
  const statusText = tile.querySelector(`#status-text-${cam.id}`);
  if (dot) dot.className = `status-dot ${cam.status?.toLowerCase() || 'created'}`;
  if (statusText) statusText.textContent = cam.status ?? 'CREATED';
  const name = tile.querySelector('.tile-name');
  if (name) {
    name.textContent = cam.name;
    name.title = cam.rtsp_url;
  }

  // Tile border class
  tile.className = `camera-tile${isError ? ' status-error' : ''}`;

  // Update simulation button
  const simBtn = tile.querySelector(`#sim-${cam.id}`);
  if (simBtn) {
    const isOffline = cam.simulated_offline;
    simBtn.className = `btn-tile ${isOffline ? 'btn-sim-on' : 'btn-sim-off'}`;
    simBtn.title = isOffline ? 'Restore now (simulation automatically restores after 15 seconds)' : 'Simulate offline for 15 seconds; alert is raised after 10 seconds';
    simBtn.innerHTML = `<i data-lucide="${isOffline ? 'play' : 'zap-off'}"></i> ${isOffline ? 'Sim On' : 'Sim Off'}`;
    lucide.createIcons({ nodes: [simBtn] });
  }

  // HLS player management based on status change
  if (isOnline && cam.hls_url) {
    // Check if tile is visible (IntersectionObserver will handle this too,
    // but we try immediately in case tile is already visible)
    const rect = tile.getBoundingClientRect();
    const isVisible = rect.top < window.innerHeight && rect.bottom > 0;
    if (isVisible && !hlsPlayers[cam.id]) {
      startHLS(cam.id, cam.hls_url, cam.display_fps ?? 5);
    } else if (isVisible && hlsPlayers[cam.id]) {
      // Already playing — update canvas FPS if it changed
      updateCanvasFps(cam.id, cam.display_fps ?? 5);
    }
  } else if (!isOnline && hlsPlayers[cam.id]) {
    // Camera went offline — stop streaming
    destroyHLS(cam.id);
    showPlaceholder(cam.id, isError);
  }

  // Metrics
  const uptime = tile.querySelector(`#uptime-${cam.id}`);
  if (uptime) {
    uptime.textContent = isOnline
      ? formatUptime(cam.uptime_seconds ?? 0)
      : (cam.last_error || cam.status || 'CREATED');
  }

  const reconn = tile.querySelector(`#reconn-${cam.id}`);
  if (reconn) reconn.textContent = cam.reconnect_count ?? 0;

  const dfpsEl = tile.querySelector(`#dfps-${cam.id}`);
  if (dfpsEl) dfpsEl.textContent = cam.display_fps ?? 5;

  const fpsLabel = tile.querySelector(`#fps-label-${cam.id}`);
  if (fpsLabel) fpsLabel.textContent = `${cam.display_fps ?? 5} FPS`;

  // Sync real-time updates to maximized modal
  if (maximizedCameraId === cam.id) {
    const modalStatus = document.getElementById('stream-modal-status');
    const modalUptime = document.getElementById('stream-modal-uptime');
    const modalReconn = document.getElementById('stream-modal-reconnects');

    if (modalStatus) modalStatus.textContent = cam.status ?? 'CREATED';
    if (modalUptime) {
      modalUptime.textContent = isOnline
        ? formatUptime(cam.uptime_seconds ?? 0)
        : (cam.last_error || cam.status || 'CREATED');
    }
    if (modalReconn) modalReconn.textContent = cam.reconnect_count ?? 0;

    // Restart player in modal if stream connects
    const modalVideo = document.getElementById('stream-modal-video');
    const modalPlaceholder = document.getElementById('stream-modal-placeholder');
    if (isOnline && cam.hls_url && !maximizedHls) {
      startMaximizedHLS(cam.hls_url, cam.display_fps ?? 5);
    } else if (!isOnline && maximizedHls) {
      destroyMaximizedHLS();
      if (modalPlaceholder) modalPlaceholder.style.display = 'flex';
    }
  }
}

function attachTileListeners(tile, cam) {
  const editBtn = tile.querySelector(`#edit-${cam.id}`);
  if (editBtn) {
    editBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      openEditModal(cam.id);
    });
  }
  const deleteBtn = tile.querySelector(`#delete-${cam.id}`);
  if (deleteBtn) {
    deleteBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      deleteCamera(cam.id);
    });
  }
  const simBtn = tile.querySelector(`#sim-${cam.id}`);
  if (simBtn) {
    simBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      // Read current state from cameras array — NOT from captured `cam` reference.
      // `cam` becomes stale after fetchCameras() replaces the cameras array.
      const currentCam = cameras.find(c => c.id === cam.id);
      const isCurrentlyOffline = currentCam?.simulated_offline ?? false;
      toggleCameraSimulation(cam.id, isCurrentlyOffline);
    });
  }
  const videoArea = tile.querySelector('.video-area');
  if (videoArea) {
    videoArea.addEventListener('click', (e) => {
      if (!e.target.closest('.badge-status') && !e.target.closest('.badge-fps')) {
        openStreamModal(cam.id);
      }
    });
  }
}

// ─── API Actions ──────────────────────────────────────────────────────────────
async function deleteCamera(cameraId) {
  if (!confirm('Are you sure you want to delete this camera?')) return;
  try {
    const res = await fetch(`${API}/cameras/${cameraId}`, { method: 'DELETE' });
    if (res.ok) {
      destroyHLS(cameraId);
      if (maximizedCameraId === cameraId) {
        closeStreamModal();
      }
      showToast('Camera deleted successfully', 'success');
      addEvent('INFO', `Deleted camera: ${cameraId}`);
      await fetchCameras();
    } else {
      showToast('Failed to delete camera', 'error');
    }
  } catch (e) {
    showToast('Network error while deleting camera', 'error');
  }
}

async function registerCamera(formData) {
  try {
    const res = await fetch(`${API}/cameras`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData),
    });
    if (res.ok) {
      const cam = await res.json();
      showToast(`Camera "${cam.name}" registered!`, 'success');
      addEvent('SUCCESS', `Camera registered: ${cam.name} → ${cam.rtsp_url}`);
      await fetchCameras();
    } else {
      const err = await res.json();
      showToast(`Error: ${err.detail || 'Registration failed'}`, 'error');
    }
  } catch (e) {
    showToast('Network error', 'error');
  }
}

async function updateCamera(cameraId, formData) {
  try {
    const res = await fetch(`${API}/cameras/${cameraId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData),
    });
    if (res.ok) {
      const cam = await res.json();
      destroyHLS(cameraId);
      showToast(`Camera "${cam.name}" updated`, 'success');
      addEvent('INFO', `Camera updated: ${cam.name} -> ${cam.rtsp_url}`);
      await fetchCameras();
      return true;
    }
    const err = await res.json();
    showToast(`Error: ${err.detail || 'Update failed'}`, 'error');
  } catch (e) {
    showToast('Network error while updating camera', 'error');
  }
  return false;
}

// ─── Event Log ────────────────────────────────────────────────────────────────
function addEvent(type, message) {
  const id = `evt-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const time = new Date().toLocaleTimeString();
  events.unshift({ id, time, type, message });
  if (events.length > EVENT_LIMIT) events = events.slice(0, EVENT_LIMIT);
  renderEvents();
}

function addEventFromApi(evt) {
  const typeMap = {
    'INFO': 'INFO', 'SUCCESS': 'SUCCESS',
    'WARNING': 'WARNING', 'CRITICAL': 'CRITICAL', 'ERROR': 'ERROR',
  };
  const type = typeMap[evt.severity] || typeMap[evt.event_type] || 'INFO';
  const time = evt.created_at
    ? new Date(evt.created_at).toLocaleTimeString()
    : new Date().toLocaleTimeString();
  const id = evt.id || `evt-${Date.now()}`;
  if (events.find(e => e.id === id)) return;
  events.unshift({ id, time, type, message: evt.message });
  if (events.length > EVENT_LIMIT) events = events.slice(0, EVENT_LIMIT);
  renderEvents();
}

function renderEvents() {
  const list = document.getElementById('event-list');
  if (!list) return;
  list.innerHTML = events.map(evt => `
    <div class="event-item">
      <span class="event-time">[${evt.time}]</span>
      <span class="event-msg ${evt.type}">${escapeHtml(evt.message)}</span>
    </div>`).join('');
}

// ─── Register Modal ───────────────────────────────────────────────────────────
function setupModal() {
  const overlay = document.getElementById('modal-overlay');
  const openBtn = document.getElementById('btn-open-modal');
  const closeBtn = document.getElementById('btn-close-modal');
  const form = document.getElementById('register-form');
  const urlInput = document.getElementById('form-url');
  const demoSource = document.getElementById('form-demo-source');

  openBtn?.addEventListener('click', openRegisterModal);
  closeBtn?.addEventListener('click', closeCameraModal);
  overlay?.addEventListener('click', (e) => { if (e.target === overlay) closeCameraModal(); });
  demoSource?.addEventListener('change', () => {
    if (demoSource.value) urlInput.value = demoSource.value;
  });
  urlInput?.addEventListener('input', () => {
    if (demoSource.value !== urlInput.value) demoSource.value = '';
  });

  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = {
      name: document.getElementById('form-name').value,
      rtsp_url: document.getElementById('form-url').value,
      resolution: document.getElementById('form-resolution').value || '640x360',
      target_fps: parseInt(document.getElementById('form-fps').value) || 10,
      display_fps: parseInt(document.getElementById('form-display-fps').value) || 5,
      enabled: true,
    };
    if (editingCameraId) {
      if (await updateCamera(editingCameraId, data)) closeCameraModal();
    } else {
      await registerCamera(data);
      closeCameraModal();
    }
  });
}

function openRegisterModal() {
  editingCameraId = null;
  document.getElementById('register-form')?.reset();
  document.getElementById('modal-title-text').textContent = 'Register New Camera';
  document.getElementById('btn-submit-camera').textContent = 'Register';
  document.getElementById('modal-overlay').style.display = 'flex';
}

function openEditModal(cameraId) {
  const cam = cameras.find(item => item.id === cameraId);
  if (!cam) return;
  editingCameraId = cameraId;
  document.getElementById('form-name').value = cam.name || '';
  document.getElementById('form-url').value = cam.rtsp_url || '';
  document.getElementById('form-demo-source').value = cam.rtsp_url || '';
  document.getElementById('form-resolution').value = cam.resolution || '640x360';
  document.getElementById('form-fps').value = cam.target_fps || 10;
  document.getElementById('form-display-fps').value = cam.display_fps || 5;
  document.getElementById('modal-title-text').textContent = 'Edit Camera';
  document.getElementById('btn-submit-camera').textContent = 'Update';
  document.getElementById('modal-overlay').style.display = 'flex';
}

function closeCameraModal() {
  editingCameraId = null;
  document.getElementById('modal-overlay').style.display = 'none';
  document.getElementById('register-form')?.reset();
}

// ─── Stream Maximize Modal ────────────────────────────────────────────────────
function setupStreamModal() {
  const overlay = document.getElementById('stream-modal-overlay');
  const closeBtn = document.getElementById('btn-close-stream-modal');
  closeBtn?.addEventListener('click', closeStreamModal);
  overlay?.addEventListener('click', (e) => { if (e.target === overlay) closeStreamModal(); });
}

function openStreamModal(cameraId) {
  const cam = cameras.find(c => c.id === cameraId);
  if (!cam) return;
  maximizedCameraId = cameraId;

  document.getElementById('stream-modal-title-text').textContent = cam.name;
  document.getElementById('stream-modal-rtsp').textContent = cam.rtsp_url;
  document.getElementById('stream-modal-status').textContent = cam.status ?? 'CREATED';
  document.getElementById('stream-modal-resolution').textContent = cam.resolution || '640x360';
  document.getElementById('stream-modal-uptime').textContent = cam.status === 'CONNECTED'
    ? formatUptime(cam.uptime_seconds ?? 0)
    : (cam.last_error || cam.status || 'CREATED');
  document.getElementById('stream-modal-reconnects').textContent = cam.reconnect_count ?? 0;
  document.getElementById('stream-modal-display-fps').textContent = cam.display_fps ?? 5;

  const video = document.getElementById('stream-modal-video');
  const placeholder = document.getElementById('stream-modal-placeholder');
  if (video) video.style.display = 'none';
  if (placeholder) placeholder.style.display = 'flex';

  document.getElementById('stream-modal-overlay').style.display = 'flex';
  lucide.createIcons({ nodes: [document.getElementById('stream-modal-overlay')] });

  if (cam.status === 'CONNECTED' && cam.hls_url) {
    startMaximizedHLS(cam.hls_url, cam.display_fps ?? 5);
  }
}

function closeStreamModal() {
  maximizedCameraId = null;
  document.getElementById('stream-modal-overlay').style.display = 'none';
  destroyMaximizedHLS();
}

function startMaximizedHLS(hlsUrl, displayFps) {
  destroyMaximizedHLS();
  const video = document.getElementById('stream-modal-video');
  const canvas = document.getElementById('stream-modal-canvas');
  const placeholder = document.getElementById('stream-modal-placeholder');
  if (!video || !hlsUrl) return;

  if (Hls.isSupported()) {
    maximizedHls = new Hls({
      enableWorker: true,
      lowLatencyMode: false,
      backBufferLength: 10,
      maxBufferLength: 15,
      startLevel: -1,
    });
    maximizedHls.loadSource(hlsUrl);
    maximizedHls.attachMedia(video);

    maximizedHls.on(Hls.Events.MANIFEST_PARSED, () => {
      video.play().catch(() => {});
      if (canvas) {
        canvas.style.display = 'block';
        startCanvasThrottle('__modal__', video, canvas, displayFps ?? 5);
      } else {
        video.style.display = 'block';
      }
      if (placeholder) placeholder.style.display = 'none';
    });

    maximizedHls.on(Hls.Events.ERROR, (event, data) => {
      if (data.fatal) {
        destroyMaximizedHLS();
        if (canvas) canvas.style.display = 'none';
        if (placeholder) placeholder.style.display = 'flex';
      }
    });
  } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
    video.src = hlsUrl;
    video.play().catch(() => {});
    if (canvas) {
      canvas.style.display = 'block';
      startCanvasThrottle('__modal__', video, canvas, displayFps ?? 5);
    } else {
      video.style.display = 'block';
    }
    if (placeholder) placeholder.style.display = 'none';
    maximizedHls = { native: true };
  }
}

function destroyMaximizedHLS() {
  stopCanvasThrottle('__modal__');
  if (!maximizedHls) return;

  if (maximizedHls.native) {
    const video = document.getElementById('stream-modal-video');
    if (video) { video.src = ''; video.load(); }
  } else if (typeof maximizedHls.destroy === 'function') {
    maximizedHls.destroy();
  }
  maximizedHls = null;

  const video = document.getElementById('stream-modal-video');
  if (video) video.style.display = 'none';
  const canvas = document.getElementById('stream-modal-canvas');
  if (canvas) canvas.style.display = 'none';
}

// ─── Toast ────────────────────────────────────────────────────────────────────
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function formatUptime(seconds) {
  seconds = Math.floor(seconds || 0);
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ─── Simulation Controls ──────────────────────────────────────────────────────
function setupSimulationPanel() {
  const cpuBtn = document.getElementById('btn-sim-cpu');
  const memBtn = document.getElementById('btn-sim-mem');

  cpuBtn?.addEventListener('click', async () => {
    try {
      const res = await fetch(`${API}/system/simulate/cpu`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        showToast(data.message, 'success');
      } else {
        showToast('Simulation failed', 'error');
      }
    } catch (e) {
      showToast('Network error during simulation', 'error');
    }
  });

  memBtn?.addEventListener('click', async () => {
    try {
      const res = await fetch(`${API}/system/simulate/memory`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        showToast(data.message, 'success');
      } else {
        showToast('Simulation failed', 'error');
      }
    } catch (e) {
      showToast('Network error during simulation', 'error');
    }
  });
}

function setupTelegramPanel() {
  const form = document.getElementById('telegram-form');
  const tokenInput = document.getElementById('telegram-token');
  const chatInput = document.getElementById('telegram-chat-id');
  const status = document.getElementById('telegram-status');
  const tokenHint = document.getElementById('telegram-token-hint');

  document.querySelectorAll('.secret-toggle').forEach(button => {
    button.addEventListener('click', () => {
      const input = document.getElementById(button.dataset.target);
      if (!input) return;
      const currentlyShown = input.type === 'text';
      input.type = currentlyShown ? 'password' : 'text';
      button.setAttribute('aria-label', currentlyShown ? 'Show value' : 'Hide value');
      button.innerHTML = `<i data-lucide="${currentlyShown ? 'eye' : 'eye-off'}"></i>`;
      lucide.createIcons({ nodes: [button] });
    });
  });

  async function loadTelegramConfig() {
    try {
      const res = await fetch(`${API}/system/telegram-config`);
      if (!res.ok) return;
      const data = await res.json();
      chatInput.value = data.chat_id || '';
      const ready = data.enabled && data.token_configured;
      status.textContent = ready ? 'Enabled' : 'Disabled';
      status.className = `live-badge${ready ? ' connected' : ''}`;
      tokenHint.textContent = data.token_configured
        ? 'Token available. Leave blank to test it, or enter a replacement.'
        : 'Token is not configured.';
    } catch (e) {
      status.textContent = 'Unavailable';
    }
  }

  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API}/system/telegram-config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bot_token: tokenInput.value || null,
          chat_id: chatInput.value,
        }),
      });
      if (res.ok) {
        tokenInput.value = '';
        await loadTelegramConfig();
        showToast('Test message delivered. Telegram alerts enabled.', 'success');
      } else {
        const error = await res.json();
        showToast(error.detail || 'Could not save Telegram configuration', 'error');
      }
    } catch (e) {
      showToast('Network error while saving Telegram configuration', 'error');
    }
  });

  loadTelegramConfig();
}

async function toggleCameraSimulation(cameraId, currentlyOffline) {
  const action = currentlyOffline ? 'reconnect' : 'disconnect';
  try {
    const res = await fetch(`${API}/system/simulate/${action}/${cameraId}`, { method: 'POST' });
    if (res.ok) {
      showToast(currentlyOffline ? 'Restored actual camera status' : 'Simulated offline: alert at 10s, automatic restore at 15s', 'info');
      await fetchCameras();
    } else {
      showToast('Simulation action failed', 'error');
    }
  } catch (e) {
    showToast('Network error during simulation', 'error');
  }
}
