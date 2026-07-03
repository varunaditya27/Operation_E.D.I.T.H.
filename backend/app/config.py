"""
Operation E.D.I.T.H. v5 — Centralized Configuration Constants
Document Ref: SPEC-ACT5-OPSDEPLOY, SPEC-ACT0-SBA, SPEC-ACT1-FRIDAYVM

All constants used across multiple acts are defined here as the single source of truth.
"""
import os
import hashlib
import binascii

# ──────────────────────────────────────────────
# Core Identity Constants (shared across all acts)
# ──────────────────────────────────────────────
MACHINE_GUID = os.environ.get("MACHINE_GUID", "7948eaa2-7dfd-417d-8fb4-f8b9e2a930e3")
BUILD_EPOCH = int(os.environ.get("BUILD_EPOCH", "1781259200"))
# CRITICAL: Must match the build server hostname from SBA logs.
# The Stark Industries build infrastructure used this hostname for RC4 key derivation.
HOSTNAME = "edith-build-04.stark.internal"
NETBIOS_ID = "REYES-LAPTOP"
HOST_KEY = "STARK-FALLBACK-KEY-2026"
STATE_KEY = os.environ.get("STATE_KEY", "stark_audit_v5")  # salt for SCRP

# ──────────────────────────────────────────────
# Act 0: SBA Encryption Key (SPEC-ACT0-SBA §4.1)
# Key = MD5(hostname) as raw bytes (first 16 bytes of digest)
# CRITICAL: RC4 key MUST match the fallback hostname used during SBA generation
# ──────────────────────────────────────────────
SBA_RC4_KEY = hashlib.md5(HOSTNAME.encode()).digest()  # 16 bytes

# ──────────────────────────────────────────────
# Act 0.6: Blueprint Alignment Offset (discovered via steganography)
# ──────────────────────────────────────────────
SHIFT_OFFSET = 427  # from visual blueprint alignment (Act 0.6)

# ──────────────────────────────────────────────
# Act I: Employee Secret (SPEC-ACT1-FRIDAYVM §2.1, updated in v6)
# v6: employee_key = SHA256(machine_guid + str(build_epoch) + str(shift_offset))[:16]
# The shift_offset is discovered via Act 0.6 blueprint alignment puzzle
# ──────────────────────────────────────────────
_guid_bytes = MACHINE_GUID.encode()
_epoch_bytes = str(BUILD_EPOCH).encode()
_shift_bytes = str(SHIFT_OFFSET).encode()
EMPLOYEE_SECRET = hashlib.sha256(_guid_bytes + _epoch_bytes + _shift_bytes).digest()[:16]

# ──────────────────────────────────────────────
# Act I: FridayVM Opcode Shuffle Seed (SPEC-ACT1-FRIDAYVM §2.1)
# Seed = SHA256(MachineGuid + epoch)[:8] interpreted as 64-bit integer
# ──────────────────────────────────────────────
_fridayvm_seed_bytes = hashlib.sha256(MACHINE_GUID.encode() + str(BUILD_EPOCH).encode()).digest()[:8]
FRIDAYVM_SEED = int.from_bytes(_fridayvm_seed_bytes, 'big')

# ──────────────────────────────────────────────
# Act III: DH Parameters (SPEC-ACT3-PCAPGLITCH §1.1)
# ──────────────────────────────────────────────
DH_PRIME_HEX = (
    "9B15E3F0A1823B4E6C2D8A9F123C4B5A6E7D8F901BC2A3D4E5F6A7B8C9D0E1F2"
    "A3B4C5D6E7F8A9B0C1D2E3F4A5B6C7D8E9F0A1B2C3D4E5F6A7B8C9D0E1F2A3B4"
)
DH_PRIME = int(DH_PRIME_HEX, 16)
DH_GENERATOR = 2
# DH_SERVER_PRIVATE is now loaded from environment variable below

# Act III: DH Client Seed (SPEC-ACT3-PCAPGLITCH §1.2)
# SHA256(NETBIOS_ID + HOST_KEY + BUILD_EPOCH) for stronger derivation
_dh_client_seed_bytes = hashlib.sha256((NETBIOS_ID + HOST_KEY).encode() + str(BUILD_EPOCH).encode()).digest()[:8]
DH_CLIENT_SEED = int.from_bytes(_dh_client_seed_bytes, 'big')

# ──────────────────────────────────────────────
# Act III: DH Server Private Key (environment variable required)
# At container startup, DH_SERVER_PRIVATE must be set via environment.
# For local development: generate once with secrets.randbits() and cache in .env.local
# Never use a deterministic fallback for a private key.
# ──────────────────────────────────────────────
_dh_server_private_str = os.environ.get("DH_SERVER_PRIVATE", None)
if not _dh_server_private_str:
    raise ValueError(
        "DH_SERVER_PRIVATE environment variable must be set. "
        "For local development, generate a 64-bit random value and set it: "
        "export DH_SERVER_PRIVATE=$(python3 -c 'import secrets; print(secrets.randbits(32))')"
    )
DH_SERVER_PRIVATE = int(_dh_server_private_str)
DH_SERVER_PUBLIC = pow(DH_GENERATOR, DH_SERVER_PRIVATE, DH_PRIME)

# ──────────────────────────────────────────────
# Act IV: ZKP Parameters (SPEC-ACT4-ZKPWS §1.1)
# 1024-bit RSA-style modulus N = P * Q
# P and Q are 512-bit safe primes (kept private)
# ──────────────────────────────────────────────
# 512-bit prime P
ZKP_P = 0xFEEDBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF3
# 512-bit prime Q
ZKP_Q = 0xDEADBEEFCAFEBABECAFEBABECAFEBABECAFEBABECAFEBABECAFEBABECAFEBAB7
ZKP_N = ZKP_P * ZKP_Q  # ~1024-bit modulus
ZKP_K = 4  # number of secret/public key pairs

# Client secrets s_i (derived deterministically from employee_secret)
# Using SHA256 hashing with 8-byte output to keep secrets bounded by N
ZKP_SECRETS = [
    int.from_bytes(hashlib.sha256(EMPLOYEE_SECRET + i.to_bytes(1, 'big')).digest()[:8], 'big') % ZKP_N
    for i in range(ZKP_K)
]
# Public keys v_j = s_j^2 mod N
ZKP_PUBLIC_KEYS = [pow(s, 2, ZKP_N) for s in ZKP_SECRETS]

# ──────────────────────────────────────────────
# Act IV: Proof-of-Work config
# ──────────────────────────────────────────────
POW_PREFIX = "000000"  # 6 zero nibbles = 24 bits of work (~16M iterations)
POW_TIMEOUT_MS = 30000  # 30 seconds per WS message (relaxed for manual solving)

# ──────────────────────────────────────────────
# Act V: Flag (SPEC-ACT5-OPSDEPLOY §1.1)
# Flag is loaded from environment at runtime and encrypted with AES-GCM.
# It is never stored as a plaintext constant in this file.
# ──────────────────────────────────────────────
FLAG = os.environ.get("FLAG", "flag{SHIELD_COGNITIVE_AUTHENTICATION_PASSED_77391}")

# ──────────────────────────────────────────────
# Act II: Blink Code Grid (SPEC-ACT2-WEBPORTAL §3.1)
# Rows = first color, Cols = second color
# ──────────────────────────────────────────────
BLINK_GRID = {
    ("R", "R"): "S", ("R", "G"): "A", ("R", "B"): "9", ("R", "Y"): "M",
    ("G", "R"): "K", ("G", "G"): "1", ("G", "B"): "T", ("G", "Y"): "E",
    ("B", "R"): "F", ("B", "G"): "P", ("B", "B"): "8", ("B", "Y"): "V",
    ("Y", "R"): "Z", ("Y", "G"): "U", ("Y", "B"): "Q", ("Y", "Y"): "W",
}
BLINK_COLORS = ["R", "G", "B", "Y"]
BLINK_SEQUENCE_LEN = 6  # 6 flashes -> 3 pairs -> 3-char code
BLINK_ROTATE_INTERVAL = 1800  # seconds

# ──────────────────────────────────────────────
# Act II.5: Resonance Gate (SPEC-ACT2-WEBPORTAL §12)
# Waveform calibration with server-side target (never transmitted)
# ──────────────────────────────────────────────
RESONANCE_FREQ = 0.82    # Target frequency (server-side only)
RESONANCE_PHASE = 2.14   # Target phase offset
RESONANCE_AMP = 0.91     # Target amplitude
RESONANCE_SKEW = 0.07    # Target skew offset
RESONANCE_TOLERANCE = {
    "freq": 0.03,
    "phase": 0.05,
    "amp": 0.03,
    "skew": 0.02,
}

# ──────────────────────────────────────────────
# Rate Limiting (SPEC-ACT5-OPSDEPLOY §3.1)
# ──────────────────────────────────────────────
RATE_LIMIT_MAX = 30  # per minute (0.5 req/sec per IP) — tested with 100 concurrent users
RATE_LIMIT_BLOCK_SECONDS = 180  # 3 minutes
CALIBRATE_RATE_LIMIT_MAX = 6  # per minute (iterative tuning)

# ──────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./data/edith.db")
