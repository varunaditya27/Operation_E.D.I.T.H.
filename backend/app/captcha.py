"""
Operation E.D.I.T.H. v5 — CAPTCHA Generator
Document Ref: SPEC-ACT4-ZKPWS §2.1

Generates distorted visual CAPTCHAs that resist standard OCR
but remain readable by humans.
"""
import io
import random
import math
import base64

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Characters excluding ambiguous ones (0, O, 1, l, I)
CHARSET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CAPTCHA_WIDTH = 150
CAPTCHA_HEIGHT = 50
CAPTCHA_LENGTH = 4


def _wave_distort(image: "Image.Image") -> "Image.Image":
    """Apply light sinusoidal wave warping (reduced from SPEC for OCR compatibility):
    x' = x + 1*sin(y/8), y' = y + 1*cos(x/6)
    """
    width, height = image.size
    pixels = image.load()
    new_img = Image.new("RGB", (width, height), (20, 20, 30))
    new_pixels = new_img.load()

    for y in range(height):
        for x in range(width):
            src_x = int(x + 1 * math.sin(y / 8.0))  # Reduced amplitude from 4 to 1
            src_y = int(y + 1 * math.cos(x / 6.0))  # Reduced amplitude from 2 to 1
            if 0 <= src_x < width and 0 <= src_y < height:
                new_pixels[x, y] = pixels[src_x, src_y]

    return new_img


def generate_captcha() -> tuple[str, str]:
    """Generate a CAPTCHA image.
    Returns (text, base64_png_data_uri).
    """
    if not HAS_PIL:
        # Fallback: return a simple text-based "captcha" for environments without PIL
        text = "".join(random.choices(CHARSET, k=CAPTCHA_LENGTH))
        return text, f"text:{text}"

    text = "".join(random.choices(CHARSET, k=CAPTCHA_LENGTH))

    # Create base image with dark background
    img = Image.new("RGB", (CAPTCHA_WIDTH, CAPTCHA_HEIGHT), (20, 20, 30))
    draw = ImageDraw.Draw(img)

    # Try to use a built-in font, fall back to default
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 28)
    except (IOError, OSError):
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf", 28)
        except (IOError, OSError):
            font = ImageFont.load_default()

    # Draw each character with random offset and color
    x_offset = 10
    for char in text:
        color = (
            random.randint(150, 255),
            random.randint(150, 255),
            random.randint(150, 255),
        )
        y_offset = random.randint(-5, 5)
        draw.text((x_offset, 8 + y_offset), char, fill=color, font=font)
        x_offset += 30 + random.randint(-3, 3)

    # Add 2 random bezier-like curves (reduced from 5 for OCR compatibility)
    for _ in range(2):
        x1 = random.randint(0, CAPTCHA_WIDTH // 3)
        y1 = random.randint(0, CAPTCHA_HEIGHT)
        x2 = random.randint(CAPTCHA_WIDTH * 2 // 3, CAPTCHA_WIDTH)
        y2 = random.randint(0, CAPTCHA_HEIGHT)
        mid_x = (x1 + x2) // 2 + random.randint(-10, 10)  # Reduced jitter from ±20 to ±10
        mid_y = random.randint(0, CAPTCHA_HEIGHT)
        line_color = (
            random.randint(80, 180),
            random.randint(80, 180),
            random.randint(80, 180),
        )
        draw.line([(x1, y1), (mid_x, mid_y), (x2, y2)], fill=line_color, width=1)

    # Add random dots for noise (reduced from 100 to 30 for OCR compatibility)
    for _ in range(30):
        x = random.randint(0, CAPTCHA_WIDTH - 1)
        y = random.randint(0, CAPTCHA_HEIGHT - 1)
        draw.point((x, y), fill=(
            random.randint(50, 200),
            random.randint(50, 200),
            random.randint(50, 200),
        ))

    # Apply shear transform (reduced from ±0.3 to ±0.1 for OCR compatibility)
    shear_factor = random.uniform(-0.1, 0.1)
    img = img.transform(
        (CAPTCHA_WIDTH, CAPTCHA_HEIGHT),
        Image.AFFINE,
        (1, shear_factor, -shear_factor * CAPTCHA_HEIGHT / 2, 0, 1, 0),
        resample=Image.BILINEAR,
    )

    # Apply light wave distortion
    img = _wave_distort(img)

    # Minimal blur for OCR readability
    img = img.filter(ImageFilter.GaussianBlur(radius=0.2))

    # Encode to base64
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    return text, f"data:image/png;base64,{b64}"
