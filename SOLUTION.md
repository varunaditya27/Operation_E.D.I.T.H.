# Operation E.D.I.T.H. — Official Solution Walkthrough

> **Flag:** `rvcectf{SH13LD_C0GN1T1V3_4UTH}`

---

## Starting Point: What You Were Given

On the external challenge portal you receive three files:

- `CHALLENGE_BRIEF.md` — narrative and setup
- `auth_backup.sba` — a custom binary archive in the Stark Binary Archive format
- `sba_extract.py.broken` — a Python extraction script with three functions deliberately broken

There is no portal to visit yet. Everything begins offline. Your first task: understand the extractor, fix it, and use it to unpack the archive.

---

## Repairing the Extraction Script

Open `sba_extract.py.broken`. Read it carefully — not just the code but the docstrings. The comments on each broken function describe precisely what it was supposed to do. Three functions need to be reconstructed:

### `rle_decompress` — Run-Length Encoding

The archive uses a custom RLE compression scheme. The decompression loop exists but the escape byte handler (`0xBC`) does nothing. The docstring describes a dual-role escape:

- `0xBC 0x00` → emit a single literal `0xBC` byte (advance 2 bytes)
- `0xBC [count] [byte]` → emit `byte` repeated `count` times (advance 3 bytes)

```python
def rle_decompress(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == 0xBC:
            length = data[i + 1]
            if length == 0x00:
                out.append(0xBC)
                i += 2
            else:
                byte = data[i + 2]
                out.extend([byte] * length)
                i += 3
        else:
            out.append(data[i])
            i += 1
    return bytes(out)
```

### `stark_rc4_decrypt` — Modified RC4

The Key Schedule Algorithm (KSA) is intact. The PRGA is missing one line — the "Stark modification" the docstring mentions. After the standard `j = (j + S[i]) % 256`, the index `j` is additionally XORed with the current key byte:

```python
def stark_rc4_decrypt(data: bytes, key: bytes) -> bytes:
    S = list(range(256))
    j = 0
    for i in range(256):
        j = (j + S[i] + key[i % len(key)]) % 256
        S[i], S[j] = S[j], S[i]
    i = 0; j = 0
    out = bytearray()
    for idx in range(len(data)):
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        j = (j ^ key[idx % len(key)]) % 256   # Stark modification
        S[i], S[j] = S[j], S[i]
        t = (S[i] + S[j]) % 256
        out.append(data[idx] ^ S[t])
    return bytes(out)
```

### `derive_rc4_key` — Key from Hostname

The docstring says "a name becomes a secret when passed through the crucible." The key is the raw 16-byte MD5 digest of the build server's hostname:

```python
def derive_rc4_key(hostname: str) -> bytes:
    import hashlib
    return hashlib.md5(hostname.encode()).digest()
```

The hostname itself is not in the script. It is in `build_server.log` — an unencrypted file inside the archive. Running the partially-working script will extract it first. The log contains the line:

```
STARK INDUSTRIES BUILD SERVER: edith-build-04.stark.internal
```

Use `edith-build-04.stark.internal` as the hostname input to `derive_rc4_key`.

### Running the Repaired Script

With all three functions fixed, run:

```bash
python3 sba_extract.py auth_backup.sba
```

This extracts **six files**:

| File | Encrypted? |
|---|---|
| `build_server.log` | No — cleartext |
| `syslog.log` | No — cleartext |
| `shield_blueprint_alpha.png` | No — cleartext |
| `shield_blueprint_beta.png` | No — cleartext |
| `StarkEmployeePortal.exe` | Yes — RC4 + RLE |
| `README.txt` | Yes — RC4 + RLE |

**Read `README.txt` in full.** It is the Rosetta Stone for everything that follows — it contains riddles and explicit hints for every subsequent step.

---

## Extracting the Calibration Code from the Blueprints

You have `shield_blueprint_alpha.png` and `shield_blueprint_beta.png`. They appear identical. The `README.txt` hints:

> *"When the crimson veil is reversed, what truth hides in the azure depths? Eight whispers rise from silence."*

This describes two things:

1. **The Red channel of the beta image is inverted.** Every pixel satisfies `R_beta = 255 - R_alpha`. This is the observable difference between the two files.
2. **The Blue channel of the alpha image (the unmodified reference) carries hidden data in its Least Significant Bits (LSBs).** Reading the last bit of each blue channel pixel value across the image's pixels, 8 bits at a time, LSB-first, spells out ASCII characters.

The process:

```python
from PIL import Image
import numpy as np

alpha = np.array(Image.open("shield_blueprint_alpha.png"))
beta  = np.array(Image.open("shield_blueprint_beta.png"))

# Confirm: beta red channel is inverted
assert np.all(beta[:, :, 0] == (255 - alpha[:, :, 0])), "Red channel mismatch"

# Extract LSBs from blue channel of alpha (flattened row by row)
blue_flat = alpha[:, :, 2].flatten()
bits = [int(blue_flat[i]) & 1 for i in range(32)]   # 32 bits = 4 characters

chars = []
for i in range(0, 32, 8):
    byte_val = sum(bits[i + b] << b for b in range(8))  # LSB-first
    chars.append(chr(byte_val))

print("".join(chars))   # prints: 0427
```

The output is the string `"0427"`.

> [!IMPORTANT]
> The `README.txt` explicitly warns: the blueprints encode `0427` (with a leading zero), but when this value is used mathematically, use the **integer** `427` — strip the leading zero. The formula that derives the master secret concatenates it as the string `"427"`, not `"0427"`.

---

## Reconstructing the Master Employee Secret

Run `strings StarkEmployeePortal.exe` (or open it in a hex editor). Embedded in the binary's string table is a section explicitly labeled `--- AUTHENTICATION KERNEL CONSTANTS ---` that lists three values:

| Constant | Value |
|---|---|
| `MACHINE_GUID` | `7948eaa2-7dfd-417d-8fb4-f8b9e2a930e3` |
| `BUILD_EPOCH` | `1781259200` |
| `SHIFT_OFFSET` | `427` |

The string table also contains the exact derivation formula:

```
Formula: EMPLOYEE_SECRET = SHA256(GUID_bytes + EPOCH_bytes + OFFSET_bytes)[:16]
Where:
  GUID_bytes   = encode("7948eaa2-7dfd-417d-8fb4-f8b9e2a930e3")
  EPOCH_bytes  = encode(str(1781259200))
  OFFSET_bytes = encode(str(427))
```

The three components are **encoded to bytes separately** then **concatenated as bytes** before hashing:

```python
import hashlib

MACHINE_GUID  = "7948eaa2-7dfd-417d-8fb4-f8b9e2a930e3"
BUILD_EPOCH   = 1781259200
SHIFT_OFFSET  = 427

raw = (
    MACHINE_GUID.encode()
    + str(BUILD_EPOCH).encode()
    + str(SHIFT_OFFSET).encode()
)
EMPLOYEE_SECRET = hashlib.sha256(raw).digest()[:16]
print(EMPLOYEE_SECRET.hex())
```

> [!IMPORTANT]
> This is equivalent to `SHA256(b"7948eaa2-7dfd-417d-8fb4-f8b9e2a930e31781259200427")`. The bytes are concatenated, not comma-separated or space-joined. Keep the hyphens in the UUID. Use `"427"` not `"0427"`.

Keep `EMPLOYEE_SECRET`. It is used in every subsequent step of the challenge.

---

## Authenticating at the Portal

Navigate to `http://134.209.148.23/`. The page immediately fetches a cryptographic challenge from the server at `GET /api/v1/auth/challenge?username=mreyes`. The response contains:

- `challenge_id` — a unique ID for this challenge token
- `challenge` — a 32-hex-character random string
- `salt` — the constant string `"stark_audit_v5"`
- `timestamp` — Unix epoch when the challenge was issued
- `blink_sequence` — an array of 6 color characters: `["R","G","B","Y",...]`

The challenge is valid for 30 minutes. You must submit two things to authenticate:

### 1. The HMAC Response

Concatenate the challenge string with the salt (`"stark_audit_v5"`), then compute HMAC-SHA256 using `EMPLOYEE_SECRET` as the key:

```python
import hmac, hashlib

challenge = "<challenge string from /api/v1/auth/challenge>"
salt      = "stark_audit_v5"
message   = (challenge + salt).encode()

response_hex = hmac.new(EMPLOYEE_SECRET, message, hashlib.sha256).hexdigest()
```

Paste this hex string into the **HMAC-SHA256 Response** field.

### 2. The Blink Code

The portal shows six colored circles. Group them into three consecutive pairs (positions 0-1, 2-3, 4-5). Look up each pair in the **Reference Grid** displayed on the page:

| | **R** | **G** | **B** | **Y** |
|:---|:---:|:---:|:---:|:---:|
| **R** | `S` | `A` | `9` | `M` |
| **G** | `K` | `1` | `T` | `E` |
| **B** | `F` | `P` | `8` | `V` |
| **Y** | `Z` | `U` | `Q` | `W` |

Row = first color of the pair. Column = second color. This yields a 3-character string.

*Example:* Sequence `["R","G","Y","B","R","G"]` → pairs `(R,G)`, `(Y,B)`, `(R,G)` → `A`, `Q`, `A` → code `"AQA"`.

Enter this code in the **Enter Blink Code** field and click **Access Portal**.

On success, the server issues a `session_token` and redirects you to `/dashboard`.

---

## The Dashboard and Downloading the Network Capture

The dashboard page calls `GET /api/v1/dashboard` with your `Authorization: Bearer <session_token>` header. This marks your session as dashboard-accessed and **enables the PCAP download**.

Click the **Download HYDRA Capture** button. The browser calls `GET /api/v1/artifacts/hydra-capture`. The server responds with the file and includes the header:

```
X-PCAP-Token: <one-time token>
```

The browser stores this token in `localStorage` under the key `pcap_token`. **This token is single-use and required to open the Director Terminal WebSocket.** It is issued fresh each time you download, so if it expires or is consumed, you can re-download.

From the dashboard, navigate to `/calibrate` via the **Calibrate** button.

---

## Resonance Calibration

The calibration page shows two waveforms on a canvas: a cyan reference wave (the target, fetched from `GET /api/v1/calibrate/target`) and an amber wave you control via four sliders.

Your amber wave is rendered as:
$$y = A \sin(\omega x + \phi) + C$$

You must tune your sliders until your wave aligns with the cyan reference. The server checks tolerance on `POST /api/v1/calibrate/submit` — it only returns pass or fail, no distance or gradient.

The target values are:

| Parameter | Symbol | Target | Tolerance |
|---|---|---|---|
| Frequency | ω | `0.82` | ± `0.03` |
| Phase | φ | `2.14` | ± `0.05` |
| Amplitude | A | `0.91` | ± `0.03` |
| Skew | C | `0.07` | ± `0.02` |

> [!NOTE]
> You are rate-limited to **6 attempts per minute**. The server gives no directional feedback — only binary pass/fail. Use the visual canvas to guide your adjustments.

Submit the calibration:

```python
import requests

headers = {"Authorization": f"Bearer {session_token}"}
resp = requests.post(
    "http://134.209.148.23/api/v1/calibrate/submit",
    json={"freq": 0.82, "phase": 2.14, "amp": 0.91, "skew": 0.07},
    headers=headers,
)
print(resp.json())  # {"pass": true, "message": "Resonance calibration successful..."}
```

On success, the page redirects you to `/director`. Your session is now marked as calibration-complete, which is required to use the Director Terminal.

---

## Breaking the Network Capture

Open `HYDRA_CAPTURE.pcapng` in Wireshark or parse it with Scapy/dpkt. It contains **4 Enhanced Packet Blocks (EPBs)**, each an AES-256-CBC encrypted JSON payload prepended with a 16-byte IV.

| EPB | Host | Status |
|---|---|---|
| 1 | `REYES-DESKTOP` | Decoy — session ends in 401 |
| 2 | `REYES-LAPTOP` | **Active** — contains real ZKP parameters |
| 3 | `HYDRA-SNIFFER` | Decoy — interceptor with bad credentials |
| 4 | `REYES-WORKSTATION` | Decoy — contains **wrong** ZKP parameters |

> [!WARNING]
> EPB 4 (`REYES-WORKSTATION`) deliberately contains a fake ZKP modulus `N` and fake public keys `v`. Using them in the Director Terminal will cause every proof to fail immediately. Only use the parameters from EPB 2.

### Breaking EPB 2: Recovering the DH Private Key

Each EPB begins with the Diffie-Hellman parameters exchanged. For EPB 2, the DH parameters are:

- **512-bit prime** `p` = `0x9B15E3F0A1823B4E6C2D8A9F123C4B5A6E7D8F901BC2A3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4A5B6C7D8E9F0A1B2C3D4E5F6A7B8C9D0E1F2A3B4`
- **Generator** `g` = `2`
- **Server public key** `A` = readable from the `dh_server_hello` packet in EPB 2

The client's private key `b` was generated by a flawed seeded LCG instead of a secure random source. The seed is:

```python
import hashlib

NETBIOS_ID = "REYES-LAPTOP"
HOST_KEY   = "STARK-FALLBACK-KEY-2026"
BUILD_EPOCH = 1781259200

seed_input = (NETBIOS_ID + HOST_KEY).encode() + str(BUILD_EPOCH).encode()
seed = int.from_bytes(hashlib.sha256(seed_input).digest()[:8], 'big')
```

The LCG uses the PCG64 constants:

```python
LCG_A = 6364136223846793005
LCG_C = 1442695040888963407
MOD   = 2**64

def lcg_next(state):
    return (LCG_A * state + LCG_C) % MOD

X1 = lcg_next(seed)
X2 = lcg_next(X1)

b = (X1 << 32) | X2   # 96-bit private exponent
```

### Decrypting the Payload

With `b` and the server public key `A` extracted from EPB 2, compute the shared secret and AES key:

```python
p = 0x9B15E3F0A1823B4E6C2D8A9F123C4B5A6E7D8F901BC2A3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4A5B6C7D8E9F0A1B2C3D4E5F6A7B8C9D0E1F2A3B4

K       = pow(A, b, p)
aes_key = hashlib.sha256(K.to_bytes(64, 'big')).digest()
```

Each EPB packet in the raw file is structured as:
```
[16-byte IV] [ciphertext ...]
```

Decrypt EPB 2's payload with AES-256-CBC:

```python
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

def decrypt_cbc(payload: bytes, key: bytes) -> bytes:
    iv         = payload[:16]
    ciphertext = payload[16:]
    cipher     = Cipher(algorithms.AES(key), modes.CBC(iv))
    dec        = cipher.decryptor()
    padded     = dec.update(ciphertext) + dec.finalize()
    return padding.PKCS7(128).unpadder().update(padded) + padding.PKCS7(128).unpadder().finalize()
```

The decrypted payload is a JSON object. Inside the `zkp_params_observed` packet entry you find:

- `N` — a 1024-bit RSA modulus (hex string)
- `public_keys_v` — a list of four hex strings `[v0, v1, v2, v3]`
- `k` = `4`

Save these. They are the public parameters for the Director's ZKP handshake.

---

## The Director's Terminal

Navigate to `/director`. You are presented with a black command-line terminal interface.

The terminal has five commands:

| Command | Action |
|---|---|
| `help` | List all commands |
| `init` | Initialize a Director session (fetches nonce + flash sequence) |
| `connect` | Open the WebSocket connection using your transcribed flash code |
| `schema` | Print the full WebSocket message schema |
| `status` | Show timeout values and current state |

### Step 1: Initialize the Session

Type `init`. The terminal calls `POST /api/v1/session/init` with your session token. The server:

1. Checks that your session exists and that calibration is marked complete — if not, it returns an error and tells you to go to `/calibrate` first.
2. Generates a **nonce** (`secrets.token_hex(8)`) valid for 5 minutes.
3. Derives a **4-color flash sequence** from this nonce using SHA256: `SHA256(nonce.encode())`, taking the first 4 bytes and mapping each `% 4` to one of `[R, G, B, Y]`.
4. Returns `{"nonce": "...", "flash_sequence": ["R","B","G","Y"], "flash_code": "XX"}`.

The **FLASH CODE TRANSCRIPTION** panel on the right side of the page will now show:
- A large cycling colored circle (animates through the 4 colors over a 20-second loop)
- Four numbered colored squares showing the full 4-color sequence
- A text box labeled `2-CHAR CODE`

Read the four colors in order (positions 1, 2, 3, 4). Group them into two pairs (1-2, 3-4). Look up each pair in the Asgardian Lexicon table (same table as login, same rules). This gives a **2-character code**. Type it into the `2-CHAR CODE` input box.

### Step 2: Connect

Type `connect`. The terminal calls:

```
ws://134.209.148.23/api/v1/admin/auth/ws
  ?pcap_token=<your pcap_token>
  &nonce=<the init nonce>
  &flash_code=<your 2-char transcription>
```

The server validates **in this order**:

1. Checks `pcap_token` is present (rejects immediately if missing, before accepting the connection)
2. Validates the `nonce` and `flash_code` match what it derived
3. **Only if both pass**, consumes the `pcap_token` (marking it used)

This ordering means a transcription typo does **not** burn your token. If the flash code is wrong, close and type `init` again to get a new nonce and flash sequence, then retry `connect` with the same `pcap_token`.

If the `pcap_token` is already consumed (from a previous successful but failed ZKP attempt), go back to `/dashboard`, re-download the PCAP to get a fresh token, then return to `/director`.

### Step 3: WebSocket — Server Init

After accepting the connection, the server immediately sends a `server_init` event:

```json
{
  "event": "server_init",
  "nonce": "<16-hex-char session nonce>",
  "captcha_image": "data:image/png;base64,...",
  "zkp_params": {
    "N": "0x...",
    "v": ["0x...", "0x...", "0x...", "0x..."],
    "k": 4
  }
}
```

> [!IMPORTANT]
> A **new nonce** is generated here inside the WebSocket handler — `secrets.token_hex(8)`. This is **not** the same nonce from `session/init`. **Save it.** This `session_nonce` will be used as the **AAD (Additional Authenticated Data)** for AES-GCM flag decryption.

The CAPTCHA image appears in the **SECURE CAPTCHA FEED** panel. It is 150×50 px containing 4 characters from the set `ABCDEFGHJKMNPQRSTUVWXYZ23456789` (no ambiguous characters like `0`, `O`, `1`, `I`). Noise lines and shear distortion are applied. Read it with your eyes.

### Step 4: Compute ZKP Secrets

Before sending anything, compute your four ZKP secrets from `EMPLOYEE_SECRET` and `N` (extracted from the PCAP):

```python
N = int("<N from zkp_params>", 16)

secrets_s = []
for i in range(4):
    h = hashlib.sha256(EMPLOYEE_SECRET + bytes([i])).digest()[:8]
    s = int.from_bytes(h, 'big') % N
    secrets_s.append(s)
```

You can verify these are correct: for each `j`, `pow(secrets_s[j], 2, N)` must equal `int(v[j], 16)`. If they don't match, your `EMPLOYEE_SECRET` is wrong.

### Step 5: ZKP Round 1

You have **180 seconds** per message (timeout is `120s * 1.5`).

**Send commitment** — choose a random witness `r` in `[1, N-1]`, compute `x = r² mod N`:

```python
import random

r1 = random.randint(1, N - 1)
x1 = pow(r1, 2, N)

await ws.send(json.dumps({
    "event": "client_commit",
    "captcha_input": "KXQM",   # your CAPTCHA solution
    "x": hex(x1)
}))
```

**Receive challenge** — the server sends `{"event": "server_challenge", "round": 1, "e": [1, 0, 1, 0]}`.

**Send response** — multiply your witness by the secrets corresponding to each `e[j] == 1`:

```python
y1 = r1
for j, ej in enumerate(e1):
    if ej == 1:
        y1 = (y1 * secrets_s[j]) % N

await ws.send(json.dumps({"event": "client_respond", "y": hex(y1)}))
```

The server verifies: `y1² ≡ x1 · ∏(v[j] where e[j]==1) (mod N)`. If correct, Round 1 passes.

### Step 6: ZKP Round 2

Same structure. No CAPTCHA this time. Use a **new random witness** `r2`.

```python
r2 = random.randint(1, N - 1)
x2 = pow(r2, 2, N)

await ws.send(json.dumps({"event": "client_commit", "x": hex(x2)}))

# receive challenge e2...

y2 = r2
for j, ej in enumerate(e2):
    if ej == 1:
        y2 = (y2 * secrets_s[j]) % N

await ws.send(json.dumps({"event": "client_respond", "y": hex(y2)}))
```

> [!IMPORTANT]
> **Save `y2`.** This is Stone #5 in the final decryption key. Do not confuse it with `y1`.

### Step 7: Proof-of-Work

After Round 2 passes, the server sends:

```json
{"event": "server_pow", "salt": "pow_salt_a3f8c2...", "prefix": "000000"}
```

You have **120 seconds** to find a nonce `n` such that:

```python
hashlib.sha256(f"{salt}{n}".encode()).hexdigest().startswith("000000")
```

This searches ~16.7 million candidates on average (~17 seconds in Python, under 1 second in C/Rust). Brute-force from 0:

```python
pow_nonce = 0
while True:
    if hashlib.sha256(f"{salt}{pow_nonce}".encode()).hexdigest().startswith("000000"):
        break
    pow_nonce += 1

await ws.send(json.dumps({"event": "client_pow_solve", "pow": pow_nonce}))
```

> [!TIP]
> If Python is too slow, use `multiprocessing` or rewrite the inner loop using `hashlib` in a C extension. The terminal itself hints: *"Rust whispers louder than Python."*

> [!IMPORTANT]
> Save `pow_nonce`. It is Stone #6.

### Step 8: Receive and Decrypt the Flag

The server sends a `directors_log` event:

```json
{
  "event": "directors_log",
  "session_nonce": "...",
  "encrypted_flag": {
    "nonce": "a3b4c5d6e7f8a9b0c1d2e3f4",
    "ciphertext": "..."
  }
}
```

There are **three distinct nonces** in this system — do not confuse them:

| Nonce | Where it comes from | Purpose |
|---|---|---|
| **Init nonce** | Returned by `POST /api/v1/session/init` | Used as WS query parameter |
| **Session nonce** | Inside `server_init` WS message | **AAD for AES-GCM** |
| **GCM IV nonce** | Inside `encrypted_flag.nonce` | AES-GCM initialization vector |

Assemble the **6 Infinity Stones** as a concatenated string:

```python
key_material = (
    hex(secrets_s[0]) +   # Stone 1
    hex(secrets_s[1]) +   # Stone 2
    hex(secrets_s[2]) +   # Stone 3
    hex(secrets_s[3]) +   # Stone 4
    hex(y2)           +   # Stone 5 (Round 2 response, NOT Round 1)
    str(pow_nonce)        # Stone 6 (decimal string, NOT hex)
)
aes_key = hashlib.sha256(key_material.encode()).digest()
```

Decrypt using AES-256-GCM:

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

gcm_iv     = bytes.fromhex(encrypted_flag["nonce"])       # 12 bytes
ciphertext = bytes.fromhex(encrypted_flag["ciphertext"])
aad        = session_nonce.encode()                        # from server_init

flag = AESGCM(aes_key).decrypt(gcm_iv, ciphertext, aad).decode()
print(flag)
# rvcectf{SH13LD_C0GN1T1V3_4UTH}
```

---

## Recovery Procedures

**If the WebSocket closes with code `4008`:** A timeout was exceeded. The session is terminated. To restart: go to `/dashboard`, re-download the PCAP (get a fresh `pcap_token`), return to `/director`, type `init`, transcribe the new flash code, type `connect`.

**If calibration fails:** The server gives no gradient or directional feedback. Use the canvas visualization to make visual adjustments. You have 6 attempts per minute.

**If the CAPTCHA is unreadable:** The character set is `ABCDEFGHJKMNPQRSTUVWXYZ23456789`. No `0`, `O`, `1`, `I`, or `L`. If in doubt, reconnect to get a new CAPTCHA (this consumes your `pcap_token`, so plan accordingly).
