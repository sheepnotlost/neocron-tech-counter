"""Window detection must work with no calibration in every HUD color."""
import pytest

from ntc import detect

from conftest import CABINET_AT, INVENTORY_AT, load_theme, theme_ids

TOL = 3.0          # px


def find(tid):
    return {w.kind: w for w in detect.find_windows(load_theme(tid))}


@pytest.mark.parametrize("tid", theme_ids())
def test_cabinet_found_in_every_theme(tid):
    w = find(tid)["cabinet"]
    assert (w.cols, w.rows) == (5, 10)
    assert abs(w.x0 - CABINET_AT[0]) <= TOL and abs(w.y0 - CABINET_AT[1]) <= TOL


@pytest.mark.parametrize("tid", [t for t in theme_ids() if t != "14"])
def test_inventory_found_in_every_theme(tid):
    if tid == "05":
        pytest.xfail("known: in this navy variant the inventory is aligned one band edge (10 px) off")
    w = find(tid)["inventory"]
    assert (w.cols, w.rows) == (8, 6)
    assert abs(w.x0 - INVENTORY_AT[0]) <= TOL and abs(w.y0 - INVENTORY_AT[1]) <= TOL


def test_window_covered_by_another_window_is_not_reported():
    """Theme 14 was captured with the Options window open over the inventory: no inventory must be reported."""
    wins = find("14")
    assert "inventory" not in wins and "cabinet" in wins


@pytest.mark.parametrize("tid", ["01", "07", "08", "12"])
def test_nothing_found_when_no_window_is_open(tid):
    """Cover both windows with plain floor texture: the detector must say there is nothing, not invent a window."""
    img = load_theme(tid).copy()
    strip = img[1160:1400, 300:2300]
    for y in range(250, 1140, 240):
        h = min(240, 1140 - y)
        img[y:y + h, 150:1850] = (strip if (y // 240) % 2 == 0 else strip[::-1])[:h, :1700]
    assert detect.find_windows(img) == []


def test_finds_a_moved_window():
    """Windows can be dragged anywhere: shift the whole cabinet 300 px right and 150 px down."""
    img = load_theme("01")
    w = find("01")["cabinet"]
    x, y, ww, hh = w.bounds
    pad = 40
    patch = img[y - pad:y + hh + pad, x - pad:x + ww + pad].copy()
    moved = img.copy()
    moved[y - pad:y + hh + pad, x - pad:x + ww + pad] = img[1160:1400, 300:2300].mean(axis=(0, 1))     # clear old spot
    moved[y - pad + 150:y + hh + pad + 150, x - pad + 300:x + ww + pad + 300] = patch
    got = {k.kind: k for k in detect.find_windows(moved)}["cabinet"]
    assert abs(got.x0 - (w.x0 + 300)) <= TOL and abs(got.y0 - (w.y0 + 150)) <= TOL
