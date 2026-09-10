# SocialIQ — Blockchain-based Audit & Integrity Layer
**SIH 2026 Problem Statement 26152 · Social Media Analytics System**
*Presented by Team NEXORA*

---

## 1. Executive Summary & Purpose

In SocialIQ, analytical intelligence reports inform critical decisions regarding public sentiment, narrative propagation, and engagement trends. To prevent fraudulent alterations or accidental tampering, SocialIQ implements a **Blockchain-based Audit & Integrity Layer**.

### Core Architecture Principle
- **PostgreSQL / Supabase** remains the main operational store for rich analytical reports, engagement metrics, and historical data.
- **The Blockchain** acts strictly as an **immutable, tamper-evident audit fingerprint reference**.
- **Zero Sensitive Data On-Chain**: No personal data, credentials, full social media text, or raw datasets are stored on-chain. Only the **Report ID**, **Canonical SHA-256 Hash**, **Timestamp**, and **Block Number** are committed.

```
+---------------------------+
|  Social Media Analytics   | (YouTube, Telegram, Reddit, X, Instagram, Facebook)
+-------------+-------------+
              |
              v
+---------------------------+
|   Generated Report/JSON   | (Metrics, Sentiment, Emotion, AI Summary)
+-------------+-------------+
              |
              +--------------------------------+
              | Canonical UTF-8 Serialization  |
              | Stable Recursive Key Sorting   |
              | Exclude Ephemeral Ticks        |
              v                                v
+---------------------------+    +---------------------------+
|    SHA-256 Hash Digest    |    |   Supabase / PostgreSQL   |
|   (32-byte Fingerprint)   |    |    (Off-Chain Storage)    |
+-------------+-------------+    +-------------+-------------+
              |                                |
              v                                |
+---------------------------+                  |
|  Solidity Smart Contract  |                  |
|  (SocialIQReportAudit)    |                  |
+-------------+-------------+                  |
              |                                |
              v                                v
+------------------------------------------------------------+
|                  INTEGRITY VERIFICATION                    |
| Recalculate Current SHA-256 <===> Smart Contract On-Chain  |
|      --> MATCH: VERIFIED    |   MISMATCH: MODIFIED         |
+------------------------------------------------------------+
```

---

## 2. Technical Stack

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Smart Contract** | Solidity (`^0.8.20`) | `SocialIQReportAudit.sol` audit registry with overwrite protection |
| **Blockchain Toolchain** | Hardhat Local Node | Local EVM JSON-RPC node (`http://127.0.0.1:8545`, Chain ID `31337`) |
| **Backend Integration** | Python + `web3.py` (v8.0) | Automated signer, receipt verification, canonical hashing |
| **Off-Chain Database** | PostgreSQL / Supabase | Audit metadata (`blockchain_audits` table), full report payloads |
| **Client Interface** | Vanilla JS / CSS | Live status badge, audit modal, copyable tx proofs, tamper test |

---

## 3. How It Works: Step-by-Step

### A. Canonical Report Hashing (`backend/blockchain/hasher.py`)
1. Filters out transient runtime values (e.g. `refresh_tick`, ephemeral UI timings).
2. Recursively sorts all dictionary keys to ensure deterministic serialization regardless of frontend object order.
3. Normalizes numeric types (rounding floats to 6 decimal places).
4. Produces compact UTF-8 JSON bytes with `(",", ":")` separators.
5. Computes `hashlib.sha256(canonical_bytes)` -> produces a 64-character hexadecimal digest and a 32-byte binary representation.

### B. Smart Contract Execution (`blockchain/contracts/SocialIQReportAudit.sol`)
1. Backend signs `recordAudit(string reportId, bytes32 reportHash, uint256 timestamp)` using server-side local development signer.
2. The contract checks if `reportId` was already audited:
   - If previously recorded with the **exact same hash**, it succeeds idempotently without spending redundant gas.
   - If an attempt is made to overwrite with a **different hash**, the contract reverts (`"immutability violation"`).
3. The contract records `reportHash`, `timestamp`, `blockNumber`, and `recordedBy`, emitting an `AuditRecorded` event.
4. Transaction receipt is confirmed on the EVM node, and metadata is saved into Supabase / PostgreSQL (`blockchain_audits`).

### C. Tamper-Evident Verification Flow
1. User clicks **"Verify Integrity"** in the dashboard.
2. The server loads the report payload and recomputes the SHA-256 canonical hash.
3. The server calls `verifyAudit(reportId, currentHash)` directly on the smart contract.
4. If hashes match: returns **`INTEGRITY: VERIFIED`** (Untampered).
5. If hashes differ (even by 1 integer in reach or sentiment): returns **`INTEGRITY: MODIFIED`** (Tamper detected).

---

## 4. Quick Start & Demonstration Guide

### Step 1: Start the Local EVM Node
In a separate terminal or background task:
```bash
cd blockchain
node ./node_modules/hardhat/internal/cli/cli.js node
```
*Listens on `http://127.0.0.1:8545` with Chain ID 31337.*

### Step 2: Deploy the Smart Contract
From the project root:
```bash
.\.venv\Scripts\python.exe -m backend.blockchain.deploy
```
*Output:*
- Contract Address: `0x5FbDB2315678afecb367f032d93F642f64180aa3`
- Saves deployment record to `blockchain/deployment.json` and updates `.env`.

### Step 3: Run Automated Tests
```bash
.\.venv\Scripts\python.exe -m pytest tests/test_blockchain.py -v
```
*Runs all 15 unit and integration tests verifying hashing, deployment, recording, verification, duplicate handling, and tamper simulation.*

### Step 4: Run Live SIH Demonstration
1. Start the SocialIQ API backend:
   ```bash
   .\.venv\Scripts\python.exe -m uvicorn backend.app:app --port 8001
   ```
2. Open the frontend dashboard (`frontend/index.html`).
3. Click the **"Blockchain: Ready"** status button in the top controls bar.
4. Click **"⚡ Record Audit on Blockchain"**:
   - Notice the genuine EVM transaction hash, block number, and contract address.
5. Click **"🔍 Verify Integrity"**:
   - Instantly shows **`INTEGRITY VERIFIED ✓`** with green status.
6. Click **"🧪 Simulate Tamper Test"**:
   - The system modifies 1 metric value and recalculates the hash.
   - Instantly shows **`ALERT: REPORT MODIFIED ✗`** with red status, demonstrating real tamper detection!
7. Open **✨ Ask SocialIQ AI** and ask:
   *"Is this report verified on the blockchain?"*
   - The AI responds with the actual transaction hash, block number, and cryptographic status from the smart contract!

---

## 5. Security & Privacy Guarantees

- **No Private Keys Exposed**: Private keys are held strictly server-side. The frontend receives only safe transaction hashes, contract addresses, and verification results.
- **Zero Data Leakage**: Complete social media messages and user profiles are never placed on-chain.
- **Graceful Degradation**: If the local blockchain node is offline or stopped, SocialIQ continues operating normally, honestly reporting `"Blockchain: Offline"` without crashing.
- **Tamper Evidence, Not Oracle Truth**: As emphasized by SIH guidelines, the blockchain proves that the report content has not been altered since audit creation; it does not claim to validate external reality.
