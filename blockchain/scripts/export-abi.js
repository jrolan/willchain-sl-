import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const directory = path.dirname(fileURLToPath(import.meta.url));
const artifactPath = path.join(directory, "..", "artifacts", "contracts", "WillIntegrityRegistry.sol", "WillIntegrityRegistry.json");
const outputPath = path.join(directory, "..", "..", "backend", "apps", "integrity", "contract_abi.json");
const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf8"));

fs.writeFileSync(outputPath, `${JSON.stringify(artifact.abi, null, 2)}\n`);
