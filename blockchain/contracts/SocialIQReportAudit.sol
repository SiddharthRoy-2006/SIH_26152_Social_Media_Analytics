// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title SocialIQReportAudit
 * @notice Tamper-evident blockchain audit registry for SocialIQ Analytics.
 * @dev Stores SHA-256 cryptographic fingerprints of canonical analytical reports.
 * Raw social-media data, personal info, and large analytical datasets remain strictly off-chain
 * in PostgreSQL / Supabase. Only verifiable audit metadata is recorded here.
 */
contract SocialIQReportAudit {
    struct AuditRecord {
        bytes32 reportHash;
        uint256 timestamp;
        uint256 blockNumber;
        address recordedBy;
        bool exists;
    }

    // Owner / authorized backend auditor address
    address public owner;

    // Total audit count recorded
    uint256 public totalAudits;

    // Mapping: reportId => AuditRecord
    mapping(string => AuditRecord) private _audits;

    // Events
    event AuditRecorded(
        string indexed reportId,
        bytes32 indexed reportHash,
        uint256 timestamp,
        uint256 blockNumber,
        address indexed recordedBy
    );

    event OwnershipTransferred(
        address indexed previousOwner,
        address indexed newOwner
    );

    modifier onlyOwner() {
        require(msg.sender == owner, "SocialIQReportAudit: caller is not the owner");
        _;
    }

    constructor() {
        owner = msg.sender;
        emit OwnershipTransferred(address(0), msg.sender);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "SocialIQReportAudit: new owner is zero address");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    /**
     * @notice Records an audit hash for a SocialIQ report.
     * @dev Reverts if attempting to overwrite an existing record with a different hash.
     * Returns true if newly recorded, false if already recorded with identical hash.
     * @param reportId Unique string identifier of the report
     * @param reportHash 32-byte SHA-256 hash of the canonical report representation
     * @param reportTimestamp Epoch timestamp of report generation
     */
    function recordAudit(
        string calldata reportId,
        bytes32 reportHash,
        uint256 reportTimestamp
    ) external onlyOwner returns (bool) {
        require(bytes(reportId).length > 0, "SocialIQReportAudit: empty reportId");
        require(reportHash != bytes32(0), "SocialIQReportAudit: empty reportHash");

        AuditRecord storage existing = _audits[reportId];
        if (existing.exists) {
            require(
                existing.reportHash == reportHash,
                "SocialIQReportAudit: report already audited with different hash (immutability violation)"
            );
            return false;
        }

        uint256 ts = reportTimestamp > 0 ? reportTimestamp : block.timestamp;
        _audits[reportId] = AuditRecord({
            reportHash: reportHash,
            timestamp: ts,
            blockNumber: block.number,
            recordedBy: msg.sender,
            exists: true
        });

        totalAudits++;

        emit AuditRecorded(reportId, reportHash, ts, block.number, msg.sender);
        return true;
    }

    /**
     * @notice Retrieves audit details for a given reportId.
     */
    function getAudit(string calldata reportId)
        external
        view
        returns (
            bytes32 reportHash,
            uint256 timestamp,
            uint256 blockNumber,
            address recordedBy,
            bool exists
        )
    {
        AuditRecord storage record = _audits[reportId];
        return (
            record.reportHash,
            record.timestamp,
            record.blockNumber,
            record.recordedBy,
            record.exists
        );
    }

    /**
     * @notice Verifies whether a given reportId and reportHash match the on-chain audit record.
     * @return isVerified True if record exists AND hashes match
     * @return exists True if an audit record exists for reportId
     * @return recordedHash The recorded on-chain hash
     * @return timestamp The timestamp when the report was audited
     */
    function verifyAudit(string calldata reportId, bytes32 reportHash)
        external
        view
        returns (
            bool isVerified,
            bool exists,
            bytes32 recordedHash,
            uint256 timestamp
        )
    {
        AuditRecord storage record = _audits[reportId];
        if (!record.exists) {
            return (false, false, bytes32(0), 0);
        }
        bool matches = (record.reportHash == reportHash);
        return (matches, true, record.reportHash, record.timestamp);
    }
}
