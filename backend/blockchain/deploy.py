"""
backend/blockchain/deploy.py

Automated deployment utility for SocialIQReportAudit smart contract.
Connects to local EVM node (Hardhat/Anvil), deploys contract, and records deployment metadata.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import sys

from web3 import Web3

# Base directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACT_PATH = PROJECT_ROOT / "blockchain" / "artifacts" / "contracts" / "SocialIQReportAudit.sol" / "SocialIQReportAudit.json"
DEPLOYMENT_FILE = PROJECT_ROOT / "blockchain" / "deployment.json"
ENV_FILE = PROJECT_ROOT / ".env"

# Standard local development account for Hardhat node (well-known public test credentials)
DEV_DEFAULT_PRIVATE_KEY = (
    "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
)
DEV_DEFAULT_ACCOUNT = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

logger = logging.getLogger("blockchain.deploy")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def load_contract_artifact() -> dict:
    if not ARTIFACT_PATH.exists():
        raise FileNotFoundError(
            f"Contract artifact not found at {ARTIFACT_PATH}. "
            "Please run 'node ./node_modules/hardhat/internal/cli/cli.js compile' in blockchain/ folder first."
        )
    with open(ARTIFACT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def deploy_contract(
    rpc_url: str = "http://127.0.0.1:8545",
    private_key: str | None = None,
) -> dict:
    """
    Deploy SocialIQReportAudit to the EVM network at rpc_url.
    Returns dictionary with deployed contract address, tx hash, and block number.
    """
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise ConnectionError(
            f"Cannot connect to local EVM node at {rpc_url}. "
            "Ensure the local blockchain node is running (e.g. 'npm run node' in blockchain/ folder)."
        )

    chain_id = w3.eth.chain_id
    logger.info("Connected to EVM RPC at %s (Chain ID: %d)", rpc_url, chain_id)

    # Use specified private key, or env, or local Hardhat account #0
    pk = (
        private_key
        or os.getenv("BLOCKCHAIN_PRIVATE_KEY", "").strip()
        or DEV_DEFAULT_PRIVATE_KEY
    )
    if not pk.startswith("0x"):
        pk = "0x" + pk

    account = w3.eth.account.from_key(pk)
    deployer_address = account.address
    balance_wei = w3.eth.get_balance(deployer_address)
    balance_eth = w3.from_wei(balance_wei, "ether")
    logger.info("Deployer Address: %s (Balance: %.4f ETH)", deployer_address, float(balance_eth))

    if balance_wei == 0:
        raise ValueError(
            f"Deployer account {deployer_address} has 0 ETH. Please fund account or use a local dev account."
        )

    artifact = load_contract_artifact()
    abi = artifact["abi"]
    bytecode = artifact["bytecode"]

    contract_factory = w3.eth.contract(abi=abi, bytecode=bytecode)

    nonce = w3.eth.get_transaction_count(deployer_address)
    gas_price = w3.eth.gas_price

    logger.info("Building deployment transaction (nonce: %d)...", nonce)
    construct_txn = contract_factory.constructor().build_transaction({
        "from": deployer_address,
        "nonce": nonce,
        "gas": 2_500_000,
        "gasPrice": gas_price,
        "chainId": chain_id,
    })

    signed = w3.eth.account.sign_transaction(construct_txn, private_key=pk)
    logger.info("Broadcasting contract deployment transaction...")
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    tx_hash_hex = tx_hash.hex()
    logger.info("Transaction sent: %s. Awaiting receipt...", tx_hash_hex)

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    contract_address = receipt.contractAddress
    block_number = receipt.blockNumber

    logger.info("Contract deployed successfully!")
    logger.info("Contract Address: %s", contract_address)
    logger.info("Mined in Block:   %d", block_number)
    logger.info("Gas Used:         %d", receipt.gasUsed)

    result = {
        "contract_address": contract_address,
        "deployer_address": deployer_address,
        "transaction_hash": tx_hash_hex,
        "block_number": block_number,
        "chain_id": chain_id,
        "rpc_url": rpc_url,
        "network_name": "Local EVM (Hardhat Node)",
    }

    # Save to deployment.json
    DEPLOYMENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DEPLOYMENT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    logger.info("Saved deployment record to %s", DEPLOYMENT_FILE)

    # Update or write .env
    _update_env_file(result, pk)

    return result


def _update_env_file(info: dict, private_key: str) -> None:
    """Safely updates or appends blockchain settings in .env."""
    lines = []
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

    keys_to_set = {
        "BLOCKCHAIN_RPC_URL": info["rpc_url"],
        "BLOCKCHAIN_CHAIN_ID": str(info["chain_id"]),
        "BLOCKCHAIN_NETWORK_NAME": info["network_name"],
        "BLOCKCHAIN_CONTRACT_ADDRESS": info["contract_address"],
        "BLOCKCHAIN_ACCOUNT_ADDRESS": info["deployer_address"],
        "BLOCKCHAIN_PRIVATE_KEY": private_key,
        "BLOCKCHAIN_ENABLED": "true",
    }

    found = set()
    new_lines = []
    for line in lines:
        matched = False
        for k, v in keys_to_set.items():
            if line.startswith(f"{k}=") or line.startswith(f"#{k}="):
                new_lines.append(f"{k}={v}\n")
                found.add(k)
                matched = True
                break
        if not matched:
            new_lines.append(line)

    for k, v in keys_to_set.items():
        if k not in found:
            new_lines.append(f"{k}={v}\n")

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    logger.info("Updated %s with active contract address and settings.", ENV_FILE)


if __name__ == "__main__":
    rpc = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8545"
    deploy_contract(rpc_url=rpc)
