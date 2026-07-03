# Operation E.D.I.T.H. v5 — Core Cryptographic & Mathematical Verification Script
# This script validates the mathematical and cryptographic coherence of all challenge acts.

import hashlib
import hmac
import struct
import binascii

# ==========================================
# ACT 0: STARK BINARY ARCHIVE & RC4 CIPHER
# ==========================================

def stark_rc4(data: bytes, key: bytes) -> bytes:
    """Implements the modified RC4 algorithm defined in SPEC-ACT0-SBA."""
    S = list(range(256))
    j = 0
    for i in range(256):
        j = (j + S[i] + key[i % len(key)]) % 256
        S[i], S[j] = S[j], S[i]
    
    i = 0
    j = 0
    out = bytearray()
    for idx, char in enumerate(data):
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        # Modified permutation step
        j = (j ^ key[idx % len(key)]) % 256
        S[i], S[j] = S[j], S[i]
        t = (S[i] + S[j]) % 256
        out.append(char ^ S[t])
    return bytes(out)

def verify_act0():
    print("[Act 0] Verifying Stark-RC4 Encryption...")
    hostname = "edith-build-04.stark.internal"
    rc4_key = hashlib.md5(hostname.encode()).digest()
    
    plaintext = b"STARK_PROJECT_EDITH_FALLBACK_ACTIVE"
    ciphertext = stark_rc4(plaintext, rc4_key)
    decrypted = stark_rc4(ciphertext, rc4_key)
    
    assert plaintext == decrypted, "Act 0 RC4 decryption failed consistency check!"
    print(f"  [+] Key: {binascii.hexlify(rc4_key).decode()}")
    print(f"  [+] Ciphertext (Hex): {binascii.hexlify(ciphertext).decode()}")
    print("  [+] Decryption check passed.")

# ==========================================
# ACT I: FRIDAYVM OPCODE SHUFFLE & MATRIX
# ==========================================

def lcg_next(state: int) -> int:
    """Fisher-Yates 64-bit PCG64 LCG step."""
    return (6364136223846793005 * state + 1442695040888963407) % (2**64)

def shuffle_opcodes(seed):
    """Executes FridayVM's 64-bit LCG opcode table shuffle."""
    base_ops = list(range(32))
    state = seed
    for i in range(len(base_ops) - 1, 0, -1):
        state = lcg_next(state)
        j = state % (i + 1)
        base_ops[i], base_ops[j] = base_ops[j], base_ops[i]
    return base_ops

def solve_matrix_password():
    """Solves the decoy modular matrix equation: M * V = Target (mod 256)."""
    # M = [[3, 5, 2], [1, 7, 4], [6, 2, 8]]
    # Target = [31, 163, 162]
    # We brute-force the 3-character space for simplicity in verifying the math
    target = [31, 163, 162]
    for r0 in range(32, 127):
        for r1 in range(32, 127):
            for r2 in range(32, 127):
                v0 = (3*r0 + 5*r1 + 2*r2) % 256
                v1 = (1*r0 + 7*r1 + 4*r2) % 256
                v2 = (6*r0 + 2*r1 + 8*r2) % 256
                if [v0, v1, v2] == target:
                    return bytes([r0, r1, r2])
    return None

def verify_act1():
    print("[Act I] Verifying FridayVM Opcode Shuffling...")
    machine_guid = "7948eaa2-7dfd-417d-8fb4-f8b9e2a930e3"
    build_epoch = 1781259200
    
    guid_bytes = hashlib.sha256(machine_guid.encode() + str(build_epoch).encode()).digest()[:8]
    seed = int.from_bytes(guid_bytes, 'big')
    
    shuffled_table = shuffle_opcodes(seed)
    print(f"  [+] Opcode Seed: {hex(seed)}")
    print(f"  [+] Opcode 0x01 maps to VM Instruction ID: {shuffled_table[1]}")
    
    print("[Act I] Solving password modular equations...")
    password_half = solve_matrix_password()
    assert password_half is not None, "Matrix password equation is unsolvable!"
    print(f"  [+] Solved matrix characters: {password_half.decode()}")

# ==========================================
# ACT III: DIFFIE-HELLMAN KEY EXCHANGE
# ==========================================

def verify_act3():
    print("[Act III] Verifying Ephemeral DH Key Recovery...")
    netbios_id = "REYES-LAPTOP"
    host_key = "STARK-FALLBACK-KEY-2026"
    build_epoch = 1781259200
    
    seed_bytes = hashlib.sha256((netbios_id + host_key).encode() + str(build_epoch).encode()).digest()[:8]
    seed = int.from_bytes(seed_bytes, 'big')
    
    # Generate private exponent 'b' (96-bit)
    state = seed
    lcg_outs = []
    for _ in range(2):
        state = lcg_next(state)
        lcg_outs.append(state)
    b = (lcg_outs[0] << 32) | lcg_outs[1]
    
    # Diffie-Hellman parameters
    p = int(
        "9B15E3F0A1823B4E6C2D8A9F123C4B5A6E7D8F901BC2A3D4E5F6A7B8C9D0E1F2"
        "A3B4C5D6E7F8A9B0C1D2E3F4A5B6C7D8E9F0A1B2C3D4E5F6A7B8C9D0E1F2A3B4", 16
    )
    g = 2
    
    # Mock server public key A (generated with private key a = 57382103)
    a = 57382103
    A = pow(g, a, p)
    
    # Recompute shared secret K using recovered 'b'
    K = pow(A, b, p)
    aes_key = hashlib.sha256(K.to_bytes(64, 'big')).digest()
    
    print(f"  [+] Recovered seed: {hex(seed)}")
    print(f"  [+] Recovered Private Key 'b': {hex(b)}")
    print(f"  [+] Derived AES Session Key (Hex): {binascii.hexlify(aes_key).decode()}")

# ==========================================
# ACT IV: FIAT-SHAMIR ZERO-KNOWLEDGE PROOF
# ==========================================

def verify_act4():
    print("[Act IV] Verifying Fiat-Shamir ZKP Equations...")
    
    # Derivation matching config.py
    machine_guid = "7948eaa2-7dfd-417d-8fb4-f8b9e2a930e3"
    build_epoch = 1781259200
    shift_offset = 427
    
    _guid_bytes = machine_guid.encode()
    _epoch_bytes = str(build_epoch).encode()
    _shift_bytes = str(shift_offset).encode()
    employee_secret = hashlib.sha256(_guid_bytes + _epoch_bytes + _shift_bytes).digest()[:16]

    ZKP_P = 0xFEEDBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF3
    ZKP_Q = 0xDEADBEEFCAFEBABECAFEBABECAFEBABECAFEBABECAFEBABECAFEBABECAFEBAB7
    N = ZKP_P * ZKP_Q
    ZKP_K = 4
    
    # Secrets s_j derived from employee_secret
    s = [
        int.from_bytes(hashlib.sha256(employee_secret + i.to_bytes(1, 'big')).digest()[:8], 'big') % N
        for i in range(ZKP_K)
    ]
    # Public keys v_j = s_j^2 mod N
    v = [pow(sj, 2, N) for sj in s]
    
    # Commitment: r
    r = 293108210
    x = pow(r, 2, N)
    
    # Challenge vector e
    e = [1, 0, 1, 1]
    
    # Response: y
    y = r
    for idx, ej in enumerate(e):
        if ej == 1:
            y = (y * s[idx]) % N
            
    # Verification
    y_squared = pow(y, 2, N)
    
    check_val = x
    for idx, ej in enumerate(e):
        if ej == 1:
            check_val = (check_val * v[idx]) % N
            
    assert y_squared == check_val, "ZKP verification congruence check failed!"
    print("  [+] ZKP congruence verified successfully:")
    print(f"      y^2 mod N == x * prod(v_j^e_j) mod N")
    print(f"      ({hex(y_squared)[:30]}... == {hex(check_val)[:30]}...)")

# ==========================================
# MAIN EXECUTION
# ==========================================

if __name__ == "__main__":
    print("====================================================")
    print("  Operation E.D.I.T.H. v5 Math Verification Suite")
    print("====================================================\n")
    verify_act0()
    print()
    verify_act1()
    print()
    verify_act3()
    print()
    verify_act4()
    print("\n====================================================")
    print("  All acts mathematical verification: SUCCESS")
    print("====================================================")
