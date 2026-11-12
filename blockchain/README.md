# WillChain integrity registry

The Solidity registry stores only random 32-byte references, salted SHA-256 commitments, and registration timestamps. A document record is linked to its will by a random reference, never by a database ID or person identifier. The contract does not store will text, file bytes, filenames, personal details, or private evidence. Registrations are immutable; a duplicate reference reverts.

## Off-chain commitment format

At finalization, Django serializes a versioned snapshot containing the will title, finalized content, version, and finalization timestamp as UTF-8 JSON with sorted object keys, compact separators, Unicode preserved, and non-finite numbers rejected. SHA-256 of those exact canonical bytes is the content digest. Owner identity and database IDs are excluded.

For each will or eligible active document, the backend generates a cryptographically random 32-byte record reference and 32-byte salt. The on-chain commitment is:

```text
SHA-256(record_reference_bytes || content_digest_bytes || salt_bytes)
```

The salt and canonical will snapshot are encrypted before database storage and never returned by an API. Document digests are computed from the actual private file bytes and must match the accepted document checksum before the document is queued for anchoring. Later verification recomputes the digest from the finalized will or private file, reconstructs the commitment, checks the registry, and validates the stored transaction receipt and event. Hash matching establishes integrity against the anchored snapshot; it does not establish legal validity, capacity, authorship, or truth.

`INTEGRITY_ENCRYPTION_KEY` should be a stable Fernet key kept in a secrets manager or environment configuration. If it is unset, local development derives the encryption key from `DJANGO_SECRET_KEY`; production deployments should configure a separate stable key and plan key rotation so existing snapshots remain decryptable.

## Local Hardhat setup

From the repository root, install and test the Solidity project:

```powershell
Set-Location .\blockchain
npm.cmd install
npm.cmd test
npm.cmd run sync:abi
```

Start the local chain in one terminal:

```powershell
npm.cmd run node
```

Hardhat prints deterministic development accounts and keys. These are for local testing only; never use them on a public network or put them in the repository. In a second terminal, set the backend registrar address if it differs from the deployer, then deploy:

```powershell
$env:INTEGRITY_SIGNER_ADDRESS = "0x<backend-registrar-address>"
npm.cmd run deploy:local
```

The deployment prints the registry address. Set that address, the local chain ID, and the matching local-only registrar key in `backend/.env`:

```dotenv
INTEGRITY_NETWORK_NAME=hardhat-local
INTEGRITY_CHAIN_ID=31337
INTEGRITY_RPC_URL=http://127.0.0.1:8545
INTEGRITY_CONTRACT_ADDRESS=0x<deployed-registry-address>
INTEGRITY_SIGNER_PRIVATE_KEY=<local-only-hardhat-account-key>
INTEGRITY_CONFIRMATIONS=1
```

When using Docker Compose on Windows, set `INTEGRITY_RPC_URL=http://host.docker.internal:8545` so the backend and worker containers can reach the host's Hardhat node. Compose starts the integrity outbox worker automatically after the backend is ready. For a backend run directly on the host, start the worker separately:

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py process_integrity_anchors --loop
```

Will finalization creates the immutable off-chain snapshot and queued outbox records inside the same database transaction. It does not wait for an RPC call, so a stopped node cannot undo a successful finalization. The worker stores a signed transaction in encrypted form before broadcasting, safely retries the same transaction after interruptions, and reports `CONFIRMED` only after a successful receipt, matching registration event, and configured confirmation count. Temporary RPC failures remain retryable. Administrators can requeue permanent failures from the protected operations API.

After changing the Solidity ABI, run `npm.cmd run sync:abi` to refresh the backend ABI file. Django tests use an in-memory database by default. To run the optional end-to-end Django-to-Hardhat test, start the local node, deploy the contract, set the backend blockchain environment variables, then run:

```powershell
$env:RUN_HARDHAT_INTEGRATION = "1"
.\.venv\Scripts\python.exe manage.py test apps.integrity.tests.LocalHardhatIntegrationTests
```

## API access

- Owners: `GET` and `POST /api/v1/wills/<will_id>/integrity/` for their own wills.
- Assigned lawyers: `GET` and `POST /api/v1/wills/<will_id>/integrity/lawyer/` only while the existing case permission allows access. Lawyer APIs remain read-only and do not return document-level metadata.
- Administrators: `GET /api/v1/integrity/admin/operations/` and `POST /api/v1/integrity/admin/operations/<random-reference>/retry/`. These return operational metadata only, not will content.

There is no public verification API. No blockchain key or salt is sent to the frontend.

## Optional Sepolia

Sepolia has not been deployed or verified as part of this implementation. To prepare it, configure `SEPOLIA_RPC_URL`, `DEPLOYER_PRIVATE_KEY`, and `INTEGRITY_SIGNER_ADDRESS` only in the deployment environment, then deploy with `npm.cmd run deploy:sepolia`. Configure the backend with the resulting contract address, `INTEGRITY_NETWORK_NAME=sepolia`, `INTEGRITY_CHAIN_ID=11155111`, a funded server-side `INTEGRITY_SIGNER_PRIVATE_KEY`, and an appropriate `INTEGRITY_CONFIRMATIONS` value. Never commit or paste these credentials. The backend checks the configured chain ID and leaves records pending or failed rather than claiming an anchor on the wrong network.

## Operational limitations

- Local development uses a single-node Hardhat chain; it is not durable production evidence.
- The database snapshot and encrypted salt are required for later reconstruction. Back them up securely with the configured encryption key.
- Public chains expose references, commitments, timestamps, and transaction metadata. Random references avoid direct personal identifiers but do not prevent correlation by timing.
- Existing legal review, beneficiary release, and document-access permissions remain authoritative; a blockchain match does not grant access.
- Transaction explorer links are not configured. The UI shows the verified transaction hash and block without inventing an explorer URL.
- `npm audit` currently reports a high-severity Zod advisory in the Hardhat development toolchain. The Hardhat plugins require Zod 3, while the advisory fix is in Zod 4; forcing that major upgrade is not compatible with the declared plugin peer dependency. Recheck after the Hardhat plugins publish a compatible fix.
