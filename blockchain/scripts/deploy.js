import { network } from "hardhat";

const { ethers } = await network.getOrCreate();
const [deployer] = await ethers.getSigners();
const registry = await ethers.deployContract("WillIntegrityRegistry");
await registry.waitForDeployment();

const registrarAddress = process.env.INTEGRITY_SIGNER_ADDRESS;
if (registrarAddress && registrarAddress.toLowerCase() !== deployer.address.toLowerCase()) {
  const transaction = await registry.setRegistrar(registrarAddress, true);
  await transaction.wait();
}

console.log(`WillIntegrityRegistry: ${await registry.getAddress()}`);
console.log(`Chain ID: ${(await ethers.provider.getNetwork()).chainId}`);
