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
HOSTNAME = "edith-build-04.stark.internal"
NETBIOS_ID = "REYES-LAPTOP"
HOST_KEY = "STARK-FALLBACK-KEY-2026"
STATE_KEY = os.environ.get("STATE_KEY", "stark_audit_v5")  # salt for SCRP

# ──────────────────────────────────────────────
# Act 0: SBA Encryption Key (SPEC-ACT0-SBA §4.1)
# Key = MD5(hostname) as raw bytes (first 16 bytes of digest)
# ──────────────────────────────────────────────
SBA_RC4_KEY = hashlib.md5(HOSTNAME.encode()).digest()  # 16 bytes

# ──────────────────────────────────────────────
# Act I: Employee Secret (SPEC-ACT1-FRIDAYVM §2.1)
# employee_key = SHA256(machine_guid + str(build_epoch))[:16]
# ──────────────────────────────────────────────
_guid_bytes = MACHINE_GUID.encode()
_epoch_bytes = str(BUILD_EPOCH).encode()
EMPLOYEE_SECRET = hashlib.sha256(_guid_bytes + _epoch_bytes).digest()[:16]

# ──────────────────────────────────────────────
# Act I: FridayVM Opcode Shuffle Seed (SPEC-ACT1-FRIDAYVM §2.1)
# Seed = CRC32(MachineGuid) XOR build_epoch
# ──────────────────────────────────────────────
FRIDAYVM_SEED = binascii.crc32(MACHINE_GUID.encode()) ^ BUILD_EPOCH

# ──────────────────────────────────────────────
# Act III: DH Parameters (SPEC-ACT3-PCAPGLITCH §1.1)
# ──────────────────────────────────────────────
DH_PRIME_HEX = (
    "9B15E3F0A1823B4E6C2D8A9F123C4B5A6E7D8F901BC2A3D4E5F6A7B8C9D0E1F2"
    "A3B4C5D6E7F8A9B0C1D2E3F4A5B6C7D8E9F0A1B2C3D4E5F6A7B8C9D0E1F2A3B4"
)
DH_PRIME = int(DH_PRIME_HEX, 16)
DH_GENERATOR = 2
DH_SERVER_PRIVATE = 57382103  # Server's secret exponent 'a'
DH_SERVER_PUBLIC = pow(DH_GENERATOR, DH_SERVER_PRIVATE, DH_PRIME)

# Act III: DH Client Seed (SPEC-ACT3-PCAPGLITCH §1.2)
DH_CLIENT_SEED = binascii.crc32((NETBIOS_ID + HOST_KEY).encode()) ^ BUILD_EPOCH
SHIFT_OFFSET = 42  # from visual blueprint alignment (Act 0)

# ──────────────────────────────────────────────
# Act IV: ZKP Parameters (SPEC-ACT4-ZKPWS §1.1)
# Using smaller primes for demonstration; production uses 1024-bit
# ──────────────────────────────────────────────
ZKP_P = 982451653
ZKP_Q = 982451629
ZKP_N = ZKP_P * ZKP_Q
ZKP_K = 4  # number of secret/public key pairs
# Client secrets s_i (derived deterministically from employee_secret)
ZKP_SECRETS = [
    int.from_bytes(hashlib.sha256(EMPLOYEE_SECRET + i.to_bytes(1, 'big')).digest()[:4], 'big') % ZKP_N
    for i in range(ZKP_K)
]
# Public keys v_j = s_j^2 mod N
ZKP_PUBLIC_KEYS = [pow(s, 2, ZKP_N) for s in ZKP_SECRETS]

# ──────────────────────────────────────────────
# Act IV: Proof-of-Work config
# ──────────────────────────────────────────────
POW_PREFIX = "00000"  # 5 zero nibbles
POW_TIMEOUT_MS = 1000  # 1 second per WS round

# ──────────────────────────────────────────────
# Act V: Flag (SPEC-ACT5-OPSDEPLOY §1.1)
# ──────────────────────────────────────────────
FLAG_PLAINTEXT = "FLAG{SHIELD_COGNITIVE_AUTHENTICATION_PASSED_77391}"

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
BLINK_ROTATE_INTERVAL = 10  # seconds

# ──────────────────────────────────────────────
# Rate Limiting (SPEC-ACT5-OPSDEPLOY §3.1)
# ──────────────────────────────────────────────
RATE_LIMIT_MAX = 12  # per minute
RATE_LIMIT_BLOCK_SECONDS = 180  # 3 minutes

# ──────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./data/edith.db")
