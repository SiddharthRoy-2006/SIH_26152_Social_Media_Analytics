/* ================================================================
   SOCIALIQ ANALYTICS — credentials.js
   Settings "PLATFORM API & DATA ACCESS", Security Toolbar,
   per-platform credential cards, show/hide toggles, Save & Test,
   and Enter-key form submissions.
   ================================================================ */

'use strict';

const PLATFORM_CONFIG_METADATA = {
  'YouTube': {
    icon: '▶',
    title: 'YouTube Data API v3',
    desc: 'Access public YouTube videos, engagement statistics, tags, and comment threads.',
    testTime: '~1–3 seconds',
    fields: [
      { id: 'api_key', label: 'YouTube Data API v3 API Key', placeholder: 'AIzaSy...' }
    ]
  },
  'Telegram': {
    icon: '✈',
    title: 'Telegram MTProto API',
    desc: 'Public channel search, discussion message streams, and reply threads.',
    testTime: '~1–3 seconds',
    fields: [
      { id: 'api_id', label: 'Telegram MTProto API ID', placeholder: 'e.g. 12345678' },
      { id: 'api_hash', label: 'Telegram MTProto API Hash', placeholder: 'e.g. 0123456789abcdef0123456789abcdef' }
    ]
  },
  'Reddit': {
    icon: '💬',
    title: 'Reddit OAuth2 API',
    desc: 'Subreddit public submissions, user discussions, and comment trees via OAuth2.',
    testTime: '~1–3 seconds',
    fields: [
      { id: 'client_id', label: 'Reddit OAuth Client ID', placeholder: 'OAuth App Client ID' },
      { id: 'client_secret', label: 'Reddit OAuth Client Secret', placeholder: 'OAuth App Client Secret' }
    ]
  },
  'Twitter / X': {
    icon: '𝕏',
    title: 'X / Twitter API v2',
    desc: 'Recent tweet search, metrics, and conversation threads (requires active API credits).',
    testTime: '~1–3 seconds',
    fields: [
      { id: 'bearer_token', label: 'X API Bearer Token', placeholder: 'AAAAAAAAAAAAAAAAAAAA...' }
    ]
  },
  'Instagram': {
    icon: '📷',
    title: 'Instagram Graph API',
    desc: 'Professional/Business account discovery, public hashtags, and media analytics.',
    testTime: '~1–3 seconds',
    fields: [
      { id: 'access_token', label: 'Meta User / Graph Access Token', placeholder: 'EAAB...' },
      { id: 'account_id', label: 'Instagram Professional Account ID', placeholder: 'e.g. 17841400000000000' }
    ]
  },
  'Facebook': {
    icon: '👤',
    title: 'Facebook Graph API',
    desc: 'Page public content access, post engagement, and conversation insights.',
    testTime: '~1–3 seconds',
    fields: [
      { id: 'access_token', label: 'Meta Page Access Token', placeholder: 'EAAB...' },
      { id: 'page_id', label: 'Facebook Page ID', placeholder: 'e.g. 100080000000000' }
    ]
  }
};

function renderSettingsPage(ca, d) {
  ca.innerHTML = `
    <div class="fade-in">
      <div class="page-header">
        <div class="page-header-info">
          <div class="panel-label">CONFIGURATION & SECURITY</div>
          <h2>Settings</h2>
          <p>Application preferences, security toolbar, and live platform API credentials.</p>
        </div>
        <button class="back-btn" onclick="goBack()">← Back</button>
      </div>

      <!-- SECURITY & PRIVACY TOOLBAR -->
      <div class="security-toolbar">
        <div class="sec-toolbar-header">
          <span>🛡️</span>
          <span>SECURE API CREDENTIALS — Zero-Leakage Guarantee</span>
        </div>
        <div class="sec-toolbar-grid">
          <div class="sec-item"><span class="sec-item-icon">✓</span><span>Credentials are never stored in client localStorage</span></div>
          <div class="sec-item"><span class="sec-item-icon">✓</span><span>Masked inputs with strict zero-logging policy</span></div>
          <div class="sec-item"><span class="sec-item-icon">✓</span><span>Secrets are never sent to AI models or client source</span></div>
          <div class="sec-item"><span class="sec-item-icon">✓</span><span>Full copy-paste enabled (Ctrl+C, Ctrl+V supported)</span></div>
          <div class="sec-item"><span class="sec-item-icon">✓</span><span>Encrypted in-transit · HTTPS ready architecture</span></div>
          <div class="sec-item"><span class="sec-item-icon">✓</span><span>Truthful API verification · No silent demo replacements</span></div>
        </div>
      </div>

      <!-- PLATFORM API & DATA ACCESS -->
      <div class="panel mb">
        <div class="panel-top">
          <div>
            <div class="panel-label">LIVE DATA CONNECTIVITY</div>
            <h2>Platform API & Data Access</h2>
          </div>
          <button class="panel-action" id="refreshAllCapsBtn">↻ Check All Statuses</button>
        </div>
        <p style="font-size:12.5px;color:var(--text-2);margin-bottom:16px">
          Configure authentic platform credentials below. Each connector performs an actual live API probe upon saving to verify connectivity.
        </p>

        <div class="cred-platform-grid" id="credPlatformGrid">
          <!-- Rendered dynamically -->
        </div>
      </div>

      <!-- Appearance -->
      <div class="panel mb">
        <div class="panel-top"><div><h2>Appearance</h2></div></div>
        <div class="setting-row">
          <div class="setting-info">
            <div class="setting-name">Theme</div>
            <div class="setting-desc">Choose between light and dark mode for the entire application.</div>
          </div>
          <div style="display:flex;gap:8px">
            <button class="theme-btn${state.theme==='light'?' active':''}" id="lightModeBtn">☀ Light</button>
            <button class="theme-btn${state.theme==='dark'?' active':''}" id="darkModeBtn">☾ Dark</button>
          </div>
        </div>
      </div>

      <!-- Data & Refresh -->
      <div class="panel mb">
        <div class="panel-top"><div><h2>Data & Refresh</h2></div></div>
        <div class="setting-row">
          <div class="setting-info">
            <div class="setting-name">Auto Refresh</div>
            <div class="setting-desc">Automatically refresh analytics every 15 minutes.</div>
          </div>
          <button class="toggle on" id="autoRefreshToggle" aria-label="Toggle auto refresh"></button>
        </div>
        <div class="setting-row">
          <div class="setting-info">
            <div class="setting-name">Active Data Mode</div>
            <div class="setting-desc">Current data-first operational mode.</div>
          </div>
          <span class="source-badge ${state.dataSource==='live'?'live':state.dataSource==='demo'?'demo':'empty'}">${esc(state.dataSource.toUpperCase())}</span>
        </div>
        <div class="setting-row">
          <div class="setting-info">
            <div class="setting-name">Export Report</div>
            <div class="setting-desc">Download current analytics state as JSON.</div>
          </div>
          <button class="export-btn" id="exportBtn">↓ Export JSON</button>
        </div>
      </div>

      <!-- About SocialIQ -->
      <div class="panel mb">
        <div class="panel-top"><div><h2>About SocialIQ</h2></div></div>
        <div style="display:flex;flex-direction:column;gap:8px;font-size:13px;color:var(--text-2)">
          <div><strong>Project:</strong> SIH 26152 — Social Media Analytics Platform</div>
          <div><strong>Architecture:</strong> Real-World Data First · FastAPI Backend · Modular Vanilla UI</div>
          <div><strong>Presenting Team:</strong> Team NEXORA (Smart India Hackathon)</div>
        </div>
      </div>

      <!-- Session -->
      <div class="panel mb">
        <div class="panel-top"><div><h2>Session</h2></div></div>
        <div class="setting-row">
          <div class="setting-info">
            <div class="setting-name">Logout</div>
            <div class="setting-desc">Return to the login screen.</div>
          </div>
          <button class="back-btn" id="logoutBtn">Sign Out</button>
        </div>
      </div>
    </div>`;

  // Bind settings listeners
  $('lightModeBtn')?.addEventListener('click', () => { applyTheme('light'); renderCurrentView(); });
  $('darkModeBtn')?.addEventListener('click',  () => { applyTheme('dark');  renderCurrentView(); });
  $('exportBtn')?.addEventListener('click', exportReport);
  $('logoutBtn')?.addEventListener('click', () => { stopAutoRefresh(); showLogin(); showToast('Signed out'); });
  $('autoRefreshToggle')?.addEventListener('click', function() {
    const on = this.classList.toggle('on');
    if (on) startAutoRefresh(); else stopAutoRefresh();
    showToast(on ? 'Auto-refresh enabled' : 'Auto-refresh paused');
  });
  $('refreshAllCapsBtn')?.addEventListener('click', async () => {
    showToast('Probing all platform connectors…');
    await fetchCredentialsStatusApi();
    renderCredentialCards();
  });

  renderCredentialCards();
}

function renderCredentialCards() {
  const grid = $('credPlatformGrid');
  if (!grid) return;

  const caps = state.platformCapabilities || {};

  grid.innerHTML = Object.entries(PLATFORM_CONFIG_METADATA).map(([platform, meta]) => {
    const cap = caps[platform] || { status: 'not_configured', reason: 'Not configured' };
    const statusClass = cap.status || 'not_configured';
    const statusLabel = statusClass === 'connected' ? 'LIVE CONNECTED' :
                        statusClass === 'limited' ? 'LIMITED ACCESS' :
                        statusClass === 'not_configured' ? 'NOT CONFIGURED' :
                        statusClass === 'unavailable' ? 'UNAVAILABLE' :
                        statusClass === 'rate_limited' ? 'RATE LIMITED' : 'ERROR';

    const inputsHTML = meta.fields.map(f => `
      <div class="cred-input-group">
        <div class="cred-label-row">
          <label class="cred-label" for="input_${platform}_${f.id}">${esc(f.label)}</label>
        </div>
        <div class="cred-input-wrap">
          <input class="cred-input" id="input_${platform}_${f.id}" type="password"
                 data-platform="${esc(platform)}" data-field="${esc(f.id)}"
                 placeholder="${esc(f.placeholder)}" autocomplete="off">
          <button type="button" class="cred-toggle-eye" data-target="input_${platform}_${f.id}" title="Toggle secret visibility">
            👁️
          </button>
        </div>
      </div>
    `).join('');

    return `
      <div class="cred-card" id="card_${esc(platform)}">
        <div>
          <div class="cred-card-header">
            <div class="cred-platform-title">
              <span class="cred-platform-icon">${meta.icon}</span>
              <span>${esc(platform)}</span>
            </div>
            <span class="cred-badge ${statusClass}">${statusLabel}</span>
          </div>

          <div class="cred-desc">${esc(cap.reason || meta.desc)}</div>

          <form class="cred-inputs" onsubmit="return false;">
            ${inputsHTML}
          </form>
        </div>

        <div class="cred-card-footer">
          <div class="cred-test-time">Test time: ${esc(meta.testTime)}</div>
          <div class="cred-actions">
            <button type="button" class="cred-btn-help" onclick="showCredentialHelpModal('${esc(platform)}')">What do I need?</button>
            <button type="button" class="cred-btn-clear" onclick="handleClearCredential('${esc(platform)}')">Clear</button>
            <button type="button" class="cred-btn-save" id="btnSave_${esc(platform)}" onclick="handleSaveAndTest('${esc(platform)}')">
              <span>Save & Test</span>
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');

  // Wire up Show/Hide eye toggles
  grid.querySelectorAll('.cred-toggle-eye').forEach(btn => {
    btn.addEventListener('click', e => {
      e.preventDefault();
      const targetId = btn.dataset.target;
      const input = $(targetId);
      if (!input) return;
      const isPass = input.type === 'password';
      input.type = isPass ? 'text' : 'password';
      btn.textContent = isPass ? '🔒' : '👁️';
    });
  });

  // Wire up Enter key submission on inputs
  grid.querySelectorAll('.cred-input').forEach(inp => {
    inp.addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const platform = inp.dataset.platform;
        if (platform) handleSaveAndTest(platform);
      }
    });
  });
}

let _isTestingCred = false;

async function handleSaveAndTest(platform) {
  if (_isTestingCred) return;
  _isTestingCred = true;

  const btn = $(`btnSave_${platform}`);
  if (btn) {
    btn.classList.add('testing');
    btn.innerHTML = '<span>Testing…</span>';
  }

  const meta = PLATFORM_CONFIG_METADATA[platform];
  const creds = {};
  if (meta && meta.fields) {
    meta.fields.forEach(f => {
      const inp = $(`input_${platform}_${f.id}`);
      if (inp && inp.value.trim()) {
        creds[f.id] = inp.value.trim();
      }
    });
  }

  try {
    const result = await saveCredentialApi(platform, creds);
    const isSuccess = result.status === 'connected' || result.status === 'limited';

    renderCredentialCards();
    showCredentialResultModal(platform, result, isSuccess);
  } catch (err) {
    showCredentialResultModal(platform, {
      status: 'error',
      message: `Connection test request failed: ${err.message || err}`,
      detail: 'Ensure the backend server is running and reachable.',
    }, false);
  } finally {
    _isTestingCred = false;
    if (btn) {
      btn.classList.remove('testing');
      btn.innerHTML = '<span>Save & Test</span>';
    }
  }
}

async function handleClearCredential(platform) {
  try {
    const result = await clearCredentialApi(platform);
    showToast(`Removed credentials for ${platform}`);
    renderCredentialCards();
  } catch (err) {
    showToast(`Failed to clear: ${err.message}`);
  }
}
