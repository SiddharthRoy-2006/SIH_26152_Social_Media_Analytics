/* ================================================================
   SOCIALIQ ANALYTICS — Application Script v2.0
   SIH Problem Statement 26152
   ================================================================ */

'use strict';

/* ================================================================
   CONSTANTS
   ================================================================ */

const API_BASE  = 'http://127.0.0.1:8001';
const AUTO_MS   = 15 * 60 * 1000; // EXACTLY 15 minutes
const CHART_COLORS = ['#2563eb','#7c3aed','#059669','#d97706','#dc2626','#0284c7','#db2777','#ea580c'];
const EMOTION_COLORS = {
  happy:'#059669', excited:'#2563eb', supportive:'#0284c7', surprise:'#d97706',
  sad:'#7c3aed',   anxious:'#dc2626', angry:'#f87171',      opposition:'#9f1239',
  fear:'#92400e',  disgust:'#4b5563', sarcasm:'#6d28d9',    other:'#94a3b8',
};
const COMMUNITY_COLORS = ['#2563eb','#7c3aed','#059669','#d97706','#dc2626','#0284c7'];
const PLATFORM_COLORS  = {
  'Instagram':'#e1306c','YouTube':'#ff0000','Facebook':'#1877f2',
  'Twitter / X':'#000000','All Platforms':'#2563eb',
};

/* ================================================================
   STATE
   ================================================================ */

const state = {
  view:        'login',      // login | mode | app
  mode:        null,         // 'general' | 'topic'
  theme:       localStorage.getItem('socialiq-theme') || 'light',
  platform:    'All Platforms',
  dateRange:   'Last 30 Days',
  chartPeriod: 'Monthly',
  campaign:    { topic: '', query: '' },
  currentPage: 'dashboard',
  username:    'Analyst',
  backendOK:   false,
  dataAvail:   false,
  dataSource:  'none',
  lastUpdated: null,
  data:        null,         // normalised response for current mode
  raw:         null,         // raw backend JSON
  autoTimer:   null,
};

/* Apply saved theme immediately */
document.documentElement.dataset.theme = state.theme;

/* ================================================================
   UTILS
   ================================================================ */

const $ = id => document.getElementById(id);
const safe   = v => (v != null ? v : '');
const safeN  = (v, d=0) => { const n = parseFloat(v); return isNaN(n) ? d : n; };
const safeS  = (v, d='—') => (v != null && String(v).trim() !== '' ? String(v) : d);
const fmt    = n => n >= 1e9 ? (n/1e9).toFixed(1)+'B' : n >= 1e6 ? (n/1e6).toFixed(1)+'M' : n >= 1e3 ? (n/1e3).toFixed(1)+'K' : String(Math.round(n));
const fmtN   = n => Math.abs(n) >= 1e6 ? (n/1e6).toFixed(2)+'M' : Math.abs(n) >= 1e3 ? (n/1e3).toFixed(1)+'K' : String(n);
const pct    = n => safeN(n).toFixed(1)+'%';
const clamp  = (v,min,max) => Math.max(min, Math.min(max, v));
const esc    = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return 'GOOD MORNING';
  if (h < 17) return 'GOOD AFTERNOON';
  return 'GOOD EVENING';
}

/* ================================================================
   TOAST
   ================================================================ */

let _toastTimer;
function showToast(msg, dur=3000) {
  const el = $('toast');
  if (!el) return;
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove('show'), dur);
}

/* ================================================================
   POPOVER SYSTEM
   ================================================================ */

let _activePopover = null;
function closeAllPopovers() {
  const root = $('popoverRoot');
  if (root) {
    root.innerHTML = '';
    root.style.pointerEvents = 'none';
  }
  _activePopover = null;
}

function openPopover(anchorEl, contentHTML, alignRight=false) {
  closeAllPopovers();
  const root = $('popoverRoot');
  if (!root || !anchorEl) return;
  const rect = anchorEl.getBoundingClientRect();

  const backdrop = document.createElement('div');
  backdrop.className = 'popover-backdrop';
  backdrop.addEventListener('click', () => closeAllPopovers());

  const div = document.createElement('div');
  div.className = 'popover';
  div.style.top = (rect.bottom + window.scrollY + 6) + 'px';
  if (alignRight) {
    div.style.right = (window.innerWidth - rect.right) + 'px';
  } else {
    div.style.left = rect.left + 'px';
  }
  div.innerHTML = contentHTML;

  root.appendChild(backdrop);
  root.appendChild(div);
  root.style.pointerEvents = 'all';
  _activePopover = div;
}

/* ================================================================
   THEME
   ================================================================ */

function applyTheme(t) {
  state.theme = t;
  document.documentElement.dataset.theme = t;
  localStorage.setItem('socialiq-theme', t);
}

/* ================================================================
   DATA NORMALISATION
   Extends existing normalizer; all new fields are handled.
   ================================================================ */

function normalizePayload(source) {
  if (!source || typeof source !== 'object') return emptyData();
  const m = source.metrics  || {};
  const a = source.audience || {};
  const s = source.sentiment || {};
  const e = source.emotions  || {};
  const t = source.trending  || {};
  const n = source.network   || {};
  const ins = source.insights || {};

  return {
    /* Core */
    platform:        safeS(source.platform),
    topic:           safeS(source.topic,''),
    query:           safeS(source.query,''),
    period:          safeS(source.period),
    chartPeriod:     safeS(source.chart_period),
    dataAvailable:   !!source.data_available,
    source:          safeS(source.source,'empty'),
    mode:            safeS(source.mode,'topic'),
    refreshTick:     safeN(source.refresh_tick),

    /* Metrics (flat) */
    followers:     safeN(m.followers),
    reach:         safeN(m.reach),
    likes:         safeN(m.likes),
    comments:      safeN(m.comments),
    shares:        safeN(m.shares),
    contentVolume: safeN(m.content_volume || m.contentVolume),
    engagement:    safeN(m.engagement_rate || m.engagement),
    growth:        safeN(m.growth || m.growth_rate),

    /* Audience (legacy 4-bucket) */
    age18_24: safeN(a.age18_24),
    age25_34: safeN(a.age25_34),
    age35_44: safeN(a.age35_44),
    age45:    safeN(a.age45),

    /* Sentiment */
    sentPositive: safeN(s.positive),
    sentNegative: safeN(s.negative),
    sentNeutral:  safeN(s.neutral),

    /* Emotions (all keys, pass-through) */
    emotions: e,

    /* Trending (legacy) */
    trendTopic:    safeS(t.topic),
    trendKeyword:  safeS(t.keyword),
    trendTopics:   Array.isArray(t.topics)   ? t.topics   : [],
    trendKeywords: Array.isArray(t.keywords) ? t.keywords : [],

    /* Network (legacy) */
    netNodes:       safeN(n.nodes),
    netConnections: safeN(n.connections),
    netCommunities: safeN(n.communities),

    /* Activity */
    activity:     Array.isArray(source.activity)     ? source.activity     : [0,0,0,0,0],
    growthSeries: Array.isArray(source.growth_series) ? source.growth_series : [],

    /* Insights (legacy dict) */
    scoreStatus:   safeS(ins.score_status),
    scoreMsg:      safeS(ins.score_message),
    bestPostTime:  safeS(ins.best_posting_time),
    growthSignal:  safeS(ins.growth_signal),
    recommendation:safeS(ins.recommendation),
    activityWin:   safeS(ins.activity_window),

    /* Extended (new fields) */
    aiInsights:     Array.isArray(source.ai_insights)    ? source.ai_insights    : [],
    sentSeries:     Array.isArray(source.sentiment_series) ? source.sentiment_series : [],
    topTrends:      Array.isArray(source.top_trends)     ? source.top_trends     : [],
    influencers:    Array.isArray(source.influencers)    ? source.influencers    : [],
    networkGraph:   (source.network_graph && typeof source.network_graph === 'object') ? source.network_graph : {},
    geoDist:        (source.geo_distribution && typeof source.geo_distribution === 'object') ? source.geo_distribution : {},
    langDist:       (source.language_distribution && typeof source.language_distribution === 'object') ? source.language_distribution : {},
    interests:      (source.interest_segments && typeof source.interest_segments === 'object') ? source.interest_segments : {},
    activitySeries: Array.isArray(source.activity_series)   ? source.activity_series   : [],
    engageSeries:   Array.isArray(source.engagement_series)  ? source.engagement_series  : [],
  };
}

function emptyData() {
  return normalizePayload({
    platform:'—', topic:'', query:'', period:'—', chart_period:'—',
    data_available:false, source:'empty', mode:'topic',
    metrics:{}, audience:{}, sentiment:{}, emotions:{}, trending:{}, network:{}, insights:{},
    activity:[0,0,0,0,0], growth_series:[],
  });
}

/* ================================================================
   API LAYER
   ================================================================ */

let _isLoadingData = false;

async function loadData() {
  if (_isLoadingData) return;
  _isLoadingData = true;

  const refreshBtn = $('refreshBtn');
  if (refreshBtn) refreshBtn.classList.add('spinning');
  updateStatusBadge('connecting');

  try {
    let url;
    if (state.mode === 'general') {
      url = `${API_BASE}/general?platform=${encodeURIComponent(state.platform)}&period=${encodeURIComponent(state.dateRange)}&chart_period=${encodeURIComponent(state.chartPeriod)}`;
    } else {
      url = `${API_BASE}/analysis?topic=${encodeURIComponent(state.campaign.topic)}&query=${encodeURIComponent(state.campaign.query)}&platform=${encodeURIComponent(state.platform)}&period=${encodeURIComponent(state.dateRange)}&chart_period=${encodeURIComponent(state.chartPeriod)}`;
    }
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const json = await resp.json();
    state.raw  = json;
    state.data = normalizePayload(json);
    state.backendOK  = true;
    state.dataAvail  = state.data.dataAvailable;
    state.dataSource = state.data.source;
    state.lastUpdated = new Date();
    updateStatusBadge(state.dataAvail ? 'demo' : 'empty');
    renderCurrentView();
  } catch(err) {
    state.backendOK = false;
    state.data = emptyData();
    updateStatusBadge('offline');
    renderCurrentView();
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
  if (s === 'demo')       { badge.classList.add('demo');  text.textContent = 'Demo Data'; }
  else if (s === 'offline') { text.textContent = 'Offline'; }
  else if (s === 'connecting') { text.textContent = 'Loading…'; }
  else { text.textContent = 'No Data'; }
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

/* ================================================================
   VIEW MANAGEMENT
   ================================================================ */

function showLogin() {
  state.view = 'login';
  $('loginGate').classList.remove('hidden');
  $('modeGate').classList.add('hidden');
  $('appShell').classList.add('hidden');
  stopAutoRefresh();
}

function showModeSelect() {
  state.view = 'mode';
  $('loginGate').classList.add('hidden');
  $('modeGate').classList.remove('hidden');
  $('appShell').classList.add('hidden');
}

function showApp(mode) {
  state.mode = mode;
  state.view = 'app';
  $('loginGate').classList.add('hidden');
  $('modeGate').classList.add('hidden');
  $('appShell').classList.remove('hidden');

  // Apply mode defaults
  if (mode === 'general') {
    state.platform = 'All Platforms';
    state.currentPage = 'dashboard';
    $('platformSelect').value = 'All Platforms';
  } else {
    state.platform = 'Instagram';
    state.currentPage = 'dashboard';
    $('platformSelect').value = 'Instagram';
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
   NAVIGATION / PAGE ROUTING
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

  switch(page) {
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

/* ================================================================
   SVG CHART HELPERS
   ================================================================ */

function svgPath(points, closed=false) {
  if (!points.length) return '';
  const p = points.map((pt,i) => (i===0?'M':'L')+pt[0].toFixed(1)+' '+pt[1].toFixed(1)).join(' ');
  return closed ? p+' Z' : p;
}

function smoothPath(points) {
  if (points.length < 2) return svgPath(points);
  let d = `M ${points[0][0]} ${points[0][1]}`;
  for (let i=1; i<points.length; i++) {
    const p0 = points[i-1], p1 = points[i];
    const cpx = (p0[0]+p1[0])/2;
    d += ` C ${cpx} ${p0[1]}, ${cpx} ${p1[1]}, ${p1[0]} ${p1[1]}`;
  }
  return d;
}

/* ================================================================
   CHART: AREA CHART
   ================================================================ */

function renderAreaChart(container, series, labels, opts={}) {
  if (!series || !series.length) { container.innerHTML = '<div style="height:180px;display:flex;align-items:center;justify-content:center;color:var(--text-3);font-size:12px;">No data</div>'; return; }
  const W = 640, H = 180, PL = 48, PR = 16, PT = 12, PB = 28;
  const max = Math.max(...series, 1);
  const color = opts.color || '#2563eb';
  const n = series.length;
  const step = (W - PL - PR) / Math.max(n-1,1);

  const pts = series.map((v,i) => [PL + i*step, PT + (H-PT-PB) * (1 - v/max)]);
  const areaBottom = H - PB;

  const linePath = smoothPath(pts);
  const areaPath = `${linePath} L${pts[pts.length-1][0]} ${areaBottom} L${PL} ${areaBottom} Z`;

  const gradId = `ag_${Math.random().toString(36).slice(2,7)}`;
  const dotsHTML = pts.map(p => `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="3" fill="${color}"/>`).join('');

  container.innerHTML = `
    <div class="chart-wrap">
      <svg viewBox="0 0 ${W} ${H}" class="area-svg" preserveAspectRatio="none">
        <defs>
          <linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="${color}" stop-opacity="0.18"/>
            <stop offset="100%" stop-color="${color}" stop-opacity="0.01"/>
          </linearGradient>
        </defs>
        <path d="${areaPath}" fill="url(#${gradId})"/>
        <path d="${linePath}" fill="none" stroke="${color}" stroke-width="2.2" stroke-linejoin="round"/>
        ${dotsHTML}
      </svg>
      ${labels && labels.length ? `<div class="x-labels">${labels.map(l=>`<span>${esc(l)}</span>`).join('')}</div>` : ''}
    </div>`;
}

/* ================================================================
   CHART: DONUT
   ================================================================ */

function renderDonut(container, segments, size=130) {
  // segments: [{label, value, color}]
  const total = segments.reduce((s,d)=>s+d.value, 0) || 1;
  const R = size/2 - 20, cx = size/2, cy = size/2, SW = 22;
  const C = 2 * Math.PI * R;
  let offset = 0;

  const arcs = segments.map(seg => {
    const frac = seg.value / total;
    const dashLen = frac * C;
    const arc = { ...seg, dashLen, dashOffset: -(offset) };
    offset += dashLen;
    return arc;
  });

  const biggest = segments.reduce((a,b) => a.value>b.value?a:b, segments[0]);

  const svgStr = `
    <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
      <circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="var(--surface-2)" stroke-width="${SW}"/>
      ${arcs.map(a => `
        <circle cx="${cx}" cy="${cy}" r="${R}" fill="none"
          stroke="${a.color}" stroke-width="${SW}"
          stroke-dasharray="${a.dashLen.toFixed(2)} ${(C-a.dashLen).toFixed(2)}"
          stroke-dashoffset="${a.dashOffset.toFixed(2)}"
          transform="rotate(-90 ${cx} ${cy})"/>
      `).join('')}
      <text x="${cx}" y="${cy-6}" text-anchor="middle" font-size="17" font-weight="700" fill="var(--text)">${biggest.value}%</text>
      <text x="${cx}" y="${cy+10}" text-anchor="middle" font-size="10" fill="var(--text-3)">${esc(biggest.label)}</text>
    </svg>`;

  const legendStr = segments.map(s => `
    <div class="donut-item">
      <span class="donut-dot" style="background:${s.color}"></span>
      <span class="donut-lbl">${esc(s.label)}</span>
      <span class="donut-val">${s.value}%</span>
    </div>`).join('');

  container.innerHTML = `<div class="donut-wrap">${svgStr}<div class="donut-legend">${legendStr}</div></div>`;
}

/* ================================================================
   CHART: HORIZONTAL BAR
   ================================================================ */

function renderHBars(container, items, opts={}) {
  // items: [{label, value, color, max}]
  const maxVal = opts.maxVal || Math.max(...items.map(i=>i.value), 1);
  container.innerHTML = `
    <div class="hbar">
      ${items.map(item => {
        const pctW = clamp((item.value/maxVal)*100, 0, 100).toFixed(1);
        const color = item.color || CHART_COLORS[0];
        return `<div class="hbar-row">
          <span class="hbar-lbl">${esc(item.label)}</span>
          <div class="hbar-track"><div class="hbar-fill" style="width:${pctW}%;background:${color}"></div></div>
          <span class="hbar-val">${item.value}%</span>
        </div>`;
      }).join('')}
    </div>`;
}

/* ================================================================
   CHART: SCORE RING
   ================================================================ */

function renderScoreRing(container, score, opts={}) {
  const cx=65, cy=65, R=52, SW=10;
  const C = 2*Math.PI*R;
  const frac = clamp(score/100, 0, 1);
  const color = score >= 70 ? 'var(--success)' : score >= 40 ? 'var(--warning)' : 'var(--danger)';
  const label = opts.label || 'Score';
  const msg   = opts.msg   || '';
  container.innerHTML = `
    <div class="score-wrap">
      <svg class="score-svg" viewBox="0 0 130 130">
        <circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="var(--surface-2)" stroke-width="${SW}"/>
        <circle cx="${cx}" cy="${cy}" r="${R}" fill="none"
          stroke="${color}" stroke-width="${SW}"
          stroke-dasharray="${(frac*C).toFixed(2)} ${((1-frac)*C).toFixed(2)}"
          stroke-dashoffset="${(C/4).toFixed(2)}"
          transform="rotate(180 ${cx} ${cy})"
          stroke-linecap="round"/>
        <text x="${cx}" y="${cy-5}" text-anchor="middle" font-size="22" font-weight="700" fill="var(--text)">${score.toFixed(0)}</text>
        <text x="${cx}" y="${cy+12}" text-anchor="middle" font-size="11" fill="var(--text-3)">${esc(label)}</text>
      </svg>
      ${msg ? `<p class="score-msg">${esc(msg)}</p>` : ''}
    </div>`;
}

/* ================================================================
   ACTIVITY BARS
   ================================================================ */

const ACT_DAYS = ['Mon','Tue','Wed','Thu','Fri'];

function renderActivityBars(container, activity) {
  const max = Math.max(...activity, 1);
  container.innerHTML = `
    <div class="act-bars">
      ${activity.slice(0,5).map((v,i) => `
        <div class="act-row">
          <span class="act-day">${ACT_DAYS[i]}</span>
          <div class="act-track">
            <div class="act-fill" style="width:${clamp(v/max*100,0,100).toFixed(1)}%"></div>
          </div>
          <span class="act-val">${v}</span>
        </div>`).join('')}
    </div>`;
}

/* ================================================================
   GEO BARS
   ================================================================ */

function renderGeoBars(container, dist) {
  const entries = Object.entries(dist).sort((a,b)=>b[1]-a[1]).slice(0,8);
  const max = Math.max(...entries.map(e=>e[1]), 1);
  const colors = CHART_COLORS;
  container.innerHTML = `
    <div class="geo-list">
      ${entries.map(([name,val],i) => `
        <div class="geo-row">
          <span class="geo-name" title="${esc(name)}">${esc(name)}</span>
          <div class="geo-track">
            <div class="geo-fill" style="width:${clamp(val/max*100,0,100).toFixed(1)}%;background:${colors[i%colors.length]}"></div>
          </div>
          <span class="geo-pct">${val}%</span>
        </div>`).join('')}
    </div>`;
}

/* ================================================================
   TREND TABLE
   ================================================================ */

function renderTrendTable(container, trends, compact=false) {
  if (!trends || !trends.length) {
    container.innerHTML = '<p style="color:var(--text-3);font-size:13px;padding:12px;">No trend data available.</p>';
    return;
  }
  const inf_colors = COMMUNITY_COLORS;
  container.innerHTML = `
    <table class="trend-table">
      <thead>
        <tr>
          <th>#</th><th>Topic</th><th>Growth</th><th>Mentions</th>
          ${!compact ? '<th>Leading Influencer</th>' : ''}
        </tr>
      </thead>
      <tbody>
        ${trends.map((t,i) => {
          const dir   = t.direction === 'rising' ? 'r' : t.direction === 'falling' ? 'f' : 's';
          const arrow = dir === 'r' ? '↑' : dir === 'f' ? '↓' : '→';
          const initials = (t.influencer_name || 'U').split(' ').map(w=>w[0]).join('').slice(0,2).toUpperCase();
          const color = inf_colors[i % inf_colors.length];
          return `
            <tr>
              <td class="t-rank">${String(t.rank).padStart(2,'0')}</td>
              <td>
                <div class="t-name">${esc(t.name)}</div>
                <div class="t-kw">${esc(t.keyword||'')}</div>
              </td>
              <td>
                <span class="growth-badge ${dir}">${arrow} ${pct(t.growth_pct)}</span>
              </td>
              <td style="font-size:12px;color:var(--text-2);">${fmtN(t.mentions||0)}</td>
              ${!compact ? `
              <td>
                <div class="inf-chip">
                  <div class="inf-av" style="background:${color}">${esc(initials)}</div>
                  <div>
                    <div class="inf-n">${esc(t.influencer_name||'—')}</div>
                    <div class="inf-sc">${pct(safeN(t.influencer_score)*100)}</div>
                  </div>
                </div>
              </td>` : ''}
            </tr>`;
        }).join('')}
      </tbody>
    </table>`;
}

/* ================================================================
   INFLUENCER LIST
   ================================================================ */

function renderInfluencerList(container, influencers) {
  if (!influencers || !influencers.length) {
    container.innerHTML = '<p style="color:var(--text-3);font-size:13px;">No influencer data.</p>';
    return;
  }
  const colors = COMMUNITY_COLORS;
  container.innerHTML = `<div class="inf-list">${influencers.slice(0,8).map((inf,i) => {
    const initials = (inf.name||'U').split(' ').map(w=>w[0]).join('').slice(0,2).toUpperCase();
    const score    = clamp(safeN(inf.score)*100, 0, 100);
    const color    = colors[i % colors.length];
    return `<div class="inf-row">
      <span class="inf-rk">${inf.rank}</span>
      <div class="inf-big-av" style="background:${color}">${esc(initials)}</div>
      <div class="inf-info">
        <div class="n">${esc(inf.name||'—')}</div>
        <div class="c">${esc(inf.community||'—')}</div>
      </div>
      <div class="inf-score-col">
        <span class="inf-score-val">${score.toFixed(0)}</span>
        <div class="inf-score-trk"><div class="inf-score-fill" style="width:${score.toFixed(1)}%"></div></div>
      </div>
    </div>`;
  }).join('')}</div>`;
}

/* ================================================================
   AI INSIGHTS CARDS
   ================================================================ */

function renderAICards(container, insights, showAll=false) {
  if (!insights || !insights.length) {
    container.innerHTML = '<p style="color:var(--text-3);font-size:13px;">Generating insights…</p>';
    return;
  }
  const shown = showAll ? insights : insights.slice(0,5);
  container.innerHTML = `<div class="insights-list">${shown.map(ins => {
    const cls = ins.type === 'warning' ? 'warning' : ins.type === 'alert' ? 'alert' : ins.type === 'info' ? 'info' : '';
    return `<div class="insight-card ${cls}">
      <div class="ins-icon">${esc(ins.icon||'💡')}</div>
      <div class="ins-body">
        <div class="ins-title">${esc(ins.title||'Insight')}</div>
        <div class="ins-text">${esc(ins.text||'')}</div>
      </div>
    </div>`;
  }).join('')}</div>`;
}

/* ================================================================
   NETWORK GRAPH (Community Cluster Layout)
   ================================================================ */

function renderNetworkGraph(container, graphData, topic) {
  if (!graphData || !graphData.nodes || !graphData.nodes.length) {
    container.innerHTML = '<div style="height:320px;display:flex;align-items:center;justify-content:center;color:var(--text-3);font-size:13px;">No network data available.</div>';
    return;
  }

  const W=700, H=320, nodes = graphData.nodes, edges = graphData.edges || [], communities = graphData.communities || [];
  const n_comm = communities.length || 6;

  // Compute cluster-based layout
  const centers = communities.map((comm,ci) => {
    const angle = (2*Math.PI*ci/n_comm) - Math.PI/2;
    const r = Math.min(W,H)*0.30;
    return { id:comm.id, cx: W/2 + r*Math.cos(angle), cy: H/2 + r*Math.sin(angle), color:comm.color };
  });

  // Group nodes by community
  const byComm = {};
  nodes.forEach(node => {
    const cid = node.community;
    if (!byComm[cid]) byComm[cid] = [];
    byComm[cid].push(node);
  });

  // Position each node around its community center
  const posMap = {};
  Object.entries(byComm).forEach(([cid, cNodes]) => {
    const center = centers.find(c=>c.id===parseInt(cid)) || {cx:W/2,cy:H/2,color:'#2563eb'};
    const n = cNodes.length;
    cNodes.forEach((node,i) => {
      const angle = (2*Math.PI*i/Math.max(n,1));
      const r = node.is_hub ? 14 : 32 + (i%3)*10;
      posMap[node.id] = {
        x: clamp(center.cx + r*Math.cos(angle), 14, W-14),
        y: clamp(center.cy + r*Math.sin(angle), 14, H-14),
        color: node.color || center.color,
      };
    });
  });

  // Build edges SVG
  const edgesHTML = edges.map(e => {
    const s = posMap[e.source], t = posMap[e.target];
    if (!s || !t) return '';
    return `<line x1="${s.x.toFixed(1)}" y1="${s.y.toFixed(1)}" x2="${t.x.toFixed(1)}" y2="${t.y.toFixed(1)}"
      class="net-edge${e.type==='cross'?' cross':''}" stroke-width="${(safeN(e.weight)*1.5).toFixed(1)}"/>`;
  }).join('');

  // Build nodes SVG
  const nodesHTML = nodes.map(node => {
    const pos   = posMap[node.id] || {x:W/2,y:H/2,color:'#2563eb'};
    const r     = node.is_hub ? 8 + safeN(node.influence)*6 : 4 + safeN(node.influence)*5;
    const label = node.is_hub ? esc(node.label||'') : '';
    return `<g class="net-node${node.is_hub?' net-hub':''}"
        data-name="${esc(node.label||'')}"
        data-comm="${esc(node.community_label||'')}"
        data-score="${safeN(node.influence).toFixed(3)}"
        data-inf="${node.is_hub?'Hub':''}"
        style="cursor:pointer">
      <circle cx="${pos.x.toFixed(1)}" cy="${pos.y.toFixed(1)}" r="${r.toFixed(1)}"
        fill="${pos.color}" fill-opacity="${node.is_hub?'0.9':'0.65'}"/>
      ${node.is_hub && label ? `<text x="${pos.x.toFixed(1)}" y="${(pos.y+r+8).toFixed(1)}"
        text-anchor="middle" font-size="8" class="net-label" fill="var(--text-2)">${label}</text>` : ''}
    </g>`;
  }).join('');

  // Legend
  const legendHTML = communities.slice(0,6).map(c => `
    <div class="net-leg-item">
      <span class="net-leg-dot" style="background:${c.color}"></span>
      <span>${esc(c.label||'')}</span>
    </div>`).join('');

  container.innerHTML = `
    <div class="net-svg-wrap">
      <svg viewBox="0 0 ${W} ${H}" class="net-svg" style="height:320px">
        ${edgesHTML}
        ${nodesHTML}
      </svg>
    </div>
    <div class="net-legend">${legendHTML}</div>`;

  // Bind hover tooltips
  const tooltip = $('netTooltip');
  container.querySelectorAll('.net-node').forEach(el => {
    el.addEventListener('mouseenter', ev => {
      if (!tooltip) return;
      tooltip.innerHTML = `
        <div class="net-tt-name">${esc(el.dataset.name)}</div>
        <div class="net-tt-comm">${esc(el.dataset.comm)}</div>
        <div class="net-tt-score">Influence: ${(safeN(el.dataset.score)*100).toFixed(0)} ${el.dataset.inf}</div>`;
      tooltip.className = 'net-tooltip show';
      tooltip.style.top  = (ev.clientY + 14) + 'px';
      tooltip.style.left = (ev.clientX + 14) + 'px';
    });
    el.addEventListener('mouseleave', () => { if (tooltip) tooltip.className = 'net-tooltip'; });
    el.addEventListener('mousemove',  ev => {
      if (!tooltip) return;
      tooltip.style.top  = (ev.clientY + 14) + 'px';
      tooltip.style.left = (ev.clientX + 14) + 'px';
    });
  });
}

/* ================================================================
   PROPAGATION FLOW VISUALIZATION
   ================================================================ */

function renderPropagation(container, propagation, topic) {
  if (!propagation || !propagation.length) {
    container.innerHTML = '<p style="color:var(--text-3);font-size:13px;">No propagation data.</p>';
    return;
  }

  const W=700, H=160, n=propagation.length;
  const step = (W-60) / Math.max(n-1,1);
  const cy = H/2;

  const pts = propagation.map((p,i) => ({
    x: 30 + i*step,
    y: cy,
    r: 14 + (i/(n-1))*24,
    ...p,
  }));

  // Arrow marker
  const defs = `<defs>
    <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="var(--border-2)"/>
    </marker>
  </defs>`;

  // Lines
  const lines = pts.slice(0,-1).map((p,i) => {
    const next = pts[i+1];
    const gap  = next.x - p.x - p.r - next.r - 4;
    return `<line x1="${(p.x+p.r+2).toFixed(1)}" y1="${cy}" x2="${(p.x+gap+p.r+2).toFixed(1)}" y2="${cy}"
      stroke="var(--border-2)" stroke-width="1.5" marker-end="url(#arrow)"/>`;
  }).join('');

  // Circles + labels
  const circles = pts.map(p => {
    const initials = p.label.slice(0,2);
    return `
      <circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="${p.r.toFixed(1)}"
        fill="var(--accent)" fill-opacity="${0.2 + (p.step-1)*0.14}"/>
      <text x="${p.x.toFixed(1)}" y="${(p.y+1).toFixed(1)}" text-anchor="middle" dominant-baseline="middle"
        font-size="9" font-weight="700" fill="var(--accent)" class="prop-step-label">${esc(initials)}</text>
      <text x="${p.x.toFixed(1)}" y="${(p.y+p.r+10).toFixed(1)}" text-anchor="middle"
        font-size="8.5" fill="var(--text-2)" class="prop-step-label">${esc(p.label)}</text>
      <text x="${p.x.toFixed(1)}" y="${(p.y-p.r-5).toFixed(1)}" text-anchor="middle"
        font-size="10" font-weight="700" fill="var(--accent)">${p.pct_reached}%</text>`;
  }).join('');

  container.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" class="prop-svg" style="height:160px">
      ${defs}${lines}${circles}
    </svg>
    <div style="text-align:center;margin-top:6px;font-size:11px;color:var(--text-3)">
      Information propagation path for <strong>${esc(topic||'trending topic')}</strong>
    </div>`;
}

/* ================================================================
   PAGE: GENERAL DASHBOARD
   ================================================================ */

function renderGeneralDashboard(ca, d) {
  const reach = d.reach || 0;
  const eng   = d.engagement || 0;
  const pos   = d.sentPositive || 0;
  const ntopics = d.topTrends ? d.topTrends.length : 0;

  ca.innerHTML = `
    <div class="fade-in">
      <!-- Back btn -->
      <div style="margin-bottom:var(--gap);display:flex;justify-content:flex-end">
        <button class="back-btn" id="genBackBtn" type="button">← Back to Mode Selection</button>
      </div>

      <!-- Stats -->
      <div class="stats-grid">
        ${statCard('Total Reach', fmt(reach), 'ic-blue', '📡', `${d.growth>=0?'+':''}${pct(d.growth)} vs last period`, d.growth>=0)}
        ${statCard('Engagement Rate', pct(eng), 'ic-green', '💬', d.scoreStatus || 'Moderate engagement', true)}
        ${statCard('Positive Sentiment', pct(pos), 'ic-accent', '😊', `${d.sentNegative}% negative, ${d.sentNeutral}% neutral`, pos>=50)}
        ${statCard('Trending Topics', ntopics, 'ic-purple', '📈', 'Active topics tracked', true)}
      </div>

      <!-- Reach Over Time + Sentiment Donut -->
      <div class="grid-2-1">
        <div class="panel">
          <div class="panel-top">
            <div><div class="panel-label">ACTIVITY INTELLIGENCE</div><h2>Reach Over Time</h2></div>
          </div>
          <div id="g_areaChart"></div>
        </div>
        <div class="panel">
          <div class="panel-top">
            <div><div class="panel-label">SENTIMENT</div><h2>Sentiment Distribution</h2></div>
          </div>
          <div id="g_donut" style="margin-top:8px"></div>
        </div>
      </div>

      <!-- Emotions + Age Groups -->
      <div class="grid-1-1">
        <div class="panel">
          <div class="panel-top">
            <div><div class="panel-label">EMOTION ANALYSIS</div><h2>Emotion Distribution</h2></div>
          </div>
          <div id="g_emotions"></div>
        </div>
        <div class="panel">
          <div class="panel-top">
            <div><div class="panel-label">DEMOGRAPHICS</div><h2>Audience Age Groups</h2></div>
          </div>
          <div id="g_ageGroups"></div>
        </div>
      </div>

      <!-- Top 10 Trending Topics -->
      <div class="panel mb">
        <div class="panel-top">
          <div><div class="panel-label">REAL-TIME TREND INTELLIGENCE</div><h2>Top 10 Trending Topics</h2></div>
          <span class="sec-badge">Live</span>
        </div>
        <div id="g_trendTable"></div>
      </div>

      <!-- Influencer Rankings + Network Stats -->
      <div class="grid-1-1">
        <div class="panel">
          <div class="panel-top">
            <div><div class="panel-label">INFLUENTIAL USER DETECTION</div><h2>Top Influencers</h2></div>
          </div>
          <div id="g_influencers"></div>
        </div>
        <div class="panel">
          <div class="panel-top">
            <div><div class="panel-label">NETWORK TOPOLOGY</div><h2>Network Stats</h2></div>
          </div>
          <div id="g_netStats"></div>
        </div>
      </div>

      <!-- Geo + Language -->
      <div class="grid-1-1">
        <div class="panel">
          <div class="panel-top">
            <div><div class="panel-label">GEOGRAPHIC DISTRIBUTION</div><h2>Audience by Region</h2></div>
          </div>
          <div id="g_geo"></div>
        </div>
        <div class="panel">
          <div class="panel-top">
            <div><div class="panel-label">LANGUAGE DISTRIBUTION</div><h2>Audience by Language</h2></div>
          </div>
          <div id="g_lang"></div>
        </div>
      </div>

      <!-- AI Insights -->
      <div class="panel mb">
        <div class="panel-top">
          <div><div class="panel-label">AI INTELLIGENCE LAYER</div><h2>AI Insights & Alerts</h2></div>
          <button class="panel-action" id="g_refreshInsights">↻ Refresh</button>
        </div>
        <div id="g_aiInsights"></div>
      </div>

      <!-- Info Spread -->
      <div class="panel mb">
        <div class="panel-top">
          <div><div class="panel-label">INFORMATION SPREAD ANALYSIS</div><h2>Topic Propagation Path</h2></div>
        </div>
        <div id="g_propagation"></div>
      </div>

      <!-- Engagement over time -->
      <div class="panel mb">
        <div class="panel-top">
          <div><div class="panel-label">HISTORICAL INTELLIGENCE</div><h2>Engagement Over Time</h2></div>
        </div>
        <div id="g_engChart"></div>
      </div>

    </div>`;

  // Bind back button
  $('genBackBtn')?.addEventListener('click', () => showModeSelect());
  $('g_refreshInsights')?.addEventListener('click', () => { loadData(); showToast('Refreshing insights…'); });

  // Render sub-charts after DOM is ready
  requestAnimationFrame(() => {
    // Area chart
    const labels = d.growthSeries.length > 0 ? generateDateLabels(d.period, d.growthSeries.length) : [];
    renderAreaChart($('g_areaChart'), d.growthSeries, labels);

    // Donut
    renderDonut($('g_donut'), [
      { label:'Positive', value: d.sentPositive, color:'#059669' },
      { label:'Negative', value: d.sentNegative, color:'#dc2626' },
      { label:'Neutral',  value: d.sentNeutral,  color:'#94a3b8' },
    ]);

    // Emotions
    const emotionEntries = Object.entries(d.emotions).filter(([k,v])=>v>0).sort((a,b)=>b[1]-a[1]).slice(0,10);
    renderHBars($('g_emotions'), emotionEntries.map(([k,v]) => ({ label:capitalise(k), value:v, color:EMOTION_COLORS[k]||CHART_COLORS[0] })));

    // Age groups
    const ageDist = buildAgeDist(d);
    renderHBars($('g_ageGroups'), Object.entries(ageDist).map(([k,v],i) => ({ label:k, value:v, color:CHART_COLORS[i%CHART_COLORS.length] })));

    // Trend table (Top 10)
    renderTrendTable($('g_trendTable'), d.topTrends);

    // Influencer list
    renderInfluencerList($('g_influencers'), d.influencers);

    // Network stats
    renderNetworkStatsPanel($('g_netStats'), d);

    // Geo
    renderGeoBars($('g_geo'), d.geoDist);

    // Language
    renderGeoBars($('g_lang'), d.langDist);

    // AI Insights
    renderAICards($('g_aiInsights'), d.aiInsights, true);

    // Propagation
    const propData = d.networkGraph?.propagation || [];
    renderPropagation($('g_propagation'), propData, d.topTrends?.[0]?.name || 'Trending Topic');

    // Engagement chart
    const engLabels = generateDateLabels(d.period, d.engageSeries.length);
    renderAreaChart($('g_engChart'), d.engageSeries.map(v=>Math.round(v)), engLabels, { color:'#059669' });
  });
}

function renderNetworkStatsPanel(container, d) {
  if (!container) return;
  const graph = d.networkGraph;
  const stats = graph?.stats || {};
  const comms = graph?.communities || [];
  const topComm = comms.sort((a,b)=>b.node_count-a.node_count)[0];
  container.innerHTML = `
    <div class="info-cards" style="grid-template-columns:repeat(2,1fr)">
      <div class="info-card">
        <span class="info-lbl">Total Nodes</span>
        <div class="info-val">${stats.total_nodes || d.netNodes}</div>
        <div class="info-sub">Users / entities</div>
      </div>
      <div class="info-card">
        <span class="info-lbl">Connections</span>
        <div class="info-val">${stats.total_edges || d.netConnections}</div>
        <div class="info-sub">Active links</div>
      </div>
      <div class="info-card">
        <span class="info-lbl">Communities</span>
        <div class="info-val">${stats.n_communities || d.netCommunities}</div>
        <div class="info-sub">Distinct clusters</div>
      </div>
      <div class="info-card">
        <span class="info-lbl">Network Density</span>
        <div class="info-val">${((stats.density||0)*100).toFixed(2)}%</div>
        <div class="info-sub">Connectivity ratio</div>
      </div>
    </div>
    ${topComm ? `<div style="margin-top:10px;padding:12px;background:var(--surface-2);border-radius:var(--r-md);font-size:13px">
      <span style="color:var(--text-3);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px">Largest Community</span><br>
      <strong>${esc(topComm.label)}</strong> · ${topComm.node_count} members<br>
      <span style="color:var(--text-3)">Top influencer: ${esc(topComm.top_influencer)}</span>
    </div>` : ''}`;
}

/* ================================================================
   PAGE: TOPIC DASHBOARD
   ================================================================ */

function renderTopicDashboard(ca, d) {
  ca.innerHTML = `
    <div class="fade-in">
      <!-- Back btn -->
      <div style="margin-bottom:var(--gap);display:flex;justify-content:flex-end">
        <button class="back-btn" id="topicBackBtn" type="button">← Back to Mode Selection</button>
      </div>

      <!-- Campaign Panel -->
      <div class="campaign-panel">
        <h2>Campaign / Topic Analysis</h2>
        <div class="campaign-fields">
          <div class="camp-field">
            <label for="topicInput">Topic or Campaign</label>
            <input id="topicInput" type="text" placeholder="e.g. AI in Education, NEP 2020, Digital India…"
              value="${esc(state.campaign.topic)}" maxlength="120">
          </div>
          <div class="camp-field">
            <label for="queryInput">Optional Query Refinement</label>
            <input id="queryInput" type="text" placeholder="e.g. impact, sentiments, debate…"
              value="${esc(state.campaign.query)}" maxlength="120">
          </div>
          <button class="analyze-btn" id="analyzeBtn" type="button">→ Analyze</button>
        </div>
        ${d.dataAvailable && d.topic ? `<div class="camp-ctx">
          Showing results for <strong>${esc(d.topic)}</strong> on <strong>${esc(d.platform)}</strong> · ${esc(d.period)} · Auto-refreshes every 15 min
        </div>` : '<div class="camp-ctx">Enter a topic above and click Analyze to generate intelligence.</div>'}
      </div>

      ${!d.dataAvailable ? `<div style="text-align:center;padding:40px 20px;color:var(--text-3);font-size:14px">
        <div style="font-size:32px;margin-bottom:12px">📊</div>
        <div>Enter a topic to generate intelligence, or run the backend in <code>demo</code> mode.</div>
      </div>` : `
      <!-- Stats -->
      <div class="stats-grid">
        ${statCard('Total Reach',     fmt(d.reach),      'ic-blue',  '📡', `${d.growth>=0?'+':''}${pct(d.growth)} vs prev`, d.growth>=0)}
        ${statCard('Total Likes',     fmt(d.likes),      'ic-red',   '♥', `${fmt(d.shares)} shares`, true)}
        ${statCard('Comments',        fmt(d.comments),   'ic-green',  '💬', `${fmt(d.contentVolume)} posts published`, true)}
        ${statCard('Engagement Rate', pct(d.engagement), 'ic-purple', '✦', d.scoreStatus || 'Engagement quality', d.engagement>=5)}
      </div>

      <!-- Area Chart + Score Ring -->
      <div class="grid-2-1">
        <div class="panel">
          <div class="panel-top">
            <div><div class="panel-label">REACH INTELLIGENCE</div><h2>Reach Over Time</h2></div>
            <div style="display:flex;gap:6px">
              ${['Daily','Weekly','Monthly','Yearly'].map(p=>`
                <button class="theme-btn${state.chartPeriod===p?' active':''}" style="font-size:11px;padding:4px 10px"
                  onclick="selectChartPeriod('${p}')">${p}</button>`).join('')}
            </div>
          </div>
          <div id="t_areaChart"></div>
        </div>
        <div class="panel">
          <div class="panel-top">
            <div><div class="panel-label">ENGAGEMENT</div><h2>Score</h2></div>
          </div>
          <div id="t_scoreRing"></div>
        </div>
      </div>

      <!-- Activity + AI Preview -->
      <div class="grid-1-1">
        <div class="panel">
          <div class="panel-top">
            <div><div class="panel-label">WEEKLY ACTIVITY</div><h2>Activity by Day</h2></div>
          </div>
          <div id="t_actBars"></div>
        </div>
        <div class="panel">
          <div class="panel-top">
            <div><div class="panel-label">AI INTELLIGENCE</div><h2>Quick Insights</h2></div>
            <button class="panel-action" onclick="navigateTo('ai')">View All →</button>
          </div>
          <div id="t_aiPreview"></div>
        </div>
      </div>

      <!-- Trending Preview -->
      <div class="panel mb">
        <div class="panel-top">
          <div><div class="panel-label">TRENDING TOPICS</div><h2>Top Trends for "${esc(d.topic)}"</h2></div>
          <button class="panel-action" onclick="navigateTo('trending')">Full Table →</button>
        </div>
        <div id="t_trendPreview"></div>
      </div>
      `}
    </div>`;

  // Bind back & analyze
  $('topicBackBtn')?.addEventListener('click', () => showModeSelect());
  $('analyzeBtn')?.addEventListener('click', () => {
    const t = $('topicInput')?.value.trim() || '';
    const q = $('queryInput')?.value.trim() || '';
    state.campaign = { topic:t, query:q };
    loadData();
    showToast(`Analyzing "${t || 'All Topics'}"…`);
  });

  if (!d.dataAvailable) return;

  requestAnimationFrame(() => {
    const labels = generateDateLabels(d.period, d.growthSeries.length);
    renderAreaChart($('t_areaChart'), d.growthSeries, labels);

    const ringScore = clamp(d.engagement * 5, 0, 100);
    renderScoreRing($('t_scoreRing'), ringScore, { label:'Engagement', msg: d.scoreMsg });

    renderActivityBars($('t_actBars'), d.activity);
    renderAICards($('t_aiPreview'), d.aiInsights.slice(0,3));
    renderTrendTable($('t_trendPreview'), d.topTrends.slice(0,5), true);
  });
}

/* ================================================================
   PAGE: SENTIMENT & EMOTIONS
   ================================================================ */

function renderSentimentPage(ca, d) {
  ca.innerHTML = `
    <div class="fade-in">
      <div class="page-header">
        <div class="page-header-info">
          <div class="panel-label">SENTIMENT INTELLIGENCE</div>
          <h2>Sentiment & Emotion Analysis</h2>
          <p>Simulated sentiment classification across social media content${d.topic ? ` for "${esc(d.topic)}"` : ''}.</p>
        </div>
        <button class="back-btn" onclick="goBack()">← Back</button>
      </div>

      <div class="grid-1-1">
        <div class="panel">
          <div class="panel-top"><div><div class="panel-label">SENTIMENT</div><h2>Sentiment Distribution</h2></div></div>
          <div id="s_donut"></div>
          <div class="info-cards" style="grid-template-columns:repeat(3,1fr);margin-top:14px">
            ${[['Positive',d.sentPositive,'var(--success)'],['Negative',d.sentNegative,'var(--danger)'],['Neutral',d.sentNeutral,'var(--text-3)']].map(([l,v,c])=>`
              <div class="info-card" style="text-align:center">
                <span class="info-lbl">${l}</span>
                <div class="info-val" style="color:${c}">${v}%</div>
              </div>`).join('')}
          </div>
        </div>
        <div class="panel">
          <div class="panel-top"><div><div class="panel-label">EMOTIONS</div><h2>Emotion Breakdown</h2></div></div>
          <div id="s_emotions"></div>
        </div>
      </div>

      <div class="panel mb">
        <div class="panel-top">
          <div><div class="panel-label">HISTORICAL SENTIMENT</div><h2>Sentiment Trend Over Time</h2></div>
        </div>
        <div id="s_sentTrend"></div>
        <div class="x-labels" id="s_xLabels" style="margin-top:5px"></div>
      </div>

      <div class="grid-1-1">
        <div class="panel">
          <div class="panel-top"><div><div class="panel-label">CONTEXT</div><h2>Sentiment by Keyword</h2></div></div>
          <div class="tag-cloud" style="margin-top:4px">
            ${(d.trendKeywords||[]).slice(0,10).map((kw,i)=>`<span class="tag" style="border-color:${i%3===0?'var(--success)':i%3===1?'var(--danger)':'var(--text-3)'}">
              ${esc(kw)}</span>`).join('')}
          </div>
        </div>
        <div class="panel">
          <div class="panel-top"><div><div class="panel-label">IMPACT</div><h2>Dominant Emotion</h2></div></div>
          ${(() => {
            const top = Object.entries(d.emotions).sort((a,b)=>b[1]-a[1])[0];
            const color = top ? (EMOTION_COLORS[top[0]] || '#2563eb') : '#2563eb';
            return `<div style="text-align:center;padding:20px 0">
              <div style="font-size:40px;margin-bottom:8px">${emotionEmoji(top?.[0]||'')}</div>
              <div style="font-size:20px;font-weight:700;color:${color}">${capitalise(top?.[0]||'—')}</div>
              <div style="font-size:13px;color:var(--text-3);margin-top:4px">${top?.[1]||0}% of content</div>
            </div>`;
          })()}
        </div>
      </div>
    </div>`;

  requestAnimationFrame(() => {
    renderDonut($('s_donut'), [
      { label:'Positive', value:d.sentPositive, color:'#059669' },
      { label:'Negative', value:d.sentNegative, color:'#dc2626' },
      { label:'Neutral',  value:d.sentNeutral,  color:'#94a3b8' },
    ]);

    const emotionItems = Object.entries(d.emotions).filter(([k,v])=>v>0)
      .sort((a,b)=>b[1]-a[1]).slice(0,11)
      .map(([k,v]) => ({ label:capitalise(k), value:v, color:EMOTION_COLORS[k]||CHART_COLORS[0] }));
    renderHBars($('s_emotions'), emotionItems);

    const labels = generateDateLabels(d.period, d.sentSeries.length);
    renderAreaChart($('s_sentTrend'), d.sentSeries, labels, { color:'#059669' });
  });
}

/* ================================================================
   PAGE: AUDIENCE DEMOGRAPHICS
   ================================================================ */

function renderAudiencePage(ca, d) {
  const ageDist = buildAgeDist(d);
  ca.innerHTML = `
    <div class="fade-in">
      <div class="page-header">
        <div class="page-header-info">
          <div class="panel-label">DEMOGRAPHIC PROFILING</div>
          <h2>Audience Demographics</h2>
          <p>Aggregate anonymised audience intelligence — no personal identification.</p>
        </div>
        <button class="back-btn" onclick="goBack()">← Back</button>
      </div>

      <div class="grid-1-1">
        <div class="panel">
          <div class="panel-top"><div><div class="panel-label">AGE DISTRIBUTION</div><h2>Audience Age Groups</h2></div></div>
          <div id="a_age"></div>
        </div>
        <div class="panel">
          <div class="panel-top"><div><div class="panel-label">GEOGRAPHIC</div><h2>Top Regions</h2></div></div>
          <div id="a_geo"></div>
        </div>
      </div>

      <div class="grid-1-1">
        <div class="panel">
          <div class="panel-top"><div><div class="panel-label">LANGUAGE</div><h2>Audience Language</h2></div></div>
          <div id="a_lang"></div>
        </div>
        <div class="panel">
          <div class="panel-top"><div><div class="panel-label">INTERESTS</div><h2>Interest Segments</h2></div></div>
          <div id="a_interests"></div>
        </div>
      </div>

      <div class="panel mb">
        <div class="panel-top"><div><div class="panel-label">AUDIENCE OVERVIEW</div><h2>Key Demographics</h2></div></div>
        <div class="info-cards">
          <div class="info-card"><span class="info-lbl">Total Reach</span><div class="info-val">${fmt(d.reach)}</div><div class="info-sub">Estimated audience</div></div>
          <div class="info-card"><span class="info-lbl">Followers</span><div class="info-val">${fmt(d.followers)}</div><div class="info-sub">Across platform</div></div>
          <div class="info-card"><span class="info-lbl">Age 18–34</span><div class="info-val">${d.age18_24+d.age25_34}%</div><div class="info-sub">Core demographic</div></div>
          <div class="info-card"><span class="info-lbl">Engagement</span><div class="info-val">${pct(d.engagement)}</div><div class="info-sub">Active audience rate</div></div>
        </div>
      </div>
    </div>`;

  requestAnimationFrame(() => {
    renderHBars($('a_age'), Object.entries(ageDist).map(([k,v],i)=>({label:k, value:v, color:CHART_COLORS[i%CHART_COLORS.length]})));
    renderGeoBars($('a_geo'), d.geoDist);
    renderGeoBars($('a_lang'), d.langDist);
    renderHBars($('a_interests'), Object.entries(d.interests).sort((a,b)=>b[1]-a[1]).map(([k,v],i)=>({label:k, value:v, color:CHART_COLORS[i%CHART_COLORS.length]})));
  });
}

/* ================================================================
   PAGE: TRENDING TOPICS
   ================================================================ */

function renderTrendingPage(ca, d) {
  ca.innerHTML = `
    <div class="fade-in">
      <div class="page-header">
        <div class="page-header-info">
          <div class="panel-label">REAL-TIME TREND DETECTION</div>
          <h2>Trending Topics</h2>
          <p>Emerging topics and keywords ranked by growth score — auto-refreshed periodically.</p>
        </div>
        <button class="back-btn" onclick="goBack()">← Back</button>
      </div>

      <!-- Trend stats -->
      <div class="info-cards mb" style="grid-template-columns:repeat(4,1fr)">
        <div class="info-card"><span class="info-lbl">Total Trends</span><div class="info-val">${d.topTrends.length}</div></div>
        <div class="info-card"><span class="info-lbl">Top Growth</span><div class="info-val tc-green">↑${d.topTrends[0]?.growth_pct?.toFixed(0)||0}%</div></div>
        <div class="info-card"><span class="info-lbl">Top Mentions</span><div class="info-val">${fmtN(d.topTrends[0]?.mentions||0)}</div></div>
        <div class="info-card"><span class="info-lbl">Leading Topic</span><div class="info-val" style="font-size:13px">${esc(d.topTrends[0]?.name||'—')}</div></div>
      </div>

      <!-- Full Table -->
      <div class="panel mb">
        <div class="panel-top">
          <div><div class="panel-label">TREND RANKINGS</div><h2>Top 10 Trending Topics with Influencers</h2></div>
        </div>
        <div id="trend_table"></div>
      </div>

      <!-- Keywords -->
      <div class="panel mb">
        <div class="panel-top"><div><div class="panel-label">TRENDING KEYWORDS</div><h2>Hot Keywords & Hashtags</h2></div></div>
        <div class="tag-cloud">
          ${(d.trendKeywords||[]).concat(d.topTrends.map(t=>t.keyword||'')).filter(Boolean).slice(0,20).map((kw,i)=>`
            <span class="tag" style="border-color:${CHART_COLORS[i%CHART_COLORS.length]};color:${CHART_COLORS[i%CHART_COLORS.length]}">${esc(kw)}</span>`).join('')}
        </div>
      </div>

      <!-- Growth chart -->
      <div class="panel mb">
        <div class="panel-top"><div><div class="panel-label">TREND VELOCITY</div><h2>Topic Activity Over Time</h2></div></div>
        <div id="trend_chart"></div>
      </div>
    </div>`;

  requestAnimationFrame(() => {
    renderTrendTable($('trend_table'), d.topTrends);
    const actSeries = d.activitySeries.length ? d.activitySeries : d.growthSeries;
    renderAreaChart($('trend_chart'), actSeries, generateDateLabels(d.period, actSeries.length), { color:'#7c3aed' });
  });
}

/* ================================================================
   PAGE: NETWORK ANALYSIS
   ================================================================ */

function renderNetworkPage(ca, d) {
  ca.innerHTML = `
    <div class="fade-in">
      <div class="page-header">
        <div class="page-header-info">
          <div class="panel-label">LINK ANALYSIS & NETWORK TOPOLOGY</div>
          <h2>Network Analysis</h2>
          <p>Social network graph — nodes are entities, edges are interactions. Size = influence score.</p>
        </div>
        <button class="back-btn" onclick="goBack()">← Back</button>
      </div>

      <!-- Stats row -->
      <div class="info-cards mb" style="grid-template-columns:repeat(4,1fr)">
        <div class="info-card"><span class="info-lbl">Total Nodes</span><div class="info-val">${d.netNodes}</div><div class="info-sub">Users / entities</div></div>
        <div class="info-card"><span class="info-lbl">Connections</span><div class="info-val">${d.netConnections}</div><div class="info-sub">Active links</div></div>
        <div class="info-card"><span class="info-lbl">Communities</span><div class="info-val">${d.netCommunities}</div><div class="info-sub">Distinct clusters</div></div>
        <div class="info-card"><span class="info-lbl">Top Influencer</span><div class="info-val" style="font-size:13px">${esc(d.influencers?.[0]?.name||'—')}</div></div>
      </div>

      <!-- Network Graph -->
      <div class="panel mb">
        <div class="panel-top">
          <div><div class="panel-label">NETWORK GRAPH</div><h2>Social Network Topology</h2></div>
          <span class="sec-badge" style="background:var(--accent-light);color:var(--accent)">Hover nodes for details</span>
        </div>
        <div id="net_graph"></div>
      </div>

      <!-- Influencer rankings + Propagation -->
      <div class="grid-1-1">
        <div class="panel">
          <div class="panel-top"><div><div class="panel-label">INFLUENTIAL USER DETECTION</div><h2>Top Influencers by Score</h2></div></div>
          <div id="net_influencers"></div>
        </div>
        <div class="panel">
          <div class="panel-top"><div><div class="panel-label">COMMUNITY STRUCTURE</div><h2>Community Breakdown</h2></div></div>
          <div id="net_communities"></div>
        </div>
      </div>

      <!-- Information Spread -->
      <div class="panel mb">
        <div class="panel-top">
          <div><div class="panel-label">INFORMATION SPREAD ANALYSIS</div><h2>Topic Propagation Through Network</h2></div>
        </div>
        <div id="net_spread"></div>
      </div>
    </div>`;

  requestAnimationFrame(() => {
    renderNetworkGraph($('net_graph'), d.networkGraph, d.topic || 'Trending Narrative');
    renderInfluencerList($('net_influencers'), d.influencers);
    renderCommunityBreakdown($('net_communities'), d.networkGraph?.communities || []);
    renderPropagation($('net_spread'), d.networkGraph?.propagation || [], d.topic || 'Trending Topic');
  });
}

function renderCommunityBreakdown(container, communities) {
  if (!container || !communities.length) return;
  container.innerHTML = `<div style="display:flex;flex-direction:column;gap:9px">${communities.map(c => `
    <div style="display:flex;align-items:center;gap:10px">
      <span style="width:10px;height:10px;border-radius:50%;background:${c.color};flex-shrink:0"></span>
      <span style="flex:1;font-size:13px;font-weight:500">${esc(c.label)}</span>
      <span style="font-size:12px;color:var(--text-3)">${c.node_count} nodes</span>
      <div style="width:60px;height:4px;background:var(--surface-2);border-radius:99px;overflow:hidden">
        <div style="width:${c.avg_influence*100}%;height:100%;background:${c.color};border-radius:99px"></div>
      </div>
    </div>`).join('')}</div>`;
}

/* ================================================================
   PAGE: AI INSIGHTS
   ================================================================ */

function renderAIPage(ca, d) {
  const warnings = d.aiInsights.filter(i=>i.type==='warning'||i.type==='alert');
  ca.innerHTML = `
    <div class="fade-in">
      <div class="page-header">
        <div class="page-header-info">
          <div class="panel-label">AI INTELLIGENCE LAYER</div>
          <h2>AI Insights & Alerts</h2>
          <p>Data-driven simulation intelligence — generated from current analytics${d.topic?` for "${esc(d.topic)}"`:''}.
             ${warnings.length > 0 ? `<strong class="tc-red"> ${warnings.length} alert${warnings.length>1?'s':''} active.</strong>` : ''}</p>
        </div>
        <button class="back-btn" onclick="goBack()">← Back</button>
      </div>

      ${warnings.length ? `
      <div class="panel mb" style="border-color:var(--danger);background:var(--danger-bg)">
        <div class="panel-top">
          <div><div class="panel-label">⚠ ALERTS</div><h2>Active Warnings & Alerts</h2></div>
        </div>
        <div id="ai_warnings"></div>
      </div>` : ''}

      <div class="panel mb">
        <div class="panel-top">
          <div><div class="panel-label">BASELINE INTELLIGENCE</div><h2>Current Intelligence Summary</h2></div>
          <button class="panel-action" onclick="loadData();showToast('Refreshing insights…')">↻ Refresh</button>
        </div>
        <div id="ai_baseline"></div>
      </div>

      <div class="panel mb">
        <div class="panel-top"><div><div class="panel-label">DATA CONTEXT</div><h2>Underlying Metrics</h2></div></div>
        <div class="info-cards">
          <div class="info-card"><span class="info-lbl">Reach</span><div class="info-val">${fmt(d.reach)}</div></div>
          <div class="info-card"><span class="info-lbl">Growth</span><div class="info-val ${d.growth>=0?'tc-green':'tc-red'}">${d.growth>=0?'+':''}${pct(d.growth)}</div></div>
          <div class="info-card"><span class="info-lbl">Engagement</span><div class="info-val">${pct(d.engagement)}</div></div>
          <div class="info-card"><span class="info-lbl">Positive Sent.</span><div class="info-val tc-green">${d.sentPositive}%</div></div>
          <div class="info-card"><span class="info-lbl">Negative Sent.</span><div class="info-val tc-red">${d.sentNegative}%</div></div>
          <div class="info-card"><span class="info-lbl">Top Trend</span><div class="info-val" style="font-size:13px">${esc(d.topTrends?.[0]?.name||'—')}</div></div>
        </div>
      </div>

      <div class="panel mb">
        <div class="panel-top"><div><div class="panel-label">POSTING STRATEGY</div><h2>Recommended Actions</h2></div></div>
        <div style="display:flex;flex-direction:column;gap:10px;padding:4px 0">
          <div style="display:flex;gap:12px;align-items:flex-start">
            <span style="font-size:18px">⏰</span>
            <div><div style="font-size:13px;font-weight:600;color:var(--text)">Optimal Posting Time</div>
            <div style="font-size:12px;color:var(--text-2)">${esc(d.bestPostTime)}</div></div>
          </div>
          <div style="display:flex;gap:12px;align-items:flex-start">
            <span style="font-size:18px">📅</span>
            <div><div style="font-size:13px;font-weight:600;color:var(--text)">Most Active Window</div>
            <div style="font-size:12px;color:var(--text-2)">${esc(d.activityWin)}</div></div>
          </div>
          <div style="display:flex;gap:12px;align-items:flex-start">
            <span style="font-size:18px">💡</span>
            <div><div style="font-size:13px;font-weight:600;color:var(--text)">Recommendation</div>
            <div style="font-size:12px;color:var(--text-2)">${esc(d.recommendation)}</div></div>
          </div>
        </div>
      </div>

      <div style="margin-top:8px;padding:12px 14px;background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r-md);font-size:11.5px;color:var(--text-3)">
        ℹ The AI Insights module uses a lightweight data-driven simulation layer operating on demo data. In production, this would connect to trained NLP/ML models and real social-media API streams.
      </div>
    </div>`;

  requestAnimationFrame(() => {
    if (warnings.length) renderAICards($('ai_warnings'), warnings, true);
    const baseline = d.aiInsights.filter(i=>i.type!=='warning'&&i.type!=='alert');
    renderAICards($('ai_baseline'), baseline, true);
  });
}

/* ================================================================
   PAGE: ANALYTICS
   ================================================================ */

function renderAnalyticsPage(ca, d) {
  ca.innerHTML = `
    <div class="fade-in">
      <div class="page-header">
        <div class="page-header-info">
          <div class="panel-label">DEEP ANALYTICS</div>
          <h2>Analytics</h2>
          <p>In-depth performance metrics${d.topic?` for "${esc(d.topic)}"`:''} on ${esc(d.platform)}.</p>
        </div>
        <button class="back-btn" onclick="goBack()">← Back</button>
      </div>

      <div class="stats-grid">
        ${statCard('Followers', fmt(d.followers), 'ic-blue', '👥', 'Total followers', true)}
        ${statCard('Reach', fmt(d.reach), 'ic-accent', '📡', 'Estimated impressions', d.growth>=0)}
        ${statCard('Likes', fmt(d.likes), 'ic-red', '♥', 'Content interactions', true)}
        ${statCard('Shares', fmt(d.shares), 'ic-green', '↗', 'Shares & retweets', true)}
      </div>

      <div class="grid-2-1">
        <div class="panel">
          <div class="panel-top"><div><div class="panel-label">REACH OVER TIME</div><h2>Audience Growth</h2></div></div>
          <div id="an_area"></div>
        </div>
        <div class="panel">
          <div class="panel-top"><div><div class="panel-label">ENGAGEMENT</div><h2>Engagement Score</h2></div></div>
          <div id="an_ring"></div>
        </div>
      </div>

      <div class="grid-1-1">
        <div class="panel">
          <div class="panel-top"><div><div class="panel-label">ENGAGEMENT OVER TIME</div><h2>Engagement Rate Trend</h2></div></div>
          <div id="an_engChart"></div>
        </div>
        <div class="panel">
          <div class="panel-top"><div><div class="panel-label">CONTENT</div><h2>Content Activity</h2></div></div>
          <div class="info-cards" style="grid-template-columns:1fr 1fr;margin-top:4px">
            <div class="info-card"><span class="info-lbl">Posts Published</span><div class="info-val">${d.contentVolume}</div></div>
            <div class="info-card"><span class="info-lbl">Comments</span><div class="info-val">${fmt(d.comments)}</div></div>
            <div class="info-card"><span class="info-lbl">Growth Rate</span><div class="info-val ${d.growth>=0?'tc-green':'tc-red'}">${d.growth>=0?'+':''}${pct(d.growth)}</div></div>
            <div class="info-card"><span class="info-lbl">Best Post Time</span><div class="info-val" style="font-size:13px">${esc(d.bestPostTime)}</div></div>
          </div>
        </div>
      </div>
    </div>`;

  requestAnimationFrame(() => {
    renderAreaChart($('an_area'), d.growthSeries, generateDateLabels(d.period, d.growthSeries.length));
    renderScoreRing($('an_ring'), clamp(d.engagement*5,0,100), { label:'Engagement', msg:d.scoreMsg });
    renderAreaChart($('an_engChart'), d.engageSeries.map(v=>Math.round(v)), generateDateLabels(d.period, d.engageSeries.length), { color:'#059669' });
  });
}

/* ================================================================
   PAGE: CONTENT
   ================================================================ */

function renderContentPage(ca, d) {
  ca.innerHTML = `
    <div class="fade-in">
      <div class="page-header">
        <div class="page-header-info">
          <div class="panel-label">CONTENT INTELLIGENCE</div>
          <h2>Content</h2>
          <p>Content performance and posting strategy insights.</p>
        </div>
        <button class="back-btn" onclick="goBack()">← Back</button>
      </div>

      <div class="stats-grid">
        ${statCard('Content Volume', d.contentVolume, 'ic-accent', '📄', 'Posts in period', true)}
        ${statCard('Avg Likes/Post', fmt(Math.round(d.likes/Math.max(d.contentVolume,1))), 'ic-red', '♥', 'Average engagement', true)}
        ${statCard('Avg Comments', fmt(Math.round(d.comments/Math.max(d.contentVolume,1))), 'ic-green', '💬', 'Per post', true)}
        ${statCard('Avg Shares', fmt(Math.round(d.shares/Math.max(d.contentVolume,1))), 'ic-blue', '↗', 'Per post', true)}
      </div>

      <div class="grid-1-1">
        <div class="panel">
          <div class="panel-top"><div><div class="panel-label">ACTIVITY</div><h2>Weekly Activity Pattern</h2></div></div>
          <div id="c_actBars"></div>
        </div>
        <div class="panel">
          <div class="panel-top"><div><div class="panel-label">STRATEGY</div><h2>Posting Recommendations</h2></div></div>
          <div style="display:flex;flex-direction:column;gap:12px;padding-top:4px">
            <div class="info-card"><span class="info-lbl">Best Time to Post</span><div class="info-val" style="font-size:16px">${esc(d.bestPostTime)}</div></div>
            <div class="info-card"><span class="info-lbl">Active Window</span><div class="info-val" style="font-size:16px">${esc(d.activityWin)}</div></div>
            <div class="info-card"><span class="info-lbl">Strategy</span><div class="info-val" style="font-size:13px">${esc(d.recommendation)}</div></div>
          </div>
        </div>
      </div>

      <div class="panel mb">
        <div class="panel-top"><div><div class="panel-label">TOPIC KEYWORDS</div><h2>Content Themes</h2></div></div>
        <div class="tag-cloud">
          ${(d.trendTopics||[]).concat(d.trendKeywords||[]).filter(Boolean).slice(0,16).map((t,i)=>`
            <span class="tag" style="color:${CHART_COLORS[i%CHART_COLORS.length]};border-color:${CHART_COLORS[i%CHART_COLORS.length]}">${esc(t)}</span>`).join('')}
        </div>
      </div>
    </div>`;

  requestAnimationFrame(() => renderActivityBars($('c_actBars'), d.activity));
}

/* ================================================================
   PAGE: SETTINGS
   ================================================================ */

function renderSettingsPage(ca, d) {
  ca.innerHTML = `
    <div class="fade-in">
      <div class="page-header">
        <div class="page-header-info">
          <div class="panel-label">SYSTEM</div>
          <h2>Settings</h2>
          <p>Application preferences and configuration.</p>
        </div>
        <button class="back-btn" onclick="goBack()">← Back</button>
      </div>

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
            <div class="setting-name">Data Mode</div>
            <div class="setting-desc">Current backend data mode. Change via SOCIALIQ_DATA_MODE environment variable.</div>
          </div>
          <span class="demo-badge">${esc(d.source||'empty')}</span>
        </div>
        <div class="setting-row">
          <div class="setting-info">
            <div class="setting-name">Export Report</div>
            <div class="setting-desc">Download current analytics state as JSON.</div>
          </div>
          <button class="export-btn" id="exportBtn">↓ Export JSON</button>
        </div>
      </div>

      <div class="panel mb">
        <div class="panel-top"><div><h2>About SocialIQ</h2></div></div>
        <div style="display:flex;flex-direction:column;gap:8px;font-size:13px;color:var(--text-2)">
          <div><strong>Version:</strong> 2.0 (SIH Prototype)</div>
          <div><strong>Problem Statement:</strong> 26152 — Social Media Analytics</div>
          <div><strong>Event:</strong> Smart India Hackathon 2024</div>
          <div><strong>Mode:</strong> Demo / Simulation — No real API data</div>
          <div><strong>Backend:</strong> FastAPI · <strong>Frontend:</strong> Vanilla HTML/JS/CSS</div>
          <div><strong>ML Layer:</strong> Lightweight simulation engines (ml/ package)</div>
        </div>
      </div>

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

  $('lightModeBtn')?.addEventListener('click', () => { applyTheme('light'); renderCurrentView(); });
  $('darkModeBtn')?.addEventListener('click',  () => { applyTheme('dark');  renderCurrentView(); });
  $('exportBtn')?.addEventListener('click', exportReport);
  $('logoutBtn')?.addEventListener('click', () => { stopAutoRefresh(); showLogin(); showToast('Signed out'); });
  $('autoRefreshToggle')?.addEventListener('click', function() {
    const on = this.classList.toggle('on');
    if (on) startAutoRefresh(); else stopAutoRefresh();
    showToast(on ? 'Auto-refresh enabled' : 'Auto-refresh paused');
  });
}

/* ================================================================
   PAGE: PROFILE
   ================================================================ */

function renderProfilePage(ca, d) {
  ca.innerHTML = `
    <div class="fade-in">
      <div class="page-header">
        <div class="page-header-info">
          <div class="panel-label">USER</div>
          <h2>Profile</h2>
        </div>
        <button class="back-btn" onclick="goBack()">← Back</button>
      </div>
      <div class="panel mb" style="max-width:480px">
        <div style="display:flex;align-items:center;gap:16px;margin-bottom:20px">
          <div style="width:56px;height:56px;background:var(--accent);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:700;color:#fff">
            ${esc((state.username||'A').slice(0,1).toUpperCase())}
          </div>
          <div>
            <div style="font-size:18px;font-weight:700;color:var(--text)">${esc(state.username)}</div>
            <div style="font-size:13px;color:var(--text-3)">Demo Analyst · SIH 26152</div>
          </div>
        </div>
        <div style="display:flex;flex-direction:column;gap:10px;font-size:13px">
          <div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border)">
            <span style="color:var(--text-2)">Role</span><span>Analytics Analyst</span>
          </div>
          <div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border)">
            <span style="color:var(--text-2)">Mode</span><span>${state.mode === 'general' ? 'General Intelligence' : 'Topic Analysis'}</span>
          </div>
          <div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border)">
            <span style="color:var(--text-2)">Platform</span><span>${esc(state.platform)}</span>
          </div>
          <div style="display:flex;justify-content:space-between;padding:10px 0">
            <span style="color:var(--text-2)">Session Type</span><span>Demo</span>
          </div>
        </div>
      </div>
    </div>`;
}

/* ================================================================
   SHARED HELPERS
   ================================================================ */

function statCard(label, value, iconClass, icon, subText, isPositive=true) {
  const subColor = isPositive ? 'var(--success)' : 'var(--danger)';
  return `
    <div class="stat-card">
      <div class="stat-top">
        <span class="stat-label">${esc(label)}</span>
        <div class="stat-icon ${iconClass}">${icon}</div>
      </div>
      <div class="stat-val">${esc(value)}</div>
      <div class="stat-foot" style="color:${subColor}">${esc(subText)}</div>
    </div>`;
}

function buildAgeDist(d) {
  // Extended age groups from geo/demographic engine if available, else legacy 4-bucket
  if (d.geoDist && Object.keys(d.geoDist).length) {
    return {
      '13–17': 4, '18–24': d.age18_24, '25–34': d.age25_34,
      '35–44': d.age35_44, '45–54': Math.round(d.age45*0.55), '55+': Math.round(d.age45*0.45),
    };
  }
  return { '18–24': d.age18_24, '25–34': d.age25_34, '35–44': d.age35_44, '45+': d.age45 };
}

function generateDateLabels(period, n) {
  if (!n) return [];
  const labels = [];
  const now = new Date();
  const fmt_short = d => `${d.getDate()}/${d.getMonth()+1}`;
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  for (let i = n-1; i >= 0; i--) {
    const d = new Date(now);
    if (period === 'Today')        { d.setHours(now.getHours()-i*2); labels.push(d.getHours()+':00'); }
    else if (period === 'Last 7 Days')  { d.setDate(now.getDate()-i); labels.push(fmt_short(d)); }
    else if (period === 'Last 30 Days') { d.setDate(now.getDate()-Math.round(i*(30/n))); labels.push(fmt_short(d)); }
    else { d.setMonth(now.getMonth()-i); labels.push(months[d.getMonth()]); }
  }
  return labels.reverse ? labels : labels;
}

function capitalise(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

function emotionEmoji(key) {
  const map = { happy:'😊', excited:'🎉', supportive:'🤝', surprise:'😮', sad:'😢',
    anxious:'😰', angry:'😠', opposition:'✊', fear:'😨', disgust:'🤢', sarcasm:'😏' };
  return map[key] || '💬';
}

function exportReport() {
  if (!state.raw) { showToast('No data to export.'); return; }
  const blob = new Blob([JSON.stringify(state.raw, null, 2)], { type:'application/json' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `socialiq-report-${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
  showToast('Report exported');
}

function selectChartPeriod(p) {
  state.chartPeriod = p;
  $('chartPeriodLabel').textContent = p;
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
      <button>Clear All</button>
    `, true);
  });

  // Quick actions
  $('quickActionBtn')?.addEventListener('click', e => {
    openPopover(e.currentTarget, `
      <div class="pop-section">Quick Actions</div>
      <button onclick="loadData();closeAllPopovers();showToast('Refreshing…')">↻ Refresh</button>
      <button onclick="navigateTo('trending');closeAllPopovers()">📈 View Trends</button>
      <button onclick="navigateTo('network');closeAllPopovers()">🔗 Network Graph</button>
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

  // Visibility-based refresh: only refresh if more than 15 mins passed while hidden
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && state.view === 'app' && state.lastUpdated) {
      const elapsed = Date.now() - state.lastUpdated.getTime();
      if (elapsed >= AUTO_MS) {
        loadData();
      }
    }
  });
}

function selectDateRange(range) {
  state.dateRange = range;
  $('dateFilterLabel').textContent = range;
  closeAllPopovers();
  loadData();
}

/* ================================================================
   LOGIN SETUP
   ================================================================ */

function setupLogin() {
  $('loginForm')?.addEventListener('submit', () => {
    const user = $('loginUser')?.value.trim();
    const pass = $('loginPass')?.value.trim();
    if (!user || !pass) { showToast('Please enter username and password.'); return; }
    state.username = user;
    $('profileName').textContent = user;
    showModeSelect();
  });

  $('loginBtn')?.addEventListener('click', () => $('loginForm').dispatchEvent(new Event('submit')));
}

/* ================================================================
   MODE SELECT SETUP
   ================================================================ */

function setupModeSelect() {
  $('modeGeneralBtn')?.addEventListener('click', () => showApp('general'));
  $('modeTopicBtn')?.addEventListener('click',   () => showApp('topic'));
  $('modeBackBtn')?.addEventListener('click',    () => showLogin());
}

/* ================================================================
   GLOBAL EXPORTS (Ensures inline onclick handlers always resolve)
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

/* ================================================================
   INIT
   ================================================================ */

function init() {
  // Apply saved theme
  document.documentElement.dataset.theme = state.theme;

  // Wire up login + mode select
  setupLogin();
  setupModeSelect();

  // Wire up app controls
  setupControls();

  // Start on login screen
  showLogin();

  // Restore session if user refreshed while in app
  const savedMode = sessionStorage.getItem('socialiq-mode');
  if (savedMode) {
    const savedUser = sessionStorage.getItem('socialiq-user');
    if (savedUser) { state.username = savedUser; $('profileName').textContent = savedUser; }
    showApp(savedMode);
  }
}

// Save session on navigation
window.addEventListener('beforeunload', () => {
  if (state.view === 'app') {
    sessionStorage.setItem('socialiq-mode', state.mode);
    sessionStorage.setItem('socialiq-user', state.username);
  } else {
    sessionStorage.removeItem('socialiq-mode');
  }
});

// Close popovers on ESC
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeAllPopovers();
});

// Boot
init();
