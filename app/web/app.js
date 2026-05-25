/**
 * ORBRO VMS Dashboard — app.js
 *
 * Architecture:
 *  - WebSocket to /api/v1/ws/dashboard for real-time updates
 *  - Falls back to polling GET /api/v1/cameras every 2s if WS fails
 *  - Polls GET /api/v1/system/metrics every 2s
 *  - Polls GET /api/v1/stream-events for event log (if no WS)
 */

const API = '/api/v1';
const POLL_INTERVAL_MS = 2000;
const EVENT_LIMIT = 80;
const ALLOWED_FPS = [1, 3, 5, 10, 15];

// ─── State ───────────────────────────────────────────────────────────────────
let cameras = [];        // [{id, name, rtsp_url, status, actual_fps, ...}]
let events = [];         // [{id, time, type, message}]
let ws = null;
let wsConnected = false;
let pollingTimers = [];

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  lucide.createIcons();
  setupModal();
  setupChaosButtons();
  connectWebSocket();
  startPolling();
  addEvent('INFO', 'Dashboard initialized. Connecting to backend...');
});

// ─── WebSocket ────────────────────────────────────────────────────────────────
function connectWebSocket() {
  const wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}${API}/ws/dashboard`;
  try {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      wsConnected = true;
      updateWsBadge(true);
      addEvent('SUCCESS', 'WebSocket connected. Real-time updates active.');
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
      // Reconnect after 5s
      setTimeout(connectWebSocket, 5000);
    };

    ws.onerror = () => {
      wsConnected = false;
      updateWsBadge(false);
    };
  } catch (e) {
    wsConnected = false;
    updateWsBadge(false);
  }
}

function handleWsMessage(msg) {
  switch (msg.type) {
    case 'camera_status_snapshot':
      // Merge runtime status into existing camera list
      if (Array.isArray(msg.data)) {
        msg.data.forEach(runtime => {
          const cam = cameras.find(c => c.id === runtime.camera_id);
          if (cam) Object.assign(cam, runtime);
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
  fetchCameras();
  fetchMetrics();
  fetchEvents();

  pollingTimers.push(setInterval(fetchCameras, POLL_INTERVAL_MS));
  pollingTimers.push(setInterval(fetchMetrics, POLL_INTERVAL_MS));
  pollingTimers.push(setInterval(() => {
    if (!wsConnected) fetchEvents();
  }, 3000));
}

async function fetchCameras() {
  try {
    const res = await fetch(`${API}/cameras`);
    if (!res.ok) return;
    const data = await res.json();
    cameras = data;
    renderCameras();
  } catch (e) { /* network error */ }
}

async function fetchMetrics() {
  try {
    const res = await fetch(`${API}/system/metrics`);
    if (!res.ok) return;
    const data = await res.json();
    updateMetrics(data);
  } catch (e) { /* network error */ }
}

async function fetchEvents() {
  try {
    const res = await fetch(`${API}/stream-events?limit=30`);
    if (!res.ok) return;
    const data = await res.json();
    // Only add new events
    data.reverse().forEach(evt => {
      if (!events.find(e => e.id === evt.id)) {
        addEventFromApi(evt);
      }
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

  cameras.forEach(cam => {
    let tile = document.getElementById(`tile-${cam.id}`);
    if (!tile) {
      tile = document.createElement('div');
      tile.id = `tile-${cam.id}`;
      tile.className = 'camera-tile';
      tile.innerHTML = buildTileHTML(cam);
      grid.appendChild(tile);
      lucide.createIcons({ nodes: [tile] });
      attachTileListeners(tile, cam);
    } else {
      updateTile(tile, cam);
    }
  });

  // Remove tiles for deleted cameras
  const ids = cameras.map(c => `tile-${c.id}`);
  Array.from(grid.children).forEach(child => {
    if (!ids.includes(child.id) && child.id.startsWith('tile-')) {
      grid.removeChild(child);
    }
  });
}

function buildTileHTML(cam) {
  const statusClass = cam.status?.toLowerCase() || 'created';
  const isOnline = cam.status === 'CONNECTED';
  const isError = cam.status === 'ERROR';
  const lowFps = cam.actual_fps > 0 && cam.actual_fps < cam.target_fps * 0.5;

  return `
    <div class="video-area">
      ${isOnline
        ? `<img class="video-feed" id="img-${cam.id}"
               src="${API}/streams/${cam.id}/mjpeg"
               alt="${cam.name}"
               onerror="this.style.display='none'; document.getElementById('placeholder-${cam.id}').style.display='flex'" />`
        : ''}
      <div class="video-placeholder ${isError ? 'error' : ''}" id="placeholder-${cam.id}"
           style="${isOnline ? 'display:none' : 'display:flex'}">
        <i data-lucide="${isError ? 'server-crash' : 'wifi-off'}"></i>
        <span>${isError ? 'SERVER UNREACHABLE' : 'NO SIGNAL'}</span>
      </div>

      <div class="badge-status" id="badge-${cam.id}">
        <span class="status-dot ${statusClass}" id="dot-${cam.id}"></span>
        <span id="status-text-${cam.id}">${cam.status ?? 'CREATED'}</span>
      </div>

      <div class="badge-fps ${lowFps ? 'low-fps' : ''}" id="fps-badge-${cam.id}">
        <span id="fps-val-${cam.id}">${cam.actual_fps?.toFixed(1) ?? '0.0'}</span> FPS
      </div>
    </div>

    <div class="tile-controls">
      <div class="tile-header">
        <span class="tile-name" title="${cam.rtsp_url}">${cam.name}</span>
        <div class="tile-actions">
          <button class="btn-tile btn-kill" id="kill-${cam.id}"
                  ${!isOnline ? 'disabled' : ''}
                  title="Simulate stream disconnect">
            <i data-lucide="pause"></i> Kill Stream
          </button>
        </div>
      </div>

      <div class="tile-metrics">
        <div class="tile-metric-row">
          <span>Latency:</span>
          <span class="metric-val" id="latency-${cam.id}">
            ${isOnline ? `${cam.latency_ms?.toFixed(0) ?? '0'}ms` : '---'}
          </span>
        </div>
        <div class="tile-metric-row">
          <span>Display FPS:</span>
          <select class="fps-select" id="dfps-select-${cam.id}" title="Change display FPS">
            ${ALLOWED_FPS.map(f =>
              `<option value="${f}" ${f === cam.display_fps ? 'selected' : ''}>${f}</option>`
            ).join('')}
          </select>
        </div>
        <div class="tile-metric-row">
          <span>Reconnects:</span>
          <span class="metric-val reconnects" id="reconn-${cam.id}">${cam.reconnect_count ?? 0}</span>
        </div>
        <div class="tile-metric-row">
          <span>Uptime:</span>
          <span class="metric-val" id="uptime-${cam.id}">
            ${formatUptime(cam.uptime_seconds ?? 0)}
          </span>
        </div>
      </div>
    </div>`;
}

function updateTile(tile, cam) {
  const isOnline = cam.status === 'CONNECTED';
  const isError = cam.status === 'ERROR';
  const lowFps = cam.actual_fps > 0 && cam.actual_fps < (cam.target_fps || 10) * 0.5;

  // Status dot and text
  const dot = tile.querySelector(`#dot-${cam.id}`);
  const statusText = tile.querySelector(`#status-text-${cam.id}`);
  if (dot) dot.className = `status-dot ${cam.status?.toLowerCase() || 'created'}`;
  if (statusText) statusText.textContent = cam.status ?? 'CREATED';

  // FPS badge
  const fpsBadge = tile.querySelector(`#fps-badge-${cam.id}`);
  const fpsVal = tile.querySelector(`#fps-val-${cam.id}`);
  if (fpsBadge) fpsBadge.className = `badge-fps${lowFps ? ' low-fps' : ''}`;
  if (fpsVal) fpsVal.textContent = cam.actual_fps?.toFixed(1) ?? '0.0';

  // MJPEG img src (reconnect if coming back online)
  const img = tile.querySelector(`#img-${cam.id}`);
  const placeholder = tile.querySelector(`#placeholder-${cam.id}`);
  if (img && placeholder) {
    if (isOnline) {
      img.style.display = 'block';
      placeholder.style.display = 'none';
      // Refresh MJPEG src on reconnect
      if (!img.src.includes(cam.id)) {
        img.src = `${API}/streams/${cam.id}/mjpeg`;
      }
    } else {
      img.style.display = 'none';
      placeholder.style.display = 'flex';
      // Update icon
      const icon = placeholder.querySelector('[data-lucide]');
      if (icon) icon.setAttribute('data-lucide', isError ? 'server-crash' : 'wifi-off');
    }
  }

  // Kill button state
  const killBtn = tile.querySelector(`#kill-${cam.id}`);
  if (killBtn) killBtn.disabled = !isOnline;

  // Tile border class
  tile.className = `camera-tile${isError ? ' status-error' : ''}`;

  // Metrics
  const latency = tile.querySelector(`#latency-${cam.id}`);
  if (latency) latency.textContent = isOnline ? `${cam.latency_ms?.toFixed(0) ?? 0}ms` : '---';

  const reconn = tile.querySelector(`#reconn-${cam.id}`);
  if (reconn) reconn.textContent = cam.reconnect_count ?? 0;

  const uptime = tile.querySelector(`#uptime-${cam.id}`);
  if (uptime) uptime.textContent = formatUptime(cam.uptime_seconds ?? 0);
}

function attachTileListeners(tile, cam) {
  // Kill stream button
  const killBtn = tile.querySelector(`#kill-${cam.id}`);
  if (killBtn) {
    killBtn.addEventListener('click', () => simulateDisconnect(cam.id));
  }

  // Display FPS select
  const fpsSelect = tile.querySelector(`#dfps-select-${cam.id}`);
  if (fpsSelect) {
    fpsSelect.addEventListener('change', (e) => {
      updateDisplayFps(cam.id, parseInt(e.target.value));
    });
  }
}

// ─── API Actions ──────────────────────────────────────────────────────────────
async function simulateDisconnect(cameraId) {
  // Simulates killing a stream by patching display_fps to 1 (just a debug trigger)
  // In real scenario: call stop_rtsp_streams.sh
  addEvent('INFO', `[Debug] Kill Stream triggered for camera ${cameraId}`);
  showToast('Stream kill signal sent (stop the FFmpeg process manually)', 'info');
}

async function updateDisplayFps(cameraId, fps) {
  try {
    const res = await fetch(`${API}/cameras/${cameraId}/display-fps`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_fps: fps }),
    });
    if (res.ok) {
      addEvent('INFO', `Display FPS updated to ${fps} for camera ${cameraId}`);
    }
  } catch (e) {
    showToast('Failed to update display FPS', 'error');
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

// ─── Event Log ────────────────────────────────────────────────────────────────
function addEvent(type, message) {
  const id = `evt-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const time = new Date().toLocaleTimeString();
  events.unshift({ id, time, type, message });
  if (events.length > EVENT_LIMIT) events = events.slice(0, EVENT_LIMIT);
  renderEvents();
}

function addEventFromApi(evt) {
  // Map API severity/event_type to display type
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

// ─── Chaos Buttons ────────────────────────────────────────────────────────────
function setupChaosButtons() {
  document.getElementById('chaos-cpu')?.addEventListener('click', () => {
    addEvent('CRITICAL', 'HIGH CPU ALERT (>90%) — Chaos injection triggered.');
    showToast('HIGH_CPU event injected', 'info');
  });

  document.getElementById('chaos-ram')?.addEventListener('click', () => {
    addEvent('CRITICAL', 'HIGH MEMORY ALERT (>85%) — Memory pressure injected.');
    showToast('HIGH_MEMORY event injected', 'info');
  });

  document.getElementById('chaos-disconnect')?.addEventListener('click', () => {
    if (cameras.length > 0) {
      const cam = cameras.find(c => c.status === 'CONNECTED') || cameras[0];
      addEvent('ERROR', `Simulating stream disconnect for [${cam.name}]. Stop FFmpeg manually.`);
      showToast('Disconnect simulated. Stop FFmpeg process to test.', 'info');
    }
  });

  document.getElementById('chaos-refresh')?.addEventListener('click', async () => {
    await fetchCameras();
    await fetchMetrics();
    await fetchEvents();
    addEvent('INFO', 'Manual refresh triggered.');
    showToast('Status refreshed', 'success');
  });
}

// ─── Register Modal ───────────────────────────────────────────────────────────
function setupModal() {
  const overlay = document.getElementById('modal-overlay');
  const openBtn = document.getElementById('btn-open-modal');
  const closeBtn = document.getElementById('btn-close-modal');
  const form = document.getElementById('register-form');

  openBtn?.addEventListener('click', () => { overlay.style.display = 'flex'; });
  closeBtn?.addEventListener('click', () => { overlay.style.display = 'none'; });
  overlay?.addEventListener('click', (e) => { if (e.target === overlay) overlay.style.display = 'none'; });

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
    await registerCamera(data);
    overlay.style.display = 'none';
    form.reset();
  });
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
