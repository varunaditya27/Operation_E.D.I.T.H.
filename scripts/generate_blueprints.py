#!/usr/bin/env python3
"""
Operation E.D.I.T.H. v6 — Blueprint Steganography Generator
Document Ref: SPEC-ACT0.6-VISUAL-ALIGNMENT

Generates two 1200x1200px PNG noise images where overlaying beta onto alpha
at offset (87, 112) reveals a 4-digit hidden number via LSB steganography
at 8% opacity.

The hidden text is blended into beta BEFORE the shift, so it only becomes
legible when beta is shifted back to alignment with alpha.
"""
import sys
import os
import struct
import hashlib
import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("ERROR: Pillow required. Install with: pip install Pillow")
    sys.exit(1)


# ─────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────
IMAGE_WIDTH = 1200
IMAGE_HEIGHT = 1200
SHIFT_X = 87
SHIFT_Y = 112
HIDDEN_NUMBER = 427  # The shift_offset value
OPACITY_PERCENT = 8  # Glyph blending opacity


def generate_noise(width: int, height: int, seed: int) -> np.ndarray:
    """Generate deterministic structured noise using seeded Perlin-like noise."""
    rng = np.random.RandomState(seed)

    # Generate octaves of simple periodic noise
    noise = np.zeros((height, width), dtype=np.float32)

    # Multi-octave noise combining different frequencies
    for octave in range(4):
        frequency = 2 ** octave
        amplitude = 1.0 / (octave + 1)

        # Create periodic sine/cosine wave patterns
        x = np.linspace(0, frequency * 2 * np.pi, width)
        y = np.linspace(0, frequency * 2 * np.pi, height)
        X, Y = np.meshgrid(x, y)

        noise += amplitude * np.sin(X) * np.cos(Y)

    # Normalize to [0, 255]
    noise = ((noise - noise.min()) / (noise.max() - noise.min()) * 255).astype(np.uint8)
    return noise


def create_glyph_pattern(text: str, width: int, height: int) -> np.ndarray:
    """Create a simple monochrome glyph pattern for the hidden text."""
    # Create a simple text image
    text_img = Image.new('L', (width, height), color=0)
    draw = ImageDraw.Draw(text_img)

    # Use default font (monospace-ish)
    # Draw large digits
    font_size = 200
    try:
        # Try to use a monospace font if available
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", font_size)
    except:
        # Fall back to default
        font = ImageFont.load_default()

    # Draw the 4-digit number centered
    text_str = str(HIDDEN_NUMBER).zfill(4)
    bbox = draw.textbbox((0, 0), text_str, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x_pos = (width - text_width) // 2
    y_pos = (height - text_height) // 2

    draw.text((x_pos, y_pos), text_str, fill=255, font=font)

    return np.array(text_img, dtype=np.uint8)


def blend_images(base: np.ndarray, overlay: np.ndarray, opacity: float) -> np.ndarray:
    """Blend overlay onto base with given opacity (0-100)."""
    alpha = opacity / 100.0
    result = (base.astype(float) * (1 - alpha) + overlay.astype(float) * alpha)
    return np.clip(result, 0, 255).astype(np.uint8)


def shift_image(img: np.ndarray, shift_x: int, shift_y: int) -> np.ndarray:
    """Shift image by (shift_x, shift_y) pixels, filling with white."""
    height, width = img.shape[:2]
    shifted = np.full_like(img, fill_value=255) if len(img.shape) == 2 else np.ones_like(img) * 255

    # Calculate the valid region
    src_y_start = max(0, -shift_y)
    src_y_end = min(height, height - shift_y)
    src_x_start = max(0, -shift_x)
    src_x_end = min(width, width - shift_x)

    dst_y_start = max(0, shift_y)
    dst_y_end = min(height, height + shift_y)
    dst_x_start = max(0, shift_x)
    dst_x_end = min(width, width + shift_x)

    if src_y_end > src_y_start and src_x_end > src_x_start:
        shifted[dst_y_start:dst_y_end, dst_x_start:dst_x_end] = img[src_y_start:src_y_end, src_x_start:src_x_end]

    return shifted


def generate_blueprints(output_dir: str = "."):
    """Generate alpha and beta blueprint images."""

    print(f"Generating {IMAGE_WIDTH}x{IMAGE_HEIGHT} blueprint images...")
    print(f"Hidden number: {HIDDEN_NUMBER}")
    print(f"Shift offset: ({SHIFT_X}, {SHIFT_Y})")
    print(f"Glyph opacity: {OPACITY_PERCENT}%")

    # Generate base noise (alpha)
    print("Generating noise field for alpha.png...")
    seed_alpha = 0xDEADBEEF
    noise_alpha = generate_noise(IMAGE_WIDTH, IMAGE_HEIGHT, seed_alpha)

    # Create glyph pattern
    print("Creating hidden glyph pattern...")
    glyph = create_glyph_pattern(str(HIDDEN_NUMBER).zfill(4), IMAGE_WIDTH, IMAGE_HEIGHT)

    # Blend glyph into noise BEFORE shifting (this is critical for the steganography to work)
    print(f"Blending glyph at {OPACITY_PERCENT}% opacity...")
    noise_with_glyph = blend_images(noise_alpha, glyph, OPACITY_PERCENT)

    # Shift the glyph-blended noise
    print(f"Shifting blended noise by ({SHIFT_X}, {SHIFT_Y})...")
    noise_beta = shift_image(noise_with_glyph, SHIFT_X, SHIFT_Y)

    # Save as PNG images
    alpha_path = os.path.join(output_dir, "shield_blueprint_alpha.png")
    beta_path = os.path.join(output_dir, "shield_blueprint_beta.png")

    print(f"Saving alpha.png to {alpha_path}...")
    Image.fromarray(noise_alpha, 'L').save(alpha_path, 'PNG')

    print(f"Saving beta.png to {beta_path}...")
    Image.fromarray(noise_beta, 'L').save(beta_path, 'PNG')

    print(f"\n✓ Blueprint images generated successfully!")
    print(f"  - {alpha_path} ({os.path.getsize(alpha_path)} bytes)")
    print(f"  - {beta_path} ({os.path.getsize(beta_path)} bytes)")
    print(f"\nTo find the hidden number:")
    print(f"  1. Open both images in an image editor")
    print(f"  2. Layer beta on top of alpha")
    print(f"  3. Adjust opacity of beta layer to ~50%")
    print(f"  4. Shift beta by approximately ({SHIFT_X}, {SHIFT_Y}) pixels")
    print(f"  5. The 4-digit number should become visible: {HIDDEN_NUMBER}")


if __name__ == "__main__":
    output_dir = "backend/assets" if os.path.exists("backend/assets") else "."
    generate_blueprints(output_dir)
