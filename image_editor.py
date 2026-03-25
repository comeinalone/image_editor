"""
Basic Image Editor — Pure Python, No External Libraries
Reads/writes PPM (P6 binary) files manually, pixel by pixel.

Supported operations:
  • Greyscale    — convert to luminance-weighted grey
  • Blue filter  — zero out R and G channels
  • Crop         — extract a rectangular sub-region
  • Invert       — flip every channel value (255 - v)

Usage:
  python image_editor.py <input.ppm> <operation> [options] <output.ppm>

Operations:
  greyscale   <input.ppm> greyscale <output.ppm>
  blue        <input.ppm> blue      <output.ppm>
  invert      <input.ppm> invert    <output.ppm>
  crop        <input.ppm> crop <x> <y> <width> <height> <output.ppm>

Demo (no arguments):
  python image_editor.py
  — generates a sample PPM, applies all four effects and saves them.
"""

import sys
import os
import struct


# ---------------------------------------------------------------------------
# PPM I/O  (supports P6 binary and P3 ASCII)
# ---------------------------------------------------------------------------

class Image:
    """Minimal image container: width, height, max_val, and a flat pixel list."""

    def __init__(self, width: int, height: int, max_val: int = 255):
        self.width   = width
        self.height  = height
        self.max_val = max_val
        # pixels stored as flat list of (R, G, B) tuples
        self.pixels: list[tuple[int, int, int]] = [(0, 0, 0)] * (width * height)

    # ------------------------------------------------------------------
    # Pixel access helpers
    # ------------------------------------------------------------------

    def get_pixel(self, x: int, y: int) -> tuple[int, int, int]:
        """Return (R, G, B) for pixel at column x, row y."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(f"Pixel ({x},{y}) is out of bounds for {self.width}×{self.height} image.")
        return self.pixels[y * self.width + x]

    def set_pixel(self, x: int, y: int, rgb: tuple[int, int, int]) -> None:
        """Set pixel at (x, y) to (R, G, B)."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(f"Pixel ({x},{y}) is out of bounds.")
        self.pixels[y * self.width + x] = rgb

    # ------------------------------------------------------------------
    # PPM readers
    # ------------------------------------------------------------------

    @classmethod
    def load_ppm(cls, path: str) -> "Image":
        """
        Read a PPM file (P3 ASCII or P6 binary) and return an Image.
        All bytes are parsed manually — no external libraries used.
        """
        with open(path, "rb") as f:
            raw = f.read()

        pos = 0

        def skip_whitespace_and_comments():
            nonlocal pos
            while pos < len(raw):
                if raw[pos:pos+1] == b"#":
                    while pos < len(raw) and raw[pos:pos+1] != b"\n":
                        pos += 1
                elif raw[pos:pos+1] in (b" ", b"\t", b"\n", b"\r"):
                    pos += 1
                else:
                    break

        def read_token() -> bytes:
            nonlocal pos
            skip_whitespace_and_comments()
            start = pos
            while pos < len(raw) and raw[pos:pos+1] not in (b" ", b"\t", b"\n", b"\r"):
                pos += 1
            return raw[start:pos]

        magic   = read_token().decode("ascii")
        width   = int(read_token())
        height  = int(read_token())
        max_val = int(read_token())

        if magic not in ("P3", "P6"):
            raise ValueError(f"Unsupported PPM format: {magic!r}  (only P3 and P6 are supported)")

        img = cls(width, height, max_val)

        if magic == "P6":
            # --- binary pixel data starts after the single whitespace byte ---
            pos += 1          # skip the mandatory single whitespace after max_val
            bytes_per_channel = 2 if max_val > 255 else 1
            total_bytes = width * height * 3 * bytes_per_channel
            pixel_data = raw[pos: pos + total_bytes]

            if bytes_per_channel == 1:
                # fast path: each byte is one channel value
                for i in range(width * height):
                    r = pixel_data[i * 3]
                    g = pixel_data[i * 3 + 1]
                    b = pixel_data[i * 3 + 2]
                    img.pixels[i] = (r, g, b)
            else:
                # 16-bit big-endian channels
                for i in range(width * height):
                    base = i * 6
                    r = struct.unpack_from(">H", pixel_data, base)[0]
                    g = struct.unpack_from(">H", pixel_data, base + 2)[0]
                    b = struct.unpack_from(">H", pixel_data, base + 4)[0]
                    img.pixels[i] = (r, g, b)

        else:  # P3 — ASCII tokens
            for i in range(width * height):
                r = int(read_token())
                g = int(read_token())
                b = int(read_token())
                img.pixels[i] = (r, g, b)

        print(f"[load]  {path}  ({width}×{height}, max={max_val}, format={magic})")
        return img

    # ------------------------------------------------------------------
    # PPM writer (always writes P6 binary)
    # ------------------------------------------------------------------

    def save_ppm(self, path: str) -> None:
        """Write image to a P6 (binary) PPM file."""
        header = f"P6\n{self.width} {self.height}\n{self.max_val}\n".encode("ascii")
        pixel_bytes = bytearray(self.width * self.height * 3)
        for i, (r, g, b) in enumerate(self.pixels):
            pixel_bytes[i * 3]     = r
            pixel_bytes[i * 3 + 1] = g
            pixel_bytes[i * 3 + 2] = b
        with open(path, "wb") as f:
            f.write(header)
            f.write(pixel_bytes)
        print(f"[save]  {path}  ({self.width}×{self.height})")


# ---------------------------------------------------------------------------
# Image operations  (each returns a NEW Image, input is never modified)
# ---------------------------------------------------------------------------

def greyscale(img: Image) -> Image:
    """
    Convert to greyscale using the luminance formula:
        Y = 0.2126·R + 0.7152·G + 0.0722·B
    The weights reflect human eye sensitivity — green appears brightest.
    """
    out = Image(img.width, img.height, img.max_val)
    for i, (r, g, b) in enumerate(img.pixels):
        y = int(0.2126 * r + 0.7152 * g + 0.0722 * b)
        out.pixels[i] = (y, y, y)
    print("[op]    greyscale applied")
    return out


def blue_filter(img: Image) -> Image:
    """
    Keep only the blue channel; set R and G to zero.
    """
    out = Image(img.width, img.height, img.max_val)
    for i, (r, g, b) in enumerate(img.pixels):
        out.pixels[i] = (0, 0, b)
    print("[op]    blue filter applied")
    return out


def invert(img: Image) -> Image:
    """
    Invert all colour channels:  new_channel = max_val − old_channel.
    """
    out = Image(img.width, img.height, img.max_val)
    mv  = img.max_val
    for i, (r, g, b) in enumerate(img.pixels):
        out.pixels[i] = (mv - r, mv - g, mv - b)
    print("[op]    colour invert applied")
    return out


def crop(img: Image, x: int, y: int, width: int, height: int) -> Image:
    """
    Crop a rectangular region starting at (x, y) with the given size.

    Parameters
    ----------
    x, y    : top-left corner of the crop box (0-indexed, in pixels)
    width   : number of columns to keep
    height  : number of rows to keep
    """
    # Clamp to image bounds
    x2 = min(x + width,  img.width)
    y2 = min(y + height, img.height)
    x  = max(x, 0)
    y  = max(y, 0)

    new_w = x2 - x
    new_h = y2 - y

    if new_w <= 0 or new_h <= 0:
        raise ValueError("Crop region is entirely outside the image.")

    out = Image(new_w, new_h, img.max_val)
    for row in range(new_h):
        for col in range(new_w):
            out.pixels[row * new_w + col] = img.get_pixel(x + col, y + row)

    print(f"[op]    crop applied  ({x},{y}) → {new_w}×{new_h}")
    return out


# ---------------------------------------------------------------------------
# Demo: create a synthetic test image and apply all four effects
# ---------------------------------------------------------------------------

def create_test_image(width: int = 200, height: int = 150) -> Image:
    """
    Generate a colourful test image with:
      • a red-to-blue horizontal gradient in the top half
      • a green-to-yellow horizontal gradient in the bottom half
      • a white diagonal stripe
    """
    img = Image(width, height)
    for y in range(height):
        for x in range(width):
            t = x / max(width - 1, 1)        # 0.0 → 1.0 left to right

            if y < height // 2:
                # top half: red → blue
                r = int((1 - t) * 255)
                g = 30
                b = int(t * 255)
            else:
                # bottom half: green → yellow
                r = int(t * 255)
                g = 200
                b = 30

            # white diagonal stripe  ±4 px wide
            if abs(x - y * width // height) < 5:
                r, g, b = 255, 255, 255

            img.set_pixel(x, y, (r, g, b))

    print(f"[demo]  created synthetic test image ({width}×{height})")
    return img


def run_demo():
    os.makedirs("demo_output", exist_ok=True)

    original_path  = "demo_output/original.ppm"
    grey_path      = "demo_output/greyscale.ppm"
    blue_path      = "demo_output/blue.ppm"
    invert_path    = "demo_output/invert.ppm"
    crop_path      = "demo_output/crop.ppm"

    # 1. Create and save the test image
    img = create_test_image(200, 150)
    img.save_ppm(original_path)

    # 2. Reload it (exercises the reader)
    img = Image.load_ppm(original_path)

    # 3. Apply each effect and save
    greyscale(img).save_ppm(grey_path)
    blue_filter(img).save_ppm(blue_path)
    invert(img).save_ppm(invert_path)
    crop(img, x=30, y=20, width=120, height=80).save_ppm(crop_path)

    print("\nAll demo images saved to ./demo_output/")
    print("  original.ppm  — source image")
    print("  greyscale.ppm — luminance-weighted grey")
    print("  blue.ppm      — blue channel only")
    print("  invert.ppm    — colour inverted")
    print("  crop.ppm      — cropped region (30,20) 120×80")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

USAGE = """
Usage:
  python image_editor.py                                         (demo mode)
  python image_editor.py <input.ppm> greyscale <output.ppm>
  python image_editor.py <input.ppm> blue      <output.ppm>
  python image_editor.py <input.ppm> invert    <output.ppm>
  python image_editor.py <input.ppm> crop <x> <y> <w> <h> <output.ppm>
"""

def main():
    args = sys.argv[1:]

    if not args:
        run_demo()
        return

    if len(args) < 3:
        print(USAGE)
        sys.exit(1)

    input_path = args[0]
    operation  = args[1].lower()

    img = Image.load_ppm(input_path)

    if operation == "greyscale":
        result = greyscale(img)
        result.save_ppm(args[2])

    elif operation == "blue":
        result = blue_filter(img)
        result.save_ppm(args[2])

    elif operation == "invert":
        result = invert(img)
        result.save_ppm(args[2])

    elif operation == "crop":
        if len(args) < 7:
            print("crop requires: <x> <y> <width> <height> <output.ppm>")
            sys.exit(1)
        x, y, w, h = int(args[2]), int(args[3]), int(args[4]), int(args[5])
        result = crop(img, x, y, w, h)
        result.save_ppm(args[6])

    else:
        print(f"Unknown operation: {operation!r}")
        print(USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()