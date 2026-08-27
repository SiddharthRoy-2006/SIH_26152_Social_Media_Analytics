/* ================================================================
   SOCIALIQ ANALYTICS — topology.js
   Network graph topology, interactive force layout simulation,
   topic-specific nodes, zoom (+ / - / Fit) and pan controls,
   and information propagation visualization.
   ================================================================ */

'use strict';

let _topologyZoom = 1.0;
let _topologyPan = { x: 0, y: 0 };
let _isTopologyDragging = false;
let _topologyDragStart = { x: 0, y: 0 };

function zoomTopology(factor) {
  _topologyZoom = clamp(_topologyZoom * factor, 0.4, 3.5);
  updateTopologyTransform();
}

function resetTopologyZoom() {
  _topologyZoom = 1.0;
  _topologyPan = { x: 0, y: 0 };
  updateTopologyTransform();
}

function updateTopologyTransform() {
  const g = $('topologyCanvasG');
  const badge = $('zoomLevel');
  if (g) {
    g.setAttribute('transform', `translate(${_topologyPan.x}, ${_topologyPan.y}) scale(${_topologyZoom})`);
  }
  if (badge) {
    badge.textContent = `${Math.round(_topologyZoom * 100)}%`;
  }
}

function renderNetworkGraph(container, graphData, topic) {
  if (!container) return;
  if (!graphData || !graphData.nodes || !graphData.nodes.length) {
    container.innerHTML = '<div style="height:320px;display:flex;align-items:center;justify-content:center;color:var(--text-3);font-size:13px;">No network topology available.</div>';
    return;
  }

  const W = 760, H = 380;
  const nodes = graphData.nodes;
  const edges = graphData.edges || [];
  const communities = graphData.communities || [];

  // Map community colors
  const commColorMap = {};
  communities.forEach(c => { commColorMap[c.id] = c.color; });

  // Deterministic 2D force simulation approximation
  const n = nodes.length;
  const posMap = {};
  const kComms = Math.max(communities.length, 1);

  // Community centers around circle
  const commCenters = {};
  communities.forEach((c, idx) => {
    const angle = (2 * Math.PI * idx) / kComms;
    const cr = Math.min(W, H) * 0.28;
    commCenters[c.id] = {
      x: W / 2 + cr * Math.cos(angle),
      y: H / 2 + cr * Math.sin(angle),
    };
  });

  nodes.forEach((node, i) => {
    const center = commCenters[node.community] || { x: W / 2, y: H / 2 };
    const localAngle = (2 * Math.PI * (i % 8)) / 8;
    const localR = 25 + ((i * 19) % 55);
    posMap[node.id] = {
      x: clamp(center.x + localR * Math.cos(localAngle), 40, W - 40),
      y: clamp(center.y + localR * Math.sin(localAngle), 35, H - 35),
      color: commColorMap[node.community] || '#2563eb',
    };
  });

  // Build edges SVG
  const edgesHTML = edges.map(e => {
    const s = posMap[e.source];
    const t = posMap[e.target];
    if (!s || !t) return '';
    return `<line x1="${s.x.toFixed(1)}" y1="${s.y.toFixed(1)}" x2="${t.x.toFixed(1)}" y2="${t.y.toFixed(1)}"
      class="net-edge${e.type==='cross'?' cross':''}" stroke-width="${(safeN(e.weight)*1.5).toFixed(1)}"/>`;
  }).join('');

  // Build nodes SVG
  const nodesHTML = nodes.map(node => {
    const pos   = posMap[node.id] || { x: W / 2, y: H / 2, color: '#2563eb' };
    const r     = node.is_hub ? 9 + safeN(node.influence) * 7 : 4.5 + safeN(node.influence) * 5.5;
    const label = node.is_hub ? esc(node.label || '') : '';
    return `<g class="net-node${node.is_hub ? ' net-hub' : ''}"
        data-name="${esc(node.label || '')}"
        data-comm="${esc(node.community_label || '')}"
        data-score="${safeN(node.influence).toFixed(3)}"
        data-inf="${node.is_hub ? 'Hub / Influencer' : ''}"
        style="cursor:pointer">
      <circle cx="${pos.x.toFixed(1)}" cy="${pos.y.toFixed(1)}" r="${r.toFixed(1)}"
        fill="${pos.color}" fill-opacity="${node.is_hub ? '0.95' : '0.72'}" stroke="#fff" stroke-width="${node.is_hub ? '1.5' : '0.5'}"/>
      ${node.is_hub && label ? `<text x="${pos.x.toFixed(1)}" y="${(pos.y + r + 9).toFixed(1)}"
        text-anchor="middle" font-size="9" font-weight="600" class="net-label" fill="var(--text)">${label}</text>` : ''}
    </g>`;
  }).join('');

  // Legend
  const legendHTML = communities.slice(0, 6).map(c => `
    <div class="net-leg-item">
      <span class="net-leg-dot" style="background:${c.color}"></span>
      <span>${esc(c.label || '')}</span>
    </div>`).join('');

  container.innerHTML = `
    <div class="topology-header-actions" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <div style="font-size:12px;color:var(--text-3)">
        Topology Focus: <strong style="color:var(--text)">${esc(topic || 'General Ecosystem')}</strong> · ${nodes.length} entities · ${edges.length} connections
      </div>
      <div class="topology-zoom-toolbar">
        <button class="zoom-btn" onclick="zoomTopology(1.25)" title="Zoom In">＋</button>
        <button class="zoom-btn" onclick="zoomTopology(0.8)" title="Zoom Out">－</button>
        <button class="zoom-btn" onclick="resetTopologyZoom()" title="Reset / Fit to View">⟲ Fit</button>
        <span class="zoom-level-badge" id="zoomLevel">${Math.round(_topologyZoom * 100)}%</span>
      </div>
    </div>
    <div class="net-svg-wrap" id="netSvgWrap">
      <svg viewBox="0 0 ${W} ${H}" class="net-svg" id="netSvgElem" style="height:380px">
        <g id="topologyCanvasG" transform="translate(${_topologyPan.x}, ${_topologyPan.y}) scale(${_topologyZoom})">
          ${edgesHTML}
          ${nodesHTML}
        </g>
      </svg>
    </div>
    <div class="net-legend">${legendHTML}</div>`;

  // Bind pan/drag and wheel zoom handlers
  const wrap = $('netSvgWrap');
  if (wrap) {
    wrap.addEventListener('mousedown', e => {
      if (e.target.closest('.net-node')) return;
      _isTopologyDragging = true;
      wrap.classList.add('dragging');
      _topologyDragStart = { x: e.clientX - _topologyPan.x, y: e.clientY - _topologyPan.y };
    });

    window.addEventListener('mousemove', e => {
      if (!_isTopologyDragging) return;
      _topologyPan.x = e.clientX - _topologyDragStart.x;
      _topologyPan.y = e.clientY - _topologyDragStart.y;
      updateTopologyTransform();
    });

    window.addEventListener('mouseup', () => {
      if (_isTopologyDragging) {
        _isTopologyDragging = false;
        wrap?.classList.remove('dragging');
      }
    });

    wrap.addEventListener('wheel', e => {
      e.preventDefault();
      const delta = e.deltaY < 0 ? 1.15 : 0.88;
      _topologyZoom = clamp(_topologyZoom * delta, 0.4, 3.5);
      updateTopologyTransform();
    }, { passive: false });
  }

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

function renderPropagation(container, propagation, topic) {
  if (!container) return;
  if (!propagation || !propagation.length) {
    container.innerHTML = '<p style="color:var(--text-3);font-size:13px;">No propagation data.</p>';
    return;
  }

  const W = 700, H = 160, n = propagation.length;
  const step = (W - 60) / Math.max(n - 1, 1);
  const cy = H / 2;

  const pts = propagation.map((p, i) => ({
    x: 30 + i * step,
    y: cy,
    r: 14 + (i / (n - 1)) * 24,
    ...p,
  }));

  const defs = `<defs>
    <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="var(--border-2)"/>
    </marker>
  </defs>`;

  const lines = pts.slice(0, -1).map((p, i) => {
    const next = pts[i + 1];
    const gap  = next.x - p.x - p.r - next.r - 4;
    return `<line x1="${(p.x + p.r + 2).toFixed(1)}" y1="${cy}" x2="${(p.x + gap + p.r + 2).toFixed(1)}" y2="${cy}"
      stroke="var(--border-2)" stroke-width="1.5" marker-end="url(#arrow)"/>`;
  }).join('');

  const circles = pts.map(p => {
    const initials = p.label.slice(0, 2);
    return `
      <circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="${p.r.toFixed(1)}"
        fill="var(--accent)" fill-opacity="${0.2 + (p.step - 1) * 0.14}"/>
      <text x="${p.x.toFixed(1)}" y="${(p.y + 1).toFixed(1)}" text-anchor="middle" dominant-baseline="middle"
        font-size="9" font-weight="700" fill="var(--accent)" class="prop-step-label">${esc(initials)}</text>
      <text x="${p.x.toFixed(1)}" y="${(p.y + p.r + 10).toFixed(1)}" text-anchor="middle"
        font-size="8.5" fill="var(--text-2)" class="prop-step-label">${esc(p.label)}</text>
      <text x="${p.x.toFixed(1)}" y="${(p.y - p.r - 5).toFixed(1)}" text-anchor="middle"
        font-size="10" font-weight="700" fill="var(--accent)">${p.pct_reached}%</text>`;
  }).join('');

  container.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" class="prop-svg" style="height:160px">
      ${defs}${lines}${circles}
    </svg>
    <div style="text-align:center;margin-top:6px;font-size:11px;color:var(--text-3)">
      Information propagation path for <strong>${esc(topic || 'trending narrative')}</strong>
    </div>`;
}

function renderNetworkStatsPanel(container, d) {
  if (!container) return;
  const graph = d.networkGraph;
  const stats = graph?.stats || {};
  const comms = graph?.communities || [];
  const topComm = comms.sort((a, b) => b.node_count - a.node_count)[0];
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
        <div class="info-val">${((stats.density || 0) * 100).toFixed(2)}%</div>
        <div class="info-sub">Connectivity ratio</div>
      </div>
    </div>
    ${topComm ? `<div style="margin-top:10px;padding:12px;background:var(--surface-2);border-radius:var(--r-md);font-size:13px">
      <span style="color:var(--text-3);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px">Largest Community</span><br>
      <strong>${esc(topComm.label)}</strong> · ${topComm.node_count} members<br>
      <span style="color:var(--text-3)">Top influencer: ${esc(topComm.top_influencer)}</span>
    </div>` : ''}`;
}
