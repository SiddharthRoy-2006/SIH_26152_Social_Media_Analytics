"""
backend/blockchain/service.py

High-performance, production-grade Blockchain Service for SocialIQ Analytics.
Handles Web3 connection, contract interactions, transaction management,
canonical hashing, and tamper-evident integrity verification.

Safety guarantees:
- Never crashes analytics if blockchain node is unreachable.
- Never logs, returns, or leaks private keys.
- Idempotent: avoids duplicate transactions for identical report hashes.
- Tamper detection: instantly flags mismatches between current report and on-chain hash.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Any

from web3 import Web3
from web3.exceptions import Web3Exception

from backend.blockchain.hasher import (
    compute_report_hash,
    derive_report_id,
    serialize_canonical,
)
from backend.core.config import settings
from backend.database.repository import (
    get_blockchain_audit,
    save_blockchain_audit,
    update_blockchain_audit_status,
)

logger = logging.getLogger("blockchain.service")

# Contract Artifact Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACT_PATH = PROJECT_ROOT / "blockchain" / "artifacts" / "contracts" / "SocialIQReportAudit.sol" / "SocialIQReportAudit.json"
DEPLOYMENT_FILE = PROJECT_ROOT / "blockchain" / "deployment.json"

# Local testnet default development key (Hardhat Node account #0)
DEV_DEFAULT_PRIVATE_KEY = (
    "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
)


class BlockchainService:
    """Singleton service managing Web3 RPC connection and audit smart contract interactions."""

    def __init__(self) -> None:
        self._w3: Web3 | None = None
        self._contract = None
        self._abi: list[dict[str, Any]] | None = None
        self._bytecode: str | None = None
        self._last_health_check: float = 0.0
        self._cached_health: dict[str, Any] | None = None

    def get_w3(self) -> Web3:
        """Returns or initializes Web3 instance with configured RPC provider."""
        rpc_url = settings.blockchain_rpc_url or "http://127.0.0.1:8545"
        if self._w3 is None:
            self._w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 5.0}))
        return self._w3

    def is_connected(self) -> bool:
        """Probe whether the EVM blockchain RPC is reachable."""
        try:
            w3 = self.get_w3()
            return bool(w3.is_connected())
        except Exception:
            return False

    def load_artifact(self) -> dict[str, Any]:
        """Load contract ABI and bytecode from compilation artifact."""
        if self._abi is not None and self._bytecode is not None:
            return {"abi": self._abi, "bytecode": self._bytecode}

        if ARTIFACT_PATH.exists():
            try:
                with open(ARTIFACT_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._abi = data.get("abi", [])
                    self._bytecode = data.get("bytecode", "")
                    return data
            except Exception as exc:
                logger.warning("Failed to load artifact file: %s", exc)

        return {"abi": [], "bytecode": ""}

    def get_contract_address(self) -> str:
        """Resolve contract address from settings or deployment.json."""
        configured = settings.blockchain_contract_address.strip()
        if configured and Web3.is_address(configured):
            try:
                w3 = self.get_w3()
                if w3.is_connected():
                    code = w3.eth.get_code(Web3.to_checksum_address(configured))
                    if code and len(code) > 2:
                        return configured
            except Exception:
                return configured

        if DEPLOYMENT_FILE.exists():
            try:
                with open(DEPLOYMENT_FILE, "r", encoding="utf-8") as f:
                    deploy_info = json.load(f)
                    addr = deploy_info.get("contract_address", "") or deploy_info.get("address", "")
                    if addr and Web3.is_address(addr):
                        return addr.strip()
            except Exception:
                pass

        return configured or ""

    def deploy_contract(self) -> str | None:
        """
        Deploy SocialIQReportAudit smart contract to the connected EVM node
        using Account #0. Updates deployment.json and returns contract address.
        """
        if not self.is_connected():
            logger.warning("Cannot deploy contract: EVM node is not reachable.")
            return None

        artifact = self.load_artifact()
        abi = artifact.get("abi")
        bytecode = artifact.get("bytecode")
        if not abi or not bytecode:
            logger.warning("Cannot deploy contract: artifact ABI or bytecode missing.")
            return None

        try:
            w3 = self.get_w3()
            account = self.get_account()
            Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
            nonce = w3.eth.get_transaction_count(account.address)
            gas_price = w3.eth.gas_price

            logger.info("Deploying SocialIQReportAudit to EVM from %s...", account.address)
            tx = Contract.constructor().build_transaction({
                "from": account.address,
                "nonce": nonce,
                "gas": 2_000_000,
                "gasPrice": gas_price,
                "chainId": w3.eth.chain_id,
            })

            pk = settings.blockchain_private_key.strip() or DEV_DEFAULT_PRIVATE_KEY
            if not pk.startswith("0x"):
                pk = "0x" + pk

            signed = w3.eth.account.sign_transaction(tx, private_key=pk)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=15)
            deployed_addr = receipt.contractAddress

            if deployed_addr:
                deployed_addr = Web3.to_checksum_address(deployed_addr)
                self._contract = w3.eth.contract(address=deployed_addr, abi=abi)
                # Persist to deployment.json
                deploy_info = {
                    "contract_address": deployed_addr,
                    "deployer_address": account.address,
                    "transaction_hash": tx_hash.hex(),
                    "block_number": receipt.blockNumber,
                    "chain_id": w3.eth.chain_id,
                    "rpc_url": settings.blockchain_rpc_url,
                    "network_name": settings.blockchain_network_name,
                    "deployed_at": datetime.now(timezone.utc).isoformat(),
                }
                try:
                    with open(DEPLOYMENT_FILE, "w", encoding="utf-8") as f:
                        json.dump(deploy_info, f, indent=2)
                    logger.info("SocialIQReportAudit deployed successfully to %s", deployed_addr)
                except Exception as file_err:
                    logger.warning("Could not write deployment.json: %s", file_err)
                return deployed_addr

        except Exception as exc:
            logger.error("Contract deployment failed: %s", exc)
            return None

    def ensure_contract_deployed(self) -> bool:
        """
        Verify that the contract is deployed on-chain; if the node is connected
        but the contract has no bytecode at the configured address, automatically deploy it.
        """
        if not self.is_connected():
            return False

        w3 = self.get_w3()
        contract_addr = self.get_contract_address()

        if contract_addr and Web3.is_address(contract_addr):
            try:
                checksum_addr = Web3.to_checksum_address(contract_addr)
                code = w3.eth.get_code(checksum_addr)
                if code and len(code) > 2:
                    return True
            except Exception:
                pass

        # Node is connected but no contract exists at address -> deploy automatically
        new_addr = self.deploy_contract()
        return bool(new_addr)

    def get_contract(self):
        """Returns loaded Web3 contract instance if address and ABI are valid."""
        if self._contract is not None:
            return self._contract

        if self.is_connected():
            self.ensure_contract_deployed()

        contract_addr = self.get_contract_address()
        if not contract_addr or not Web3.is_address(contract_addr):
            return None

        artifact = self.load_artifact()
        abi = artifact.get("abi")
        if not abi:
            return None

        try:
            w3 = self.get_w3()
            checksum_addr = Web3.to_checksum_address(contract_addr)
            self._contract = w3.eth.contract(address=checksum_addr, abi=abi)
            return self._contract
        except Exception as exc:
            logger.warning("Could not instantiate contract: %s", exc)
            return None

    def get_account(self):
        """Returns signing account configured from environment or dev default."""
        pk = settings.blockchain_private_key.strip()
        if not pk:
            # Fallback to standard local development test account
            pk = DEV_DEFAULT_PRIVATE_KEY

        if not pk.startswith("0x"):
            pk = "0x" + pk

        w3 = self.get_w3()
        return w3.eth.account.from_key(pk)

    def get_health(self, force_refresh: bool = False) -> dict[str, Any]:
        """
        Return comprehensive, truthful health metrics for the blockchain subsystem.
        Never throws exceptions.
        """
        now = time.time()
        if not force_refresh and self._cached_health and (now - self._last_health_check < 5.0):
            return dict(self._cached_health)

        rpc_url = settings.blockchain_rpc_url
        contract_addr = self.get_contract_address()
        network_name = settings.blockchain_network_name

        if not settings.blockchain_enabled:
            health = {
                "status": "DISABLED",
                "connected": False,
                "network": network_name,
                "rpc_url": rpc_url,
                "chain_id": None,
                "block_number": None,
                "contract_address": contract_addr,
                "contract_ready": False,
                "message": "Blockchain auditing disabled in configuration.",
            }
            self._cached_health = health
            self._last_health_check = now
            return health

        try:
            w3 = self.get_w3()
            connected = w3.is_connected()
            if not connected:
                health = {
                    "status": "UNAVAILABLE",
                    "connected": False,
                    "network": network_name,
                    "rpc_url": rpc_url,
                    "chain_id": None,
                    "block_number": None,
                    "contract_address": contract_addr,
                    "contract_ready": False,
                    "message": f"Cannot reach local EVM RPC node at {rpc_url}.",
                }
                self._cached_health = health
                self._last_health_check = now
                return health

            chain_id = w3.eth.chain_id
            block_number = w3.eth.block_number

            # Ensure contract is deployed and ready
            contract_ready = self.ensure_contract_deployed()
            contract_addr = self.get_contract_address()
            contract_msg = "Contract verified and ready on-chain." if contract_ready else "Contract deployment pending."

            account = self.get_account()
            account_address = account.address if account else None

            health = {
                "status": "CONNECTED" if contract_ready else "CONNECTED_NO_CONTRACT",
                "connected": True,
                "network": network_name,
                "rpc_url": rpc_url,
                "chain_id": chain_id,
                "block_number": block_number,
                "contract_address": contract_addr,
                "contract_ready": contract_ready,
                "account_address": account_address,
                "message": "Blockchain connected: " + contract_msg,
            }
        except Exception as exc:
            health = {
                "status": "ERROR",
                "connected": False,
                "network": network_name,
                "rpc_url": rpc_url,
                "chain_id": None,
                "block_number": None,
                "contract_address": contract_addr,
                "contract_ready": False,
                "message": f"Blockchain connection error: {str(exc)}",
            }

        self._cached_health = health
        self._last_health_check = now
        return health

    # -----------------------------------------------------------------------
    # Report Audit Operations
    # -----------------------------------------------------------------------

    def record_audit(
        self,
        report_payload: dict[str, Any],
        explicit_report_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Computes canonical SHA-256 hash of report_payload, checks for duplicates,
        submits audit transaction to the Solidity contract, waits for receipt,
        and saves off-chain metadata to the database.
        """
        report_id = derive_report_id(report_payload, explicit_report_id)
        hex_hash, raw_hash_bytes = compute_report_hash(report_payload)
        now_dt = datetime.now(timezone.utc)
        epoch_ts = int(now_dt.timestamp())

        report_meta = {
            "platform": report_payload.get("platform", "Unknown"),
            "topic": report_payload.get("topic", ""),
            "period": report_payload.get("period", ""),
            "chart_period": report_payload.get("chart_period", ""),
            "generated_at": now_dt.isoformat(),
        }

        # Check if already audited locally
        existing_db_audit = get_blockchain_audit(report_id)
        if existing_db_audit and existing_db_audit.get("report_hash") == hex_hash:
            v_status = existing_db_audit.get("verification_status")
            if v_status == "RECORDED":
                logger.info("Report %s already audited with identical hash (%s). Reusing audit record.", report_id, v_status)
                return {
                    "success": True,
                    "report_id": report_id,
                    "report_hash": hex_hash,
                    "status": "RECORDED",
                    "duplicate": True,
                    "transaction_hash": existing_db_audit.get("transaction_hash"),
                    "block_number": existing_db_audit.get("block_number"),
                    "contract_address": existing_db_audit.get("contract_address"),
                    "network": existing_db_audit.get("blockchain_network"),
                    "recorded_at": str(existing_db_audit.get("recorded_at")),
                    "message": "Report was already audited with this exact cryptographic hash.",
                }
            elif v_status == "PENDING_BLOCKCHAIN" and not self.is_connected():
                logger.info("Report %s already saved as PENDING_BLOCKCHAIN and node is still offline.", report_id)
                return {
                    "success": False,
                    "report_id": report_id,
                    "report_hash": hex_hash,
                    "status": "PENDING_BLOCKCHAIN",
                    "duplicate": True,
                    "transaction_hash": None,
                    "block_number": None,
                    "contract_address": existing_db_audit.get("contract_address"),
                    "network": existing_db_audit.get("blockchain_network"),
                    "recorded_at": str(existing_db_audit.get("recorded_at")),
                    "message": "Report was already saved locally pending blockchain connection.",
                }

        # Verify blockchain is online and contract loaded
        contract = self.get_contract()
        if contract is None or not self.is_connected():
            logger.warning("Blockchain unavailable; saving audit as PENDING_BLOCKCHAIN.")
            audit_id = f"audit-{report_id[:24]}-{int(time.time())}"
            saved = save_blockchain_audit(
                audit_id=audit_id,
                report_id=report_id,
                report_hash=hex_hash,
                blockchain_network=settings.blockchain_network_name,
                chain_id=settings.blockchain_chain_id,
                contract_address=self.get_contract_address() or "unconfigured",
                transaction_hash=None,
                block_number=None,
                verification_status="PENDING_BLOCKCHAIN",
                audited_by=None,
                report_metadata=report_meta,
                report_payload=report_payload,
            )
            return {
                "success": False,
                "report_id": report_id,
                "report_hash": hex_hash,
                "status": "PENDING_BLOCKCHAIN",
                "message": "Blockchain node is currently unavailable. Audit record saved locally.",
                "recorded_at": now_dt.isoformat(),
            }

        w3 = self.get_w3()
        account = self.get_account()

        try:
            # Check on-chain duplicate state
            try:
                on_chain_record = contract.functions.getAudit(report_id).call()
                # returns (reportHash, timestamp, blockNumber, recordedBy, exists)
                if on_chain_record[4]:  # exists
                    on_chain_hash_hex = on_chain_record[0].hex().lower()
                    if on_chain_hash_hex == hex_hash:
                        logger.info("Contract already holds identical audit for %s", report_id)
                        audit_id = f"audit-{report_id[:24]}-{epoch_ts}"
                        save_blockchain_audit(
                            audit_id=audit_id,
                            report_id=report_id,
                            report_hash=hex_hash,
                            blockchain_network=settings.blockchain_network_name,
                            chain_id=w3.eth.chain_id,
                            contract_address=contract.address,
                            transaction_hash=None,
                            block_number=on_chain_record[2],
                            verification_status="RECORDED",
                            audited_by=on_chain_record[3],
                            report_metadata=report_meta,
                            report_payload=report_payload,
                        )
                        return {
                            "success": True,
                            "report_id": report_id,
                            "report_hash": hex_hash,
                            "status": "RECORDED",
                            "duplicate": True,
                            "block_number": on_chain_record[2],
                            "contract_address": contract.address,
                            "network": settings.blockchain_network_name,
                            "recorded_at": datetime.fromtimestamp(on_chain_record[1], timezone.utc).isoformat(),
                            "message": "Report was already recorded on-chain with identical hash.",
                        }
            except Exception as read_exc:
                logger.debug("Check existing audit read error: %s", read_exc)

            # Build and send transaction
            nonce = w3.eth.get_transaction_count(account.address)
            gas_price = w3.eth.gas_price

            logger.info("Submitting audit transaction for report %s (hash: %s)...", report_id, hex_hash[:16])
            tx = contract.functions.recordAudit(
                report_id,
                raw_hash_bytes,
                epoch_ts,
            ).build_transaction({
                "from": account.address,
                "nonce": nonce,
                "gas": 300_000,
                "gasPrice": gas_price,
                "chainId": w3.eth.chain_id,
            })

            pk = settings.blockchain_private_key.strip() or DEV_DEFAULT_PRIVATE_KEY
            if not pk.startswith("0x"):
                pk = "0x" + pk

            signed_tx = w3.eth.account.sign_transaction(tx, private_key=pk)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash_hex = tx_hash.hex()
            logger.info("Audit transaction broadcast: %s. Awaiting receipt...", tx_hash_hex)

            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=15)
            block_number = receipt.blockNumber

            audit_id = f"audit-{report_id[:24]}-{epoch_ts}"
            save_blockchain_audit(
                audit_id=audit_id,
                report_id=report_id,
                report_hash=hex_hash,
                blockchain_network=settings.blockchain_network_name,
                chain_id=w3.eth.chain_id,
                contract_address=contract.address,
                transaction_hash=tx_hash_hex,
                block_number=block_number,
                verification_status="RECORDED",
                audited_by=account.address,
                report_metadata=report_meta,
                report_payload=report_payload,
            )

            return {
                "success": True,
                "report_id": report_id,
                "report_hash": hex_hash,
                "status": "RECORDED",
                "transaction_hash": tx_hash_hex,
                "block_number": block_number,
                "contract_address": contract.address,
                "network": settings.blockchain_network_name,
                "audited_by": account.address,
                "recorded_at": now_dt.isoformat(),
                "message": "Report successfully recorded and audited on blockchain.",
            }

        except Exception as exc:
            logger.error("Audit transaction failed for %s: %s", report_id, exc)
            return {
                "success": False,
                "report_id": report_id,
                "report_hash": hex_hash,
                "status": "FAILED",
                "error": str(exc),
                "message": f"Blockchain transaction failed: {str(exc)}",
            }

    # -----------------------------------------------------------------------
    # Verification Flow
    # -----------------------------------------------------------------------

    def verify_integrity(
        self,
        report_payload: dict[str, Any] | None = None,
        report_id: str | None = None,
        persist_status: bool = True,
    ) -> dict[str, Any]:
        """
        Verify report integrity against smart contract.
        1. Obtains or reconstructs report payload.
        2. Re-computes SHA-256 hash.
        3. Retrieves on-chain audit record via verifyAudit / getAudit.
        4. Compares current hash with blockchain recorded hash.
        5. Returns status: VERIFIED | MODIFIED | NOT_AUDITED | UNAVAILABLE.
        """
        if not report_payload and not report_id:
            return {
                "verified": False,
                "status": "ERROR",
                "message": "Neither report payload nor report_id provided for verification.",
            }

        # Resolve payload and report_id
        if not report_payload and report_id:
            db_record = get_blockchain_audit(report_id)
            if not db_record:
                return {
                    "verified": False,
                    "status": "NOT_AUDITED",
                    "report_id": report_id,
                    "message": f"No audit metadata found for report {report_id}.",
                }
            report_payload = db_record.get("report_payload") or {}
            if not report_payload:
                return {
                    "verified": False,
                    "status": "PAYLOAD_MISSING",
                    "report_id": report_id,
                    "message": "Off-chain report content missing; cannot recalculate hash.",
                }

        resolved_report_id = derive_report_id(report_payload, report_id)
        current_hex_hash, current_hash_bytes = compute_report_hash(report_payload)

        contract = self.get_contract()
        if contract is None or not self.is_connected():
            # Blockchain offline; fallback comparison with DB recorded hash
            db_record = get_blockchain_audit(resolved_report_id)
            if db_record:
                recorded_hash = db_record.get("report_hash", "").lower()
                matches = (current_hex_hash == recorded_hash)
                if matches and persist_status:
                    update_blockchain_audit_status(resolved_report_id, "VERIFIED")
                elif not matches and persist_status:
                    update_blockchain_audit_status(resolved_report_id, "MODIFIED")
                return {
                    "verified": matches,
                    "status": "VERIFIED_OFFCHAIN" if matches else "MODIFIED_OFFCHAIN",
                    "report_id": resolved_report_id,
                    "current_hash": current_hex_hash,
                    "recorded_hash": recorded_hash,
                    "blockchain_online": False,
                    "network": settings.blockchain_network_name,
                    "message": (
                        "Blockchain node unavailable. Hash compared with off-chain audit metadata: "
                        + ("MATCH (Untampered)" if matches else "MISMATCH (Tampered)")
                    ),
                }

            return {
                "verified": False,
                "status": "UNAVAILABLE",
                "report_id": resolved_report_id,
                "current_hash": current_hex_hash,
                "message": "Blockchain node is currently unreachable.",
            }

        try:
            # Query on-chain verifyAudit
            is_verified, exists, on_chain_hash_bytes, timestamp = contract.functions.verifyAudit(
                resolved_report_id,
                current_hash_bytes,
            ).call()

            on_chain_hex = on_chain_hash_bytes.hex().lower() if exists else ""
            db_record = get_blockchain_audit(resolved_report_id)
            tx_hash = db_record.get("transaction_hash") if db_record else None
            block_number = db_record.get("block_number") if db_record else None

            if not exists:
                if db_record and db_record.get("verification_status") in ("PENDING_BLOCKCHAIN", "RECORDED"):
                    recorded_hash = db_record.get("report_hash", "").lower()
                    matches = (current_hex_hash == recorded_hash)
                    if matches:
                        if persist_status:
                            update_blockchain_audit_status(resolved_report_id, "VERIFIED")
                        return {
                            "verified": True,
                            "status": "VERIFIED_OFFCHAIN",
                            "report_id": resolved_report_id,
                            "current_hash": current_hex_hash,
                            "recorded_hash": recorded_hash,
                            "blockchain_online": True,
                            "network": settings.blockchain_network_name,
                            "contract_address": contract.address,
                            "message": "Report verified against off-chain audit record (pending on-chain sync).",
                        }
                    else:
                        if persist_status:
                            update_blockchain_audit_status(resolved_report_id, "MODIFIED")
                        return {
                            "verified": False,
                            "status": "MODIFIED_OFFCHAIN",
                            "report_id": resolved_report_id,
                            "current_hash": current_hex_hash,
                            "recorded_hash": recorded_hash,
                            "blockchain_online": True,
                            "network": settings.blockchain_network_name,
                            "contract_address": contract.address,
                            "message": "CRITICAL ALERT: Report modified! Current hash does NOT match off-chain audit record.",
                        }

                return {
                    "verified": False,
                    "status": "NOT_AUDITED",
                    "report_id": resolved_report_id,
                    "current_hash": current_hex_hash,
                    "recorded_hash": None,
                    "network": settings.blockchain_network_name,
                    "contract_address": contract.address,
                    "message": f"Report {resolved_report_id} has not been audited on the blockchain.",
                }

            if is_verified:
                if persist_status:
                    update_blockchain_audit_status(resolved_report_id, "VERIFIED")
                return {
                    "verified": True,
                    "status": "VERIFIED",
                    "report_id": resolved_report_id,
                    "current_hash": current_hex_hash,
                    "recorded_hash": on_chain_hex,
                    "timestamp": timestamp,
                    "recorded_at": datetime.fromtimestamp(timestamp, timezone.utc).isoformat() if timestamp else None,
                    "transaction_hash": tx_hash,
                    "block_number": block_number,
                    "contract_address": contract.address,
                    "network": settings.blockchain_network_name,
                    "message": "INTEGRITY VERIFIED: Current report SHA-256 hash matches the immutable blockchain record perfectly.",
                }
            else:
                if persist_status:
                    update_blockchain_audit_status(resolved_report_id, "MODIFIED")
                return {
                    "verified": False,
                    "status": "MODIFIED",
                    "report_id": resolved_report_id,
                    "current_hash": current_hex_hash,
                    "recorded_hash": on_chain_hex,
                    "timestamp": timestamp,
                    "transaction_hash": tx_hash,
                    "block_number": block_number,
                    "contract_address": contract.address,
                    "network": settings.blockchain_network_name,
                    "message": "CRITICAL ALERT: Report modified! Current hash does NOT match on-chain audit record.",
                }

        except Exception as exc:
            logger.error("Error during blockchain verification: %s", exc)
            return {
                "verified": False,
                "status": "ERROR",
                "report_id": resolved_report_id,
                "error": str(exc),
                "message": f"Verification query failed: {str(exc)}",
            }

    def simulate_tamper(self, report_id: str, delta_metric: str = "engagement_score") -> dict[str, Any]:
        """
        Controlled demonstration utility for SIH evaluators.
        Loads an audited report from database, alters a metric value in a temporary copy,
        and verifies it against the blockchain, demonstrating immediate detection of unauthorized modification
        WITHOUT permanently altering the original report or database record.
        """
        db_record = get_blockchain_audit(report_id)
        if not db_record:
            return {"error": f"Report {report_id} not found in audit database."}

        payload = db_record.get("report_payload")
        if not payload:
            return {"error": "Original payload not stored off-chain."}

        import copy
        tampered_payload = copy.deepcopy(payload)

        # Alter a prominent metric in memory copy only
        if "metrics" in tampered_payload and isinstance(tampered_payload["metrics"], dict):
            orig_val = tampered_payload["metrics"].get("total_reach", 12500)
            tampered_payload["metrics"]["total_reach"] = orig_val + 500000
            tampered_field = "metrics.total_reach"
        elif "sentiment" in tampered_payload and isinstance(tampered_payload["sentiment"], dict):
            orig_val = tampered_payload["sentiment"].get("positive", 50)
            tampered_payload["sentiment"]["positive"] = orig_val + 30
            tampered_field = "sentiment.positive"
        else:
            tampered_payload["tampered_marker"] = True
            tampered_field = "tampered_marker"

        orig_hash, _ = compute_report_hash(payload)
        tampered_hash, _ = compute_report_hash(tampered_payload)

        # Verify tampered copy without persisting MODIFIED status into original DB audit record
        verification_result = self.verify_integrity(tampered_payload, report_id, persist_status=False)

        return {
            "report_id": report_id,
            "field_tampered": tampered_field,
            "original_hash": orig_hash,
            "tampered_hash": tampered_hash,
            "verification_result": verification_result,
            "demonstration_note": "Tamper test demonstrates that even a single integer modification alters the SHA-256 hash and fails blockchain verification. Original database record is preserved.",
        }

    def inspect_report(self, report_payload: dict[str, Any]) -> dict[str, Any]:
        """
        Inspect a report payload for the UI modal:
        Computes canonical SHA-256 hash, derives report_id, checks database
        and smart contract for an existing audit, and returns comprehensive state.
        """
        if not report_payload:
            return {
                "report_id": None,
                "canonical_hash": None,
                "is_audited": False,
                "audit": None,
                "blockchain_health": self.get_health(),
            }

        report_id = derive_report_id(report_payload)
        hex_hash, _ = compute_report_hash(report_payload)
        health = self.get_health()

        existing = get_blockchain_audit(report_id)
        if existing and existing.get("report_hash") == hex_hash:
            return {
                "report_id": report_id,
                "canonical_hash": hex_hash,
                "is_audited": True,
                "audit": {
                    "report_id": report_id,
                    "report_hash": hex_hash,
                    "status": existing.get("verification_status", "RECORDED"),
                    "transaction_hash": existing.get("transaction_hash"),
                    "block_number": existing.get("block_number"),
                    "contract_address": existing.get("contract_address") or health.get("contract_address"),
                    "network": existing.get("blockchain_network") or health.get("network"),
                    "recorded_at": str(existing.get("recorded_at")),
                },
                "blockchain_health": health,
            }

        return {
            "report_id": report_id,
            "canonical_hash": hex_hash,
            "is_audited": False,
            "audit": None,
            "blockchain_health": health,
        }


# Global singleton instance
_BLOCKCHAIN_SERVICE: BlockchainService | None = None


def get_blockchain_service() -> BlockchainService:
    global _BLOCKCHAIN_SERVICE
    if _BLOCKCHAIN_SERVICE is None:
        _BLOCKCHAIN_SERVICE = BlockchainService()
    return _BLOCKCHAIN_SERVICE
