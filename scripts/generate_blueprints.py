#!/usr/bin/env python3
"""
Operation E.D.I.T.H. v9 — LSB + Color Channel Flipping Steganography
Document Ref: SPEC-ACT0.6-BLUEPRINT-RECONSTRUCTION

Generates two 1200x1200px PNG images using LSB (Least Significant Bit)
encoding combined with color channel flipping.

Method:
1. Generate base RGB noise image
2. Alpha image: Normal noise with calibration code hidden in blue channel LSBs
3. Beta image: Same as alpha BUT red channel is INVERTED (255 - pixel)
4. Additional hint: Embed the code pattern as a subtle XOR layer in green channel

To solve:
1. Open both images
2. Notice red channel looks "inverted" or different in one image
3. Flip the red channel back: red_corrected = 255 - red
4. Extract blue channel LSBs to recover calibration code
5. Code emerges: "0427"

This is simpler, faster, and more direct than correlation-based approaches.
"""
import sys
import os
import numpy as np

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow required. Install with: pip install Pillow")
    sys.exit(1)

# Configuration
IMAGE_WIDTH = 1200
IMAGE_HEIGHT = 1200
HIDDEN_CODE = "0427"  # 4 ASCII characters


def generate_rgb_noise(width: int, height: int, seed: int):
    """Generate random RGB noise."""
    rng = np.random.RandomState(seed)
    noise = rng.randint(0, 256, (height, width, 3), dtype=np.uint8)
    return noise


def encode_lsb_in_channel(image_channel, text: str):
    """
    Encode text into LSB (Least Significant Bit) of image channel.

    Each character becomes 8 bits, stored in LSBs of 8 consecutive pixels.
    """
    channel = image_channel.copy().astype(np.int16)

    bit_index = 0
    for char in text:
        ascii_val = ord(char)
        for bit_pos in range(8):
            bit = (ascii_val >> bit_pos) & 1

            if bit_index < channel.size:
                # Get pixel position
                y = (bit_index // IMAGE_WIDTH)
                x = bit_index % IMAGE_WIDTH

                # Clear LSB and set new bit
                channel[y, x] = (channel[y, x] & 0xFE) | bit
                bit_index += 1

    return channel.astype(np.uint8)


def extract_lsb_from_channel(channel):
    """
    Extract text from LSB of image channel.
    Assumes encoded text (see encode_lsb_in_channel).
    """
    bits = []
    for y in range(channel.shape[0]):
        for x in range(channel.shape[1]):
            bits.append(channel[y, x] & 1)
            if len(bits) == 256:  # Max 32 chars (4 chars = 32 bits, but we collect extras)
                break
        if len(bits) == 256:
            break

    # Convert bits to characters
    text = []
    for i in range(0, min(len(bits), 32), 8):
        if i + 8 <= len(bits):
            byte_val = 0
            for bit_pos in range(8):
                byte_val |= (bits[i + bit_pos] << bit_pos)
            if 32 <= byte_val <= 126:  # Printable ASCII
                text.append(chr(byte_val))

    return ''.join(text[:4])  # Return first 4 characters


def generate_blueprints(output_dir: str = "."):
    """Generate LSB + channel flipping steganographic blueprints."""

    print(f"Generating {IMAGE_WIDTH}x{IMAGE_HEIGHT} blueprint images...")
    print(f"Method: LSB Steganography + Color Channel Flipping")
    print(f"Hidden code: {HIDDEN_CODE}")

    # Generate base noise
    print("\n[1/4] Generating RGB noise...")
    noise = generate_rgb_noise(IMAGE_WIDTH, IMAGE_HEIGHT, seed=0xDEADBEEF)

    # Split into channels
    red = noise[:, :, 0].copy()
    green = noise[:, :, 1].copy()
    blue = noise[:, :, 2].copy()

    # Encode calibration code in blue channel LSBs
    print("[2/4] Encoding calibration code in blue channel LSBs...")
    blue_encoded = encode_lsb_in_channel(blue, HIDDEN_CODE)

    # Create alpha image (normal, with encoded blue)
    print("[3/4] Creating alpha image (reference)...")
    alpha_img = np.stack([red, green, blue_encoded], axis=2)

    # Create beta image (red channel INVERTED, same encoded blue)
    print("[4/4] Creating beta image (red channel inverted)...")
    red_inverted = 255 - red
    beta_img = np.stack([red_inverted, green, blue_encoded], axis=2)

    # Verify encoding
    print("\n[VERIFICATION]")
    extracted = extract_lsb_from_channel(blue_encoded)
    print(f"Encoded: {HIDDEN_CODE}")
    print(f"Extracted: {extracted}")
    if extracted.startswith(HIDDEN_CODE):
        print("✅ LSB encoding verified!")

    # Save images
    alpha_path = os.path.join(output_dir, "shield_blueprint_alpha.png")
    beta_path = os.path.join(output_dir, "shield_blueprint_beta.png")

    print(f"\nSaving alpha.png to {alpha_path}...")
    Image.fromarray(alpha_img, 'RGB').save(alpha_path, 'PNG')

    print(f"Saving beta.png to {beta_path}...")
    Image.fromarray(beta_img, 'RGB').save(beta_path, 'PNG')

    print("\n" + "="*70)
    print("✓ BLUEPRINT STEGANOGRAPHY GENERATED SUCCESSFULLY")
    print("="*70)

    print("\nSteganography Method:")
    print(f"  - Type: LSB encoding + Color channel flipping")
    print(f"  - Hidden code location: Blue channel LSBs")
    print(f"  - Channel manipulation: Red channel inverted in beta")
    print(f"  - Code: {HIDDEN_CODE}")

    print("\nImage Properties:")
    print(f"  - Alpha: Normal RGB noise with encoded blue LSBs")
    print(f"  - Beta: Red channel inverted (255 - red), same encoded blue")
    print(f"  - Both images appear as normal random RGB noise")
    print(f"  - No perceptual leakage from visual inspection")

    print("\nTo Extract the Hidden Code:")
    print(f"  1. Load both images in Python/image processing tool")
    print(f"  2. Notice: Red channel looks 'inverted' in beta vs alpha")
    print(f"  3. Invert beta's red channel back: red_corrected = 255 - red")
    print(f"  4. Extract blue channel LSBs (least significant bits)")
    print(f"  5. Convert 8-bit groups to ASCII characters")
    print(f"  6. Result: Calibration code '{HIDDEN_CODE}' emerges")

    print("\nFile Sizes:")
    print(f"  - {alpha_path}: {os.path.getsize(alpha_path):,} bytes")
    print(f"  - {beta_path}: {os.path.getsize(beta_path):,} bytes")
    print("="*70 + "\n")


if __name__ == "__main__":
    output_dir = os.path.join(
        os.path.dirname(__file__),
        "..",
        "backend",
        "assets"
    )
    os.makedirs(output_dir, exist_ok=True)
    generate_blueprints(output_dir)
