/* ================================================================
   SOCIALIQ ANALYTICS — api.js
   Backend discovery, HTTP client, live analytics fetching,
   and secure credential management endpoints.
   ================================================================ */

'use strict';

let API_BASE = 'http://127.0.0.1:8001';
const API_CANDIDATES = [
  'http://127.0.0.1:8001',
  'http://localhost:8001',
  'http://127.0.0.1:8000',
  'http://localhost:8000',
];

let _apiBaseVerified = false;
let _isLoadingData = false;

async function probeBackend() {
  const origin = window.location.origin;
  if (origin && origin.startsWith('http')) {
    if (!API_CANDIDATES.includes(origin)) {
      API_CANDIDATES.unshift(origin);
    }
  }

  for (const candidate of API_CANDIDATES) {
    try {
      const resp = await fetch(`${candidate}/health`, {
        signal: AbortSignal.timeout(1800),
      });
      if (resp.ok) {
        const data = await resp.json();
        API_BASE = candidate;
        _apiBaseVerified = true;
        state.backendOK = true;
        if (data.platforms) {
          state.platformCapabilities = data.platforms;
        }
        return true;
      }
    } catch {
      // try next candidate
    }
  }
  _apiBaseVerified = false;
  state.backendOK = false;
  return false;
}

/* ================================================================
   CREDENTIALS API CLIENT (Never handles raw secrets in client logs)
   ================================================================ */

async function fetchCredentialsStatusApi() {
  if (!_apiBaseVerified) await probeBackend();
  try {
    const resp = await fetch(`${API_BASE}/api/credentials/status`, {
      signal: AbortSignal.timeout(5000),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    if (data.platforms) {
      state.platformCapabilities = data.platforms;
    }
    return data.platforms || {};
  } catch (err) {
    console.warn('Could not fetch credential status:', err);
    return state.platformCapabilities || {};
  }
}

async function testCredentialApi(platform, credentials) {
  if (!_apiBaseVerified) await probeBackend();
  const payload = { platform, credentials: credentials || {} };
  const resp = await fetch(`${API_BASE}/api/credentials/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(12000),
  });
  if (!resp.ok) {
    throw new Error(`API returned HTTP ${resp.status}`);
  }
  const result = await resp.json();
  if (state.platformCapabilities) {
    state.platformCapabilities[platform] = result;
  }
  return result;
}

async function saveCredentialApi(platform, credentials) {
  if (!_apiBaseVerified) await probeBackend();
  const payload = { platform, credentials: credentials || {} };
  const resp = await fetch(`${API_BASE}/api/credentials/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(12000),
  });
  if (!resp.ok) {
    throw new Error(`API returned HTTP ${resp.status}`);
  }
  const result = await resp.json();
  if (state.platformCapabilities) {
    state.platformCapabilities[platform] = result;
  }
  return result;
}

async function clearCredentialApi(platform) {
  if (!_apiBaseVerified) await probeBackend();
  const payload = { platform };
  const resp = await fetch(`${API_BASE}/api/credentials/clear`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(8000),
  });
  if (!resp.ok) {
    throw new Error(`API returned HTTP ${resp.status}`);
  }
  const result = await resp.json();
  if (state.platformCapabilities) {
    state.platformCapabilities[platform] = result;
  }
  return result;
}

/* ================================================================
   ANALYTICS DATA LOADER
   ================================================================ */

async function loadData() {
  if (_isLoadingData) return;
  _isLoadingData = true;

  const refreshBtn = $('refreshBtn');
  if (refreshBtn) refreshBtn.classList.add('spinning');
  const cap = state.platformCapabilities ? state.platformCapabilities[state.platform] : null;
  const isCapLive = cap?.status === 'connected' || cap?.status === 'limited';
  updateStatusBadge(isCapLive ? 'fetching' : 'connecting');

  // Verify or discover backend URL
  if (!_apiBaseVerified) {
    await probeBackend();
  }

  const isDemo = !!state.platformDemo[state.platform] || (state.platform === 'All Platforms' && !!state.platformDemo['All Platforms']);
  const demoParam = isDemo ? '&demo=true' : '';

  try {
    let url;
    if (state.mode === 'general') {
      url = `${API_BASE}/general?platform=${encodeURIComponent(state.platform)}&period=${encodeURIComponent(state.dateRange)}&chart_period=${encodeURIComponent(state.chartPeriod)}${demoParam}`;
    } else {
      if (!state.campaign.topic.trim()) {
        state.data = emptyData();
        state.backendOK = true;
        state.dataAvail = false;
        updateStatusBadge('empty');
        if (typeof renderCurrentView === 'function') renderCurrentView();
        return;
      }
      url = `${API_BASE}/analysis?topic=${encodeURIComponent(state.campaign.topic)}&query=${encodeURIComponent(state.campaign.query)}&platform=${encodeURIComponent(state.platform)}&period=${encodeURIComponent(state.dateRange)}&chart_period=${encodeURIComponent(state.chartPeriod)}${demoParam}`;
    }

    const resp = await fetch(url, { signal: AbortSignal.timeout(8000) });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const json = await resp.json();
    state.raw  = json;
    state.data = normalizePayload(json);
    state.backendOK  = true;
    state.dataAvail  = state.data.dataAvailable;
    state.dataSource = state.data.source;
    state.lastUpdated = new Date();

    if (!state.dataAvail) {
      updateStatusBadge('empty');
    } else if (state.dataSource === 'live') {
      updateStatusBadge('live');
    } else if (state.dataSource === 'limited') {
      updateStatusBadge('limited');
    } else if (state.dataSource === 'demo') {
      updateStatusBadge('demo');
    } else {
      updateStatusBadge('demo');
    }

    if (typeof renderCurrentView === 'function') renderCurrentView();
  } catch (err) {
    // Attempt re-probe
    const found = await probeBackend();
    if (found) {
      _isLoadingData = false;
      return loadData();
    }
    state.backendOK = false;
    state.data = emptyData();
    updateStatusBadge('offline');
    if (typeof renderCurrentView === 'function') renderCurrentView();
  } finally {
    _isLoadingData = false;
    if (refreshBtn) refreshBtn.classList.remove('spinning');
  }
}

function updateStatusBadge(s) {
  const badge = $('statusBadge');
  const text  = $('statusText');
  if (!badge) return;
  badge.className = 'status-badge';
  const cap = state.platformCapabilities ? state.platformCapabilities[state.platform] : null;
  const isCapLive = cap?.status === 'connected' || cap?.status === 'limited';

  if (s === 'live') {
    badge.classList.add('live');
    text.textContent = `LIVE — ${state.platform}`;
  } else if (s === 'limited') {
    badge.classList.add('limited');
    text.textContent = 'Limited Access';
  } else if (s === 'demo') {
    badge.classList.add('demo');
    text.textContent = 'DEMO (Explicit Selection)';
  } else if (s === 'offline') {
    text.textContent = 'Backend Offline';
  } else if (s === 'connecting' || s === 'fetching') {
    text.textContent = isCapLive ? 'Fetching live data…' : 'Connecting…';
  } else {
    if (cap?.status === 'not_configured') text.textContent = 'Not Configured';
    else if (cap?.status === 'unavailable') text.textContent = 'Unavailable';
    else text.textContent = 'No Data';
  }
}

function startAutoRefresh() {
  stopAutoRefresh();
  state.autoTimer = setInterval(() => {
    if (state.view === 'app') {
      loadData();
    }
  }, AUTO_MS);
}

function stopAutoRefresh() {
  if (state.autoTimer) {
    clearInterval(state.autoTimer);
    state.autoTimer = null;
  }
}
