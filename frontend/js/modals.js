/* ================================================================
   SOCIALIQ ANALYTICS — modals.js
   Credential result dialogs (persistent), capability modals,
   "What do I need?" information tools, and demo data choices.
   ================================================================ */

'use strict';

let _allPlatModalTimer = null;

/* ================================================================
   1. CREDENTIAL TEST RESULT POPUP (PERSISTENT — NO 60s AUTO CLOSE)
   ================================================================ */

function showCredentialResultModal(platform, result, isSuccess) {
  const root = $('popoverRoot');
  if (!root) return;

  closeAllPopovers();

  const iconClass = isSuccess ? 'success' : result.status === 'rate_limited' ? 'warning' : 'error';
  const iconEmoji = isSuccess ? '✓' : result.status === 'rate_limited' ? '⏳' : '✕';
  const title = isSuccess ? `${platform} — Live Connection Successful` : `${platform} — Connection Probe Notice`;
  const sub = isSuccess ? 'Credential accepted · Real API request completed successfully' : 'Diagnostic response from real platform gateway';

  const modalBackdrop = document.createElement('div');
  modalBackdrop.className = 'modal-backdrop';
  modalBackdrop.style.display = 'flex';
  modalBackdrop.style.alignItems = 'center';
  modalBackdrop.style.justifyContent = 'center';
  modalBackdrop.style.zIndex = '9999';

  modalBackdrop.innerHTML = `
    <div class="cred-result-dialog fade-in" role="dialog" aria-modal="true">
      <div class="cred-result-header">
        <div class="cred-result-icon ${iconClass}">${iconEmoji}</div>
        <div>
          <div class="cred-result-title">${esc(title)}</div>
          <div class="cred-result-subtitle">${esc(sub)}</div>
        </div>
      </div>
      <div class="cred-result-body">
        <div style="font-weight:600;margin-bottom:6px;color:var(--text)">${esc(result.message || 'Probe completed.')}</div>
        ${result.detail ? `<div style="font-size:12px;color:var(--text-3);margin-top:6px;font-family:monospace">${esc(result.detail)}</div>` : ''}
      </div>
      <div class="cred-result-footer">
        <button class="btn-demo-secondary" id="credResultCloseBtn" style="padding:8px 16px">Close</button>
        ${isSuccess ? `<button class="btn-demo-primary" id="credResultProceedBtn" style="padding:8px 18px">Enter / Continue →</button>` : ''}
      </div>
    </div>
  `;

  root.appendChild(modalBackdrop);
  root.style.pointerEvents = 'all';

  const closeBtn = modalBackdrop.querySelector('#credResultCloseBtn');
  closeBtn?.addEventListener('click', () => {
    modalBackdrop.remove();
    root.style.pointerEvents = 'none';
  });

  const proceedBtn = modalBackdrop.querySelector('#credResultProceedBtn');
  proceedBtn?.addEventListener('click', async () => {
    modalBackdrop.remove();
    root.style.pointerEvents = 'none';

    // Switch platform and retrieve real live data
    state.platform = platform;
    const select = $('platformSelect');
    if (select) select.value = platform;
    if (typeof updatePlatformDot === 'function') updatePlatformDot();

    // Show loading state
    updateStatusBadge('connecting');
    await loadData();

    // Show small 2-second confirmation toast
    showToast('🟢 LIVE DATA CONNECTED', 2000);
  });
}

/* ================================================================
   2. "WHAT DO I NEED?" INFORMATION TOOL
   ================================================================ */

const PLATFORM_HELP_INFO = {
  'YouTube': {
    title: 'YouTube Data API v3',
    paste: 'Google Cloud API Key with YouTube Data API v3 enabled',
    from: 'Google Cloud Console (console.cloud.google.com) → APIs & Services → Credentials',
    usedFor: 'Public video metadata, comments, views, likes, tags, and channel information',
    testTime: 'Usually 1–3 seconds',
    limitation: 'Google Cloud daily quota limit (default 10,000 units/day; video search costs 100 units)',
    successLooksLike: 'LIVE status badge, verified connection to Google YouTube endpoints',
    failureMeaning: 'Invalid API Key, YouTube Data API v3 not enabled in Google Cloud project, or daily quota reached',
  },
  'Telegram': {
    title: 'Telegram MTProto API',
    paste: 'Telegram App API ID and API Hash (and optional Bot Token)',
    from: 'Telegram Core Portal (my.telegram.org) → API development tools',
    usedFor: 'Public channel discussions, message feeds, and thread replies',
    testTime: 'Usually 1–3 seconds',
    limitation: 'Only public channels and previews are accessible; private user chats are never accessed',
    successLooksLike: 'CONNECTED status, operational gateway for public channel ingestion',
    failureMeaning: 'Incorrect numeric API ID, invalid 32-character API Hash, or flood-wait cooldown',
  },
  'Reddit': {
    title: 'Reddit OAuth2 Data API',
    paste: 'Reddit Script App Client ID and Client Secret',
    from: 'Reddit App Preferences (reddit.com/prefs/apps) → Create App ("script" type)',
    usedFor: 'Public subreddit submissions, discussion threads, scores, and comment trees',
    testTime: 'Usually 1–3 seconds',
    limitation: 'Subject to Reddit Data API terms and rate limit (60 requests/minute per client)',
    successLooksLike: 'LIVE connected with active OAuth2 client credentials token',
    failureMeaning: 'Invalid Client ID or Client Secret, or application type is not configured as "script"',
  },
  'Twitter / X': {
    title: 'X / Twitter API v2',
    paste: 'X API v2 App-Only Bearer Token',
    from: 'X Developer Portal (developer.x.com) → Projects & Apps → Keys and Tokens',
    usedFor: 'Recent public tweet searches, conversation trees, and tweet engagement stats',
    testTime: 'Usually 1–3 seconds',
    limitation: 'X API enforces pay-per-use monthly credits; zero-credit accounts are blocked by X billing',
    successLooksLike: 'CONNECTED status with verified v2 developer gateway access',
    failureMeaning: 'Account lacks active API credits or monthly billing entitlement, or invalid Bearer Token',
  },
  'Instagram': {
    title: 'Instagram Graph API (Meta)',
    paste: 'Meta Graph API User/Page Access Token and Instagram Professional Account ID',
    from: 'Meta for Developers (developers.facebook.com) → Tools → Graph API Explorer',
    usedFor: 'Business discovery, hashtag metrics, and permitted public professional media',
    testTime: 'Usually 1–3 seconds',
    limitation: 'Requires an active Instagram Business or Creator account linked to a Meta App with review permissions',
    successLooksLike: 'CONNECTED with verified Professional Account ID and valid token permissions',
    failureMeaning: 'Personal accounts are unsupported; token expired or missing instagram_basic / insights permissions',
  },
  'Facebook': {
    title: 'Facebook Graph API (Meta)',
    paste: 'Meta Page Access Token and Facebook Page ID',
    from: 'Meta for Developers (developers.facebook.com) → Graph API Explorer / Page Settings',
    usedFor: 'Public Page feed, post reach metrics, comments, and engagement analytics',
    testTime: 'Usually 1–3 seconds',
    limitation: 'Requires Meta Page Admin access and Page Public Content Access review permissions',
    successLooksLike: 'CONNECTED with verified Page ID and active Page Access Token',
    failureMeaning: 'User token passed instead of Page token, expired access token, or missing Page permissions',
  },
};

function showCredentialHelpModal(platform) {
  const root = $('popoverRoot');
  if (!root) return;

  closeAllPopovers();
  const info = PLATFORM_HELP_INFO[platform] || PLATFORM_HELP_INFO['YouTube'];

  const modalBackdrop = document.createElement('div');
  modalBackdrop.className = 'modal-backdrop';
  modalBackdrop.style.display = 'flex';
  modalBackdrop.style.alignItems = 'center';
  modalBackdrop.style.justifyContent = 'center';
  modalBackdrop.style.zIndex = '9999';

  modalBackdrop.innerHTML = `
    <div class="cred-help-dialog fade-in" role="dialog" aria-modal="true">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
        <h2 style="font-size:18px;font-weight:700;color:var(--text)">📖 ${esc(info.title)} Guide</h2>
        <button class="modal-close-btn" id="helpModalCloseBtn" style="font-size:16px;color:var(--text-3);cursor:pointer">✕</button>
      </div>
      <p style="font-size:12.5px;color:var(--text-2);margin-bottom:14px">
        Everything you need to connect real-time ${esc(platform)} data truthfully to SocialIQ Analytics.
      </p>
      <div class="help-section">
        <div class="help-row">
          <div class="help-row-label">What to Paste:</div>
          <div class="help-row-val"><strong>${esc(info.paste)}</strong></div>
        </div>
        <div class="help-row">
          <div class="help-row-label">Where It Comes From:</div>
          <div class="help-row-val">${esc(info.from)}</div>
        </div>
        <div class="help-row">
          <div class="help-row-label">What It Is Used For:</div>
          <div class="help-row-val">${esc(info.usedFor)}</div>
        </div>
        <div class="help-row">
          <div class="help-row-label">Approx Test Time:</div>
          <div class="help-row-val">${esc(info.testTime)}</div>
        </div>
        <div class="help-row">
          <div class="help-row-label">Important Limitation:</div>
          <div class="help-row-val" style="color:var(--warning)">${esc(info.limitation)}</div>
        </div>
        <div class="help-row">
          <div class="help-row-label">What Success Looks Like:</div>
          <div class="help-row-val" style="color:var(--success)">${esc(info.successLooksLike)}</div>
        </div>
        <div class="help-row">
          <div class="help-row-label">Common Failure Reason:</div>
          <div class="help-row-val" style="color:var(--danger)">${esc(info.failureMeaning)}</div>
        </div>
      </div>
      <div style="display:flex;justify-content:flex-end;margin-top:20px">
        <button class="btn-demo-primary" id="helpModalDoneBtn" style="padding:8px 20px">Got It</button>
      </div>
    </div>
  `;

  root.appendChild(modalBackdrop);
  root.style.pointerEvents = 'all';

  const closeFn = () => {
    modalBackdrop.remove();
    root.style.pointerEvents = 'none';
  };

  modalBackdrop.querySelector('#helpModalCloseBtn')?.addEventListener('click', closeFn);
  modalBackdrop.querySelector('#helpModalDoneBtn')?.addEventListener('click', closeFn);
}

/* ================================================================
   3. INFORMATIONAL CAPABILITY NOTICES
   ================================================================ */

function showPlatformCapabilityModal(platform) {
  const modal = $('allPlatformsModal');
  if (!modal) return;

  const cap = state.platformCapabilities ? state.platformCapabilities[platform] : null;
  const reason = cap?.reason || 'Live API access requires verified platform credentials and permissions.';
  const icon = platform === 'Instagram' ? '📷' : platform === 'Facebook' ? '👤' : platform === 'Twitter / X' ? '𝕏' : '🔒';

  modal.innerHTML = `
    <div class="modal-card">
      <div class="modal-header">
        <h2 id="allPlatModalTitle">${icon} ${esc(platform)} Capability Notice</h2>
        <button class="modal-close-btn" onclick="closeAllPlatformsModal()" title="Close">✕</button>
      </div>
      <div class="modal-body">
        <div class="modal-subtitle">
          <strong>Integration Scope:</strong> ${esc(reason)}
        </div>
        <div class="platform-notice warning" style="margin-top:14px;margin-bottom:8px;">
          <div class="platform-notice-content">
            <span class="platform-notice-icon">ℹ️</span>
            <div>In compliance with platform developer policies and security standards, only authorized public content is retrieved. Private or restricted data is never accessed.</div>
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <div class="modal-timer-note" id="modalCountdown">Auto-closing in 60s…</div>
        <div class="modal-actions">
          <button class="modal-btn-cancel" onclick="closeAllPlatformsModal()">Close</button>
          <button class="btn-demo-primary" style="font-size:12.5px;padding:8px 14px" onclick="enableDemoData('${esc(platform)}')">⚡ Use Demo Data</button>
          <button class="modal-btn-proceed" onclick="disableDemoData('${esc(platform)}')">🔒 Leave As Is</button>
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

function closeAllPlatformsModal() {
  if (_allPlatModalTimer) {
    clearInterval(_allPlatModalTimer);
    _allPlatModalTimer = null;
  }
  const modal = $('allPlatformsModal');
  if (modal) modal.classList.add('hidden');
}

/* ================================================================
   4. DEMO DATA CHOICE HANDLERS
   ================================================================ */

function enableDemoData(platform) {
  state.platformDemo[platform] = true;
  closeAllPlatformsModal();
  showToast(`⚡ Demo Mode enabled for ${platform}`);
  loadData();
}

function disableDemoData(platform) {
  delete state.platformDemo[platform];
  closeAllPlatformsModal();
  showToast(`🔒 Using truthful live / unconfigured state for ${platform}`);
  loadData();
}
