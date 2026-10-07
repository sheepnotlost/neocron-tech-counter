import pytest

from ntc import tooltip
from ntc.names import Names

from conftest import load_fixture, needs_tesseract

XS = [316, 460, 604, 748, 892]
# Ground truth verified against the cabinet labels during the live scan.
EXPECTED = {
    (0, 307): ["Component Part Of HOLY TRUE SIGHT SANCTUM", "Hull Part Of HOLY ABSORPTION",
               "Additional Technology Part Of HOLY ABSORPTION", "Core Part Of HOLY ABSORPTION",
               "Hull Part Of HOLY PROTECTION"],
    (2, 451): ["Frame Part Of HOLY ABSORPTION", "Component Part Of HOLY EXORCIST",
               "Core Part Of HOLY DEFLECTION", "Component Part Of HOLY DEFLECTION",
               "Hull Part Of HOLY CATHARSIS"],
}
CASES = [(r, c, y, x, name) for (r, y), names in EXPECTED.items() for c, (x, name) in enumerate(zip(XS, names))]


@needs_tesseract
@pytest.mark.parametrize("row,col,y,x,expected", CASES)
def test_tooltip_name(cfg, tmp_path, row, col, y, x, expected):
    img = load_fixture(f"probe_r{row}c{col}.png")
    raw = tooltip.read_from_image(img, x, y)
    name, _ = Names(tmp_path / "k.json").normalize(raw)
    assert name == expected


def test_box_geometry(cfg):
    box = tooltip.find_tooltip(load_fixture("probe_r2c1.png"), 460, 451)
    assert box == (260, 474, 403, 30)


def test_no_tooltip_when_none_shown(cfg):
    assert tooltip.find_tooltip(load_fixture("cabinet_baseline.png"), 316, 380) is None


def test_stale_tooltip_rejected(cfg):
    """A tooltip whose span does not contain the cursor x must not be accepted."""
    img = load_fixture("probe_r2c1.png")
    assert tooltip.find_tooltip(img, 1500, 451) is None
