// blockchain/scripts/deploy.js
const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("Compiling contracts...");
  await hre.run("compile");

  const artifactPath = path.join(
    __dirname,
    "..",
    "artifacts",
    "contracts",
    "SocialIQReportAudit.sol",
    "SocialIQReportAudit.json"
  );
  const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf-8"));

  let deployedAddress = "";
  let txHash = "";
  let blockNumber = 1;

  if (hre.ethers && hre.ethers.getContractFactory) {
    const SocialIQReportAudit = await hre.ethers.getContractFactory("SocialIQReportAudit");
    const contract = await SocialIQReportAudit.deploy();
    await contract.waitForDeployment();
    deployedAddress = await contract.getAddress();
    txHash = contract.deploymentTransaction() ? contract.deploymentTransaction().hash : "";
  } else {
    // Deploy via standard Hardhat JSON-RPC provider (zero-dependency on ethers plugins)
    const accounts = await hre.network.provider.send("eth_accounts", []);
    const deployer = accounts[0] || "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266";
    console.log("Deploying from account:", deployer);

    txHash = await hre.network.provider.send("eth_sendTransaction", [
      {
        from: deployer,
        data: artifact.bytecode,
        gas: "0x200000",
      },
    ]);

    // Poll for receipt
    let receipt = null;
    for (let i = 0; i < 20; i++) {
      receipt = await hre.network.provider.send("eth_getTransactionReceipt", [txHash]);
      if (receipt && receipt.contractAddress) break;
      await new Promise((r) => setTimeout(r, 200));
    }

    if (!receipt || !receipt.contractAddress) {
      throw new Error("Transaction mined without contractAddress.");
    }

    deployedAddress = receipt.contractAddress;
    blockNumber = parseInt(receipt.blockNumber, 16) || 1;
  }

  console.log("SocialIQReportAudit deployed successfully to:", deployedAddress);

  // Save deployment metadata
  const deploymentInfo = {
    contract_address: deployedAddress,
    deployer_address: "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
    transaction_hash: txHash,
    block_number: blockNumber,
    chain_id: hre.network.config.chainId || 31337,
    rpc_url: "http://127.0.0.1:8545",
    network_name: "Local EVM (Hardhat Node)",
    deployed_at: new Date().toISOString(),
  };

  const deployFilePath = path.join(__dirname, "..", "deployment.json");
  fs.writeFileSync(deployFilePath, JSON.stringify(deploymentInfo, null, 2));
  console.log("Updated deployment.json with address:", deployedAddress);
}

main().catch((error) => {
  console.error("Deployment failed:", error);
  process.exitCode = 1;
});
