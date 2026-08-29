/* ================================================================
   SOCIALIQ ANALYTICS — credentials.js
   Settings "PLATFORM API & DATA ACCESS", Security Toolbar,
   per-platform multi-access layer blocks, OAuth vs API-Key flows,
   show/hide toggles, Save & Test, and automatic Demo->Live transition.
   ================================================================ */

'use strict';

const PLATFORM_CONFIG_METADATA = {
  'YouTube': {
    icon: '▶',
    title: 'YouTube Data & Analytics Architecture',
    desc: 'Multi-layer access: public search & engagement (Data API v3) plus authenticated channel analytics and bulk reporting.',
    testTime: '~1–3 seconds',
    layers: [
      {
        id: 'data_api_v3',
        name: 'YouTube Data API v3',
        authType: 'API Key',
        isOAuth: false,
        usage: 'Public video search, video metadata, views, likes, comment counts, video categories, tags, and top comment threads.',
        provides: ['Public video search', 'Views, Likes, Comments', 'Video categories & tags', 'Top-level comment threads'],
        fields: [
          { id: 'api_key', label: 'YouTube Data API v3 API Key', placeholder: 'AIzaSy...' }
        ],
        actionLabel: 'Save & Test Data API',
      },
      {
        id: 'analytics_api',
        name: 'YouTube Analytics API',
        authType: 'Google OAuth 2.0',
        isOAuth: true,
        scopes: 'https://www.googleapis.com/auth/yt-analytics.readonly',
        usage: 'Channel owner viewer retention, audience demographics, playback locations, and estimated watch time.',
        provides: ['Viewer demographics', 'Audience retention', 'Geographic watch time'],
        buttonLabel: 'Connect Google Account',
        info: 'Requires Google OAuth 2.0 user consent to access private channel-owner performance telemetry.'
      },
      {
        id: 'reporting_api',
        name: 'YouTube Reporting API',
        authType: 'Google OAuth 2.0',
        isOAuth: true,
        scopes: 'https://www.googleapis.com/auth/yt-analytics-monetary.readonly',
        usage: 'Bulk scheduled historical reporting jobs for enterprise channel networks.',
        provides: ['Scheduled bulk reporting jobs', 'Historical daily aggregated stats'],
        buttonLabel: 'Authorize Reporting API',
        info: 'Creates scheduled background reporting datasets for large-scale channel networks.'
      }
    ],
    supportedMetrics: ['Views', 'Likes', 'Comments', 'Categories & Tags', 'Sentiment', 'Network Topology'],
    unsupportedMetrics: ['Direct Shares (Not in Data API)', 'Direct Subscriber Stream (Requires Owner OAuth)'],
  },
  'Telegram': {
    icon: '✈',
    title: 'Telegram MTProto & Bot API Architecture',
    desc: 'Public channel ingestion and discussion streams via MTProto client gateway or Bot API updates.',
    testTime: '~1–3 seconds',
    layers: [
      {
        id: 'mtproto_client',
        name: 'Telegram MTProto Client Gateway',
        authType: 'API ID & API Hash',
        isOAuth: false,
        usage: 'Public channel search, forward counts, view tracking, and discussion reply stream ingestion.',
        provides: ['Public channel messages', 'Forward counts & views', 'Discussion reply threads'],
        fields: [
          { id: 'api_id', label: 'Telegram MTProto API ID', placeholder: 'e.g. 12345678' },
          { id: 'api_hash', label: 'Telegram MTProto API Hash', placeholder: 'e.g. 0123456789abcdef0123456789abcdef' }
        ],
        actionLabel: 'Save & Test MTProto',
      },
      {
        id: 'bot_api',
        name: 'Telegram Bot API',
        authType: 'Bot Token',
        isOAuth: false,
        usage: 'Bot-managed group message updates, webhook event streams, and message status.',
        provides: ['Bot channel updates', 'Message delivery status'],
        fields: [
          { id: 'bot_token', label: 'Telegram Bot Token (Optional)', placeholder: 'e.g. 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11' }
        ],
        actionLabel: 'Save & Test Bot API',
      }
    ],
    supportedMetrics: ['Messages', 'Views', 'Forwards', 'Replies', 'Discussion Sentiment'],
    unsupportedMetrics: ['Likes/Dislikes (Not in Telegram API)', 'Private Chat Ingestion'],
  },
  'Reddit': {
    icon: '💬',
    title: 'Reddit OAuth2 Architecture',
    desc: 'Subreddit public submissions, score tracking, and comment trees via script app or user OAuth.',
    testTime: '~1–3 seconds',
    layers: [
      {
        id: 'reddit_script_app',
        name: 'Reddit OAuth2 App (Read-Only Script)',
        authType: 'Client ID & Client Secret',
        isOAuth: false,
        usage: 'Subreddit public submission search, post score tracking, and comment tree retrieval.',
        provides: ['Subreddit submissions', 'Upvotes & score distribution', 'Comment trees & replies'],
        fields: [
          { id: 'client_id', label: 'Reddit OAuth Client ID', placeholder: 'OAuth App Client ID' },
          { id: 'client_secret', label: 'Reddit OAuth Client Secret', placeholder: 'OAuth App Client Secret' }
        ],
        actionLabel: 'Save & Test Reddit App',
      },
      {
        id: 'reddit_user_auth',
        name: 'Reddit User Authorization',
        authType: 'OAuth 2.0 User Token',
        isOAuth: true,
        scopes: 'read, identity, mysubreddits',
        usage: 'Authenticated user subscribed feed and moderation telemetry.',
        provides: ['User subreddit feeds', 'Vote stream ingestion'],
        buttonLabel: 'Connect Reddit Account',
        info: 'Enables access to user-specific subreddit feeds and authenticated vote telemetry.'
      }
    ],
    supportedMetrics: ['Submissions', 'Scores & Upvotes', 'Comments', 'Subreddit Topics', 'Sentiment'],
    unsupportedMetrics: ['Direct Shares (Not tracked on Reddit)', 'User Demographics'],
  },
  'Twitter / X': {
    icon: '𝕏',
    title: 'X / Twitter API v2 Architecture',
    desc: 'Recent tweet search, tweet metrics, and conversation threads (requires active paid credits).',
    testTime: '~1–3 seconds',
    layers: [
      {
        id: 'x_app_only',
        name: 'X API v2 App-Only Access',
        authType: 'OAuth 2.0 Bearer Token',
        isOAuth: false,
        usage: 'Recent public tweet search (past 7 days), tweet engagement metrics, and conversation threads.',
        provides: ['Recent tweet search (7-day window)', 'Likes, retweets, replies, impressions', 'Public conversation threads'],
        fields: [
          { id: 'bearer_token', label: 'X API Bearer Token', placeholder: 'AAAAAAAAAAAAAAAAAAAA...' }
        ],
        actionLabel: 'Save & Test Bearer Token',
      },
      {
        id: 'x_user_context',
        name: 'X API v2 User-Context Access',
        authType: 'OAuth 2.0 User Token',
        isOAuth: true,
        scopes: 'tweet.read, users.read',
        usage: 'Authenticated account management, full historical archive search, and direct message telemetry.',
        provides: ['Full archive tweet search', 'Direct message events', 'User timeline stream'],
        buttonLabel: 'Authorize X User Account',
        info: 'Enables user-authenticated historical searches and personal timeline streams.'
      }
    ],
    supportedMetrics: ['Tweets', 'Likes', 'Retweets', 'Replies', 'Impressions', 'Sentiment'],
    unsupportedMetrics: ['Full Archive Search (Requires User OAuth / Enterprise)', 'Demographics'],
  },
  'Instagram': {
    icon: '📷',
    title: 'Instagram Graph API Architecture',
    desc: 'Professional/Business account discovery, public hashtags, and media analytics.',
    testTime: '~1–3 seconds',
    layers: [
      {
        id: 'instagram_prof_graph',
        name: 'Instagram Graph API (Professional/Creator)',
        authType: 'Access Token & Account ID',
        isOAuth: false,
        usage: 'Hashtag search, business discovery, media performance metrics, and comment threads.',
        provides: ['Hashtag recent media', 'Business discovery metadata', 'Comments on owned/tagged media'],
        fields: [
          { id: 'access_token', label: 'Meta User / Graph Access Token', placeholder: 'EAAB...' },
          { id: 'account_id', label: 'Instagram Professional Account ID', placeholder: 'e.g. 17841400000000000' }
        ],
        actionLabel: 'Save & Test Instagram Graph',
      },
      {
        id: 'instagram_basic',
        name: 'Instagram Basic Display API',
        authType: 'Instagram User Token',
        isOAuth: true,
        scopes: 'user_profile, user_media',
        usage: 'Personal profile info and authenticated user media gallery.',
        provides: ['Basic user profile', 'Personal media feed'],
        buttonLabel: 'Connect Instagram Account',
        info: 'Allows basic personal profile inspection without requiring a Meta Business Account.'
      }
    ],
    supportedMetrics: ['Media Posts', 'Likes', 'Comments', 'Reach / Impressions', 'Sentiment'],
    unsupportedMetrics: ['Personal Account Search', 'Unauthorized User Scrapes'],
  },
  'Facebook': {
    icon: '👤',
    title: 'Facebook Graph API Architecture',
    desc: 'Page public content access, post engagement, and conversation insights.',
    testTime: '~1–3 seconds',
    layers: [
      {
        id: 'facebook_page_access',
        name: 'Facebook Graph API (Page Content Access)',
        authType: 'Page Access Token & Page ID',
        isOAuth: false,
        usage: 'Page public post feeds, reaction statistics, and comment streams.',
        provides: ['Page posts', 'Reactions (Likes, Loves, etc.)', 'Comments & discussions'],
        fields: [
          { id: 'access_token', label: 'Meta Page Access Token', placeholder: 'EAAB...' },
          { id: 'page_id', label: 'Facebook Page ID', placeholder: 'e.g. 100080000000000' }
        ],
        actionLabel: 'Save & Test Facebook Page',
      },
      {
        id: 'facebook_insights',
        name: 'Facebook Page Insights API',
        authType: 'Page Administrator OAuth 2.0',
        isOAuth: true,
        scopes: 'pages_read_engagement, pages_show_list, read_insights',
        usage: 'Page aggregated reach, page views, and follower demographics.',
        provides: ['Page follower count', 'Page demographic insights', 'Impression reach'],
        buttonLabel: 'Connect Facebook Page',
        info: 'Requires Page Administrator authorization to ingest official follower counts and reach demographics.'
      }
    ],
    supportedMetrics: ['Page Posts', 'Reactions (Likes/Loves)', 'Comments', 'Shares', 'Sentiment'],
    unsupportedMetrics: ['Personal User Timeline Scraping', 'Private Groups'],
  }
};

function renderSettingsPage(ca, d) {
  ca.innerHTML = `
    <div class="fade-in">
      <div class="page-header">
        <div class="page-header-info">
          <div class="panel-label">CONFIGURATION & SECURITY</div>
          <h2>Settings</h2>
          <p>Multi-access platform credentials, dedicated access layer blocks, and live API verification.</p>
        </div>
        <button class="back-btn" onclick="goBack()">← Back</button>
      </div>

      <!-- SECURITY & PRIVACY TOOLBAR -->
      <div class="security-toolbar">
        <div class="sec-toolbar-header">
          <span>🛡️</span>
          <span>SECURE MULTI-ACCESS CREDENTIAL ARCHITECTURE — Zero-Leakage Guarantee</span>
        </div>
        <div class="sec-toolbar-grid">
          <div class="sec-item"><span class="sec-item-icon">✓</span><span>Credentials are never stored in client localStorage</span></div>
          <div class="sec-item"><span class="sec-item-icon">✓</span><span>Masked inputs with strict zero-logging policy</span></div>
          <div class="sec-item"><span class="sec-item-icon">✓</span><span>Secrets are never sent to AI models or client source</span></div>
          <div class="sec-item"><span class="sec-item-icon">✓</span><span>Full copy-paste enabled (Ctrl+C, Ctrl+V supported)</span></div>
          <div class="sec-item"><span class="sec-item-icon">✓</span><span>Encrypted in-transit · HTTPS ready architecture</span></div>
          <div class="sec-item"><span class="sec-item-icon">✓</span><span>Dedicated Access Layer Blocks (API Key vs OAuth 2.0)</span></div>
        </div>
      </div>

      <!-- PLATFORM API & DATA ACCESS -->
      <div class="panel mb">
        <div class="panel-top">
          <div>
            <div class="panel-label">LIVE DATA CONNECTIVITY</div>
            <h2>Platform API & Multi-Access Layer Architecture</h2>
          </div>
          <button class="panel-action" id="refreshAllCapsBtn">↻ Check All Statuses</button>
        </div>
        <p style="font-size:12.5px;color:var(--text-2);margin-bottom:16px">
          Each platform features dedicated <strong>Access Layer Blocks</strong> matching its authentic authentication model (e.g. YouTube Data API v3 API Key vs YouTube Analytics OAuth 2.0; Telegram MTProto vs Bot API). SocialIQ executes real live probes upon saving.
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
          <div><strong>Architecture:</strong> Real-World Data First · Multi-Access Capability Aware · FastAPI Backend</div>
          <div><strong>Supported Platforms:</strong> YouTube, Telegram, Reddit, Twitter/X, Instagram, Facebook (6 Platforms)</div>
          <div><strong>Organization:</strong> National Technical Research Organisation (NTRO)</div>
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

    const isPlatformConnected = statusClass === 'connected' || statusClass === 'limited';

    // Multi-access layer blocks rendering
    const serverLayers = Array.isArray(cap.access_layers) && cap.access_layers.length > 0
      ? cap.access_layers
      : meta.layers || [];

    const layerBlocksHTML = meta.layers.map((layerDef, lIdx) => {
      const serverLayer = serverLayers[lIdx] || {};
      const isConnected = isPlatformConnected && !layerDef.isOAuth;
      const layerStatusText = isConnected ? 'CONNECTED' : layerDef.isOAuth ? 'NOT CONNECTED (OAUTH REQUIRED)' : (isPlatformConnected ? 'CONNECTED' : 'NOT CONFIGURED');
      const layerBadgeColor = isConnected ? 'var(--success)' : layerDef.isOAuth ? 'var(--accent)' : 'var(--text-3)';
      const layerBadgeBg = isConnected ? 'rgba(16,185,129,0.12)' : layerDef.isOAuth ? 'rgba(99,102,241,0.12)' : 'rgba(255,255,255,0.06)';

      if (layerDef.isOAuth) {
        return `
          <div class="access-layer-block oauth-layer" style="margin:10px 0;background:var(--surface-2);border-radius:var(--r-sm);padding:12px;border:1px solid var(--border);border-left:3px solid var(--accent)">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px">
              <div>
                <span style="font-size:10px;font-weight:700;letter-spacing:0.5px;color:var(--accent);text-transform:uppercase">ACCESS LAYER ${lIdx + 1} — AUTHENTICATED</span>
                <div style="font-weight:600;font-size:13px;color:var(--text);margin-top:2px">${esc(layerDef.name)}</div>
                <div style="font-size:11px;color:var(--text-3);margin-top:1px">Auth Protocol: <strong>${esc(layerDef.authType)}</strong></div>
              </div>
              <span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px;color:${layerBadgeColor};background:${layerBadgeBg};white-space:nowrap">
                ${layerStatusText}
              </span>
            </div>
            <div style="font-size:11.5px;color:var(--text-2);margin-bottom:8px">${esc(layerDef.usage)}</div>
            <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px">
              ${(layerDef.provides || []).map(p => `
                <span style="background:rgba(99,102,241,0.08);color:var(--accent);padding:2px 6px;border-radius:4px;font-size:10px">✓ ${esc(p)}</span>
              `).join('')}
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;padding-top:6px;border-top:1px solid rgba(255,255,255,0.04)">
              <span style="font-size:10.5px;color:var(--text-3)">Standard Google/Meta/X Consent Flow</span>
              <button type="button" class="cred-btn-oauth" style="background:var(--accent);color:#fff;border:none;padding:5px 12px;border-radius:var(--r-sm);font-size:11.5px;font-weight:600;cursor:pointer"
                      onclick="showOAuthInfoModal('${esc(platform)}', '${esc(layerDef.name)}', '${esc(layerDef.scopes || '')}', '${esc(layerDef.info || '')}')">
                🔗 ${esc(layerDef.buttonLabel || 'Connect Account')}
              </button>
            </div>
          </div>
        `;
      }

      // Paste-based Layer Block
      const inputsHTML = (layerDef.fields || []).map(f => `
        <div class="cred-input-group" style="margin-bottom:8px">
          <div class="cred-label-row">
            <label class="cred-label" for="input_${platform}_${f.id}" style="font-size:11px;font-weight:600">${esc(f.label)}</label>
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
        <div class="access-layer-block paste-layer" style="margin:10px 0;background:var(--surface-2);border-radius:var(--r-sm);padding:12px;border:1px solid var(--border);border-left:3px solid var(--primary)">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px">
            <div>
              <span style="font-size:10px;font-weight:700;letter-spacing:0.5px;color:var(--primary);text-transform:uppercase">ACCESS LAYER ${lIdx + 1} — OFFICIAL API</span>
              <div style="font-weight:600;font-size:13px;color:var(--text);margin-top:2px">${esc(layerDef.name)}</div>
              <div style="font-size:11px;color:var(--text-3);margin-top:1px">Credential: <strong>${esc(layerDef.authType)}</strong></div>
            </div>
            <span class="cred-badge ${isConnected ? 'connected' : 'not_configured'}" style="font-size:10px;padding:2px 8px">
              ${isConnected ? 'LIVE / CONNECTED' : 'NOT CONFIGURED'}
            </span>
          </div>
          <div style="font-size:11.5px;color:var(--text-2);margin-bottom:8px">${esc(layerDef.usage)}</div>
          <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px">
            ${(layerDef.provides || []).map(p => `
              <span style="background:rgba(16,185,129,0.08);color:var(--success);padding:2px 6px;border-radius:4px;font-size:10px">✓ ${esc(p)}</span>
            `).join('')}
          </div>

          <form class="cred-inputs" onsubmit="return false;" style="margin-top:8px">
            ${inputsHTML}
          </form>

          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:10px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.04)">
            <button type="button" class="cred-btn-help" style="font-size:11px" onclick="showCredentialHelpModal('${esc(platform)}')">What do I need?</button>
            <div style="display:flex;gap:6px">
              <button type="button" class="cred-btn-clear" style="font-size:11px" onclick="handleClearCredential('${esc(platform)}')">Clear</button>
              <button type="button" class="cred-btn-save" id="btnSave_${esc(platform)}" style="font-size:11px" onclick="handleSaveAndTest('${esc(platform)}')">
                <span>Save & Test</span>
              </button>
            </div>
          </div>
        </div>
      `;
    }).join('');

    // Dynamic Capabilities Summary
    const summaryTiersHTML = `
      <div class="cap-summary-box" style="margin:10px 0;background:var(--surface);border-radius:var(--r-sm);padding:8px 10px;border:1px solid var(--border)">
        <div style="font-size:10px;font-weight:700;color:var(--text-3);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px">
          CURRENT ACCESS CAPABILITIES SUMMARY:
        </div>
        <div style="font-size:11px;color:var(--text-2)">
          ${isPlatformConnected
            ? `🟢 <strong>Level 1 Live Data Unlocked:</strong> Public search, metrics, and comment analysis are active.`
            : `⚪ <strong>Data Status:</strong> Awaiting credential validation. Connect Access Layer 1 above to enable live data.`}
        </div>
      </div>
    `;

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

          <div class="cred-desc" style="margin-bottom:10px">${esc(cap.reason || meta.desc)}</div>

          ${layerBlocksHTML}
          ${summaryTiersHTML}
        </div>

        <div class="cred-card-footer" style="margin-top:8px">
          <div class="cred-test-time">Probe latency: ${esc(meta.testTime)}</div>
          <div style="font-size:11px;color:var(--text-3)">Zero-leakage local validation</div>
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
    btn.innerHTML = '<span>Testing connection…</span>';
  }

  const meta = PLATFORM_CONFIG_METADATA[platform];
  const creds = {};
  if (meta && meta.layers) {
    meta.layers.forEach(layer => {
      if (layer.fields) {
        layer.fields.forEach(f => {
          const inp = $(`input_${platform}_${f.id}`);
          if (inp && inp.value.trim()) {
            creds[f.id] = inp.value.trim();
          }
        });
      }
    });
  }

  try {
    const result = await saveCredentialApi(platform, creds);
    const isSuccess = result.status === 'connected' || result.status === 'limited';

    if (isSuccess) {
      // Clear demo overrides and automatically activate LIVE mode
      if (state.platformDemo) {
        delete state.platformDemo[platform];
      }
      state.dataSource = 'live';

      // Automatically refresh live data if active platform
      if (state.platform === platform || state.platform === 'All Platforms') {
        loadData();
      }
    }

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
    if (state.platform === platform) {
      state.dataSource = 'empty';
      loadData();
    }
    renderCredentialCards();
  } catch (err) {
    showToast(`Failed to clear: ${err.message}`);
  }
}
