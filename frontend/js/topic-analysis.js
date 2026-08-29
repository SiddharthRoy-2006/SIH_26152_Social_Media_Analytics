/* ================================================================
   SOCIALIQ ANALYTICS — topic-analysis.js
   Topic Analysis dashboard, autocomplete engine, topic-specific
   topology visualization, and campaign metrics.
   ================================================================ */

'use strict';

let _activeAutocompleteIdx = -1;
let _currentSuggestions = [];

function hideAutocomplete() {
  const box = $('topicAutocomplete');
  if (box) {
    box.classList.remove('show');
    box.innerHTML = '';
  }
  _activeAutocompleteIdx = -1;
  _currentSuggestions = [];
}

function quickAnalyze(topic) {
  const clean = String(topic || '').trim().replace(/\s+/g, ' ');
  if (!clean) return;
  state.campaign.topic = clean;
  const input = $('topicInput');
  if (input) input.value = clean;
  hideAutocomplete();
  loadData();
  showToast(`Analyzing "${clean}"…`);
}

function selectSuggestion(name) {
  quickAnalyze(name);
}

function renderTopicDashboard(ca, d) {
  const hasTopic = !!state.campaign.topic.trim();
  const isOffline = !state.backendOK;
  const isDemo = state.dataSource === 'demo';
  const isLive = state.dataSource === 'live';
  const cap = state.platformCapabilities ? state.platformCapabilities[state.platform] : null;

  ca.innerHTML = `
    <div class="fade-in">
      <!-- Back btn -->
      <div style="margin-bottom:var(--gap);display:flex;justify-content:flex-end">
        <button class="back-btn" id="topicBackBtn" type="button">← Back to Mode Selection</button>
      </div>

      ${isOffline ? `
      <div class="offline-banner">
        <div class="offline-banner-left">
          <span>⚠️</span>
          <div>
            <strong>Backend Connection Offline:</strong> Ensure the FastAPI server is running on <code>port 8001</code>.
          </div>
        </div>
        <button class="retry-btn" onclick="loadData();showToast('Reconnecting…')">Retry Connection</button>
      </div>` : ''}

      <!-- Campaign Panel -->
      <div class="campaign-panel">
        <h2>Campaign / Topic Analysis</h2>
        <div class="campaign-fields">
          <div class="camp-field">
            <label for="topicInput">Topic or Campaign</label>
            <input id="topicInput" type="text" placeholder="Type a topic (e.g. NEP 2020, AI in Education, Digital India)…"
              value="${esc(state.campaign.topic)}" maxlength="120" autocomplete="off">
            <div id="topicAutocomplete" class="topic-autocomplete"></div>
          </div>
          <div class="camp-field">
            <label for="queryInput">Optional Query Refinement</label>
            <input id="queryInput" type="text" placeholder="e.g. impact, sentiments, debate…"
              value="${esc(state.campaign.query)}" maxlength="120" autocomplete="off">
          </div>
          <button class="analyze-btn" id="analyzeBtn" type="button">→ Analyze</button>
        </div>
        ${hasTopic && d.dataAvailable ? `<div class="camp-ctx">
          Showing results for <strong>${esc(d.topic)}</strong> on <strong>${esc(d.platform)}</strong> · ${esc(d.period)} · Auto-refreshes every 15 min
        </div>` : '<div class="camp-ctx">Enter a topic above or pick a suggested topic to generate intelligence.</div>'}
      </div>

      <!-- Data Source Transparency Banner for Topic Mode -->
      ${hasTopic && d.dataAvailable ? `
        <div class="data-source-banner ${isDemo ? 'demo' : isLive ? 'live' : 'unconfigured'}">
          <div style="display:flex;align-items:center;gap:8px">
            <span>${isLive ? '🟢' : '⚡'}</span>
            <span><strong>Data Source: ${isLive ? 'LIVE' : 'DEMO'}</strong> — ${isLive ? `Verified real-time ${esc(d.platform)} data for "${esc(d.topic)}"` : `Simulated demonstration dataset for "${esc(d.topic)}" explicitly selected`}</span>
          </div>
          ${isDemo ? `<button class="btn-demo-secondary" style="padding:4px 10px;font-size:11.5px" onclick="disableDemoData('${esc(state.platform)}')">Switch to Live / Authentic</button>` : `<span class="source-badge live">Verified Live</span>`}
        </div>
      ` : ''}

      ${!hasTopic ? `
      <!-- 1. Clean Initial State Before Topic Entry -->
      <div class="empty-topic-card">
        <div class="empty-topic-icon">🎯</div>
        <h3>Enter a topic to generate analysis</h3>
        <p>Search for a specific campaign, topic, or keyword above to compute sentiment distributions, audience reach, weekly engagement, and topic topology.</p>
        <div class="topic-suggestions">
          <span class="suggestion-label">Suggested topics:</span>
          <button class="topic-chip" onclick="quickAnalyze('NEP 2020')">NEP 2020</button>
          <button class="topic-chip" onclick="quickAnalyze('AI in Education')">AI in Education</button>
          <button class="topic-chip" onclick="quickAnalyze('Digital India')">Digital India</button>
          <button class="topic-chip" onclick="quickAnalyze('Youth Innovation')">Youth Innovation</button>
          <button class="topic-chip" onclick="quickAnalyze('Ed-Tech Growth')">Ed-Tech Growth</button>
        </div>
      </div>` : !d.dataAvailable ? `
      <!-- 2. Clean No-Data State with Explicit Demo Choice -->
      <div class="demo-fallback-card fade-in">
        <div class="demo-fallback-icon">🔍</div>
        <h3>No Live Data Found for "${esc(state.campaign.topic)}" on ${esc(state.platform)}</h3>
        <p>${esc(cap?.reason || 'Live API connector is unconfigured or returned no matching public records. Demo data is displayed strictly upon explicit request.')}</p>
        <div class="demo-fallback-actions">
          <button class="btn-demo-primary" onclick="enableDemoData('${esc(state.platform)}')">⚡ Use Demo Data</button>
          <button class="btn-demo-secondary" onclick="disableDemoData('${esc(state.platform)}')">🔒 Leave As Is</button>
        </div>
      </div>` : `
      <!-- 3. Successful Analysis State -->
      <div class="stats-grid">
        ${statCard(state.platform === 'YouTube' ? 'Total Views (Returned)' : 'Total Reach', fmt(d.reach), 'ic-blue', '📡', isLive ? (state.platform === 'YouTube' ? 'Sum of returned video views' : 'Estimated reach') : 'Simulated dataset', true)}
        ${statCard('Total Likes', fmt(d.likes), 'ic-red', '♥', isLive ? 'Observed in retrieved records' : `${fmt(d.shares)} shares`, true)}
        ${statCard('Comments', fmt(d.comments), 'ic-green', '💬', `${fmt(d.contentVolume)} ${state.platform==='YouTube'?'videos':'posts'} retrieved`, true)}
        ${statCard('Engagement Rate', pct(d.engagement), 'ic-purple', '✦', isLive ? 'Calculated from returned records' : (d.scoreStatus || 'Engagement quality'), d.engagement>=1.5)}
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
        <div class="panel" id="t_actBars"></div>
        <div class="panel">
          <div class="panel-top">
            <div><div class="panel-label">AI INTELLIGENCE</div><h2>Quick Insights</h2></div>
            <button class="panel-action" onclick="navigateTo('ai')">View All →</button>
          </div>
          <div id="t_aiPreview"></div>
        </div>
      </div>

      <!-- Topic-Specific Topology Graph -->
      <div class="panel mb">
        <div class="panel-top">
          <div><div class="panel-label">TOPIC NETWORK TOPOLOGY</div><h2>Topic Entity & Spread Network</h2></div>
          <button class="panel-action" onclick="navigateTo('network')">Detailed Analysis →</button>
        </div>
        <div id="t_networkTopology"></div>
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

  // Bind back button
  $('topicBackBtn')?.addEventListener('click', () => showModeSelect());

  // Analyze function
  const doAnalyze = () => {
    const rawT = $('topicInput')?.value || '';
    const cleanT = rawT.trim().replace(/\s+/g, ' ');
    const cleanQ = ($('queryInput')?.value || '').trim().replace(/\s+/g, ' ');
    hideAutocomplete();

    if (!cleanT) {
      showToast('Please enter a topic to analyze.');
      state.campaign.topic = '';
      renderTopicDashboard(ca, d);
      return;
    }

    state.campaign = { topic: cleanT, query: cleanQ };
    loadData();
    showToast(`Analyzing "${cleanT}"…`);
  };

  $('analyzeBtn')?.addEventListener('click', doAnalyze);
  $('queryInput')?.addEventListener('keydown', e => { if (e.key === 'Enter') doAnalyze(); });

  // Autocomplete wiring
  const topicInput = $('topicInput');
  const autoBox = $('topicAutocomplete');

  if (topicInput && autoBox) {
    topicInput.addEventListener('input', e => {
      const q = e.target.value.trim().toLowerCase();
      if (!q || q.length < 2) { hideAutocomplete(); return; }

      const matches = TOPIC_VOCABULARY
        .filter(t => t.name.toLowerCase().includes(q) || t.category.toLowerCase().includes(q))
        .slice(0, 7);

      if (!matches.length) { hideAutocomplete(); return; }

      _currentSuggestions = matches;
      _activeAutocompleteIdx = -1;

      autoBox.innerHTML = matches.map((m, idx) => `
        <div class="auto-item" data-idx="${idx}" data-name="${esc(m.name)}">
          <span class="auto-item-name">${esc(m.name)}</span>
          <span class="auto-item-cat">${esc(m.category)}</span>
        </div>
      `).join('');
      autoBox.classList.add('show');

      autoBox.querySelectorAll('.auto-item').forEach(el => {
        el.addEventListener('click', () => {
          selectSuggestion(el.dataset.name);
        });
      });
    });

    topicInput.addEventListener('keydown', e => {
      if (!autoBox.classList.contains('show') || !_currentSuggestions.length) {
        if (e.key === 'Enter') { doAnalyze(); }
        return;
      }
      const items = autoBox.querySelectorAll('.auto-item');
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        _activeAutocompleteIdx = clamp(_activeAutocompleteIdx + 1, 0, items.length - 1);
        items.forEach((it, i) => it.classList.toggle('active', i === _activeAutocompleteIdx));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        _activeAutocompleteIdx = clamp(_activeAutocompleteIdx - 1, 0, items.length - 1);
        items.forEach((it, i) => it.classList.toggle('active', i === _activeAutocompleteIdx));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (_activeAutocompleteIdx >= 0 && items[_activeAutocompleteIdx]) {
          selectSuggestion(items[_activeAutocompleteIdx].dataset.name);
        } else {
          doAnalyze();
        }
      } else if (e.key === 'Escape') {
        hideAutocomplete();
      }
    });
  }

  if (!hasTopic || !d.dataAvailable) return;

  requestAnimationFrame(() => {
    // Area chart
    const labels = d.growthSeries.length > 0 ? generateDateLabels(d.period, d.growthSeries.length, state.chartPeriod) : [];
    renderAreaChart($('t_areaChart'), d.growthSeries, labels);

    // Score ring
    renderScoreRing($('t_scoreRing'), clamp(d.engagement * 5, 0, 100), {
      label: 'Engagement Score',
      msg: d.scoreMsg || 'Based on active topic data',
    });

    // Dynamic Activity Component (Day / Week / Month / Year)
    renderDynamicActivityComponent($('t_actBars'), d);

    // AI Preview
    renderAICards($('t_aiPreview'), (d.aiInsights || []).slice(0, 2));

    // Topic Network Topology
    renderNetworkGraph($('t_networkTopology'), d.networkGraph, d.topic);

    // Trend Preview
    renderTrendTable($('t_trendPreview'), (d.topTrends || []).slice(0, 5));
  });
}
