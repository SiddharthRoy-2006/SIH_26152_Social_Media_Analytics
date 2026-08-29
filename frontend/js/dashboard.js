/* ================================================================
   SOCIALIQ ANALYTICS — dashboard.js
   General Intelligence view, deep analytics, content intelligence,
   demographics, sentiment & emotions, trend tables, and AI cards.
   ================================================================ */

'use strict';

/* ================================================================
   1. GENERAL INTELLIGENCE DASHBOARD
   ================================================================ */

function renderGeneralDashboard(ca, d) {
  const reach = d.reach || 0;
  const eng   = d.engagement || 0;
  const pos   = d.sentPositive || 0;
  const isDemo = state.dataSource === 'demo';
  const isLive = state.dataSource === 'live';
  const cap = state.platformCapabilities ? state.platformCapabilities[state.platform] : null;

  ca.innerHTML = `
    <div class="fade-in">
      <!-- Back btn -->
      <div style="margin-bottom:var(--gap);display:flex;justify-content:flex-end">
        <button class="back-btn" id="genBackBtn" type="button">← Back to Mode Selection</button>
      </div>

      <!-- Data Source Transparency Banner -->
      ${d.dataAvailable ? `
        <div class="data-source-banner ${isDemo ? 'demo' : isLive ? 'live' : 'unconfigured'}">
          <div style="display:flex;align-items:center;gap:8px">
            <span>${isLive ? '🟢' : '⚡'}</span>
            <span><strong>Data Source: ${isLive ? 'LIVE' : 'DEMO'}</strong> — ${isLive ? `Verified real-time data from active ${esc(state.platform)} connectors` : `Simulated demonstration dataset explicitly selected by user`}</span>
          </div>
          ${isDemo ? `<button class="btn-demo-secondary" style="padding:4px 10px;font-size:11.5px" onclick="disableDemoData('${esc(state.platform)}')">Switch to Live / Authentic</button>` : `<span class="source-badge live">Verified Live</span>`}
        </div>
      ` : ''}

      ${!d.dataAvailable ? `
      <!-- Unconfigured / Unavailable Platform State -->
      <div class="demo-fallback-card fade-in">
        <div class="demo-fallback-icon">🌐</div>
        <h3>Live ${esc(state.platform)} Data is Currently Not Configured</h3>
        <p>${esc(cap?.reason || 'No verified live connection available for this platform. Credentials can be configured in Settings.')}</p>
        <div class="demo-fallback-actions">
          <button class="btn-demo-primary" onclick="navigateTo('settings')">⚙ Configure API Credentials</button>
          <button class="btn-demo-secondary" onclick="enableDemoData('${esc(state.platform)}')">⚡ Use Demo Data</button>
          <button class="btn-demo-secondary" onclick="disableDemoData('${esc(state.platform)}')">🔒 Leave As Is</button>
        </div>
      </div>` : `
      <!-- Stat Cards -->
      <div class="stats-grid">
        ${statCard(state.platform === 'YouTube' ? 'Total Views (Returned)' : 'Total Reach', fmt(reach), 'ic-blue', '📡', isLive ? (state.platform === 'YouTube' ? 'Sum of returned video views' : 'Ecosystem reach') : 'Simulated dataset', true)}
        ${statCard('Total Likes', fmt(d.likes), 'ic-red', '♥', isLive ? 'Observed in retrieved records' : `${fmt(d.shares)} shares`, true)}
        ${statCard('Total Comments', fmt(d.comments), 'ic-green', '💬', `${fmt(d.contentVolume)} ${state.platform==='YouTube'?'videos':'posts'} retrieved`, true)}
        ${statCard('Engagement Rate', pct(eng), 'ic-purple', '✦', isLive ? 'Calculated from returned records' : (d.scoreStatus || 'Engagement quality'), eng>=1.5)}
      </div>

      <!-- Area Chart + Donut -->
      <div class="grid-2-1">
        <div class="panel">
          <div class="panel-top">
            <div><div class="panel-label">CROSS-PLATFORM REACH</div><h2>Reach Over Time</h2></div>
            <div style="display:flex;gap:6px">
              ${['Daily','Weekly','Monthly','Yearly'].map(p=>`
                <button class="theme-btn${state.chartPeriod===p?' active':''}" style="font-size:11px;padding:4px 10px"
                  onclick="selectChartPeriod('${p}')">${p}</button>`).join('')}
            </div>
          </div>
          <div id="g_areaChart"></div>
        </div>
        <div class="panel">
          <div class="panel-top">
            <div><div class="panel-label">SENTIMENT DISTRIBUTION</div><h2>Audience Sentiment</h2></div>
          </div>
          <div id="g_donut"></div>
        </div>
      </div>

      <!-- Emotions + Age Groups -->
      <div class="grid-1-1">
        <div class="panel">
          <div class="panel-top">
            <div><div class="panel-label">EMOTIONAL SPECTRUM</div><h2>Top Emotions Detected</h2></div>
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

      <!-- Trending Topics Table (Top 10) -->
      <div class="panel mb">
        <div class="panel-top">
          <div><div class="panel-label">ECOSYSTEM TRENDS</div><h2>Top Trending Topics with Influencer Leads</h2></div>
          <button class="panel-action" onclick="navigateTo('trending')">View All →</button>
        </div>
        <div id="g_trendTable"></div>
      </div>

      <!-- Influencer Detection + Network Stats -->
      <div class="grid-1-1">
        <div class="panel">
          <div class="panel-top">
            <div><div class="panel-label">INFLUENTIAL USER DETECTION</div><h2>Top Influencers by Network Score</h2></div>
          </div>
          <div id="g_influencers"></div>
        </div>
        <div class="panel">
          <div class="panel-top">
            <div><div class="panel-label">LINK ANALYSIS</div><h2>Network Topology Overview</h2></div>
            <button class="panel-action" onclick="navigateTo('network')">Full Graph →</button>
          </div>
          <div id="g_netStats"></div>
        </div>
      </div>

      <!-- Geographic + Language -->
      <div class="grid-1-1">
        <div class="panel">
          <div class="panel-top">
            <div><div class="panel-label">GEOGRAPHIC DISTRIBUTION</div><h2>Top Regions by Activity</h2></div>
          </div>
          <div id="g_geo"></div>
        </div>
        <div class="panel">
          <div class="panel-top">
            <div><div class="panel-label">LANGUAGE DIVERSITY</div><h2>Dominant Languages</h2></div>
          </div>
          <div id="g_lang"></div>
        </div>
      </div>

      <!-- AI Insights -->
      <div class="panel mb">
        <div class="panel-top">
          <div><div class="panel-label">AI INTELLIGENCE LAYER</div><h2>Automated Strategic Insights & Alerts</h2></div>
          <button class="panel-action" id="g_refreshInsights">↻ Refresh</button>
        </div>
        <div id="g_aiInsights"></div>
      </div>

      <!-- Information Spread / Propagation -->
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
      `}

    </div>`;

  // Bind back button
  $('genBackBtn')?.addEventListener('click', () => showModeSelect());
  $('g_refreshInsights')?.addEventListener('click', () => { loadData(); showToast('Refreshing insights…'); });

  if (!d.dataAvailable) return;

  requestAnimationFrame(() => {
    // Area chart
    const labels = d.growthSeries.length > 0 ? generateDateLabels(d.period, d.growthSeries.length, state.chartPeriod) : [];
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

    // Trend table
    renderTrendTable($('g_trendTable'), d.topTrends);

    // Influencer list
    renderInfluencerList($('g_influencers'), d.influencers);

    // Network stats
    renderNetworkStatsPanel($('g_netStats'), d);

    // Geo & Lang
    renderGeoBars($('g_geo'), d.geoDist);
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

/* ================================================================
   2. REUSABLE SUB-PANEL RENDERERS
   ================================================================ */

function renderAICards(container, insights, isGrid=false) {
  if (!container || !insights || !insights.length) {
    if (container) container.innerHTML = '<p style="color:var(--text-3);font-size:13px;padding:8px 0">No active alerts.</p>';
    return;
  }
  container.innerHTML = `
    <div class="ai-cards-list${isGrid ? ' grid' : ''}">
      ${insights.map(item => `
        <div class="ai-card ${item.type || 'info'}">
          <div class="ai-card-icon">${item.icon || '✦'}</div>
          <div class="ai-card-body">
            <div class="ai-card-title">${esc(item.title || '')}</div>
            <div class="ai-card-text">${esc(item.text || '')}</div>
          </div>
        </div>
      `).join('')}
    </div>`;
}

function renderTrendTable(container, trends) {
  if (!container) return;
  if (!trends || !trends.length) {
    container.innerHTML = '<p style="color:var(--text-3);font-size:13px;padding:12px">No trending data.</p>';
    return;
  }

  container.innerHTML = `
    <div class="trend-table-wrap">
      <table class="trend-table">
        <thead>
          <tr>
            <th style="width:40px">#</th>
            <th>Topic / Keyword</th>
            <th>Mentions</th>
            <th>Growth</th>
            <th>Top Influencer</th>
            <th>Influence</th>
          </tr>
        </thead>
        <tbody>
          ${trends.slice(0, 10).map((t, idx) => {
            const hasGrowth = typeof t.growth_pct === 'number' && t.growth_pct !== 0;
            const growthBadge = hasGrowth
              ? `<span class="growth-badge ${t.growth_pct >= 0 ? 'up' : 'down'}">${t.growth_pct >= 0 ? '↑' : '↓'}${Math.abs(t.growth_pct).toFixed(0)}%</span>`
              : `<span style="font-size:11px;color:var(--text-3)">Baseline pending</span>`;

            return `
              <tr>
                <td><span class="trend-rank rank-${idx + 1}">${t.rank || idx + 1}</span></td>
                <td>
                  <div class="trend-name" style="font-weight:600">${esc(t.name || t.keyword || '—')}</div>
                  <div class="trend-kw" style="font-size:11px;color:var(--text-3)">${esc(t.keyword || '')}</div>
                </td>
                <td><strong>${fmtN(t.mentions || t.volume || 1)}</strong></td>
                <td>${growthBadge}</td>
                <td>${esc(t.influencer_name || t.top_creator || '—')}</td>
                <td>
                  <div style="display:flex;align-items:center;gap:6px">
                    <div class="influencer-mini-bar" style="width:50px;height:5px;background:var(--border);border-radius:99px;overflow:hidden">
                      <div style="width:${Math.round((t.influencer_score || 0.5) * 100)}%;background:var(--accent);height:100%;border-radius:99px"></div>
                    </div>
                    <span style="font-size:11px;color:var(--text-3)">${Math.round((t.influencer_score || 0.5) * 100)}</span>
                  </div>
                </td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    </div>`;
}

function renderInfluencerList(container, influencers) {
  if (!container || !influencers || !influencers.length) {
    if (container) container.innerHTML = '<p style="color:var(--text-3);font-size:13px;padding:8px 0">No influencers detected in returned records.</p>';
    return;
  }

  container.innerHTML = `
    <div class="influencer-list">
      ${influencers.slice(0, 6).map((inf, i) => {
        const handle = inf.handle || ('@' + (inf.name || 'creator').replace(/[^\w]/g, '').toLowerCase());
        const score = typeof inf.score === 'number' ? (inf.score <= 1.0 ? Math.round(inf.score * 100) : Math.round(inf.score)) : 80;
        const initial = inf.avatar_initials || (inf.name || 'U').slice(0, 2).toUpperCase();
        const postsCount = inf.posts || inf.content_count || 1;
        const viewsCount = inf.followers || inf.views || 0;
        const verifiedBadge = inf.verified ? '<span title="Verified Channel / High Reach" style="color:var(--accent);margin-left:4px">✓</span>' : '';
        const badgeLabel = inf.badge || (i === 0 ? 'Lead Hub' : 'Active Contributor');

        return `
          <div class="influencer-row">
            <div class="influencer-rank" style="font-weight:700;font-size:13px;color:var(--text-3);width:20px">${inf.rank || i + 1}</div>
            <div class="influencer-avatar" style="background:${COMMUNITY_COLORS[i % COMMUNITY_COLORS.length]}">
              ${esc(initial)}
            </div>
            <div class="influencer-info" style="flex:1;min-width:0">
              <div class="influencer-name" style="display:flex;align-items:center;gap:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
                <span style="font-weight:600">${esc(inf.name)}</span>
                ${verifiedBadge}
              </div>
              <div class="influencer-sub" style="font-size:11.5px;color:var(--text-3)">
                <span style="color:var(--text-2)">${esc(handle)}</span> · ${postsCount} ${postsCount === 1 ? 'item' : 'items'} · ${viewsCount > 0 ? `${fmt(viewsCount)} views` : badgeLabel}
              </div>
            </div>
            <div style="text-align:right">
              <div class="influencer-score-badge" title="Calculated Influence Score derived from retrieved records">${score}</div>
              <div style="font-size:9.5px;color:var(--text-3);margin-top:2px">Score</div>
            </div>
          </div>
        `;
      }).join('')}
    </div>`;
}

/* ================================================================
   3. OTHER SUB-PAGES
   ================================================================ */

function renderAnalyticsPage(ca, d) {
  const isLive = state.dataSource === 'live';
  const isYT = state.platform === 'YouTube';
  const followerVal = d.followers > 0 ? fmt(d.followers) : (isLive ? 'Unavailable' : '0');
  const followerSub = d.followers > 0 ? 'Total followers' : (isLive ? 'Requires Channel Access' : 'Simulated dataset');
  const shareVal = (isYT && !d.shares) ? 'Unavailable' : fmt(d.shares);
  const shareSub = (isYT && !d.shares) ? 'Not in YouTube Data API' : 'Shares & forwards';

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
        ${statCard('Followers / Subscribers', followerVal, 'ic-blue', '👥', followerSub, d.followers > 0)}
        ${statCard('Reach / Views', fmt(d.reach), 'ic-accent', '📡', isLive ? 'Observed in retrieved records' : 'Estimated impressions', true)}
        ${statCard('Likes', fmt(d.likes), 'ic-red', '♥', 'Content interactions', true)}
        ${statCard('Shares', shareVal, 'ic-green', '↗', shareSub, (d.shares || 0) > 0)}
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
            <div class="info-card"><span class="info-lbl">Growth Rate</span><div class="info-val ${d.growth>=0?'tc-green':'tc-red'}">${d.growth ? (d.growth>=0?'+':'') + pct(d.growth) : 'Baseline pending'}</div></div>
            <div class="info-card"><span class="info-lbl">Best Post Time</span><div class="info-val" style="font-size:13px">${esc(d.bestPostTime)}</div></div>
          </div>
        </div>
      </div>
    </div>`;

  requestAnimationFrame(() => {
    renderAreaChart($('an_area'), d.growthSeries, generateDateLabels(d.period, d.growthSeries.length, state.chartPeriod));
    renderScoreRing($('an_ring'), clamp(d.engagement*5,0,100), { label:'Engagement', msg:d.scoreMsg });
    renderAreaChart($('an_engChart'), d.engageSeries.map(v=>Math.round(v)), generateDateLabels(d.period, d.engageSeries.length, state.chartPeriod), { color:'#059669' });
  });
}

function renderContentPage(ca, d) {
  const isYT = state.platform === 'YouTube';
  const avgShares = (isYT && !d.shares) ? 'Unavailable' : fmt(Math.round(d.shares / Math.max(d.contentVolume, 1)));
  const avgSharesSub = (isYT && !d.shares) ? 'Not in Data API' : 'Per post';

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
        ${statCard('Content Volume', d.contentVolume, 'ic-accent', '📄', 'Items in period', true)}
        ${statCard('Avg Likes/Post', fmt(Math.round(d.likes/Math.max(d.contentVolume,1))), 'ic-red', '♥', 'Average engagement', true)}
        ${statCard('Avg Comments', fmt(Math.round(d.comments/Math.max(d.contentVolume,1))), 'ic-green', '💬', 'Per post', true)}
        ${statCard('Avg Shares', avgShares, 'ic-blue', '↗', avgSharesSub, (d.shares || 0) > 0)}
      </div>

      <div class="grid-1-1">
        <div class="panel" id="c_actBars"></div>
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

  requestAnimationFrame(() => renderDynamicActivityComponent($('c_actBars'), d));
}

function renderAudiencePage(ca, d) {
  const ageDist = buildAgeDist(d);
  ca.innerHTML = `
    <div class="fade-in">
      <div class="page-header">
        <div class="page-header-info">
          <div class="panel-label">DEMOGRAPHIC INTELLIGENCE</div>
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

function renderSentimentPage(ca, d) {
  const emotionEntries = Object.entries(d.emotions).filter(([k,v])=>v>0).sort((a,b)=>b[1]-a[1]);
  ca.innerHTML = `
    <div class="fade-in">
      <div class="page-header">
        <div class="page-header-info">
          <div class="panel-label">NLP SENTIMENT & EMOTION ANALYSIS</div>
          <h2>Sentiment & Emotions</h2>
          <p>Multi-dimensional NLP classification${d.topic?` for "${esc(d.topic)}"`:''}.</p>
        </div>
        <button class="back-btn" onclick="goBack()">← Back</button>
      </div>

      <div class="grid-2-1">
        <div class="panel">
          <div class="panel-top"><div><div class="panel-label">SENTIMENT OVER TIME</div><h2>Positive Sentiment Trend</h2></div></div>
          <div id="s_sentChart"></div>
        </div>
        <div class="panel">
          <div class="panel-top"><div><div class="panel-label">POLARITY SPLIT</div><h2>Sentiment Breakdown</h2></div></div>
          <div id="s_donut"></div>
        </div>
      </div>

      <div class="panel mb">
        <div class="panel-top"><div><div class="panel-label">FINE-GRAINED EMOTION SPECTRUM</div><h2>Emotion Breakdown</h2></div></div>
        <div id="s_emotions"></div>
      </div>
    </div>`;

  requestAnimationFrame(() => {
    const sSeries = d.sentSeries.length ? d.sentSeries : [d.sentPositive];
    renderAreaChart($('s_sentChart'), sSeries, generateDateLabels(d.period, sSeries.length), { color:'#059669' });
    renderDonut($('s_donut'), [
      { label:'Positive', value:d.sentPositive, color:'#059669' },
      { label:'Negative', value:d.sentNegative, color:'#dc2626' },
      { label:'Neutral',  value:d.sentNeutral,  color:'#94a3b8' },
    ]);
    renderHBars($('s_emotions'), emotionEntries.map(([k,v])=>({label:`${emotionEmoji(k)} ${capitalise(k)}`, value:v, color:EMOTION_COLORS[k]||CHART_COLORS[0]})));
  });
}

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

      <div class="info-cards mb" style="grid-template-columns:repeat(4,1fr)">
        <div class="info-card"><span class="info-lbl">Total Trends</span><div class="info-val">${d.topTrends.length}</div></div>
        <div class="info-card"><span class="info-lbl">Top Growth</span><div class="info-val tc-green">↑${d.topTrends[0]?.growth_pct?.toFixed(0)||0}%</div></div>
        <div class="info-card"><span class="info-lbl">Top Mentions</span><div class="info-val">${fmtN(d.topTrends[0]?.mentions||0)}</div></div>
        <div class="info-card"><span class="info-lbl">Leading Topic</span><div class="info-val" style="font-size:13px">${esc(d.topTrends[0]?.name||'—')}</div></div>
      </div>

      <div class="panel mb">
        <div class="panel-top">
          <div><div class="panel-label">TREND RANKINGS</div><h2>Top 10 Trending Topics with Influencers</h2></div>
        </div>
        <div id="trend_table"></div>
      </div>

      <div class="panel mb">
        <div class="panel-top"><div><div class="panel-label">TRENDING KEYWORDS</div><h2>Hot Keywords & Hashtags</h2></div></div>
        <div class="tag-cloud">
          ${(d.trendKeywords||[]).concat(d.topTrends.map(t=>t.keyword||'')).filter(Boolean).slice(0,20).map((kw,i)=>`
            <span class="tag" style="border-color:${CHART_COLORS[i%CHART_COLORS.length]};color:${CHART_COLORS[i%CHART_COLORS.length]}">${esc(kw)}</span>`).join('')}
        </div>
      </div>

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

      <div class="info-cards mb" style="grid-template-columns:repeat(4,1fr)">
        <div class="info-card"><span class="info-lbl">Total Nodes</span><div class="info-val">${d.netNodes}</div><div class="info-sub">Users / entities</div></div>
        <div class="info-card"><span class="info-lbl">Connections</span><div class="info-val">${d.netConnections}</div><div class="info-sub">Active links</div></div>
        <div class="info-card"><span class="info-lbl">Communities</span><div class="info-val">${d.netCommunities}</div><div class="info-sub">Distinct clusters</div></div>
        <div class="info-card"><span class="info-lbl">Top Influencer</span><div class="info-val" style="font-size:13px">${esc(d.influencers?.[0]?.name||'—')}</div></div>
      </div>

      <div class="panel mb">
        <div class="panel-top">
          <div><div class="panel-label">NETWORK GRAPH</div><h2>Social Network Topology</h2></div>
          <span class="sec-badge" style="background:var(--accent-light);color:var(--accent)">Hover nodes for details</span>
        </div>
        <div id="net_graph"></div>
      </div>

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
    </div>`;

  requestAnimationFrame(() => {
    if (warnings.length) renderAICards($('ai_warnings'), warnings, true);
    const baseline = d.aiInsights.filter(i=>i.type!=='warning'&&i.type!=='alert');
    renderAICards($('ai_baseline'), baseline, true);
  });
}

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
            <div style="font-size:13px;color:var(--text-3)">Analytics Analyst · SIH 26152</div>
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
            <span style="color:var(--text-2)">Session Type</span><span>Active Session</span>
          </div>
        </div>
      </div>
    </div>`;
}
