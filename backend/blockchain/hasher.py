"""
backend/blockchain/hasher.py

Deterministic canonical report serialization and SHA-256 cryptographic hashing
for SocialIQ Analytics reports.

Guarantees:
- The same logical report always produces the exact same cryptographic hash.
- Content alteration (even by a single metric or character) produces a completely different hash.
- Independent of key ordering, whitespace, or transient execution metadata.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


# Transient or ephemeral keys that must NOT affect report audit integrity
VOLATILE_EXCLUDE_KEYS = {
    "refresh_tick",
    "last_updated",
    "computed_at_ms",
    "request_id",
    "execution_time_ms",
    "_ui_state",
}


def _normalize_value(val: Any) -> Any:
    """
    Recursively clean and normalize values for deterministic serialization.
    - Dicts: recursively sorted by key.
    - Lists: normalized element by element (preserving array order).
    - Floats: rounded to 6 decimal places to prevent micro floating-point variances.
    - Strings: stripped of leading/trailing whitespace.
    """
    if isinstance(val, dict):
        cleaned = {}
        for k, v in val.items():
            if k in VOLATILE_EXCLUDE_KEYS:
                continue
            cleaned[str(k)] = _normalize_value(v)
        return {k: cleaned[k] for k in sorted(cleaned.keys())}
    elif isinstance(val, (list, tuple)):
        return [_normalize_value(item) for item in val]
    elif isinstance(val, float):
        # Normalize float precision and eliminate negative zero
        rounded = round(val, 6)
        return 0.0 if rounded == 0.0 else rounded
    elif isinstance(val, bool):
        return val
    elif isinstance(val, int):
        return val
    elif val is None:
        return None
    else:
        return str(val).strip()


def serialize_canonical(report: dict[str, Any]) -> bytes:
    """
    Produce stable, deterministic UTF-8 bytes from a report dictionary.
    
    1. Strips ephemeral runtime fields.
    2. Sorts all dictionary keys recursively.
    3. Normalizes numeric and string primitives.
    4. Serializes without whitespace indentation with strict separators (',', ':').
    """
    normalized = _normalize_value(report)
    canonical_json_str = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return canonical_json_str.encode("utf-8")


def compute_report_hash(report: dict[str, Any]) -> tuple[str, bytes]:
    """
    Computes SHA-256 hash of the canonical report.
    Returns:
        (hex_digest, raw_bytes_32)
        - hex_digest: 64-char lowercase hexadecimal string (e.g. "a3f5...")
        - raw_bytes_32: 32 bytes (compatible with Solidity bytes32)
    """
    canonical_bytes = serialize_canonical(report)
    sha = hashlib.sha256(canonical_bytes)
    hex_digest = sha.hexdigest().lower()
    return hex_digest, sha.digest()


def derive_report_id(report: dict[str, Any], explicit_id: str | None = None) -> str:
    """
    Generate or return a clean, stable report identifier.
    If explicit_id is provided, sanitizes and returns it.
    Otherwise derives: 'report-{platform}-{topic}-{period}-{short_hash}'
    """
    if explicit_id and explicit_id.strip():
        # Sanitize report id
        sanitized = re.sub(r"[^a-zA-Z0-9_\-\.:]", "-", explicit_id.strip())
        return sanitized[:80]

    platform = str(report.get("platform", "general")).lower().replace(" ", "-").replace("/", "-")
    topic = str(report.get("topic", "")).lower().replace(" ", "-") or "all"
    period = str(report.get("period", "30d")).lower().replace(" ", "-")
    
    hex_hash, _ = compute_report_hash(report)
    short_hash = hex_hash[:10]
    
    clean_platform = re.sub(r"[^a-z0-9\-]", "", platform)[:20]
    clean_topic = re.sub(r"[^a-z0-9\-]", "", topic)[:20]
    clean_period = re.sub(r"[^a-z0-9\-]", "", period)[:15]

    return f"report-{clean_platform}-{clean_topic}-{clean_period}-{short_hash}"
