"""Package the transparent source artwork as a multiresolution Windows icon."""
from pathlib import Path

from PIL import Image

assets = Path(__file__).resolve().parent.parent / "assets"
with Image.open(assets / "capture-frame.png") as source:
    source.convert("RGBA").save(
        assets / "capture-frame.ico", format="ICO",
        sizes=[(size, size) for size in (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)],
    )
    print(f"Source: {source.size}, {source.mode}; Windows ICO: 16–256 px")
