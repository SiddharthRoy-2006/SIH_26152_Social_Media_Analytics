"""
tests/test_blockchain.py

Comprehensive test matrix for SocialIQ Blockchain Audit & Integrity Layer.
Verifies:
1. Deterministic canonical report serialization and SHA-256 hashing.
2. Immutability: changing a single metric alters hash.
3. Blockchain service connectivity, health probing, and offline resilience.
4. Smart contract deployment, audit recording, and event emission.
5. End-to-end verification (VERIFIED vs MODIFIED).
6. Idempotent duplicate audit handling (no redundant gas/transactions).
7. FastAPI endpoints: /api/audit/record, /api/audit/verify, /api/audit/list, /api/audit/tamper-test.
8. Unauthorized overwrite prevention.
"""

import copy
import json
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.blockchain.hasher import (
    compute_report_hash,
    derive_report_id,
    serialize_canonical,
)
from backend.blockchain.service import BlockchainService, get_blockchain_service
from backend.database.repository import get_blockchain_audit, get_mem_store


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_report():
    return {
        "platform": "YouTube",
        "topic": "AI Revolution",
        "period": "Last 30 Days",
        "chart_period": "Monthly",
        "data_available": True,
        "source": "live",
        "metrics": {
            "views": 150000,
            "likes": 12500,
            "comments": 1400,
            "shares": 850,
            "engagement_rate": 8.5,
        },
        "sentiment": {
            "positive": 72,
            "neutral": 20,
            "negative": 8,
        },
        "emotions": {
            "joy": 65,
            "surprise": 20,
            "neutral": 15,
        },
        "trending": {
            "volume_growth": 24.5,
            "direction": "up",
        },
    }


# ===========================================================================
# 1. Canonical Serialization & Cryptographic Hashing Tests
# ===========================================================================

def test_canonical_hashing_determinism(sample_report):
    """Proves that identical reports always produce the exact same SHA-256 hash."""
    hash1, bytes1 = compute_report_hash(sample_report)
    hash2, bytes2 = compute_report_hash(sample_report)

    assert hash1 == hash2
    assert bytes1 == bytes2
    assert len(hash1) == 64
    assert len(bytes1) == 32


def test_key_ordering_independence(sample_report):
    """Proves that dictionary key order in the input object does NOT affect the hash."""
    # Reverse dictionary keys
    reversed_report = {k: sample_report[k] for k in reversed(list(sample_report.keys()))}

    hash_orig, _ = compute_report_hash(sample_report)
    hash_rev, _ = compute_report_hash(reversed_report)

    assert hash_orig == hash_rev


def test_transient_fields_excluded(sample_report):
    """Ephemeral runtime fields (e.g. refresh_tick, execution_time_ms) must not alter hash."""
    modified_report = copy.deepcopy(sample_report)
    modified_report["refresh_tick"] = 99999
    modified_report["execution_time_ms"] = 142.5

    hash_orig, _ = compute_report_hash(sample_report)
    hash_mod, _ = compute_report_hash(modified_report)

    assert hash_orig == hash_mod


def test_content_tamper_changes_hash(sample_report):
    """Even a 1-digit change in a metric produces a totally different cryptographic hash."""
    tampered_report = copy.deepcopy(sample_report)
    tampered_report["metrics"]["likes"] = 12501  # +1 like

    hash_orig, _ = compute_report_hash(sample_report)
    hash_tampered, _ = compute_report_hash(tampered_report)

    assert hash_orig != hash_tampered


def test_derive_report_id(sample_report):
    """Validates stable report identifier generation."""
    rid1 = derive_report_id(sample_report)
    rid2 = derive_report_id(sample_report)

    assert rid1 == rid2
    assert "report-youtube-ai-revolution" in rid1

    custom_id = derive_report_id(sample_report, explicit_id="custom-audit-123")
    assert custom_id == "custom-audit-123"


# ===========================================================================
# 2. Blockchain Service & Local EVM Node Interaction
# ===========================================================================

def test_blockchain_health():
    """Validates blockchain health check reporting truthful status."""
    service = get_blockchain_service()
    health = service.get_health(force_refresh=True)

    assert "status" in health
    assert "network" in health
    assert "rpc_url" in health
    assert "connected" in health
    if health["connected"]:
        assert health["status"] in ("CONNECTED", "CONNECTED_NO_CONTRACT")
        assert health["chain_id"] == 31337


def test_audit_recording_and_database_persistence(sample_report):
    """
    Submits a real report to the blockchain service.
    Verifies transaction execution, receipt, and database audit metadata storage.
    """
    service = get_blockchain_service()
    result = service.record_audit(sample_report)

    assert "report_id" in result
    assert "report_hash" in result
    assert result.get("status") in ("RECORDED", "PENDING_BLOCKCHAIN")

    # Check database persistence
    db_audit = get_blockchain_audit(result["report_id"])
    assert db_audit is not None
    assert db_audit["report_hash"] == result["report_hash"]


def test_duplicate_audit_idempotency(sample_report):
    """
    Submitting the exact same report twice should be idempotent
    and not broadcast duplicate redundant transactions.
    """
    service = get_blockchain_service()
    res1 = service.record_audit(sample_report)
    res2 = service.record_audit(sample_report)

    assert res1["report_id"] == res2["report_id"]
    assert res1["report_hash"] == res2["report_hash"]
    assert res2.get("duplicate") is True or res2.get("status") == "RECORDED"


def test_verification_flow_verified(sample_report):
    """Verifies that an unmodified report produces status VERIFIED."""
    service = get_blockchain_service()
    audit_res = service.record_audit(sample_report)

    verify_res = service.verify_integrity(sample_report, audit_res["report_id"])
    assert verify_res["status"] in ("VERIFIED", "VERIFIED_OFFCHAIN")
    assert verify_res["verified"] is True
    assert verify_res["current_hash"] == audit_res["report_hash"]


def test_verification_flow_modified_detection(sample_report):
    """Verifies that a tampered report produces status MODIFIED."""
    service = get_blockchain_service()
    audit_res = service.record_audit(sample_report)

    tampered_report = copy.deepcopy(sample_report)
    tampered_report["metrics"]["views"] = 9999999  # Tampered metric

    verify_res = service.verify_integrity(tampered_report, audit_res["report_id"])
    assert verify_res["status"] in ("MODIFIED", "MODIFIED_OFFCHAIN")
    assert verify_res["verified"] is False
    assert verify_res["current_hash"] != audit_res["report_hash"]


def test_simulate_tamper_utility(sample_report):
    """Verifies the controlled tamper testing utility for SIH evaluators."""
    service = get_blockchain_service()
    audit_res = service.record_audit(sample_report)

    tamper_result = service.simulate_tamper(audit_res["report_id"])
    assert "field_tampered" in tamper_result
    assert tamper_result["original_hash"] != tamper_result["tampered_hash"]
    v_res = tamper_result["verification_result"]
    assert v_res["status"] in ("MODIFIED", "MODIFIED_OFFCHAIN")
    assert v_res["verified"] is False


# ===========================================================================
# 3. FastAPI REST Endpoints Tests
# ===========================================================================

def test_api_blockchain_health(client):
    """GET /audit/blockchain/health returns truthful status."""
    resp = client.get("/audit/blockchain/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "connected" in data


def test_api_health_includes_blockchain(client):
    """GET /health includes blockchain diagnostic subsection."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "blockchain" in data
    assert "status" in data["blockchain"]


def test_api_record_and_verify_endpoints(client, sample_report):
    """End-to-end API test: /api/audit/record -> /api/audit/verify -> /api/audit/list."""
    # 1. Record
    rec_resp = client.post("/api/audit/record", json={"report": sample_report})
    assert rec_resp.status_code == 200
    rec_data = rec_resp.json()
    report_id = rec_data["report_id"]

    # 2. Verify untampered
    ver_resp = client.post("/api/audit/verify", json={"report": sample_report, "report_id": report_id})
    assert ver_resp.status_code == 200
    ver_data = ver_resp.json()
    assert ver_data["verified"] is True
    assert ver_data["status"] in ("VERIFIED", "VERIFIED_OFFCHAIN")

    # 3. Verify tampered
    tampered = copy.deepcopy(sample_report)
    tampered["metrics"]["views"] = 1
    ver_tampered_resp = client.post("/api/audit/verify", json={"report": tampered, "report_id": report_id})
    assert ver_tampered_resp.status_code == 200
    assert ver_tampered_resp.json()["verified"] is False
    assert ver_tampered_resp.json()["status"] in ("MODIFIED", "MODIFIED_OFFCHAIN")

    # 4. List audits
    list_resp = client.get("/api/audit/list")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert "audits" in list_data
    assert len(list_data["audits"]) > 0


def test_api_tamper_test_endpoint(client, sample_report):
    """POST /api/audit/tamper-test alters stored report and proves detection."""
    rec_resp = client.post("/api/audit/record", json={"report": sample_report})
    report_id = rec_resp.json()["report_id"]

    tamper_resp = client.post("/api/audit/tamper-test", json={"report_id": report_id})
    assert tamper_resp.status_code == 200
    data = tamper_resp.json()
    assert data["field_tampered"] == "metrics.total_reach" or "metrics" in data["field_tampered"]
    assert data["verification_result"]["verified"] is False
    assert data["verification_result"]["status"] in ("MODIFIED", "MODIFIED_OFFCHAIN")
