// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract WillIntegrityRegistry {
    struct IntegrityRecord {
        bytes32 commitment;
        uint64 registeredAt;
    }

    address public owner;
    mapping(address => bool) public registrars;
    mapping(bytes32 => IntegrityRecord) private willRecords;
    mapping(bytes32 => IntegrityRecord) private documentRecords;
    mapping(bytes32 => bytes32) public documentWillReferences;

    error Unauthorized();
    error InvalidAddress();
    error InvalidIdentifier();
    error InvalidCommitment();
    error DuplicateRecord();
    error WillRecordNotFound();

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event RegistrarUpdated(address indexed registrar, bool enabled);
    event WillCommitmentRegistered(bytes32 indexed recordId, bytes32 commitment, uint64 registeredAt);
    event DocumentCommitmentRegistered(
        bytes32 indexed recordId,
        bytes32 indexed willRecordId,
        bytes32 commitment,
        uint64 registeredAt
    );

    constructor() {
        owner = msg.sender;
        emit OwnershipTransferred(address(0), msg.sender);
    }

    modifier onlyOwner() {
        if (msg.sender != owner) revert Unauthorized();
        _;
    }

    modifier onlyRegistrar() {
        if (msg.sender != owner && !registrars[msg.sender]) revert Unauthorized();
        _;
    }

    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) revert InvalidAddress();
        address previousOwner = owner;
        owner = newOwner;
        emit OwnershipTransferred(previousOwner, newOwner);
    }

    function setRegistrar(address registrar, bool enabled) external onlyOwner {
        if (registrar == address(0)) revert InvalidAddress();
        registrars[registrar] = enabled;
        emit RegistrarUpdated(registrar, enabled);
    }

    function registerWill(bytes32 recordId, bytes32 commitment) external onlyRegistrar {
        if (recordId == bytes32(0)) revert InvalidIdentifier();
        if (commitment == bytes32(0)) revert InvalidCommitment();
        if (willRecords[recordId].registeredAt != 0) revert DuplicateRecord();

        uint64 registeredAt = uint64(block.timestamp);
        willRecords[recordId] = IntegrityRecord(commitment, registeredAt);
        emit WillCommitmentRegistered(recordId, commitment, registeredAt);
    }

    function registerDocument(
        bytes32 recordId,
        bytes32 willRecordId,
        bytes32 commitment
    ) external onlyRegistrar {
        if (recordId == bytes32(0) || willRecordId == bytes32(0)) revert InvalidIdentifier();
        if (commitment == bytes32(0)) revert InvalidCommitment();
        if (willRecords[willRecordId].registeredAt == 0) revert WillRecordNotFound();
        if (documentRecords[recordId].registeredAt != 0) revert DuplicateRecord();

        uint64 registeredAt = uint64(block.timestamp);
        documentRecords[recordId] = IntegrityRecord(commitment, registeredAt);
        documentWillReferences[recordId] = willRecordId;
        emit DocumentCommitmentRegistered(recordId, willRecordId, commitment, registeredAt);
    }

    function getWillCommitment(bytes32 recordId) external view returns (bytes32 commitment, uint64 registeredAt) {
        IntegrityRecord memory record = willRecords[recordId];
        return (record.commitment, record.registeredAt);
    }

    function getDocumentCommitment(
        bytes32 recordId
    ) external view returns (bytes32 commitment, uint64 registeredAt, bytes32 willRecordId) {
        IntegrityRecord memory record = documentRecords[recordId];
        return (record.commitment, record.registeredAt, documentWillReferences[recordId]);
    }

    function verifyWillCommitment(bytes32 recordId, bytes32 suppliedCommitment) external view returns (bool) {
        return suppliedCommitment != bytes32(0) && willRecords[recordId].commitment == suppliedCommitment;
    }

    function verifyDocumentCommitment(bytes32 recordId, bytes32 suppliedCommitment) external view returns (bool) {
        return suppliedCommitment != bytes32(0) && documentRecords[recordId].commitment == suppliedCommitment;
    }
}
