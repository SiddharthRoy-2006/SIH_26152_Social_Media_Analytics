/* ================================================================
   SOCIALIQ ANALYTICS — platforms.js
   All Platforms ecosystem capabilities, status badges,
   and platform notice banners.
   ================================================================ */

'use strict';

const PLATFORMS_LIST = [
  { name: 'YouTube', icon: '▶' },
  { name: 'Telegram', icon: '✈' },
  { name: 'Reddit', icon: '💬' },
  { name: 'Twitter / X', icon: '𝕏' },
  { name: 'Instagram', icon: '📷' },
  { name: 'Facebook', icon: '👤' },
];

function showAllPlatformsModal() {
  const modal = $('allPlatformsModal');
  if (!modal) return;

  const caps = state.platformCapabilities || {};

  const rowsHTML = PLATFORMS_LIST.map(p => {
    const c = caps[p.name] || { status: 'not_configured', reason: 'Unconfigured data connector' };
    const statusLabel = c.status === 'connected' ? 'Live Connected' :
                        c.status === 'limited' ? 'Limited Access' :
                        c.status === 'not_configured' ? 'Not Configured' :
                        c.status === 'unavailable' ? 'Unavailable' :
                        c.status === 'rate_limited' ? 'Rate Limited' :
                        c.status === 'error' ? 'Error' : 'Demo Mode';
    return `
      <div class="platform-status-row">
        <div class="platform-row-info">
          <div class="platform-row-title">
            <span>${p.icon}</span>
            <span>${esc(p.name)}</span>
          </div>
          <div class="platform-row-desc">${esc(c.reason || 'Standard data source')}</div>
        </div>
        <span class="plat-pill ${esc(c.status)}">${statusLabel}</span>
      </div>
    `;
  }).join('');

  modal.innerHTML = `
    <div class="modal-card">
      <div class="modal-header">
        <h2 id="allPlatModalTitle">🌐 All Platforms Ecosystem Status</h2>
        <button class="modal-close-btn" onclick="closeAllPlatformsModal()" title="Close">✕</button>
      </div>
      <div class="modal-body">
        <div class="modal-subtitle">
          "All Platforms" aggregates live data <strong>strictly from platforms that are currently connected and authorized</strong>. Unconfigured, restricted, or rate-limited sources are excluded from live totals.
        </div>
        <div class="platform-status-list">
          ${rowsHTML}
        </div>
      </div>
      <div class="modal-footer">
        <div class="modal-timer-note" id="modalCountdown">Auto-closing in 60s…</div>
        <div class="modal-actions">
          <button class="modal-btn-cancel" onclick="closeAllPlatformsModal()">Close</button>
          <button class="btn-demo-primary" style="font-size:12.5px;padding:8px 14px" onclick="enableDemoData('All Platforms')">⚡ Use Demo Data</button>
          <button class="modal-btn-proceed" onclick="disableDemoData('All Platforms')">Proceed with Live Data</button>
        </div>
      </div>
    </div>
  `;

  modal.classList.remove('hidden');

  if (_allPlatModalTimer) clearInterval(_allPlatModalTimer);
  let secondsLeft = 60;
  const countdownEl = $('modalCountdown');
  _allPlatModalTimer = setInterval(() => {
    secondsLeft--;
    if (countdownEl) countdownEl.textContent = `Auto-closing in ${secondsLeft}s…`;
    if (secondsLeft <= 0) {
      closeAllPlatformsModal();
    }
  }, 1000);
}

function checkPlatformNotice(platform) {
  const noticeEl = $('platformNotice');
  if (!noticeEl) return;

  if (platform === 'All Platforms') {
    noticeEl.classList.add('hidden');
    noticeEl.innerHTML = '';
    return;
  }

  const cap = state.platformCapabilities ? state.platformCapabilities[platform] : null;
  if (!cap) {
    noticeEl.classList.add('hidden');
    noticeEl.innerHTML = '';
    return;
  }

  if (cap.status === 'not_configured') {
    noticeEl.className = 'platform-notice info';
    noticeEl.innerHTML = `
      <div class="platform-notice-content">
        <span class="platform-notice-icon">ℹ️</span>
        <div><strong>${esc(platform)} (Not Configured):</strong> ${esc(cap.reason || 'API credentials not yet entered.')}</div>
      </div>
      <div style="display:flex;align-items:center;gap:8px">
        <button class="btn-demo-primary" style="padding:4px 10px;font-size:11.5px" onclick="navigateTo('settings')">⚙ Configure API</button>
        <button class="platform-notice-close" onclick="dismissPlatformNotice()" title="Dismiss notice">✕</button>
      </div>
    `;
    noticeEl.classList.remove('hidden');
  } else if (cap.status === 'unavailable') {
    noticeEl.className = 'platform-notice warning';
    noticeEl.innerHTML = `
      <div class="platform-notice-content">
        <span class="platform-notice-icon">⚠️</span>
        <div><strong>${esc(platform)} (Unavailable):</strong> ${esc(cap.reason || 'Platform API requires business approval or paid tier.')}</div>
      </div>
      <button class="platform-notice-close" onclick="dismissPlatformNotice()" title="Dismiss notice">✕</button>
    `;
    noticeEl.classList.remove('hidden');
  } else if (cap.status === 'rate_limited') {
    noticeEl.className = 'platform-notice warning';
    noticeEl.innerHTML = `
      <div class="platform-notice-content">
        <span class="platform-notice-icon">⏳</span>
        <div><strong>${esc(platform)} (Rate Limited / Quota):</strong> ${esc(cap.reason || 'Quota exceeded or cooldown active.')}</div>
      </div>
      <button class="platform-notice-close" onclick="dismissPlatformNotice()" title="Dismiss notice">✕</button>
    `;
    noticeEl.classList.remove('hidden');
  } else if (cap.status === 'limited') {
    noticeEl.className = 'platform-notice info';
    noticeEl.innerHTML = `
      <div class="platform-notice-content">
        <span class="platform-notice-icon">⚡</span>
        <div><strong>${esc(platform)} (Limited Access):</strong> ${esc(cap.reason || 'Partial data access.')}</div>
      </div>
      <button class="platform-notice-close" onclick="dismissPlatformNotice()" title="Dismiss notice">✕</button>
    `;
    noticeEl.classList.remove('hidden');
  } else {
    noticeEl.classList.add('hidden');
    noticeEl.innerHTML = '';
  }
}

function dismissPlatformNotice() {
  const noticeEl = $('platformNotice');
  if (noticeEl) {
    noticeEl.classList.add('hidden');
    noticeEl.innerHTML = '';
  }
}
