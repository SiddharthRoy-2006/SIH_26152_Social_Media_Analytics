/* ================================================================
   SOCIALIQ ANALYTICS — topology.js
   Network graph topology, interactive force layout simulation,
   topic-specific nodes, zoom (10% to 10,000%), cursor-centered zoom,
   pan & fit controls, and information propagation visualization.
   ================================================================ */

'use strict';

let _topologyZoom = 1.0;
let _topologyPan = { x: 0, y: 0 };
let _isTopologyDragging = false;
let _topologyDragStart = { x: 0, y: 0 };
let _lastRenderedBounds = { minX: 40, maxX: 720, minY: 35, maxY: 345 };

function zoomTopology(factor, cursorPoint) {
  const oldZoom = _topologyZoom;
  const newZoom = clamp(_topologyZoom * factor, 0.1, 100.0); // 10% to 10,000%
  if (oldZoom === newZoom) return;

  const W = 760, H = 380;
  const cx = cursorPoint ? cursorPoint.x : W / 2;
  const cy = cursorPoint ? cursorPoint.y : H / 2;

  // Cursor-centered zoom calculation: keep the SVG point under cursor fixed
  _topologyPan.x = cx - (cx - _topologyPan.x) * (newZoom / oldZoom);
  _topologyPan.y = cy - (cy - _topologyPan.y) * (newZoom / oldZoom);
  _topologyZoom = newZoom;

  updateTopologyTransform();
}

function resetTopologyZoom() {
  fitTopologyView();
}

function fitTopologyView() {
  const W = 760, H = 380;
  const b = _lastRenderedBounds;
  const graphW = Math.max(b.maxX - b.minX + 80, 100);
  const graphH = Math.max(b.maxY - b.minY + 80, 100);
  const graphCenterX = (b.minX + b.maxX) / 2;
  const graphCenterY = (b.minY + b.maxY) / 2;

  const scaleX = W / graphW;
  const scaleY = H / graphH;
  _topologyZoom = clamp(Math.min(scaleX, scaleY, 1.25), 0.35, 2.2);

  _topologyPan.x = (W / 2) - (graphCenterX * _topologyZoom);
  _topologyPan.y = (H / 2) - (graphCenterY * _topologyZoom);

  updateTopologyTransform();
}

function setExactZoom(zoomValue) {
  const oldZoom = _topologyZoom;
  const newZoom = clamp(zoomValue, 0.1, 100.0);
  if (oldZoom === newZoom) return;

  const W = 760, H = 380;
  const cx = W / 2;
  const cy = H / 2;

  _topologyPan.x = cx - (cx - _topologyPan.x) * (newZoom / oldZoom);
  _topologyPan.y = cy - (cy - _topologyPan.y) * (newZoom / oldZoom);
  _topologyZoom = newZoom;

  updateTopologyTransform();
}

function updateTopologyTransform() {
  const g = $('topologyCanvasG');
  const badge = $('zoomLevel');
  if (g) {
    g.setAttribute('transform', `translate(${_topologyPan.x.toFixed(2)}, ${_topologyPan.y.toFixed(2)}) scale(${_topologyZoom.toFixed(4)})`);
  }
  if (badge) {
    const pctVal = Math.round(_topologyZoom * 100);
    badge.textContent = `${pctVal}%`;
  }
}

function renderNetworkGraph(container, graphData, topic) {
  if (!container) return;
  if (!graphData || !graphData.nodes || !graphData.nodes.length) {
    container.innerHTML = `
      <div style="height:380px;display:flex;flex-direction:column;align-items:center;justify-content:center;color:var(--text-3);font-size:13px;gap:8px">
        <span>🌐</span>
        <div>No network topology available for this topic and platform.</div>
        <div style="font-size:11px;color:var(--text-3)">Network relationships require live public platform records or enabled demo mode.</div>
      </div>`;
    return;
  }

  const W = 760, H = 380;
  const nodes = graphData.nodes;
  const edges = graphData.edges || [];
  const communities = graphData.communities || [];

  // Map community colors
  const commColorMap = {};
  communities.forEach(c => { commColorMap[c.id] = c.color; });

  const n = nodes.length;
  const posMap = {};
  const kComms = Math.max(communities.length, 1);

  // Distribute community center anchors in a wide elliptical circle to avoid clustering
  const commCenters = {};
  communities.forEach((c, idx) => {
    const angle = (2 * Math.PI * idx) / kComms - Math.PI / 2;
    const rx = W * 0.32;
    const ry = H * 0.30;
    commCenters[c.id] = {
      x: W / 2 + rx * Math.cos(angle),
      y: H / 2 + ry * Math.sin(angle),
    };
  });

  // Calculate distinct layout positions with dynamic orbital spacing
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;

  // Track nodes per community
  const commNodeCount = {};

  nodes.forEach((node, i) => {
    const commId = node.community;
    const center = commCenters[commId] || { x: W / 2, y: H / 2 };
    commNodeCount[commId] = (commNodeCount[commId] || 0) + 1;
    const orderInComm = commNodeCount[commId];

    let x, y;
    if (node.is_hub) {
      // Hubs placed slightly offset near their community center
      const hubAngle = (orderInComm * 1.6);
      const hubDist = 12 + (orderInComm * 10);
      x = center.x + hubDist * Math.cos(hubAngle);
      y = center.y + hubDist * Math.sin(hubAngle);
    } else {
      // Regular content entities arranged in expanding petals
      const petalAngle = (orderInComm * 0.85) + (i * 0.4);
      const petalDist = 32 + ((orderInComm * 18) % 75);
      x = center.x + petalDist * Math.cos(petalAngle);
      y = center.y + petalDist * Math.sin(petalAngle);
    }

    // Keep within reasonable base boundaries
    x = clamp(x, 50, W - 50);
    y = clamp(y, 45, H - 45);

    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minY = Math.min(minY, y);
    maxY = Math.max(maxY, y);

    posMap[node.id] = {
      x: x,
      y: y,
      color: node.color || commColorMap[node.community] || '#2563eb',
    };
  });

  _lastRenderedBounds = {
    minX: isFinite(minX) ? minX : 50,
    maxX: isFinite(maxX) ? maxX : W - 50,
    minY: isFinite(minY) ? minY : 45,
    maxY: isFinite(maxY) ? maxY : H - 45,
  };

  // Build edges SVG with connection types
  const edgesHTML = edges.map(e => {
    const s = posMap[e.source];
    const t = posMap[e.target];
    if (!s || !t) return '';
    const strokeWidth = (safeN(e.weight) * 1.8).toFixed(1);
    const isTagged = e.type === 'tagged';
    const isCross = e.type === 'cross';
    return `<line x1="${s.x.toFixed(1)}" y1="${s.y.toFixed(1)}" x2="${t.x.toFixed(1)}" y2="${t.y.toFixed(1)}"
      class="net-edge${isCross ? ' cross' : ''}${isTagged ? ' tagged' : ''}"
      stroke="${isTagged ? 'var(--accent)' : 'var(--border-2)'}"
      stroke-opacity="${isTagged ? '0.45' : '0.35'}"
      stroke-width="${strokeWidth}"
      stroke-dasharray="${isTagged ? '3 3' : 'none'}"/>`;
  }).join('');

  // Build nodes SVG with rich hover metadata
  const nodesHTML = nodes.map(node => {
    const pos   = posMap[node.id] || { x: W / 2, y: H / 2, color: '#2563eb' };
    const isHub = !!node.is_hub;
    const r     = isHub ? 8.5 + safeN(node.influence) * 6.5 : 4.0 + safeN(node.influence) * 4.5;
    const label = isHub ? esc(node.label || '') : '';
    const nodeRole = node.type === 'channel' ? 'Channel Hub' : node.type === 'topic_tag' ? 'Topic Theme' : 'Content Entity';

    return `<g class="net-node${isHub ? ' net-hub' : ''}"
        data-name="${esc(node.label || '')}"
        data-comm="${esc(node.community_label || 'General')}"
        data-score="${safeN(node.influence).toFixed(3)}"
        data-role="${esc(nodeRole)}"
        data-views="${node.views ? fmt(node.views) : ''}"
        style="cursor:pointer">
      <circle cx="${pos.x.toFixed(1)}" cy="${pos.y.toFixed(1)}" r="${r.toFixed(1)}"
        fill="${pos.color}" fill-opacity="${isHub ? '0.96' : '0.75'}" stroke="#ffffff" stroke-width="${isHub ? '1.8' : '0.6'}"/>
      ${isHub && label ? `<text x="${pos.x.toFixed(1)}" y="${(pos.y + r + 10).toFixed(1)}"
        text-anchor="middle" font-size="9" font-weight="600" class="net-label" fill="var(--text)">${label}</text>` : ''}
    </g>`;
  }).join('');

  // Legend HTML
  const legendHTML = communities.slice(0, 6).map(c => `
    <div class="net-leg-item">
      <span class="net-leg-dot" style="background:${c.color}"></span>
      <span>${esc(c.label || '')}</span>
    </div>`).join('');

  const isLive = state.dataSource === 'live';
  const isDemo = state.dataSource === 'demo';
  const sourceLabel = isLive ? `LIVE — ${esc(state.platform)}` : isDemo ? 'DEMO DATA' : 'NOT CONFIGURED';

  container.innerHTML = `
    <div class="topology-header-actions" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:8px">
      <div style="font-size:12px;color:var(--text-3)">
        Topology Focus: <strong style="color:var(--text)">${esc(topic || 'General Ecosystem')}</strong> · 
        <span>${nodes.length} entities</span> · 
        <span>${edges.length} connections</span> · 
        <span class="source-tag-inline ${isLive ? 'live' : isDemo ? 'demo' : 'unconfigured'}">${sourceLabel}</span>
      </div>
      <div class="topology-zoom-toolbar">
        <button class="zoom-btn" id="topoZoomInBtn" title="Zoom In (Graph Layer)">＋</button>
        <button class="zoom-btn" id="topoZoomOutBtn" title="Zoom Out (Graph Layer)">－</button>
        <button class="zoom-btn" id="topoFitBtn" title="Fit & Center All Nodes">⟲ Fit</button>
        <span class="zoom-level-badge" id="zoomLevel">${Math.round(_topologyZoom * 100)}%</span>
      </div>
    </div>
    <div class="net-svg-wrap" id="netSvgWrap">
      <svg viewBox="0 0 ${W} ${H}" class="net-svg" id="netSvgElem" style="height:380px;width:100%;display:block;">
        <g id="topologyCanvasG" transform="translate(${_topologyPan.x.toFixed(2)}, ${_topologyPan.y.toFixed(2)}) scale(${_topologyZoom.toFixed(4)})">
          ${edgesHTML}
          ${nodesHTML}
        </g>
      </svg>
    </div>
    <div class="net-legend">${legendHTML}</div>`;

  // Bind zoom buttons
  $('topoZoomInBtn')?.addEventListener('click', () => zoomTopology(1.25));
  $('topoZoomOutBtn')?.addEventListener('click', () => zoomTopology(0.8));
  $('topoFitBtn')?.addEventListener('click', () => fitTopologyView());

  // Bind pan/drag and wheel zoom handlers on the viewport
  const wrap = $('netSvgWrap');
  const svgElem = $('netSvgElem');

  if (wrap && svgElem) {
    const getSvgPoint = (clientX, clientY) => {
      const rect = svgElem.getBoundingClientRect();
      return {
        x: (clientX - rect.left) * (W / rect.width),
        y: (clientY - rect.top) * (H / rect.height),
      };
    };

    wrap.addEventListener('pointerdown', e => {
      if (e.target.closest('.net-node') && e.button !== 0) return;
      _isTopologyDragging = true;
      wrap.classList.add('dragging');
      try {
        wrap.setPointerCapture(e.pointerId);
      } catch {}
      _topologyDragStart = {
        x: e.clientX - _topologyPan.x,
        y: e.clientY - _topologyPan.y,
      };
    });

    wrap.addEventListener('pointermove', e => {
      if (!_isTopologyDragging) return;
      _topologyPan.x = e.clientX - _topologyDragStart.x;
      _topologyPan.y = e.clientY - _topologyDragStart.y;
      updateTopologyTransform();
    });

    const stopDragging = (e) => {
      if (_isTopologyDragging) {
        _isTopologyDragging = false;
        wrap.classList.remove('dragging');
        try {
          if (e && e.pointerId) wrap.releasePointerCapture(e.pointerId);
        } catch {}
      }
    };

    wrap.addEventListener('pointerup', stopDragging);
    wrap.addEventListener('pointercancel', stopDragging);

    // Mouse wheel zoom centered under cursor
    wrap.addEventListener('wheel', e => {
      e.preventDefault();
      const delta = e.deltaY < 0 ? 1.15 : 0.88;
      const pt = getSvgPoint(e.clientX, e.clientY);
      zoomTopology(delta, pt);
    }, { passive: false });
  }

  // Bind hover tooltips
  const tooltip = $('netTooltip');
  container.querySelectorAll('.net-node').forEach(el => {
    el.addEventListener('mouseenter', ev => {
      if (!tooltip) return;
      const viewsInfo = el.dataset.views ? `<div style="font-size:11px;color:var(--text-3)">Views: ${esc(el.dataset.views)}</div>` : '';
      tooltip.innerHTML = `
        <div class="net-tt-name">${esc(el.dataset.name)}</div>
        <div class="net-tt-comm">${esc(el.dataset.comm)} · <strong style="color:var(--accent)">${esc(el.dataset.role || 'Entity')}</strong></div>
        <div class="net-tt-score">Influence Score: ${(safeN(el.dataset.score) * 100).toFixed(0)}%</div>
        ${viewsInfo}`;
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

  // Fit automatically on first render
  updateTopologyTransform();
}

function renderPropagation(container, propagation, topic) {
  if (!container) return;
  if (!propagation || !propagation.length) {
    container.innerHTML = '<p style="color:var(--text-3);font-size:13px;">No propagation sequence available for this topic.</p>';
    return;
  }

  const W = 700, H = 160, n = propagation.length;
  const step = (W - 60) / Math.max(n - 1, 1);
  const cy = H / 2;

  const pts = propagation.map((p, i) => ({
    x: 30 + i * step,
    y: cy,
    r: 14 + (i / Math.max(n - 1, 1)) * 22,
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
    const initials = (p.label || 'Pub').slice(0, 2).toUpperCase();
    return `
      <circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="${p.r.toFixed(1)}"
        fill="var(--accent)" fill-opacity="${0.22 + (p.step - 1) * 0.15}"/>
      <text x="${p.x.toFixed(1)}" y="${(p.y + 1).toFixed(1)}" text-anchor="middle" dominant-baseline="middle"
        font-size="9" font-weight="700" fill="var(--accent)" class="prop-step-label">${esc(initials)}</text>
      <text x="${p.x.toFixed(1)}" y="${(p.y + p.r + 11).toFixed(1)}" text-anchor="middle"
        font-size="8.5" fill="var(--text-2)" class="prop-step-label">${esc(p.label)}</text>
      <text x="${p.x.toFixed(1)}" y="${(p.y - p.r - 6).toFixed(1)}" text-anchor="middle"
        font-size="10" font-weight="700" fill="var(--accent)">${p.pct_reached}%</text>`;
  }).join('');

  container.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" class="prop-svg" style="height:160px">
      ${defs}${lines}${circles}
    </svg>
    <div style="text-align:center;margin-top:6px;font-size:11px;color:var(--text-3)">
      Publication and information propagation sequence for <strong>${esc(topic || 'topic stream')}</strong>
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
        <div class="info-sub">Entities / Channels / Tags</div>
      </div>
      <div class="info-card">
        <span class="info-lbl">Connections</span>
        <div class="info-val">${stats.total_edges || d.netConnections}</div>
        <div class="info-sub">Observed relationships</div>
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
      <span style="color:var(--text-3);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px">Dominant Cluster</span><br>
      <strong>${esc(topComm.label)}</strong> · ${topComm.node_count} nodes<br>
      <span style="color:var(--text-3)">Lead creator: ${esc(topComm.top_influencer)}</span>
    </div>` : ''}`;
}

