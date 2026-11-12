import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { network } from "hardhat";

describe("WillIntegrityRegistry", () => {
  async function deployRegistry() {
    const { ethers } = await network.getOrCreate();
    const [owner, registrar, outsider] = await ethers.getSigners();
    const registry = await ethers.deployContract("WillIntegrityRegistry");
    await registry.waitForDeployment();
    await registry.setRegistrar(registrar.address, true);
    return { registry, owner, registrar, outsider, ethers };
  }

  it("allows only the owner or an authorized registrar to register a will", async () => {
    const { registry, registrar, outsider, ethers } = await deployRegistry();
    const recordId = ethers.id("will-reference");
    const commitment = ethers.id("will-commitment");

    await assert.rejects(
      registry.connect(outsider).registerWill(recordId, commitment),
      /Unauthorized/,
    );
    const receipt = await (await registry.connect(registrar).registerWill(recordId, commitment)).wait();
    const eventTopic = registry.interface.getEvent("WillCommitmentRegistered").topicHash;
    assert.ok(receipt.logs.some((log) => log.topics[0] === eventTopic));
    const [storedCommitment, registeredAt] = await registry.getWillCommitment(recordId);
    assert.equal(storedCommitment, commitment);
    assert.notEqual(registeredAt, 0n);
  });

  it("rejects zero identifiers, zero commitments, and duplicate records", async () => {
    const { registry, registrar, ethers } = await deployRegistry();
    const recordId = ethers.id("will-reference");
    const commitment = ethers.id("will-commitment");

    await assert.rejects(
      registry.connect(registrar).registerWill(ethers.ZeroHash, commitment),
      /InvalidIdentifier/,
    );
    await assert.rejects(
      registry.connect(registrar).registerWill(recordId, ethers.ZeroHash),
      /InvalidCommitment/,
    );
    await registry.connect(registrar).registerWill(recordId, commitment);
    await assert.rejects(
      registry.connect(registrar).registerWill(recordId, ethers.id("replacement")),
      /DuplicateRecord/,
    );
    assert.equal(await registry.verifyWillCommitment(recordId, commitment), true);
    assert.equal(await registry.verifyWillCommitment(recordId, ethers.id("wrong")), false);
  });

  it("registers document commitments only for an existing will and keeps them immutable", async () => {
    const { registry, registrar, outsider, ethers } = await deployRegistry();
    const willId = ethers.id("will-reference");
    const documentId = ethers.id("document-reference");
    const willCommitment = ethers.id("will-commitment");
    const documentCommitment = ethers.id("document-commitment");

    await assert.rejects(
      registry.connect(registrar).registerDocument(documentId, willId, documentCommitment),
      /WillRecordNotFound/,
    );
    await registry.connect(registrar).registerWill(willId, willCommitment);
    await assert.rejects(
      registry.connect(outsider).registerDocument(documentId, willId, documentCommitment),
      /Unauthorized/,
    );
    const receipt = await (
      await registry.connect(registrar).registerDocument(documentId, willId, documentCommitment)
    ).wait();
    const eventTopic = registry.interface.getEvent("DocumentCommitmentRegistered").topicHash;
    assert.ok(receipt.logs.some((log) => log.topics[0] === eventTopic));
    await assert.rejects(
      registry.connect(registrar).registerDocument(documentId, willId, ethers.id("replacement")),
      /DuplicateRecord/,
    );
    assert.equal(await registry.verifyDocumentCommitment(documentId, documentCommitment), true);
    assert.equal(await registry.documentWillReferences(documentId), willId);
  });

  it("allows ownership transfer and prevents the previous owner from managing registrars", async () => {
    const { registry, owner, outsider, ethers } = await deployRegistry();

    await registry.transferOwnership(outsider.address);
    await assert.rejects(
      registry.connect(owner).setRegistrar(owner.address, true),
      /Unauthorized/,
    );
    await assert.rejects(
      registry.connect(outsider).setRegistrar(ethers.ZeroAddress, true),
      /InvalidAddress/,
    );
  });
});
