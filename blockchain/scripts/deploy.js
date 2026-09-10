// blockchain/scripts/deploy.js
const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("Compiling contracts...");
  await hre.run("compile");

  const [deployer] = await hre.ethers ? await hre.ethers.getSigners() : [];
  
  // Deploy using Hardhat Artifacts directly or ethers if available
  const SocialIQReportAudit = await hre.ethers ? await hre.ethers.getContractFactory("SocialIQReportAudit") : null;
  
  if (SocialIQReportAudit) {
    const contract = await SocialIQReportAudit.deploy();
    await contract.waitForDeployment();
    const address = await contract.getAddress();
    console.log("SocialIQReportAudit deployed to:", address);
    
    // Save deployed address
    const deploymentInfo = {
      address: address,
      network: hre.network.name,
      chainId: hre.network.config.chainId || 31337,
      deployedAt: new Date().toISOString(),
    };
    fs.writeFileSync(
      path.join(__dirname, "..", "deployment.json"),
      JSON.stringify(deploymentInfo, null, 2)
    );
  } else {
    console.log("Contract factory available via artifacts.");
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
