/* ================================================================
   SOCIALIQ ANALYTICS — app.js
   Main Application bootstrap, view router, sidebar navigation,
   session restoration, and global function exports.
   ================================================================ */

'use strict';

/* ================================================================
   VIEW MANAGEMENT
   ================================================================ */

function showLogin() {
  state.view = 'login';
  $('loginGate')?.classList.remove('hidden');
  $('modeGate')?.classList.add('hidden');
  $('appShell')?.classList.add('hidden');
  stopAutoRefresh();
}

function showModeSelect() {
  state.view = 'mode';
  $('loginGate')?.classList.add('hidden');
  $('modeGate')?.classList.remove('hidden');
  $('appShell')?.classList.add('hidden');
}

function showApp(mode) {
  state.mode = mode;
  state.view = 'app';
  $('loginGate')?.classList.add('hidden');
  $('modeGate')?.classList.add('hidden');
  $('appShell')?.classList.remove('hidden');

  // Apply mode defaults
  if (mode === 'general') {
    state.platform = 'All Platforms';
    state.currentPage = 'dashboard';
    const sel = $('platformSelect');
    if (sel) sel.value = 'All Platforms';
  } else {
    state.platform = 'Instagram';
    state.currentPage = 'dashboard';
    const sel = $('platformSelect');
    if (sel) sel.value = 'Instagram';
  }

  updateModePill();
  buildSidebar();
  updateGreeting();
  updatePlatformDot();
  loadData();
  startAutoRefresh();
}

function updateModePill() {
  const pill  = $('modePill');
  const label = $('switchModeLabel');
  if (!pill) return;
  pill.className = `mode-pill ${state.mode}`;
  pill.textContent = state.mode === 'general' ? '🌐 General Intelligence' : '🎯 Topic Analysis';
  if (label) label.textContent = state.mode === 'general' ? 'Switch to Topic Analysis' : 'Switch to General';
}

function updateGreeting() {
  const el = $('topbarGreeting');
  if (el) el.textContent = greeting();
}

function updatePlatformDot() {
  const dot = $('platDot');
  if (dot) dot.style.background = PLATFORM_COLORS[state.platform] || '#2563eb';
}

/* ================================================================
   SIDEBAR NAVIGATION
   ================================================================ */

const GENERAL_NAV = [
  { id:'dashboard',      icon:'⊞', label:'Overview' },
  { id:'trending',       icon:'📈', label:'Trending Topics' },
  { id:'network',        icon:'🔗', label:'Network Analysis' },
  { id:'sentiment',      icon:'💬', label:'Sentiment & Emotions' },
  { id:'audience',       icon:'👥', label:'Audience Demographics' },
  { id:'ai',             icon:'✦', label:'AI Insights' },
  { id:'settings',       icon:'⚙', label:'Settings' },
];

const TOPIC_NAV = [
  { id:'dashboard',      icon:'⊞', label:'Dashboard' },
  { id:'analytics',      icon:'📊', label:'Analytics' },
  { id:'content',        icon:'📄', label:'Content' },
  { id:'audience',       icon:'👥', label:'Audience' },
  { id:'sentiment',      icon:'💬', label:'Sentiment & Emotions' },
  { id:'trending',       icon:'📈', label:'Trending Topics' },
  { id:'network',        icon:'🔗', label:'Network Analysis' },
  { id:'ai',             icon:'✦', label:'AI Insights' },
  { id:'settings',       icon:'⚙', label:'Settings' },
];

function buildSidebar() {
  const nav   = $('sidebarNav');
  if (!nav) return;
  const items = state.mode === 'general' ? GENERAL_NAV : TOPIC_NAV;
  nav.innerHTML = items.map(item => `
    <button class="nav-item${state.currentPage === item.id ? ' active' : ''}"
            data-page="${item.id}" type="button">
      <span class="nav-icon">${item.icon}</span>
      ${esc(item.label)}
    </button>
  `).join('');
  nav.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => navigateTo(btn.dataset.page));
  });
}

function setActiveNav(page) {
  $('sidebarNav')?.querySelectorAll('.nav-item').forEach(b => {
    b.classList.toggle('active', b.dataset.page === page);
  });
}

/* ================================================================
   NAVIGATION ROUTER
   ================================================================ */

function navigateTo(page) {
  state.currentPage = page;
  setActiveNav(page);
  renderCurrentView();
}

function renderCurrentView() {
  if (!state.data) return;
  const page = state.currentPage;
  const d    = state.data;

  let title = 'Dashboard';
  const ca  = $('contentArea');
  if (!ca) return;

  switch (page) {
    case 'dashboard':
      title = state.mode === 'general' ? 'Social Media Overview' : 'Campaign Dashboard';
      if (state.mode === 'general') renderGeneralDashboard(ca, d);
      else renderTopicDashboard(ca, d);
      break;
    case 'analytics':
      title = 'Analytics'; renderAnalyticsPage(ca, d); break;
    case 'content':
      title = 'Content Intelligence'; renderContentPage(ca, d); break;
    case 'audience':
      title = 'Audience Demographics'; renderAudiencePage(ca, d); break;
    case 'sentiment':
      title = 'Sentiment & Emotions'; renderSentimentPage(ca, d); break;
    case 'trending':
      title = 'Trending Topics'; renderTrendingPage(ca, d); break;
    case 'network':
      title = 'Network Analysis'; renderNetworkPage(ca, d); break;
    case 'ai':
      title = 'AI Insights'; renderAIPage(ca, d); break;
    case 'settings':
      title = 'Settings'; renderSettingsPage(ca, d); break;
    case 'profile':
      title = 'Profile'; renderProfilePage(ca, d); break;
  }

  const pt = $('pageTitle');
  if (pt) pt.textContent = title;
}

function goBack() {
  if (state.currentPage !== 'dashboard') navigateTo('dashboard');
  else showModeSelect();
}

function selectDateRange(range) {
  state.dateRange = range;
  const lbl = $('dateFilterLabel');
  if (lbl) lbl.textContent = range;
  closeAllPopovers();
  loadData();
}

function selectChartPeriod(p) {
  state.chartPeriod = p;
  const lbl = $('chartPeriodLabel');
  if (lbl) lbl.textContent = p;
  loadData();
}

/* ================================================================
   CONTROLS SETUP
   ================================================================ */

function setupControls() {
  // Platform selector
  $('platformSelect')?.addEventListener('change', e => {
    state.platform = e.target.value;
    updatePlatformDot();
    checkPlatformNotice(state.platform);
    if (state.platform === 'All Platforms') {
      showAllPlatformsModal();
    } else if (state.platform === 'Instagram' || state.platform === 'Facebook' || state.platform === 'Twitter / X') {
      const cap = state.platformCapabilities ? state.platformCapabilities[state.platform] : null;
      if (!cap || cap.status === 'unavailable' || cap.status === 'not_configured') {
        showPlatformCapabilityModal(state.platform);
      }
    }
    loadData();
  });

  // Date filter popover
  $('dateFilterBtn')?.addEventListener('click', e => {
    const opts = ['Today','Last 7 Days','Last 30 Days','1 Year'];
    openPopover(e.currentTarget, `
      <div class="pop-section">Date Range</div>
      ${opts.map(o => `<button onclick="selectDateRange('${o}')">${o === state.dateRange ? '✓ ':''} ${o}</button>`).join('')}
    `, true);
  });

  // Chart period popover
  $('chartPeriodBtn')?.addEventListener('click', e => {
    const opts = ['Daily','Weekly','Monthly','Yearly'];
    openPopover(e.currentTarget, `
      <div class="pop-section">Chart Period</div>
      ${opts.map(o => `<button onclick="selectChartPeriod('${o}')">${o === state.chartPeriod ? '✓ ':''} ${o}</button>`).join('')}
    `, true);
  });

  // Notifications
  $('notifBtn')?.addEventListener('click', e => {
    openPopover(e.currentTarget, `
      <div class="pop-section">Notifications</div>
      ${state.data?.aiInsights?.filter(i=>i.type==='warning'||i.type==='alert').slice(0,3).map(i=>`
        <button>${i.icon} ${i.title}</button>`).join('') || '<button>No active alerts</button>'}
      <div class="pop-divider"></div>
      <button onclick="closeAllPopovers()">Clear All</button>
    `, true);
  });

  // Quick actions
  $('quickActionBtn')?.addEventListener('click', e => {
    openPopover(e.currentTarget, `
      <div class="pop-section">Quick Actions</div>
      <button onclick="loadData();closeAllPopovers();showToast('Refreshing…')">↻ Refresh</button>
      <button onclick="navigateTo('trending');closeAllPopovers()">📈 View Trends</button>
      <button onclick="navigateTo('network');closeAllPopovers()">🔗 Network Graph</button>
      <button onclick="navigateTo('settings');closeAllPopovers()">⚙ API & Credentials</button>
      <button onclick="exportReport();closeAllPopovers()">↓ Export Report</button>
      <div class="pop-divider"></div>
      <button onclick="showModeSelect();closeAllPopovers()">⇄ Switch Mode</button>
    `, true);
  });

  // Refresh button
  $('refreshBtn')?.addEventListener('click', () => { loadData(); showToast('Refreshing…'); });

  // Switch mode button
  $('switchModeBtn')?.addEventListener('click', () => showModeSelect());

  // Profile
  $('profileBtn')?.addEventListener('click', () => navigateTo('profile'));

  // Search
  $('searchInput')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      const q = e.target.value.trim();
      if (q && state.mode === 'topic') {
        state.campaign.topic = q;
        navigateTo('dashboard');
        loadData();
      } else if (q) {
        showToast(`Searching for: "${q}"`);
      }
    }
  });

  // Visibility change auto-refresh
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && state.view === 'app' && state.lastUpdated) {
      const elapsed = Date.now() - state.lastUpdated.getTime();
      if (elapsed >= AUTO_MS) {
        loadData();
      }
    }
  });

  // Global click outside to dismiss autocomplete
  document.addEventListener('click', e => {
    const box = $('topicAutocomplete');
    const input = $('topicInput');
    if (box && !box.contains(e.target) && e.target !== input) {
      hideAutocomplete();
    }
  });
}

/* ================================================================
   LOGIN SETUP
   ================================================================ */

function handleLogin(e) {
  if (e) e.preventDefault();
  const user = ($('loginUser')?.value || '').trim();
  const pass = ($('loginPass')?.value || '').trim();
  if (!user || !pass) {
    showToast('Please enter both username and password.');
    return;
  }
  state.username = user;
  const profileName = $('profileName');
  if (profileName) profileName.textContent = user;
  showToast(`Welcome back, ${user}!`);
  showModeSelect();
}

function togglePasswordVisibility() {
  const passInput = $('loginPass');
  const toggleBtn = $('togglePasswordBtn');
  if (!passInput || !toggleBtn) return;
  const isPass = passInput.type === 'password';
  passInput.type = isPass ? 'text' : 'password';
  toggleBtn.title = isPass ? 'Hide password' : 'Show password';
  toggleBtn.setAttribute('aria-label', isPass ? 'Hide password' : 'Show password');

  const showIcon = toggleBtn.querySelector('.eye-show');
  const hideIcon = toggleBtn.querySelector('.eye-hide');
  if (showIcon && hideIcon) {
    showIcon.classList.toggle('hidden', isPass);
    hideIcon.classList.toggle('hidden', !isPass);
  }
}

function setupLogin() {
  const form = $('loginForm');
  const btn = $('loginBtn');
  const toggleBtn = $('togglePasswordBtn');

  form?.addEventListener('submit', handleLogin);
  btn?.addEventListener('click', handleLogin);

  toggleBtn?.addEventListener('click', e => {
    e.preventDefault();
    e.stopPropagation();
    togglePasswordVisibility();
  });
}

function setupModeSelect() {
  $('modeGeneralBtn')?.addEventListener('click', () => showApp('general'));
  $('modeTopicBtn')?.addEventListener('click',   () => showApp('topic'));
  $('modeBackBtn')?.addEventListener('click',    () => showLogin());
}

/* ================================================================
   GLOBAL EXPORTS (Ensures inline onclick handlers resolve)
   ================================================================ */

window.navigateTo = navigateTo;
window.goBack = goBack;
window.selectDateRange = selectDateRange;
window.selectChartPeriod = selectChartPeriod;
window.showModeSelect = showModeSelect;
window.showLogin = showLogin;
window.loadData = loadData;
window.closeAllPopovers = closeAllPopovers;
window.showToast = showToast;
window.exportReport = exportReport;
window.applyTheme = applyTheme;
window.quickAnalyze = quickAnalyze;
window.selectSuggestion = selectSuggestion;
window.hideAutocomplete = hideAutocomplete;
window.togglePasswordVisibility = togglePasswordVisibility;
window.dismissPlatformNotice = dismissPlatformNotice;
window.showAllPlatformsModal = showAllPlatformsModal;
window.showPlatformCapabilityModal = showPlatformCapabilityModal;
window.closeAllPlatformsModal = closeAllPlatformsModal;
window.enableDemoData = enableDemoData;
window.disableDemoData = disableDemoData;
window.zoomTopology = zoomTopology;
window.resetTopologyZoom = resetTopologyZoom;
window.showCredentialHelpModal = showCredentialHelpModal;
window.handleSaveAndTest = handleSaveAndTest;
window.handleClearCredential = handleClearCredential;
window.selectActivityTimeline = selectActivityTimeline;
window.renderDynamicActivityComponent = renderDynamicActivityComponent;

/* ================================================================
   INITIALIZATION
   ================================================================ */

function init() {
  document.documentElement.dataset.theme = state.theme;

  setupLogin();
  setupModeSelect();
  setupControls();
  showLogin();

  // Restore session if user refreshed while in app
  const savedMode = sessionStorage.getItem('socialiq-mode');
  if (savedMode) {
    const savedUser = sessionStorage.getItem('socialiq-user');
    if (savedUser) { state.username = savedUser; const pn = $('profileName'); if (pn) pn.textContent = savedUser; }
    showApp(savedMode);
  }
}

window.addEventListener('beforeunload', () => {
  if (state.view === 'app') {
    sessionStorage.setItem('socialiq-mode', state.mode);
    sessionStorage.setItem('socialiq-user', state.username);
  } else {
    sessionStorage.removeItem('socialiq-mode');
  }
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeAllPopovers();
});

// Boot
init();
