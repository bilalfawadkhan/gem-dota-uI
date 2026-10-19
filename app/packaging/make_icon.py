"""Draw the app icon (a cut gem on the Material Telemetry Dark surface) as ``gemstudio.ico``.

A placeholder until there is a real logo: plain geometry, no Valve artwork. Run once; the
build uses the file if it exists::

    python packaging/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 512
SURFACE = (30, 31, 32, 255)  # #1e1f20
BLUE = (138, 180, 248, 255)  # #8ab4f8, the app's primary colour
BLUE_DARK = (74, 120, 196, 255)
BLUE_LIGHT = (200, 222, 255, 255)


def draw() -> Image.Image:
    """The icon at 512 px."""
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas = ImageDraw.Draw(image)
    canvas.rounded_rectangle((16, 16, SIZE - 16, SIZE - 16), radius=96, fill=SURFACE)
    # A brilliant-cut outline: crown (top trapezoid), girdle, pavilion (bottom triangle).
    top, girdle, bottom = 150, 230, 400
    left, right = 120, 392
    crown_l, crown_r = 190, 322
    canvas.polygon([(crown_l, top), (crown_r, top), (right, girdle), (left, girdle)], fill=BLUE)
    canvas.polygon([(left, girdle), (right, girdle), (256, bottom)], fill=BLUE_DARK)
    canvas.polygon([(crown_l, top), (crown_r, top), (256, girdle)], fill=BLUE_LIGHT)
    canvas.line([(crown_l, top), (256, girdle), (crown_r, top)], fill=SURFACE, width=6)
    canvas.line([(left, girdle), (256, bottom), (right, girdle)], fill=SURFACE, width=6)
    canvas.line([(256, girdle), (256, bottom)], fill=SURFACE, width=6)
    return image


def main() -> None:
    """Write ``gemstudio.ico`` beside this script (16 to 256 px)."""
    target = Path(__file__).with_name("gemstudio.ico")
    draw().save(target, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
