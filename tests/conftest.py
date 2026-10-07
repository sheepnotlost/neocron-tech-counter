import sys
from pathlib import Path

import cv2
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ntc import config, ocr  # noqa: E402

FIX = Path(__file__).parent / "fixtures"
THEMES = FIX / "themes_native"           # full-resolution (2560x1440) captures of every HUD Color, cabinet + inventory open

# Where the windows were in the theme captures (one game session), and the ground truth read off the screen.
CABINET_AT = (401.3, 268.0)
INVENTORY_AT = (1371.2, 701.1)
CABINET_FILLED = {(r, c) for r in range(4) for c in range(5)}
INVENTORY_EMPTY = {(4, 5), (4, 6), (4, 7), (5, 0)}
INVENTORY_FILLED = {(r, c) for r in range(6) for c in range(8)} - INVENTORY_EMPTY
CABINET_STACKS = {(1, 2): 2, (1, 3): 5, (3, 1): 2, (3, 3): 2}
INVENTORY_STACKS = {(0, 0): 2, (0, 4): 2, (0, 6): 2, (5, 1): 2, (5, 2): 5, (5, 3): 2, (5, 4): 14, (5, 5): 5, (5, 6): 3}
INVENTORY_NON_TECH = {(5, 1), (5, 2), (5, 3), (5, 5)}     # the ULT stacks (label read as ULT)
# Captures where the in-game Options window was still open over part of the screen (see the notes in SPEC 14).
OPTIONS_OVER_HUD = {"04", "05", "14"}


@pytest.fixture(scope="session")
def cfg():
    c = dict(config.DEFAULTS)
    ocr.configure(c["tesseract_path"])
    return c


def theme_ids():
    return sorted(p.stem.split("_")[1] for p in THEMES.glob("theme_*.png"))


def load_theme(tid):
    return cv2.imread(str(THEMES / f"theme_{tid}.png"))


def load_fixture(name):
    return cv2.imread(str(FIX / name))


needs_tesseract = pytest.mark.skipif(not ocr.available() and not Path(config.DEFAULTS["tesseract_path"]).exists(),
                                     reason="Tesseract not installed")
