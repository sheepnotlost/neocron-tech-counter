"""Extracts the in-game tech-part sprite (assets/tech_sprite.png) from the HUD-theme captures.

Item sprites are not recolored by the HUD Color setting, while the slot background, the label and the stack
number are. So across the theme captures the sprite's pixels stay the same and everything else changes.
A majority vote over six slots with different labels (COMP, HULL, ATP, CORE, FRAM, TECH) drops label pixels.
"""
import glob
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ntc import detect  # noqa: E402

files = [f for f in sorted(glob.glob(str(ROOT / "tests/fixtures/themes_native/theme_*.png")))
         if not any(x in Path(f).stem for x in ("04", "05", "14"))]       # Options window over the HUD in those
crops = {(0, 0): [], (0, 1): [], (0, 2): [], (0, 3): [], (2, 0): [], (3, 0): []}   # COMP HULL ATP CORE FRAM TECH
for f in files:
    im = cv2.imread(f)
    w = [x for x in detect.find_windows(im) if x.kind == "cabinet"][0]
    for rc in crops:
        x, y, ww, hh = w.slot_rect(*rc)
        crops[rc].append(im[y + 2:y + hh - 2, x + 2:x + ww - 2].astype(np.float32))
masks, meds = [], []
for rc, st in crops.items():
    st = np.stack(st)
    meds.append(np.median(st, axis=0))
    masks.append(st.std(axis=0).mean(axis=2) < 9)
masks, meds = np.stack(masks), np.stack(meds)
# a label covers a given pixel in only one or two of the six slots: keep pixels that are stable in most slots,
# and take each pixel's color only from the slots where it is stable
mask = (masks.sum(axis=0) >= 4).astype(np.uint8)
w8 = masks[..., None].astype(np.float32)
color = (meds * w8).sum(axis=0) / np.maximum(w8.sum(axis=0), 1)
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
n, lab, stats, _ = cv2.connectedComponentsWithStats(mask)
mask = (lab == 1 + int(np.argmax(stats[1:, 4]))).astype(np.uint8)
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
ys, xs = np.where(mask)
x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
rgb = color[..., ::-1]
rgba = np.dstack([rgb, mask * 255]).astype(np.uint8)[y0:y1, x0:x1]
Image.fromarray(rgba).save(ROOT / "assets" / "tech_sprite.png")
print("assets/tech_sprite.png", rgba.shape[1], "x", rgba.shape[0])
