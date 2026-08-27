/* ================================================================
   SOCIALIQ ANALYTICS — utils.js
   Shared state, constants, string/math formatters, popovers,
   toast, theme, SVG chart primitives, and payload normalizer.
   ================================================================ */

'use strict';

/* ================================================================
   CONSTANTS
   ================================================================ */

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
  'Twitter / X':'#000000','Telegram':'#0088cc','Reddit':'#ff4500','All Platforms':'#2563eb',
};

const TOPIC_VOCABULARY = [
  { name: 'AI in Education', category: 'Technology' },
  { name: 'Digital Literacy', category: 'Education' },
  { name: 'Youth Innovation', category: 'Innovation' },
  { name: 'Ed-Tech Growth', category: 'Technology' },
  { name: 'Online Learning', category: 'Education' },
  { name: 'STEM Careers', category: 'Career' },
  { name: 'Digital Inclusion', category: 'Policy' },
  { name: 'Future of Work', category: 'Economy' },
  { name: 'Climate Awareness', category: 'Environment' },
  { name: 'Mental Health Advocacy', category: 'Health' },
  { name: 'Women in Tech', category: 'Diversity' },
  { name: 'Sustainable Living', category: 'Environment' },
  { name: 'Blockchain in Finance', category: 'Finance' },
  { name: 'Open Source Culture', category: 'Technology' },
  { name: 'Cybersecurity Awareness', category: 'Security' },
  { name: 'Smart Cities', category: 'Infrastructure' },
  { name: 'Health Tech', category: 'Health' },
  { name: 'Green Energy', category: 'Environment' },
  { name: 'Data Privacy', category: 'Policy' },
  { name: 'Social Commerce', category: 'Economy' },
  { name: 'Education Policy', category: 'Policy' },
  { name: 'NEP 2020 Impact', category: 'Policy' },
  { name: 'Higher Education Reform', category: 'Education' },
  { name: 'Digital Classrooms', category: 'Education' },
  { name: 'Teacher Training', category: 'Education' },
  { name: 'Student Wellbeing', category: 'Health' },
  { name: 'University Rankings', category: 'Education' },
  { name: 'Scholarship Access', category: 'Policy' },
  { name: 'Coding for Kids', category: 'Education' },
  { name: 'STEM Education', category: 'Education' },
  { name: 'Blended Learning', category: 'Education' },
  { name: 'EdTech Funding', category: 'Finance' },
  { name: 'Generative AI', category: 'Technology' },
  { name: 'Large Language Models', category: 'Technology' },
  { name: 'Quantum Computing', category: 'Technology' },
  { name: 'AR/VR Adoption', category: 'Technology' },
  { name: '5G Rollout', category: 'Telecom' },
  { name: 'Edge Computing', category: 'Technology' },
  { name: 'Open AI Debate', category: 'Technology' },
  { name: 'AI Regulation', category: 'Policy' },
  { name: 'Digital India', category: 'Governance' },
  { name: 'Skill India', category: 'Governance' },
  { name: 'Innovate India', category: 'Innovation' },
  { name: 'Mental Health Awareness', category: 'Health' },
  { name: 'Telehealth Growth', category: 'Health' },
  { name: 'Vaccine Literacy', category: 'Health' },
  { name: 'Nutrition Science', category: 'Health' },
  { name: 'AI in Diagnostics', category: 'Health' },
  { name: 'Governance Transparency', category: 'Governance' },
  { name: 'Economic Reform', category: 'Economy' },
  { name: 'Rural Development', category: 'Governance' },
];

/* ================================================================
   GLOBAL APPLICATION STATE
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
  platformCapabilities: {},  // populated from /health or /api/credentials/status
  platformDemo: {},          // explicit per-platform demo fallback toggles
  topologyZoom: 1.0,
  topologyPan: { x: 0, y: 0 },
};

/* Apply saved theme immediately */
document.documentElement.dataset.theme = state.theme;

/* ================================================================
   UTILITY FUNCTIONS
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

function capitalise(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

function emotionEmoji(key) {
  const map = { happy:'😊', excited:'🎉', supportive:'🤝', surprise:'😮', sad:'😢',
    anxious:'😰', angry:'😠', opposition:'✊', fear:'😨', disgust:'🤢', sarcasm:'😏' };
  return map[key] || '💬';
}

/* ================================================================
   TOAST SYSTEM
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

    /* Emotions */
    emotions: e,

    /* Trending */
    trendTopic:    safeS(t.topic),
    trendKeyword:  safeS(t.keyword),
    trendTopics:   Array.isArray(t.topics)   ? t.topics   : [],
    trendKeywords: Array.isArray(t.keywords) ? t.keywords : [],

    /* Network */
    netNodes:       safeN(n.nodes),
    netConnections: safeN(n.connections),
    netCommunities: safeN(n.communities),

    /* Activity */
    activity:     Array.isArray(source.activity)     ? source.activity     : [0,0,0,0,0],
    growthSeries: Array.isArray(source.growth_series) ? source.growth_series : [],

    /* Insights */
    scoreStatus:   safeS(ins.score_status),
    scoreMsg:      safeS(ins.score_message),
    bestPostTime:  safeS(ins.best_posting_time),
    growthSignal:  safeS(ins.growth_signal),
    recommendation:safeS(ins.recommendation),
    activityWin:   safeS(ins.activity_window),

    /* Extended */
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

function renderAreaChart(container, series, labels, opts={}) {
  if (!container) return;
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

function renderDonut(container, segments, size=130) {
  if (!container) return;
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

  const svgCircles = arcs.map(a => `
    <circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="${a.color}"
      stroke-width="${SW}" stroke-dasharray="${a.dashLen.toFixed(1)} ${(C-a.dashLen).toFixed(1)}"
      stroke-dashoffset="${a.dashOffset.toFixed(1)}" style="transition: stroke-dashoffset 0.4s"/>
  `).join('');

  const legend = segments.map(s => `
    <div class="donut-leg-item">
      <span class="donut-leg-dot" style="background:${s.color}"></span>
      <span class="donut-leg-label">${esc(s.label)}</span>
      <span class="donut-leg-val">${Math.round(s.value/total*100)}%</span>
    </div>
  `).join('');

  container.innerHTML = `
    <div class="donut-wrap">
      <svg viewBox="0 0 ${size} ${size}" class="donut-svg" style="width:${size}px;height:${size}px;transform:rotate(-90deg)">
        ${svgCircles}
      </svg>
      <div class="donut-legend">${legend}</div>
    </div>`;
}

function renderScoreRing(container, score, opts={}) {
  if (!container) return;
  const size = 110, SW = 10, R = size/2 - SW;
  const C = 2 * Math.PI * R;
  const frac = clamp(score/100, 0, 1);
  const color = opts.color || (score >= 70 ? '#059669' : score >= 40 ? '#d97706' : '#dc2626');

  container.innerHTML = `
    <div class="score-ring-wrap">
      <div class="score-ring-chart">
        <svg viewBox="0 0 ${size} ${size}" style="width:${size}px;height:${size}px;transform:rotate(-90deg)">
          <circle cx="${size/2}" cy="${size/2}" r="${R}" fill="none" stroke="var(--border)" stroke-width="${SW}"/>
          <circle cx="${size/2}" cy="${size/2}" r="${R}" fill="none" stroke="${color}" stroke-width="${SW}"
            stroke-dasharray="${(frac*C).toFixed(1)} ${C.toFixed(1)}" stroke-linecap="round"/>
        </svg>
        <div class="score-ring-val">${Math.round(score)}</div>
      </div>
      <div class="score-ring-info">
        <div class="score-ring-label">${esc(opts.label || 'Quality Score')}</div>
        <div class="score-ring-msg">${esc(opts.msg || 'Based on active metrics')}</div>
      </div>
    </div>`;
}

function renderHBars(container, items) {
  if (!container) return;
  if (!items || !items.length) { container.innerHTML = '<p style="color:var(--text-3);font-size:12px">No data</p>'; return; }
  const max = Math.max(...items.map(i=>i.value), 1);
  container.innerHTML = `<div class="hbar-list">${items.map(item => `
    <div class="hbar-row">
      <span class="hbar-label">${esc(item.label)}</span>
      <div class="hbar-track">
        <div class="hbar-fill" style="width:${(item.value/max*100).toFixed(1)}%;background:${item.color||'var(--accent)'}"></div>
      </div>
      <span class="hbar-val">${item.value}%</span>
    </div>
  `).join('')}</div>`;
}

function renderGeoBars(container, data) {
  if (!container) return;
  const entries = Object.entries(data || {}).sort((a,b)=>b[1]-a[1]).slice(0,5);
  if (!entries.length) { container.innerHTML = '<p style="color:var(--text-3);font-size:12px">No demographic data</p>'; return; }
  const max = Math.max(...entries.map(e=>e[1]), 1);
  container.innerHTML = `<div class="hbar-list">${entries.map(([name, val], i) => `
    <div class="hbar-row">
      <span class="hbar-label">${esc(name)}</span>
      <div class="hbar-track">
        <div class="hbar-fill" style="width:${(val/max*100).toFixed(1)}%;background:${CHART_COLORS[i%CHART_COLORS.length]}"></div>
      </div>
      <span class="hbar-val">${val}%</span>
    </div>
  `).join('')}</div>`;
}

function renderActivityBars(container, activity) {
  if (!container) return;
  const days = ['Mon','Tue','Wed','Thu','Fri'];
  const max = Math.max(...(activity||[]), 1);
  container.innerHTML = `
    <div class="activity-bars-wrap">
      ${(activity||[0,0,0,0,0]).map((val,i) => `
        <div class="act-bar-col">
          <div class="act-bar-track">
            <div class="act-bar-fill" style="height:${Math.max(8, (val/max*100).toFixed(0))}%;background:var(--accent)"></div>
          </div>
          <span class="act-bar-lbl">${days[i]||`D${i+1}`}</span>
        </div>
      `).join('')}
    </div>`;
}

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
  if (d.geoDist && Object.keys(d.geoDist).length) {
    return {
      '13–17': 4, '18–24': d.age18_24, '25–34': d.age25_34,
      '35–44': d.age35_44, '45–54': Math.round(d.age45*0.55), '55+': Math.round(d.age45*0.45),
    };
  }
  return { '18–24': d.age18_24, '25–34': d.age25_34, '35–44': d.age35_44, '45+': d.age45 };
}

function generateDateLabels(period, n) {
  if (!n || n <= 0) return [];
  const labels = [];
  const now = new Date();
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const days = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];

  if (period === 'Today') {
    for (let i = n - 1; i >= 0; i--) {
      const d = new Date(now.getTime() - i * 2 * 3600 * 1000);
      const h = String(d.getHours()).padStart(2, '0');
      labels.push(`${h}:00`);
    }
  } else if (period === 'Last 7 Days') {
    for (let i = n - 1; i >= 0; i--) {
      const d = new Date(now.getTime() - i * 24 * 3600 * 1000);
      labels.push(`${days[d.getDay()]} ${d.getDate()}`);
    }
  } else if (period === 'Last 30 Days') {
    for (let i = n - 1; i >= 0; i--) {
      const dayOffset = Math.round(i * (30 / Math.max(n - 1, 1)));
      const d = new Date(now.getTime() - dayOffset * 24 * 3600 * 1000);
      labels.push(`${d.getDate()} ${months[d.getMonth()]}`);
    }
  } else {
    // 1 Year
    for (let i = n - 1; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      labels.push(months[d.getMonth()]);
    }
  }
  return labels;
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
