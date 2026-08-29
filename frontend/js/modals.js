/* ================================================================
   SOCIALIQ ANALYTICS — modals.js
   Credential result dialogs (persistent), capability modals,
   "What do I need?" information tools, and demo data choices.
   ================================================================ */

'use strict';

/* ================================================================
   1. CREDENTIAL TEST RESULT POPUP (PERSISTENT — NO AUTO-CLOSE)
   ================================================================ */

function showCredentialResultModal(platform, result, isSuccess) {
  const root = $('popoverRoot');
  if (!root) return;

  closeAllPopovers();

  // Categorize failure type if not success
  let categoryLabel = 'VERIFIED OPERATIONAL';
  let iconClass = 'success';
  let iconEmoji = '✓';
  let title = `${platform} — Live Connection Successful`;
  let sub = 'Credential accepted · Real API request completed successfully';

  if (!isSuccess) {
    iconClass = 'error';
    iconEmoji = '✕';
    const detailLower = ((result.detail || '') + ' ' + (result.message || '')).toLowerCase();

    if (detailLower.includes('quota') || result.status === 'quota_limit') {
      categoryLabel = 'QUOTA LIMIT EXCEEDED';
      iconClass = 'warning';
      iconEmoji = '⏳';
      title = `${platform} — Daily API Quota Limit Reached`;
      sub = 'Google Cloud project has reached its daily quota limit. Resets at midnight PT.';
    } else if (detailLower.includes('billing') || detailLower.includes('credit') || result.status === 'billing_limit') {
      categoryLabel = 'BILLING / CREDIT REQUIRED';
      iconClass = 'warning';
      iconEmoji = '💳';
      title = `${platform} — Active Billing or Paid Plan Required`;
      sub = 'Developer account lacks active API credits or required subscription.';
    } else if (detailLower.includes('rate') || result.status === 'rate_limited') {
      categoryLabel = 'RATE LIMIT / COOLDOWN';
      iconClass = 'warning';
      iconEmoji = '⏳';
      title = `${platform} — Gateway Rate Limited`;
      sub = 'Temporary rate limiting active on the platform gateway.';
    } else if (detailLower.includes('forbidden') || detailLower.includes('permission') || detailLower.includes('accessnotconfigured') || result.status === 'permission_required') {
      categoryLabel = 'PERMISSION / API ACCESS REQUIRED';
      title = `${platform} — Permission / Scope Required`;
      sub = 'Credential valid, but required API or scope is not enabled for this project.';
    } else if (detailLower.includes('network') || detailLower.includes('timeout') || result.status === 'network_error') {
      categoryLabel = 'NETWORK / TIMEOUT ERROR';
      title = `${platform} — Network Connection Timeout`;
      sub = 'Could not establish connection to the platform gateway endpoints.';
    } else if (result.status === 'not_configured') {
      categoryLabel = 'NOT CONFIGURED';
      title = `${platform} — Missing Credentials`;
      sub = 'Please enter all required credentials for this platform.';
    } else {
      categoryLabel = 'INVALID CREDENTIAL';
      title = `${platform} — Credential Verification Notice`;
      sub = 'Diagnostic response from platform authentication gateway.';
    }
  }

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
          <div style="font-size:10.5px;font-weight:700;letter-spacing:0.5px;color:var(--text-3);text-transform:uppercase;margin-bottom:2px">
            STATUS: ${categoryLabel}
          </div>
          <div class="cred-result-title">${esc(title)}</div>
          <div class="cred-result-subtitle">${esc(sub)}</div>
        </div>
      </div>
      <div class="cred-result-body">
        <div style="font-weight:600;margin-bottom:6px;color:var(--text)">${esc(result.message || 'Probe completed.')}</div>
        ${result.detail ? `<div style="font-size:12px;color:var(--text-3);margin-top:6px;font-family:monospace;background:var(--surface-2);padding:8px 10px;border-radius:var(--r-sm);word-break:break-all">${esc(result.detail)}</div>` : ''}
        ${isSuccess ? `
          <div style="margin-top:10px;font-size:12px;color:var(--success);background:rgba(16,185,129,0.08);padding:8px 12px;border-radius:var(--r-sm);border:1px solid rgba(16,185,129,0.2)">
            ✓ Real platform data retrieval is ready. Click <strong>Enter / Continue</strong> to load live analytics immediately.
          </div>
        ` : ''}
      </div>
      <div class="cred-result-footer">
        <button class="btn-demo-secondary" id="credResultCloseBtn" style="padding:8px 16px">✕ Close</button>
        ${isSuccess ? `<button class="btn-demo-primary" id="credResultProceedBtn" style="padding:8px 18px">Enter / Continue →</button>` : ''}
      </div>
    </div>
  `;

  root.appendChild(modalBackdrop);
  root.style.pointerEvents = 'all';

  const closeFn = () => {
    modalBackdrop.remove();
    root.style.pointerEvents = 'none';
  };

  modalBackdrop.querySelector('#credResultCloseBtn')?.addEventListener('click', closeFn);

  const proceedBtn = modalBackdrop.querySelector('#credResultProceedBtn');
  proceedBtn?.addEventListener('click', async () => {
    closeFn();

    // Ensure demo override is cleared for this platform and live mode is active
    if (state.demoOverrides) {
      state.demoOverrides[platform] = false;
    }
    state.dataSource = 'live';

    // Switch active platform
    state.platform = platform;
    const select = $('platformSelect');
    if (select) select.value = platform;
    if (typeof updatePlatformDot === 'function') updatePlatformDot();

    // Show loading state
    updateStatusBadge('connecting');
    await loadData();

    // Small 2-second confirmation notification
    showToast(`🟢 LIVE DATA CONNECTED — ${platform}`, 2000);
  });
}

/* ================================================================
   2. "WHAT DO I NEED?" INFORMATION TOOL
   ================================================================ */

const PLATFORM_HELP_INFO = {
  'YouTube': {
    title: 'YouTube Data API v3',
    credentialName: 'YouTube Data API v3 API Key',
    paste: 'Google Cloud API Key with YouTube Data API v3 enabled',
    from: 'Google Cloud Console (console.cloud.google.com) → APIs & Services → Credentials',
    usedFor: 'Searching public videos, retrieving views, likes, comment counts, tags, and channel metadata.',
    testTime: 'Usually 1–3 seconds',
    limitation: 'Google Cloud project daily quota (default 10,000 units/day; video search costs 100 units).',
    security: 'Never share your API key publicly or commit it to source code.',
    successLooksLike: 'LIVE status badge, verified connection to Google YouTube endpoints.',
    failureMeaning: 'Invalid API Key, YouTube Data API v3 not enabled in Google Cloud project, or daily quota reached.',
  },
  'Telegram': {
    title: 'Telegram MTProto API',
    credentialName: 'Telegram MTProto API ID & API Hash',
    paste: 'Telegram App API ID and API Hash (and optional Bot Token)',
    from: 'Telegram Core Portal (my.telegram.org) → API development tools',
    usedFor: 'Ingesting public channel messages, discussion threads, and reply counts.',
    testTime: 'Usually 1–3 seconds',
    limitation: 'Only public channels and previews are accessible; private user messages are never accessed.',
    security: 'Keep MTProto credentials secure.',
    successLooksLike: 'CONNECTED status with verified channel ingestion gateway.',
    failureMeaning: 'Incorrect numeric API ID, invalid 32-character API Hash, or flood-wait cooldown.',
  },
  'Reddit': {
    title: 'Reddit OAuth2 Data API',
    credentialName: 'Reddit OAuth Client ID & Client Secret',
    paste: 'Reddit Script App Client ID and Client Secret',
    from: 'Reddit App Preferences (reddit.com/prefs/apps) → Create App ("script" type)',
    usedFor: 'Public subreddit submissions, discussion scores, upvote ratios, and comment trees.',
    testTime: 'Usually 1–3 seconds',
    limitation: 'Subject to Reddit Data API rate limits (60 requests/minute per client).',
    security: 'Client secret is stored in backend runtime memory and never exposed to the frontend.',
    successLooksLike: 'LIVE connected with active OAuth2 application token.',
    failureMeaning: 'Invalid Client ID or Client Secret, or app type is not configured as "script".',
  },
  'Twitter / X': {
    title: 'X / Twitter API v2',
    credentialName: 'X API v2 App-Only Bearer Token',
    paste: 'X API v2 App-Only Bearer Token',
    from: 'X Developer Portal (developer.x.com) → Projects & Apps → Keys and Tokens',
    usedFor: 'Recent public tweet searches, conversation trees, and tweet engagement stats.',
    testTime: 'Usually 1–3 seconds',
    limitation: 'X API enforces pay-per-use monthly credits; zero-credit accounts are blocked by X billing.',
    security: 'Bearer token is encrypted in transit and masked in UI.',
    successLooksLike: 'CONNECTED status with verified developer gateway access.',
    failureMeaning: 'Account lacks active API credits, monthly billing entitlement, or invalid Bearer Token.',
  },
  'Instagram': {
    title: 'Instagram Graph API (Meta)',
    credentialName: 'Meta User/Page Access Token & Instagram Account ID',
    paste: 'Meta Graph API Access Token and Instagram Professional Account ID',
    from: 'Meta for Developers (developers.facebook.com) → Tools → Graph API Explorer',
    usedFor: 'Business discovery, public hashtag metrics, and permitted media analytics.',
    testTime: 'Usually 1–3 seconds',
    limitation: 'Requires an active Instagram Business/Creator account linked to a Meta App with review permissions.',
    security: 'Access tokens are managed solely on the backend.',
    successLooksLike: 'CONNECTED with verified Professional Account ID and valid token permissions.',
    failureMeaning: 'Personal accounts are unsupported; token expired or missing instagram_basic / insights permissions.',
  },
  'Facebook': {
    title: 'Facebook Graph API (Meta)',
    credentialName: 'Meta Page Access Token & Facebook Page ID',
    paste: 'Meta Page Access Token and Facebook Page ID',
    from: 'Meta for Developers (developers.facebook.com) → Graph API Explorer / Page Settings',
    usedFor: 'Public Page feed, post reach metrics, comments, and engagement analytics.',
    testTime: 'Usually 1–3 seconds',
    limitation: 'Requires Meta Page Admin access and Page Public Content Access review permissions.',
    security: 'Page tokens are never exposed in browser logs or responses.',
    successLooksLike: 'CONNECTED with verified Page ID and active Page Access Token.',
    failureMeaning: 'User token passed instead of Page token, expired access token, or missing Page permissions.',
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
          <div class="help-row-label">Credential Name:</div>
          <div class="help-row-val"><strong>${esc(info.credentialName)}</strong></div>
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
          <div class="help-row-label">Quota & Limitations:</div>
          <div class="help-row-val" style="color:var(--warning)">${esc(info.limitation)}</div>
        </div>
        <div class="help-row">
          <div class="help-row-label">Security Note:</div>
          <div class="help-row-val">${esc(info.security)}</div>
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

function showOAuthInfoModal(platform, layerName, scopes, info) {
  const root = $('popoverRoot');
  if (!root) return;

  const modalBackdrop = document.createElement('div');
  modalBackdrop.className = 'modal-backdrop';
  modalBackdrop.style.display = 'flex';
  modalBackdrop.style.alignItems = 'center';
  modalBackdrop.style.justifyContent = 'center';

  modalBackdrop.innerHTML = `
    <div class="cred-help-dialog" style="max-width:540px">
      <div class="modal-header">
        <div style="display:flex;align-items:center;gap:8px">
          <span style="font-size:22px">🔐</span>
          <div>
            <h2 style="font-size:16px;margin:0">${esc(platform)} — ${esc(layerName)}</h2>
            <div style="font-size:12px;color:var(--text-3)">OAuth 2.0 Authorization Guide</div>
          </div>
        </div>
        <button class="modal-close-btn" id="oauthModalCloseBtn" title="Close">✕</button>
      </div>
      <div class="help-section">
        <div class="help-row">
          <div class="help-row-label">Auth Protocol:</div>
          <div class="help-row-val"><strong>OAuth 2.0 User-Consent Flow</strong> (Secure Redirect)</div>
        </div>
        <div class="help-row">
          <div class="help-row-label">Required Scopes:</div>
          <div class="help-row-val" style="font-family:monospace;font-size:11.5px;color:var(--accent)">${esc(scopes || 'Read-only analytics and metrics')}</div>
        </div>
        <div class="help-row">
          <div class="help-row-label">Why OAuth 2.0:</div>
          <div class="help-row-val">${esc(info || 'Provides secure, tokenized access to owner analytics and private channel metrics without exposing user passwords or static API keys.')}</div>
        </div>
        <div class="help-row">
          <div class="help-row-label">How to Authorize:</div>
          <div class="help-row-val">1. Register your OAuth Client in the platform developer portal.<br>2. Set Authorized Redirect URI to <code>http://127.0.0.1:8001/api/auth/callback</code>.<br>3. Authenticate with your channel/page owner account.</div>
        </div>
      </div>
      <div style="display:flex;justify-content:flex-end;margin-top:20px;gap:8px">
        <button class="btn-demo-secondary" id="oauthModalCloseBtn2" style="padding:8px 16px">Cancel</button>
        <button class="btn-demo-primary" id="oauthModalProceedBtn" style="padding:8px 20px">Authorize in Portal</button>
      </div>
    </div>
  `;

  root.appendChild(modalBackdrop);
  root.style.pointerEvents = 'all';

  const closeFn = () => {
    modalBackdrop.remove();
    root.style.pointerEvents = 'none';
  };

  modalBackdrop.querySelector('#oauthModalCloseBtn')?.addEventListener('click', closeFn);
  modalBackdrop.querySelector('#oauthModalCloseBtn2')?.addEventListener('click', closeFn);
  modalBackdrop.querySelector('#oauthModalProceedBtn')?.addEventListener('click', () => {
    closeFn();
    showToast(`Initiating OAuth 2.0 handshake for ${platform} ${layerName}…`);
  });
}

/* ================================================================
   3. INFORMATIONAL CAPABILITY NOTICES (PERSISTENT — NO AUTO-CLOSE)
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
            <div>In compliance with platform developer policies and security standards, our system retrieves real platform data available through configured API requests, subject to API behavior, search scope, quota, and permissions.</div>
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <div class="modal-actions">
          <button class="modal-btn-cancel" onclick="closeAllPlatformsModal()">✕ Close</button>
          <button class="btn-demo-primary" style="font-size:12.5px;padding:8px 14px" onclick="enableDemoData('${esc(platform)}')">⚡ Use Demo Data</button>
          <button class="modal-btn-proceed" onclick="disableDemoData('${esc(platform)}')">🔒 Leave As Is</button>
        </div>
      </div>
    </div>
  `;

  modal.classList.remove('hidden');
}

function closeAllPlatformsModal() {
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
