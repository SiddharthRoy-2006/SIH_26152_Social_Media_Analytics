"""
backend/routes/audit.py

FastAPI routes for Blockchain Audit & Integrity Layer.
Exposes endpoints for auditing reports, verifying report integrity against the smart contract,
listing recent audits, and performing tamper detection demonstrations.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.blockchain.service import get_blockchain_service
from backend.database.repository import (
    get_blockchain_audit,
    list_recent_blockchain_audits,
)

router = APIRouter(prefix="/audit", tags=["blockchain-audit"])


class AuditInspectRequest(BaseModel):
    report: dict[str, Any] = Field(..., description="Full analytical report object to inspect")


class AuditRecordRequest(BaseModel):
    report: dict[str, Any] = Field(..., description="Full analytical report object to audit")
    report_id: str | None = Field(default=None, description="Optional custom report identifier")


class AuditVerifyRequest(BaseModel):
    report: dict[str, Any] | None = Field(default=None, description="Report object to verify")
    report_id: str | None = Field(default=None, description="Identifier of the report to verify")


class TamperTestRequest(BaseModel):
    report_id: str = Field(..., description="Report ID of previously audited report")


@router.post("/inspect")
def inspect_report(payload: AuditInspectRequest) -> dict[str, Any]:
    """
    Computes deterministic canonical SHA-256 hash of report, derives report_id,
    and returns existing audit metadata (if already audited) along with blockchain health.
    """
    service = get_blockchain_service()
    return service.inspect_report(payload.report)


@router.post("/record")
def record_report_audit(payload: AuditRecordRequest) -> dict[str, Any]:
    """
    Computes deterministic canonical SHA-256 hash of report, submits audit transaction
    to the Solidity smart contract, and persists off-chain metadata.
    """
    if not payload.report:
        raise HTTPException(status_code=400, detail="Empty report payload provided.")

    service = get_blockchain_service()
    result = service.record_audit(payload.report, explicit_report_id=payload.report_id)
    return result


@router.post("/verify")
def verify_report_integrity(payload: AuditVerifyRequest) -> dict[str, Any]:
    """
    Verifies report integrity against the immutable smart contract record.
    Recalculates canonical SHA-256 hash and compares with on-chain hash.
    Returns VERIFIED if identical, or MODIFIED if tampered.
    """
    if not payload.report and not payload.report_id:
        raise HTTPException(status_code=400, detail="Provide either report payload or report_id.")

    service = get_blockchain_service()
    result = service.verify_integrity(report_payload=payload.report, report_id=payload.report_id)
    return result


@router.get("/list")
def list_audits(limit: int = Query(default=15, ge=1, le=100)) -> dict[str, Any]:
    """Return recent blockchain audits for display in the audit log UI."""
    audits = list_recent_blockchain_audits(limit=limit)
    return {
        "count": len(audits),
        "audits": audits,
    }


@router.get("/{report_id}")
def get_audit(report_id: str) -> dict[str, Any]:
    """Retrieve audit record and metadata for a specific report ID."""
    record = get_blockchain_audit(report_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"No audit record found for report {report_id}.")
    
    # Do not expose raw report payload in lightweight GET
    safe_record = {k: v for k, v in record.items() if k != "report_payload"}
    return safe_record


@router.post("/tamper-test")
def simulate_tamper_test(payload: TamperTestRequest) -> dict[str, Any]:
    """
    Live SIH evaluator demonstration:
    Alters a metric in an audited report and re-verifies against the smart contract,
    demonstrating immediate detection of unauthorized modification.
    """
    service = get_blockchain_service()
    result = service.simulate_tamper(payload.report_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/blockchain/health")
def get_blockchain_health() -> dict[str, Any]:
    """Direct health endpoint for blockchain RPC and contract status."""
    service = get_blockchain_service()
    return service.get_health(force_refresh=True)
