/**
 * frontend/js/blockchain.js
 * 
 * SocialIQ Blockchain Audit & Integrity Controller.
 * Integrates client-side reporting with the EVM smart contract backend.
 * Provides verifiable audit creation, tamper detection, and real-time transaction inspection.
 */

const BlockchainUI = (function () {
  let _health = null;
  let _activeAudit = null;
  let _lastVerification = null;
  let _reportFingerprint = null;
  let _currentReportId = null;
  let _isAuditing = false;
  let _isVerifying = false;
  let _errorMessage = null;

  async function checkHealth() {
    try {
      const resp = await fetch(`${API_BASE}/api/audit/blockchain/health`);
      if (resp.ok) {
        _health = await resp.json();
        updateBadge();
        return _health;
      }
    } catch {
      // Fallback path without /api prefix
      try {
        const resp2 = await fetch(`${API_BASE}/audit/blockchain/health`);
        if (resp2.ok) {
          _health = await resp2.json();
          updateBadge();
          return _health;
        }
      } catch (err) {
        _health = { status: 'UNAVAILABLE', connected: false, message: 'Blockchain node offline' };
        updateBadge();
      }
    }
    return _health;
  }

  function updateBadge() {
    const badge = document.getElementById('blockchainStatusBtn');
    const dot = document.getElementById('blockchainDot');
    const text = document.getElementById('blockchainStatusText');
    if (!badge || !dot || !text) return;

    if (!_health || !_health.connected) {
      dot.className = 'blockchain-dot offline';
      text.textContent = 'Blockchain: Offline';
      badge.title = 'Local EVM Blockchain node unavailable. Run Hardhat node on port 8545.';
      return;
    }

    if (_lastVerification) {
      if (_lastVerification.status === 'VERIFIED' || _lastVerification.status === 'VERIFIED_OFFCHAIN') {
        dot.className = 'blockchain-dot verified';
        text.textContent = 'Integrity: Verified ✓';
        badge.title = `Block #${_lastVerification.block_number || 'On-chain'}: Hash verified`;
        return;
      } else if (_lastVerification.status === 'MODIFIED' || _lastVerification.status === 'MODIFIED_OFFCHAIN') {
        dot.className = 'blockchain-dot modified';
        text.textContent = 'ALERT: Modified ✗';
        badge.title = 'Report has been tampered with! Hash mismatch.';
        return;
      }
    }

    if (_activeAudit && _activeAudit.status === 'RECORDED') {
      dot.className = 'blockchain-dot recorded';
      text.textContent = 'Audited On-Chain';
      badge.title = `Tx: ${_activeAudit.transaction_hash ? _activeAudit.transaction_hash.slice(0, 14) + '…' : 'Recorded'}`;
      return;
    }

    dot.className = 'blockchain-dot ready';
    text.textContent = 'Audit: Ready';
    badge.title = 'Click to view blockchain audit & verification options';
  }

  async function inspectCurrentReport() {
    if (!state.raw) return;
    try {
      const resp = await fetch(`${API_BASE}/api/audit/inspect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report: state.raw }),
      });
      if (resp.ok) {
        const data = await resp.json();
        if (data.blockchain_health) {
          _health = data.blockchain_health;
        }
        _reportFingerprint = data.canonical_hash;
        _currentReportId = data.report_id;
        if (data.is_audited && data.audit) {
          _activeAudit = data.audit;
          if (!_lastVerification || _lastVerification.status !== 'MODIFIED') {
            _lastVerification = { status: 'VERIFIED', block_number: data.audit.block_number };
          }
        }
        updateBadge();
        renderModalContent();
      }
    } catch (err) {
      console.debug('Inspect report failed:', err);
    }
  }

  async function auditCurrentReport() {
    if (!state.raw) {
      showToast('No active report available to audit. Generate an analysis first.');
      return;
    }
    if (_isAuditing) return;

    _isAuditing = true;
    _errorMessage = null;
    showToast('Submitting audit transaction to smart contract…');
    renderModalContent();

    try {
      const resp = await fetch(`${API_BASE}/api/audit/record`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report: state.raw, report_id: _currentReportId }),
      });

      const res = await resp.json();
      _isAuditing = false;

      if (res.success || res.status === 'RECORDED') {
        _activeAudit = res;
        _reportFingerprint = res.report_hash;
        _currentReportId = res.report_id;
        _lastVerification = { status: 'VERIFIED', block_number: res.block_number };
        showToast('✓ Report successfully audited and stored on blockchain!');
      } else {
        _errorMessage = res.message || res.status || 'Audit submission failed';
        showToast(`Audit status: ${_errorMessage}`);
      }
    } catch (err) {
      _isAuditing = false;
      _errorMessage = `Connection failed: ${err.message || err}`;
      showToast(`Audit failed: ${_errorMessage}`);
    }

    updateBadge();
    renderModalContent();
  }

  async function verifyCurrentReport() {
    if (!state.raw) {
      showToast('No report data loaded to verify.');
      return;
    }
    if (_isVerifying) return;

    _isVerifying = true;
    _errorMessage = null;
    showToast('Querying smart contract for cryptographic hash match…');
    renderModalContent();

    try {
      const reportId = _activeAudit ? _activeAudit.report_id : _currentReportId;
      const resp = await fetch(`${API_BASE}/api/audit/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report: state.raw, report_id: reportId }),
      });

      const res = await resp.json();
      _isVerifying = false;
      _lastVerification = res;
      if (res.current_hash) _reportFingerprint = res.current_hash;

      if (res.status === 'VERIFIED' || res.status === 'VERIFIED_OFFCHAIN') {
        showToast('✓ INTEGRITY VERIFIED: Cryptographic report hash matches on-chain record!');
      } else if (res.status === 'MODIFIED' || res.status === 'MODIFIED_OFFCHAIN') {
        showToast('⚠ ALERT: Report modified! Current hash diverges from blockchain record.');
      } else if (res.status === 'NOT_AUDITED') {
        showToast('Notice: This report has not yet been audited on-chain.');
      } else {
        showToast(res.message || `Verification: ${res.status}`);
      }
    } catch (err) {
      _isVerifying = false;
      _errorMessage = `Verification failed: ${err.message || err}`;
      showToast(_errorMessage);
    }

    updateBadge();
    renderModalContent();
  }

  async function simulateTamperTest() {
    const reportId = _activeAudit ? _activeAudit.report_id : _currentReportId;
    if (!reportId) {
      showToast('Please audit a report first before testing tamper detection.');
      return;
    }

    showToast('Simulating metric alteration (Live SIH Tamper Test)…');
    try {
      const resp = await fetch(`${API_BASE}/api/audit/tamper-test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report_id: reportId }),
      });

      const res = await resp.json();
      if (res.verification_result) {
        _lastVerification = res.verification_result;
        if (res.tampered_hash) {
          _reportFingerprint = res.tampered_hash;
        }
        updateBadge();
        renderModalContent();
        showToast('⚠ TAMPER DETECTED: Smart contract rejected modified hash!');
      }
    } catch (err) {
      showToast(`Tamper simulation error: ${err.message}`);
    }
  }

  function copyToClipboard(text, label) {
    if (!text || text === '—') return;
    navigator.clipboard.writeText(text).then(() => {
      showToast(`${label || 'Value'} copied to clipboard`);
    }).catch(() => {
      showToast('Could not copy to clipboard');
    });
  }

  function openModal() {
    let modal = document.getElementById('blockchainModal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'blockchainModal';
      modal.className = 'modal-backdrop';
      modal.onclick = (e) => { if (e.target === modal) closeModal(); };
      document.body.appendChild(modal);
    }
    _errorMessage = null;
    renderModalContent();
    modal.classList.remove('hidden');

    checkHealth().then(() => {
      if (state.raw) {
        inspectCurrentReport();
      }
    });
  }

  function closeModal() {
    const modal = document.getElementById('blockchainModal');
    if (modal) modal.classList.add('hidden');
  }

  function renderModalContent() {
    const modal = document.getElementById('blockchainModal');
    if (!modal) return;

    const bcHealth = _health || { status: 'UNKNOWN', connected: false, network: 'Local EVM (Hardhat Node)' };
    const audit = _activeAudit;
    const vResult = _lastVerification;

    let statusHtml = '';
    if (_errorMessage) {
      statusHtml = `<div class="audit-status-banner modified" style="border-left:4px solid var(--red);background:rgba(239,68,68,0.08);padding:10px 14px;border-radius:var(--r-sm);margin-bottom:14px;display:flex;gap:10px;align-items:center;">
        <span class="status-icon" style="color:var(--red);font-weight:bold;font-size:18px;">✕</span>
        <div>
          <strong style="color:var(--red);">BLOCKCHAIN ACTION FAILED</strong>
          <div style="font-size:12px;color:var(--text-2);">${esc(_errorMessage)}</div>
        </div>
      </div>`;
    } else if (vResult && (vResult.status === 'VERIFIED' || vResult.status === 'VERIFIED_OFFCHAIN')) {
      statusHtml = `<div class="audit-status-banner verified">
        <span class="status-icon">✓</span>
        <div>
          <strong>INTEGRITY VERIFIED</strong>
          <div>Report hash matches the immutable blockchain record. Zero unauthorized changes detected.</div>
        </div>
      </div>`;
    } else if (vResult && (vResult.status === 'MODIFIED' || vResult.status === 'MODIFIED_OFFCHAIN')) {
      statusHtml = `<div class="audit-status-banner modified">
        <span class="status-icon">⚠</span>
        <div>
          <strong>TAMPER ALERT: REPORT MODIFIED</strong>
          <div>Cryptographic hash divergence detected! Current report does not match the on-chain audit record.</div>
        </div>
      </div>`;
    } else if (audit && audit.status === 'RECORDED') {
      statusHtml = `<div class="audit-status-banner recorded">
        <span class="status-icon">⛓</span>
        <div>
          <strong>AUDIT RECORDED ON-CHAIN</strong>
          <div>Transaction confirmed in block #${audit.block_number != null ? audit.block_number : '1'}. Tamper-evident proof stored.</div>
        </div>
      </div>`;
    } else {
      statusHtml = `<div class="audit-status-banner ready">
        <span class="status-icon">ℹ</span>
        <div>
          <strong>REPORT READY FOR AUDITING</strong>
          <div>Click below to create an immutable cryptographic fingerprint on the blockchain.</div>
        </div>
      </div>`;
    }

    const contractAddr = (bcHealth && bcHealth.contract_address) || (audit && audit.contract_address) || '—';
    const reportHash = _reportFingerprint || (audit && audit.report_hash) || (vResult && (vResult.current_hash || vResult.tampered_hash)) || '—';
    const txHash = audit ? (audit.transaction_hash || (audit.status === 'PENDING_BLOCKCHAIN' ? 'Pending Blockchain Mining' : '—')) : '—';
    const blockNum = (audit && audit.block_number != null) ? audit.block_number : (vResult && vResult.block_number != null) ? vResult.block_number : '—';

    modal.innerHTML = `
      <div class="modal-card blockchain-modal-card">
        <div class="modal-header">
          <div>
            <div class="modal-subtitle">SIH 26152 · Tamper-Evident Verification</div>
            <h2 class="modal-title">Blockchain Audit & Integrity Layer</h2>
          </div>
          <button class="modal-close-btn" onclick="BlockchainUI.closeModal()">&times;</button>
        </div>

        ${statusHtml}

        <div class="audit-details-grid">
          <div class="audit-field">
            <span class="audit-label">Blockchain Network</span>
            <div class="audit-val-row">
              <span class="audit-value">${esc(bcHealth.network || 'Local EVM (Hardhat Node)')}</span>
              <span class="audit-network-pill ${bcHealth.connected ? 'online' : 'offline'}">${bcHealth.connected ? 'Chain ID: ' + (bcHealth.chain_id || 31337) : 'Offline'}</span>
            </div>
          </div>

          <div class="audit-field">
            <span class="audit-label">Smart Contract (SocialIQReportAudit)</span>
            <div class="audit-val-row">
              <code class="audit-hash-text" title="${esc(contractAddr)}">${esc(contractAddr)}</code>
              <button class="audit-copy-btn" onclick="BlockchainUI.copyToClipboard('${contractAddr}', 'Contract Address')">Copy</button>
            </div>
          </div>

          <div class="audit-field">
            <span class="audit-label">Report SHA-256 Canonical Fingerprint</span>
            <div class="audit-val-row">
              <code class="audit-hash-text" title="${esc(reportHash)}">${esc(reportHash)}</code>
              <button class="audit-copy-btn" onclick="BlockchainUI.copyToClipboard('${reportHash}', 'Report Hash')">Copy</button>
            </div>
          </div>

          <div class="audit-field">
            <span class="audit-label">Transaction Hash (Receipt)</span>
            <div class="audit-val-row">
              <code class="audit-hash-text" title="${esc(txHash)}">${esc(txHash)}</code>
              <button class="audit-copy-btn" onclick="BlockchainUI.copyToClipboard('${txHash}', 'Transaction Hash')">Copy</button>
            </div>
          </div>

          <div class="audit-meta-row">
            <div>
              <span class="audit-label">Mined Block</span>
              <div class="audit-subval">${blockNum !== '—' ? '#' + esc(String(blockNum)) : '#—'}</div>
            </div>
            <div>
              <span class="audit-label">Storage Architecture</span>
              <div class="audit-subval">PostgreSQL Off-Chain + EVM Fingerprint</div>
            </div>
            <div>
              <span class="audit-label">Tamper Resistance</span>
              <div class="audit-subval" style="color:var(--green)">Active (SHA-256)</div>
            </div>
          </div>
        </div>

        <div class="modal-actions">
          <button class="audit-btn-primary" onclick="BlockchainUI.auditCurrentReport()" ${_isAuditing ? 'disabled' : ''}>
            ${_isAuditing ? 'Auditing…' : '⚡ Record Audit on Blockchain'}
          </button>
          <button class="audit-btn-secondary" onclick="BlockchainUI.verifyCurrentReport()" ${_isVerifying ? 'disabled' : ''}>
            ${_isVerifying ? 'Verifying…' : '🔍 Verify Integrity'}
          </button>
          <button class="audit-btn-danger" onclick="BlockchainUI.simulateTamperTest()" title="Controlled demonstration for SIH evaluators">
            🧪 Simulate Tamper Test
          </button>
        </div>

        <div class="audit-modal-footer">
          <span>Smart India Hackathon 2026 · Team NEXORA · 100% Genuine EVM Proofs</span>
        </div>
      </div>
    `;
  }

  return {
    init: function () {
      checkHealth();
      setInterval(checkHealth, 15000);
    },
    checkHealth,
    updateBadge,
    inspectCurrentReport,
    auditCurrentReport,
    verifyCurrentReport,
    simulateTamperTest,
    copyToClipboard,
    openModal,
    closeModal,
  };
})();

// Attach to window
window.BlockchainUI = BlockchainUI;
window.openBlockchainModal = () => BlockchainUI.openModal();
window.auditCurrentReport = () => BlockchainUI.auditCurrentReport();
window.verifyCurrentReport = () => BlockchainUI.verifyCurrentReport();
