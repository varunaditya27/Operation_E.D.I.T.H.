# Stark Binary Archive (SBA) — File Format Specification v4.0.0
### Document ID: SPEC-ACT0-SBA
### Status: Release/Production-Ready
### Target Implementation: Act 0 Forensics

This document defines the custom binary archive format **Stark Binary Archive (SBA)**. It serves as the single source of truth for generating the `auth_backup.sba` file and writing the extraction script (`sba_extract.py`).

---

## 1. Binary Layout Layout

An SBA file consists of three sequential zones: the **Global Header**, the **File Payload Data Blocks**, and the **Table of Contents (TOC)**. All multibyte integers are serialized in **Little-Endian** byte order.

```
+-------------------------------------------------------------+
| Global Header (16 bytes)                                    |
+-------------------------------------------------------------+
| File Payload 1 (Compressed/Encrypted Data)                  |
+-------------------------------------------------------------+
| File Payload 2 (Compressed/Encrypted Data)                  |
+-------------------------------------------------------------+
| ...                                                         |
+-------------------------------------------------------------+
| Table of Contents (TOC)                                     |
+-------------------------------------------------------------+
```

### 1.1 Global Header Structure (16 Bytes)

| Offset (Bytes) | Field Name | Type | Description | Value / Constraint |
| :--- | :--- | :--- | :--- | :--- |
| `0x00 - 0x03` | `Magic` | `char[4]` | Format Identifier | Must be ASCII `"SBA\x00"` (`0x00414253`) |
| `0x04 - 0x05` | `Version` | `uint16` | Version Number | Must be `0x0004` |
| `0x06 - 0x07` | `FileCount` | `uint16` | Total files in archive | Range: `1` to `65535` |
| `0x08 - 0x0F` | `TocOffset` | `uint64` | Byte offset of Table of Contents | Points to start of TOC block |

---

## 2. Table of Contents (TOC) Specification

The TOC contains sequential directory entry structures. The size of the TOC is determined by parsing the `FileCount` field from the Global Header and reading that number of records starting from `TocOffset`.

### 2.1 File Entry Structure

| Size (Bytes) | Field Name | Type | Description |
| :--- | :--- | :--- | :--- |
| `1` | `NameLen` | `uint8` | Length of the file name string in bytes |
| `NameLen` | `FileName` | `char[]` | ASCII-encoded file name (no null-terminator) |
| `8` | `FileOffset` | `uint64` | Absolute byte offset of the data block from file start |
| `8` | `CompSize` | `uint64` | Size of the data block on disk (after compression/encryption) |
| `8` | `DecompSize`| `uint64` | Original uncompressed size of the file |
| `1` | `CompAlgo` | `uint8` | Compression algorithm selector (see 3.1) |
| `1` | `EncryptFlag`| `uint8` | Encryption status flag (see 4.1) |

---

## 3. Compression Algorithms

SBA supports two compression methods. For this challenge, we focus on **Custom Run-Length Encoding (RLE)**.

### 3.1 Custom RLE Protocol (`CompAlgo = 0x01`)
To prevent solvers from calling standard zlib or gzip decoders, the compression uses an escape-marker-based run-length encoding scheme:
* **Escape Marker:** The byte value `0xBC`.
* **Data Encoding:**
  * Single bytes are written as-is, except for the escape marker itself.
  * If the escape marker `0xBC` is encountered in the raw stream, it is encoded as `0xBC 0x00`.
  * Repeats of a byte (length $\ge 4$) are encoded as: `0xBC [Length] [Byte]`
    * `Length` is a 1-byte value indicating the repetition count (max 255).
  * *Example:*
    * Raw: `AA AA AA AA AA` (5 bytes of `0xEA`) -> Encoded: `0xBC 0x05 0xEA`
    * Raw: `BC` -> Encoded: `0xBC 0x00`

---

## 4. Encryption Specification

If `EncryptFlag = 0x01`, the payload data block is encrypted using a modified RC4 stream cipher.

### 4.1 Key Derivation
The encryption key is derived by hashing the build server host name (disclosed in cleartext within the `build_server.log` file, which is packaged with `EncryptFlag = 0x00` inside the same archive).
$$\text{Key} = \text{MD5}(\text{Hostname})[0:16]$$
* **Hostname Value:** `edith-build-04.stark.internal`
* **Raw MD5 Hash:** `e0a3e87834a34b22c26ea612dbcb182b`
* **Derived RC4 Key:** `e0a3e87834a34b22c26ea612dbcb182b` (first 16 hex characters converted to bytes: `b"\xe0\xa3\xe8\x78\x34\xa3\x4b\x22\xc2\x6e\xa6\x12\xdb\xcb\x18\x2b"`)

### 4.2 Stream Cipher Core (Stark-RC4)
The cipher uses the standard Key Scheduling Algorithm (KSA) and Pseudo-Random Generation Algorithm (PRGA), with a modified state permutation:
* **Modification:** During the PRGA step, the state index swaps are subjected to an additional XOR with the derived key byte corresponding to the current loop counter modulo key length.
* **Pseudocode for PRGA:**
  ```python
  def decrypt_rc4_modified(data, key):
      # KSA
      S = list(range(256))
      j = 0
      for i in range(256):
          j = (j + S[i] + key[i % len(key)]) % 256
          S[i], S[j] = S[j], S[i]
      
      # PRGA
      i = 0
      j = 0
      out = bytearray()
      for idx, char in enumerate(data):
          i = (i + 1) % 256
          j = (j + S[i]) % 256
          # Modification: XOR state swap index with key stream byte
          j = (j ^ key[idx % len(key)]) % 256
          S[i], S[j] = S[j], S[i]
          t = (S[i] + S[j]) % 256
          out.append(char ^ S[t])
      return bytes(out)
  ```

---

## 5. File Assets to be Packaged

The generator script must package the following files into `auth_backup.sba`:

1. **`build_server.log`** (`EncryptFlag = 0x00`, `CompAlgo = 0x01`):
   * Content:
     ```
     STARK INDUSTRIES BUILD SERVER: edith-build-04.stark.internal
     BUILD_EPOCH: 1781259200
     TARGET_PE: StarkEmployeePortal.exe
     STATUS: Fallback deployment activated successfully.
     ```
2. **`StarkEmployeePortal.exe`** (`EncryptFlag = 0x01`, `CompAlgo = 0x01`):
   * The binary running the FridayVM code.
3. **`README.txt`** (`EncryptFlag = 0x01`, `CompAlgo = 0x01`):
   * The warning explaining the fallback authentication mode and the hint regarding visual overlays.
4. **`shield_blueprint_alpha.png`** (`EncryptFlag = 0x00`, `CompAlgo = 0x00`):
   * Noise channel image.
5. **`shield_blueprint_beta.png`** (`EncryptFlag = 0x00`, `CompAlgo = 0x00`):
   * Decoupled noise channel image.

---

## 6. Playtest Verification & Test Vectors

* **Header Input:** `53 42 41 00 04 00 05 00 A0 04 00 00 00 00 00 00`
  * Decoded Magic: `SBA\x00`
  * Version: `4`
  * File Count: `5`
  * TOC Offset: `1184` bytes
* **RLE Validation:**
  * Input: `\xBC\x04\x41\x42\xBC\x00`
  * Output: `AAAAB\xBC`
* **RC4 Validation Key:** `b"stark_test_key"`
  * Plaintext: `b"test_payload"`
  * Ciphertext: Verified against local reference script.
