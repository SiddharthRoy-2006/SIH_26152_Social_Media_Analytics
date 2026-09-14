/**
 * SocialIQ AI Chat Assistant — chat.js
 * Full-Page Grounded Conversational Copilot
 * SIH Problem Statement 26152 · Team NEXORA
 *
 * Features:
 *   - Grounded analytics tool dispatch (get_metrics, get_sentiment, etc.)
 *   - Evidence-first AI responses via Python analytics backend
 *   - Copy response to clipboard
 *   - Edit last user message
 *   - New Chat / Clear History
 *   - Typing / loading indicator
 *   - Suggested prompts
 *   - Source attribution on every response
 *   - Session-bounded history (sessionStorage, max 50 messages)
 *   - Honest AI model badge (Analytical Fallback vs loaded LLM)
 *   - Back to Dashboard
 */

(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------

  let chatBusy = false;
  let _modelLoaded = false;   // updated from /api/chat/status
  let _modelChecked = false;

  // Bounded in-memory history (max 50 messages to keep UI responsive)
  const MAX_HISTORY = 50;
  let chatHistory = loadSessionHistory();

  const SUGGESTED_QUERIES = [
    'Summarize current performance',
    'What is the engagement rate and what drives it?',
    'Why is positive sentiment shifting?',
    'Who are the top network influencers?',
    'Show trending hashtags and keywords',
    'Explain engagement vs reach',
    'What is social media analytics?',
    'How does sentiment analysis work?'
  ];

  // ---------------------------------------------------------------------------
  // Session Storage (frontend-local, bounded, truthful)
  // ---------------------------------------------------------------------------

  function loadSessionHistory() {
    try {
      const raw = sessionStorage.getItem('socialiq-chat-history');
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) return parsed.slice(-MAX_HISTORY);
      }
    } catch (_) {}
    return [];
  }

  function saveSessionHistory() {
    try {
      // Keep only the last MAX_HISTORY messages to bound storage
      const bounded = chatHistory.slice(-MAX_HISTORY);
      sessionStorage.setItem('socialiq-chat-history', JSON.stringify(bounded));
    } catch (_) {}
  }

  function clearSessionHistory() {
    try {
      sessionStorage.removeItem('socialiq-chat-history');
    } catch (_) {}
  }

  // ---------------------------------------------------------------------------
  // Context from dashboard state
  // ---------------------------------------------------------------------------

  function getActiveContext() {
    const s = window.state || {};
    const isTopic = s.mode === 'topic';
    return {
      platform: s.platform || 'All Platforms',
      topic: isTopic ? (s.campaign?.topic || '') : '',
      period: s.dateRange || 'Last 30 Days',
      chart_period: s.chartPeriod || 'Monthly',
      mode: s.mode || 'general'
    };
  }

  // ---------------------------------------------------------------------------
  // Model status check (non-blocking, lazy)
  // ---------------------------------------------------------------------------

  function fetchModelStatus() {
    if (_modelChecked) return;
    _modelChecked = true;
    const apiBase = window.API_BASE || 'http://127.0.0.1:8001';
    fetch(`${apiBase}/api/chat/status`, { signal: AbortSignal.timeout(3000) })
      .then(r => r.json())
      .then(d => {
        _modelLoaded = !!(d?.primary_llm?.loaded);
        // Re-render model badge if chat is currently visible
        const badge = document.getElementById('chatModelBadge');
        if (badge) badge.textContent = _modelLoaded ? '✨ Qwen3-4B · Local LLM' : '⚙ Analytical Reasoning · Fact-First';
      })
      .catch(() => { _modelLoaded = false; });
  }

  // ---------------------------------------------------------------------------
  // Main render
  // ---------------------------------------------------------------------------

  function renderChatPage(ca, d) {
    if (!ca) return;
    const ctx = getActiveContext();
    const isTopic = ctx.mode === 'topic';

    ca.innerHTML = `
      <div class="fade-in chat-page-wrap">

        <!-- Page Header -->
        <div class="page-header">
          <div class="page-header-info">
            <div class="panel-label">CONVERSATIONAL AI INTELLIGENCE</div>
            <h2>Ask SocialIQ AI</h2>
            <p>Grounded reasoning copilot — verifies analytics before explaining. Never invents numbers.</p>
          </div>
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
            <button class="chat-ctrl-btn" id="chatNewBtn"    type="button" title="Start a new conversation">＋ New Chat</button>
            <button class="chat-ctrl-btn danger" id="chatClearBtn" type="button" title="Clear all chat history">🗑 Clear History</button>
            <button class="back-btn"  id="chatBackBtn"   type="button" onclick="goBack()">← Back to Dashboard</button>
          </div>
        </div>

        <!-- Active Context & Model Banner -->
        <div class="chat-context-banner">
          <div class="chat-context-left">
            <span class="chat-ctx-chip"><strong>Mode:</strong> ${isTopic ? '🎯 Topic Analysis' : '🌐 General Intelligence'}</span>
            <span class="chat-ctx-chip"><strong>Platform:</strong> ${esc(ctx.platform)}</span>
            ${isTopic && ctx.topic ? `<span class="chat-ctx-chip"><strong>Topic:</strong> &ldquo;${esc(ctx.topic)}&rdquo;</span>` : ''}
            <span class="chat-ctx-chip"><strong>Period:</strong> ${esc(ctx.period)}</span>
          </div>
          <div class="chat-context-right">
            <span class="ai-model-tag" id="chatModelBadge">⚙ Analytical Reasoning · Fact-First</span>
          </div>
        </div>

        <!-- Suggested Inquiries -->
        <div class="chat-suggestions-panel">
          <div class="chat-suggestions-label">SUGGESTED INQUIRIES:</div>
          <div class="chat-suggestions-list">
            ${SUGGESTED_QUERIES.map(q => `
              <button type="button" class="chat-suggestion-chip"
                      onclick="window.sendSocialIQPrompt('${q.replace(/'/g, "\\'")}')">${q}</button>
            `).join('')}
          </div>
        </div>

        <!-- Conversation Panel -->
        <div class="chat-full-panel">
          <div class="chat-stream-container" id="chatStream">
            <!-- Populated by renderStream() -->
          </div>

          <!-- Input Bar -->
          <div class="chat-input-bar">
            <div class="chat-input-wrapper">
              <input type="text" id="fullChatInput" class="chat-input-field"
                     placeholder="Ask about reach, engagement, sentiment, trends, or any analytics concept…"
                     autocomplete="off">
              <button type="button" id="fullChatSendBtn" class="chat-send-action"
                      title="Send message" aria-label="Send message">
                <span>Send</span>
                <span class="send-icon">➤</span>
              </button>
            </div>
            <div class="chat-footer-note">
              Press <strong>Enter</strong> to send · Analytics verified before explanation · No invented metrics
            </div>
          </div>
        </div>

      </div>
    `;

    renderStream();
    bindChatControls();
    fetchModelStatus();
  }

  // ---------------------------------------------------------------------------
  // Bind button events (called after innerHTML is set)
  // ---------------------------------------------------------------------------

  function bindChatControls() {
    const input   = document.getElementById('fullChatInput');
    const sendBtn = document.getElementById('fullChatSendBtn');
    const newBtn  = document.getElementById('chatNewBtn');
    const clrBtn  = document.getElementById('chatClearBtn');

    sendBtn?.addEventListener('click', handleUserSubmit);

    input?.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleUserSubmit();
      }
    });

    newBtn?.addEventListener('click', () => {
      if (chatBusy) return;
      chatHistory = [];
      saveSessionHistory();
      renderStream();
      input?.focus();
      showToast('New conversation started.');
    });

    clrBtn?.addEventListener('click', () => {
      if (chatBusy) return;
      if (!confirm('Clear all chat history? This cannot be undone.')) return;
      chatHistory = [];
      clearSessionHistory();
      renderStream();
      input?.focus();
      showToast('Chat history cleared.');
    });

    requestAnimationFrame(() => input?.focus());
  }

  // ---------------------------------------------------------------------------
  // Stream renderer
  // ---------------------------------------------------------------------------

  function renderStream() {
    const stream = document.getElementById('chatStream');
    if (!stream) return;

    if (chatHistory.length === 0) {
      stream.innerHTML = `
        <div class="chat-message-row assistant">
          <div class="chat-assistant-avatar">✨</div>
          <div class="chat-bubble-card">
            <div class="chat-bubble-header">
              <strong>SocialIQ Copilot</strong>
              <span class="chat-model-badge">Analytical Reasoning · Fact-First</span>
            </div>
            <div class="chat-bubble-text">
              <p>Hello! I am your <strong>SocialIQ AI Assistant</strong>. I retrieve verified analytics from the database before explaining trends, sentiment, and audience dynamics — I never invent metrics.</p>
              <p>Ask me to summarize current performance, explain a chart, investigate sentiment shifts, or identify top influencers. Use the suggested prompts above to get started.</p>
            </div>
          </div>
        </div>
      `;
      return;
    }

    stream.innerHTML = chatHistory.map((msg, idx) => renderMessageHTML(msg, idx)).join('');
    scrollStreamToBottom();
  }

  // ---------------------------------------------------------------------------
  // Single message HTML
  // ---------------------------------------------------------------------------

  function renderMessageHTML(msg, idx) {
    if (msg.role === 'user') {
      return `
        <div class="chat-message-row user">
          <div class="chat-bubble-card user-card">
            <div class="chat-bubble-text">${formatMessageText(msg.content)}</div>
            <div class="chat-msg-actions">
              <button class="chat-action-btn" type="button"
                      title="Edit this message" aria-label="Edit message"
                      onclick="window._chatEditMessage(${idx})">✏ Edit</button>
              <span class="chat-action-sep" aria-hidden="true">|</span>
              <button class="chat-action-btn delete" type="button"
                      title="Delete this message" aria-label="Delete message"
                      onclick="window._chatDeleteMessage(${idx})">🗑 Delete</button>
            </div>
          </div>
        </div>
      `;
    }

    const tools   = (msg.tools_used || []).map(t => `<span class="chat-tool-pill">⚙ ${esc(t)}</span>`).join('');
    const srcs    = (msg.sources || []).map(s => `<span class="chat-source-pill">✓ ${esc(s)}</span>`).join('');
    const metaHtml = (tools || srcs) ? `<div class="chat-meta-tags">${tools}${srcs}</div>` : '';

    return `
      <div class="chat-message-row assistant">
        <div class="chat-assistant-avatar">✨</div>
        <div class="chat-bubble-card">
          <div class="chat-bubble-header">
            <strong>SocialIQ Copilot</strong>
            <span class="chat-model-badge">Analytical Reasoning · Fact-First</span>
          </div>
          <div class="chat-bubble-text">${formatMessageText(msg.content)}</div>
          ${metaHtml}
          <div class="chat-msg-actions">
            <button class="chat-action-btn" type="button"
                    title="Copy response"
                    onclick="window._chatCopyResponse(${idx})">📋 Copy</button>
          </div>
        </div>
      </div>
    `;
  }

  function scrollStreamToBottom() {
    const stream = document.getElementById('chatStream');
    if (stream) stream.scrollTop = stream.scrollHeight;
  }

  // ---------------------------------------------------------------------------
  // Copy, Edit & Delete actions (global so onclick can call them)
  // ---------------------------------------------------------------------------

  window._chatCopyResponse = function (idx) {
    const msg = chatHistory[idx];
    if (!msg || msg.role !== 'assistant') return;
    const text = msg.content || '';
    navigator.clipboard.writeText(text)
      .then(() => showToast('Response copied to clipboard.'))
      .catch(() => {
        // Fallback for http:// origins where clipboard API may be blocked
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        showToast('Response copied.');
      });
  };

  window._chatEditMessage = function (idx) {
    const msg = chatHistory[idx];
    if (!msg || msg.role !== 'user') return;
    const input = document.getElementById('fullChatInput');
    if (!input) return;
    // Remove the user message and everything after it, let user re-submit
    chatHistory.splice(idx);
    saveSessionHistory();
    renderStream();
    input.value = msg.content;
    input.focus();
    // Move cursor to end
    const len = input.value.length;
    input.setSelectionRange(len, len);
  };

  window._chatDeleteMessage = function (idx) {
    const msg = chatHistory[idx];
    if (!msg || msg.role !== 'user') return;
    // Remove user message and its corresponding assistant answer if present
    const nextMsg = chatHistory[idx + 1];
    if (nextMsg && nextMsg.role === 'assistant') {
      chatHistory.splice(idx, 2);
    } else {
      chatHistory.splice(idx, 1);
    }
    saveSessionHistory();
    renderStream();
    showToast('Message deleted.');
  };

  // ---------------------------------------------------------------------------
  // Suggested prompt shortcut
  // ---------------------------------------------------------------------------

  window.sendSocialIQPrompt = function (promptText) {
    const input = document.getElementById('fullChatInput');
    if (input) {
      input.value = promptText;
      handleUserSubmit();
    }
  };

  // ---------------------------------------------------------------------------
  // Message submission & API call
  // ---------------------------------------------------------------------------

  async function handleUserSubmit() {
    const input   = document.getElementById('fullChatInput');
    const sendBtn = document.getElementById('fullChatSendBtn');
    if (!input || chatBusy) return;

    const query = input.value.trim();
    if (!query) return;

    input.value = '';
    chatBusy = true;
    if (sendBtn) sendBtn.disabled = true;

    // Enforce history bound before adding
    if (chatHistory.length >= MAX_HISTORY) {
      chatHistory = chatHistory.slice(-MAX_HISTORY + 2);
    }

    chatHistory.push({ role: 'user', content: query });
    renderStream();

    // Typing indicator
    const stream = document.getElementById('chatStream');
    const typingElem = document.createElement('div');
    typingElem.className = 'chat-message-row assistant typing-row';
    typingElem.id = 'chatTypingIndicator';
    typingElem.innerHTML = `
      <div class="chat-assistant-avatar">✨</div>
      <div class="chat-typing-indicator">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span style="font-size:11.5px;color:var(--text-3);margin-left:6px">Analyzing verified analytics…</span>
      </div>
    `;
    if (stream) {
      stream.appendChild(typingElem);
      scrollStreamToBottom();
    }

    try {
      const ctx     = getActiveContext();
      const apiBase = window.API_BASE || 'http://127.0.0.1:8001';

      const s = window.state || {};
      const d = s.data || {};
      const dashboardContext = {
        platform:          s.platform || ctx.platform,
        topic:             ctx.topic,
        query:             s.campaign?.query || '',
        period:            s.dateRange || ctx.period,
        chart_period:      s.chartPeriod || ctx.chart_period,
        mode:              s.mode || ctx.mode,
        data_source:       s.dataSource || 'empty',
        data_available:    !!s.dataAvail,
        metrics:           d.metrics || null,
        sentiment:         d.sentiment || null,
        emotions:          d.emotions || null,
        activity_series:   d.activity_series || d.activity || [],
        growth_series:     d.growth_series || [],
        top_trends:        d.top_trends || (d.trending?.topics ? d.trending.topics.map(t => ({ name: t })) : []),
        influencers:       d.influencers || [],
        insights:          d.insights || d.ai_insights || [],
        blockchain_status: s.blockchainStatus || null,
      };

      const payload = {
        message:           query,
        platform:          ctx.platform,
        topic:             ctx.topic,
        period:            ctx.period,
        chart_period:      ctx.chart_period,
        mode:              ctx.mode,
        dashboard_context: dashboardContext,
      };

      const res = await fetch(`${apiBase}/api/chat/message`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload),
        signal:  AbortSignal.timeout(30000)
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);

      const data      = await res.json();
      const replyText = data.answer || data.reply || 'No answer generated.';
      const tools     = data.tool_used ? [data.tool_used] : (data.tools_used || []);
      const sources   = data.sources || ['SocialIQ Analytics Engine'];

      chatHistory.push({
        role:       'assistant',
        content:    replyText,
        tools_used: tools,
        sources:    sources
      });

    } catch (err) {
      const isTimeout = err.name === 'TimeoutError' || err.message?.includes('timeout');
      chatHistory.push({
        role:       'assistant',
        content:    isTimeout
          ? '⚠️ **Request Timeout:** The backend took too long to respond. The server may be busy — please try again.'
          : `⚠️ **Connection Error:** Could not reach the AI service (${err.message}).\n\nPlease ensure the FastAPI server is running on port 8001.`,
        tools_used: ['connection_probe'],
        sources:    ['Local Error Handler']
      });
    } finally {
      chatBusy = false;
      if (sendBtn) sendBtn.disabled = false;
      const ind = document.getElementById('chatTypingIndicator');
      if (ind) ind.remove();
      saveSessionHistory();
      renderStream();
      scrollStreamToBottom();
    }
  }

  // ---------------------------------------------------------------------------
  // Markdown-like text formatter (fixes ol/ul closing tag bug)
  // ---------------------------------------------------------------------------

  function formatMessageText(text) {
    if (!text) return '';

    // Escape HTML
    let s = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    // Headings: ### text
    s = s.replace(/^### (.+)$/gm, '<h4 style="margin:8px 0 4px">$1</h4>');
    // Bold **text**
    s = s.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Italic *text* (but not ** already handled)
    s = s.replace(/(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');
    // Inline code `text`
    s = s.replace(/`([^`]+)`/g, '<code style="background:var(--surface-2,#f3f4f6);padding:1px 4px;border-radius:3px;font-family:monospace;font-size:0.9em">$1</code>');

    // Line-by-line list parsing
    const lines = s.split('\n');
    let inUl = false;
    let inOl = false;
    const out = [];

    for (const line of lines) {
      const trimmed = line.trim();

      // Unordered list: • or -
      if (trimmed.startsWith('• ') || trimmed.startsWith('- ')) {
        if (inOl) { out.push('</ol>'); inOl = false; }
        if (!inUl) { out.push('<ul>'); inUl = true; }
        out.push(`<li>${trimmed.substring(2)}</li>`);
        continue;
      }

      // Ordered list: 1. 2. etc.
      if (/^\d+\.\s/.test(trimmed)) {
        if (inUl) { out.push('</ul>'); inUl = false; }
        if (!inOl) { out.push('<ol>'); inOl = true; }
        out.push(`<li>${trimmed.replace(/^\d+\.\s/, '')}</li>`);
        continue;
      }

      // Close open list before any other content
      if (inUl) { out.push('</ul>'); inUl = false; }
      if (inOl) { out.push('</ol>'); inOl = false; }

      if (trimmed) {
        out.push(`<p>${trimmed}</p>`);
      }
    }

    // Close any still-open list
    if (inUl) out.push('</ul>');
    if (inOl) out.push('</ol>');

    return out.join('');
  }

  // ---------------------------------------------------------------------------
  // Exports
  // ---------------------------------------------------------------------------

  window.renderChatPage = renderChatPage;

})();
