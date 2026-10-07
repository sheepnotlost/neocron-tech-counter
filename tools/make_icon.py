"""Builds the app icon from the in-game tech sprite (run tools/extract_tech_sprite.py first).
Writes assets/icon.ico (16-256 px), assets/icon.png and assets/icon_preview.png.

The sprite is the real tech-part picture from the game, with a mint neon glow (the HUD's frame color) so it
stands out on a dark taskbar. Big sizes keep the sprite's pixels crisp (integer upscaling); small sizes are
smoothly downscaled.
"""
from pathlib import Path

from PIL import Image, ImageFilter

ASSETS = Path(__file__).resolve().parent.parent / "assets"
MINT = (78, 228, 145)


def glow(alpha, radius, strength):
    a = alpha.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(radius))
    a = a.point(lambda v: min(255, int(v * strength)))
    g = Image.new("RGBA", alpha.size, MINT + (0,))
    g.putalpha(a)
    return g


def icon(sprite, size):
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    fit = size * (1.0 if size <= 32 else 0.84)          # tiny sizes: use every pixel
    scale = fit / max(sprite.size)
    if scale >= 1.5:                                        # big: crisp pixels, integer factor
        k = int(scale)
        sp = sprite.resize((sprite.width * k, sprite.height * k), Image.NEAREST)
        if max(sp.size) < fit * 0.9:
            sp = sprite.resize((int(sprite.width * scale), int(sprite.height * scale)), Image.LANCZOS)
    else:
        sp = sprite.resize((max(1, int(sprite.width * scale)), max(1, int(sprite.height * scale))), Image.LANCZOS)
    x, y = (size - sp.width) // 2, (size - sp.height) // 2
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    layer.alpha_composite(sp, (x, y))
    if size > 32:
        canvas.alpha_composite(glow(layer.getchannel("A"), size * 0.035, 1.6))      # neon halo
    else:
        canvas.alpha_composite(glow(layer.getchannel("A"), 0.8, 2.5))               # a thin neon edge
    canvas.alpha_composite(layer)
    return canvas


def main():
    sprite = Image.open(ASSETS / "tech_sprite.png").convert("RGBA")
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    frames = [icon(sprite, s) for s in sizes]
    frames[-1].save(ASSETS / "icon.png")
    frames[-1].save(ASSETS / "icon.ico", sizes=[(s, s) for s in sizes], append_images=frames[:-1])
    sheet = Image.new("RGBA", (sum(sizes) + 20 * len(sizes) + 20, 2 * 256 + 60), (9, 24, 17, 255))
    x = 20
    for s, f in zip(sizes, frames):
        sheet.alpha_composite(f, (x, 20 + 256 - s))
        light = Image.new("RGBA", (s + 8, s + 8), (232, 236, 240, 255))
        light.alpha_composite(f, (4, 4))
        sheet.alpha_composite(light, (x - 4, 40 + 512 - s - 8))
        x += s + 20
    sheet.save(ASSETS / "icon_preview.png")
    print("wrote assets/icon.ico, icon.png, icon_preview.png")


if __name__ == "__main__":
    main()
