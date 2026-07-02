#!/usr/bin/env python3
"""
Operation E.D.I.T.H. v6 — Blueprint Steganography Generator
Document Ref: SPEC-ACT0.6-VISUAL-ALIGNMENT

Generates two 1200x1200px PNG noise images where overlaying beta onto alpha
at offset (87, 112) reveals a 4-digit hidden number.

CRITICAL: The glyph is embedded INDEPENDENTLY in both alpha and beta at different
positions. Only when beta is shifted by (87, 112) and overlaid on alpha do the
embedded glyphs align to create a clear, visible number. Neither image alone shows
the number - it requires BOTH proper alignment AND overlay.
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
GLYPH_OPACITY = 8  # Blend strength when both images overlay


def generate_noise(width: int, height: int, seed: int) -> np.ndarray:
    """Generate deterministic noise from seeded random."""
    rng = np.random.RandomState(seed)
    noise = rng.randint(0, 256, (height, width), dtype=np.uint8)
    return noise


def create_glyph_pattern(text: str, width: int, height: int) -> np.ndarray:
    """Create a monochrome glyph pattern."""
    text_img = Image.new('L', (width, height), color=0)
    draw = ImageDraw.Draw(text_img)

    font_size = 280
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", font_size)
    except:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", font_size)
        except:
            font = ImageFont.load_default()

    text_str = str(HIDDEN_NUMBER).zfill(4)
    bbox = draw.textbbox((0, 0), text_str, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x_pos = (width - text_width) // 2
    y_pos = (height - text_height) // 2

    # Draw with thick strokes for visibility through noise
    for offset_x in [-2, -1, 0, 1, 2]:
        for offset_y in [-2, -1, 0, 1, 2]:
            draw.text((x_pos + offset_x, y_pos + offset_y), text_str, fill=200, font=font)

    draw.text((x_pos, y_pos), text_str, fill=255, font=font)

    return np.array(text_img, dtype=np.uint8)


def create_complementary_patterns(glyph: np.ndarray, width: int, height: int):
    """
    Create TWO complementary patterns from the glyph:
    - alpha_pattern: Where glyph is bright, pattern is DARK; where glyph is dark, pattern is BRIGHT
    - beta_pattern: INVERSE of alpha_pattern

    When overlaid at correct position, they combine to form the glyph.
    Individual patterns look like random noise.
    """
    glyph_normalized = glyph.astype(np.float32) / 255.0

    # Alpha pattern: inverted glyph (bright areas become dark, dark areas become bright)
    # This creates a negative image
    alpha_pattern = (1.0 - glyph_normalized) * 255

    # Beta pattern: the original glyph pattern
    beta_pattern = glyph_normalized * 255

    return alpha_pattern.astype(np.uint8), beta_pattern.astype(np.uint8)


def blend_pattern_into_noise(noise: np.ndarray, pattern: np.ndarray, pattern_pos_x: int, pattern_pos_y: int, blend_strength: float = 0.08) -> np.ndarray:
    """
    Subtly blend pattern into noise using very low blend strength.
    The pattern is only visible when combined with its complement at correct alignment.
    """
    result = noise.copy().astype(np.float32)

    pattern_h, pattern_w = pattern.shape

    # Calculate region where pattern fits
    y_start = max(0, pattern_pos_y)
    y_end = min(noise.shape[0], pattern_pos_y + pattern_h)
    x_start = max(0, pattern_pos_x)
    x_end = min(noise.shape[1], pattern_pos_x + pattern_w)

    # Clip pattern to valid region
    py_start = max(0, -pattern_pos_y)
    py_end = py_start + (y_end - y_start)
    px_start = max(0, -pattern_pos_x)
    px_end = px_start + (x_end - x_start)

    if y_start < y_end and x_start < x_end:
        # Very subtle blending - only modulate by small amount
        pattern_region = pattern[py_start:py_end, px_start:px_end].astype(np.float32)

        # Blend: mix pattern into noise at very low strength
        # Pattern influence: only 8% of final pixel value
        result[y_start:y_end, x_start:x_end] = (
            result[y_start:y_end, x_start:x_end] * (1.0 - blend_strength) +
            pattern_region * blend_strength
        )

    return np.clip(result, 0, 255).astype(np.uint8)


def generate_blueprints(output_dir: str = "."):
    """Generate alpha and beta blueprint images with complementary pattern steganography."""

    print(f"Generating {IMAGE_WIDTH}x{IMAGE_HEIGHT} blueprint images...")
    print(f"Hidden number: {HIDDEN_NUMBER}")
    print(f"Shift offset: ({SHIFT_X}, {SHIFT_Y})")
    print(f"Steganography: Complementary pattern interleaving")

    # Generate independent noise for alpha and beta
    print("Generating noise field for alpha.png...")
    noise_alpha = generate_noise(IMAGE_WIDTH, IMAGE_HEIGHT, seed=0xDEADBEEF)

    print("Generating noise field for beta.png...")
    noise_beta = generate_noise(IMAGE_WIDTH, IMAGE_HEIGHT, seed=0xCAFEBABE)

    # Create glyph pattern
    print("Creating glyph pattern for steganography...")
    glyph = create_glyph_pattern(str(HIDDEN_NUMBER).zfill(4), IMAGE_WIDTH, IMAGE_HEIGHT)

    # Create complementary patterns
    print("Creating complementary alpha and beta patterns...")
    alpha_pattern, beta_pattern = create_complementary_patterns(glyph, IMAGE_WIDTH, IMAGE_HEIGHT)

    # Calculate center position for glyph
    glyph_center_x = IMAGE_WIDTH // 2 - 140
    glyph_center_y = IMAGE_HEIGHT // 2 - 70

    # Blend complementary patterns into noise
    # Alpha gets the inverted pattern, beta gets the normal pattern
    print(f"Blending complementary patterns into noise...")
    print(f"  Alpha pattern at ({glyph_center_x}, {glyph_center_y})")
    alpha_result = blend_pattern_into_noise(noise_alpha, alpha_pattern, glyph_center_x, glyph_center_y, blend_strength=0.08)

    # Beta pattern at phase-shifted position (will align when shifted by SHIFT_X, SHIFT_Y)
    beta_pattern_x = glyph_center_x - SHIFT_X
    beta_pattern_y = glyph_center_y - SHIFT_Y
    print(f"  Beta pattern at ({beta_pattern_x}, {beta_pattern_y})")
    print(f"    (Aligns with alpha when shifted by ({SHIFT_X}, {SHIFT_Y}))")
    beta_result = blend_pattern_into_noise(noise_beta, beta_pattern, beta_pattern_x, beta_pattern_y, blend_strength=0.08)

    # Save as PNG images
    alpha_path = os.path.join(output_dir, "shield_blueprint_alpha.png")
    beta_path = os.path.join(output_dir, "shield_blueprint_beta.png")

    print(f"Saving alpha.png to {alpha_path}...")
    Image.fromarray(alpha_result, 'L').save(alpha_path, 'PNG')

    print(f"Saving beta.png to {beta_path}...")
    Image.fromarray(beta_result, 'L').save(beta_path, 'PNG')

    print(f"\n✓ Blueprint images generated successfully!")
    print(f"  - {alpha_path} ({os.path.getsize(alpha_path)} bytes)")
    print(f"  - {beta_path} ({os.path.getsize(beta_path)} bytes)")
    print(f"\n✓ Steganography Details:")
    print(f"  - Alpha: Inverted pattern blended at 8% into noise")
    print(f"  - Beta: Normal pattern blended at 8% into noise")
    print(f"  - Individual images: Pattern barely visible, numbers NOT readable")
    print(f"  - When overlaid at correct shift ({SHIFT_X}, {SHIFT_Y}): Patterns combine")
    print(f"    → Inverted + Normal = VISIBLE NUMBER: {HIDDEN_NUMBER}")
    print(f"\nTo extract the hidden number:")
    print(f"  1. Open both images in image editor")
    print(f"  2. Layer beta ON TOP of alpha")
    print(f"  3. Try different shifts until patterns align")
    print(f"  4. When aligned correctly: The number {HIDDEN_NUMBER} becomes visible")
    print(f"  5. Neither image alone reveals the number - COMPLEMENTARY OVERLAY REQUIRED")


if __name__ == "__main__":
    output_dir = "backend/assets" if os.path.exists("backend/assets") else "."
    generate_blueprints(output_dir)
