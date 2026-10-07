"""Scanner behaviour with a fake screen and mouse: no windows, cursor restore, abort, and scrolling (SPEC 11, 14)."""
import numpy as np
import pytest

from ntc import detect, names, scanner
from ntc.scanner import Scanner, shift_rows, views_equal

from conftest import load_theme, needs_tesseract


class FakeGame:
    """A screen whose inventory scrolls like the real one (verified live: 2 rows per wheel notch)."""

    def __init__(self, views, pos=0, drift_after=None, rows_per_notch=None):
        self.views, self.pos = views, pos
        self.rows_per_notch = rows_per_notch          # None: one notch = one view; else views are indexed by top row
        self.cursor, self.moves, self.wheels = (111, 222), [], []
        self.drift_after = drift_after

    def grab(self):
        return self.views[self.pos]

    def grab_region(self, x, y, w, h):
        return np.zeros((h, w, 3), np.uint8)              # never shows a tooltip

    def move(self, x, y, mode):
        self.moves.append((x, y))
        self.cursor = (x, y)

    def get_cursor(self):
        if self.drift_after is not None and len(self.moves) > self.drift_after:
            return (self.cursor[0] + 200, self.cursor[1])  # the user grabbed the mouse
        return self.cursor

    def wheel(self, notches):
        """Negative = scroll down. The test views are 2 rows apart, so one notch moves one view."""
        self.wheels.append(notches)
        step = notches * (self.rows_per_notch or 1)
        self.pos = min(max(self.pos - step, 0), len(self.views) - 1)


def make(cfg, tmp_path, game, foreground="Neocron Evolution"):
    cfg = {**cfg, "tooltip_timeout_ms": 30, "tooltip_probe_ms": 30, "scroll_settle_ms": 1,
           "scroll_park_ms": 1, "scroll_notches": 1}
    return Scanner(cfg, names.Names(tmp_path / "k.json"), grab=game.grab, move=game.move,
                   get_cursor=game.get_cursor, foreground=lambda: foreground, focus=lambda title: True,
                   grab_region=game.grab_region, wheel=game.wheel)


def scrolling_views(rows_per_step=2, steps=3):
    """Views of the inventory scrolled 0, 2, 4... rows into a 12-row list made from two different themes.
    (The last view stops at the bottom, row 6, like the real window.)"""
    base, other = load_theme("07"), load_theme("12")
    w = {x.kind: x for x in detect.find_windows(base)}["inventory"]
    x0, y0, qx, qy = int(round(w.x0)), int(round(w.y0)), int(round(w.qx)), int(round(w.qy))
    band = lambda img, r: img[y0 + r * qy:y0 + (r + 1) * qy, x0:x0 + 8 * qx]
    content = [band(base, r) for r in range(6)] + [band(other, r) for r in range(6)]
    views = []
    for k in range(steps + 1):
        v = base.copy()
        for r in range(6):
            v[y0 + r * qy:y0 + (r + 1) * qy, x0:x0 + 8 * qx] = content[min(min(k * rows_per_step, 6) + r, 11)]
        views.append(v)
    return views, w


def test_shift_detection_matches_what_was_scrolled():
    views, w = scrolling_views()
    assert shift_rows(views[0], views[1], w) == 2
    assert shift_rows(views[1], views[2], w) == 2
    assert shift_rows(views[2], views[2].copy(), w) == 0 and views_equal(views[2], views[2].copy(), w)


@needs_tesseract
def test_no_windows_open_never_moves_mouse(cfg, tmp_path):
    blank = load_theme("01").copy()
    strip = blank[1160:1400, 300:2300]
    for y in range(250, 1140, 240):
        h = min(240, 1140 - y)
        blank[y:y + h, 150:1850] = (strip if (y // 240) % 2 == 0 else strip[::-1])[:h, :1700]
    game = FakeGame([blank])
    results = make(cfg, tmp_path, game).scan("all")
    assert "found" in results[0].warnings[0] and game.moves == [] and game.wheels == []


@needs_tesseract
def test_game_not_in_front_never_moves_mouse(cfg, tmp_path):
    game = FakeGame([load_theme("01")])
    results = make(cfg, tmp_path, game, foreground="Some Other Window").scan("all")
    assert results[0].warnings[0].startswith("Could not bring the game to the front") and game.moves == []


@needs_tesseract
def test_scans_both_windows_and_restores_cursor(cfg, tmp_path):
    game = FakeGame([load_theme("01")])
    results = make(cfg, tmp_path, game).scan("all")
    assert [r.kind for r in results] == ["cabinet", "inventory"]
    assert game.cursor == (111, 222)
    assert len(results[0].cells) == 20                          # every filled cabinet slot, tooltip unreadable here
    assert all("NAME_UNREAD" in c.flags for c in results[0].cells)


@needs_tesseract
@pytest.mark.parametrize("target,kinds", [("cabinet", ["cabinet"]), ("inventory", ["inventory"])])
def test_scan_target_limits_what_is_scanned(cfg, tmp_path, target, kinds):
    game = FakeGame([load_theme("01")])
    assert [r.kind for r in make(cfg, tmp_path, game).scan(target)] == kinds


@needs_tesseract
def test_scrolls_to_top_then_reads_every_row_to_the_bottom(cfg, tmp_path):
    views, _ = scrolling_views(rows_per_step=2, steps=3)       # 12 rows: tops at 0, 2, 4, 6 (6 is the last view)
    game = FakeGame(views, pos=2)                               # the inventory starts scrolled to the middle
    result = make(cfg, tmp_path, game).scan("inventory")[0]
    rows = {c.row for c in result.cells}
    assert max(rows) == 11 and min(rows) == 0, sorted(rows)     # nothing skipped, nothing counted twice
    assert any(n > 0 for n in game.wheels) and game.wheels.count(-1) >= 3
    assert not any("did not scroll" in w for w in result.warnings)


@needs_tesseract
def test_two_notch_scrolling_reads_every_row(cfg, tmp_path):
    """The default (2 notches = 4 rows per step) must still see every row of a 12-row inventory."""
    views, _ = scrolling_views(rows_per_step=1, steps=6)       # views indexed by top row 0..6
    game = FakeGame(views, pos=3, rows_per_notch=2)
    s = make(cfg, tmp_path, game)
    s.cfg["scroll_notches"] = 2
    result = s.scan("inventory")[0]
    rows = {c.row for c in result.cells}
    assert min(rows) == 0 and max(rows) == 11, sorted(rows)
    assert game.wheels.count(-2) >= 2 and not any("Lost track" in w for w in result.warnings)


@needs_tesseract
def test_window_that_does_not_scroll_is_reported(cfg, tmp_path):
    game = FakeGame([load_theme("07")])
    inv = [r for r in make(cfg, tmp_path, game).scan("all") if r.kind == "inventory"][0]
    assert any("did not scroll" in w for w in inv.warnings)     # the last row has items, so this matters


@needs_tesseract
def test_manual_mouse_move_aborts_and_restores(cfg, tmp_path):
    game = FakeGame([load_theme("01")], drift_after=3)
    results = make(cfg, tmp_path, game).scan("all")
    assert any(r.aborted and "ABORTED - partial" in r.warnings for r in results)
    assert game.cursor == (111, 222)


def test_abort_request_stops_scan(cfg, tmp_path):
    s = make(cfg, tmp_path, FakeGame([load_theme("01")]))
    s.request_abort()
    assert s.aborted()


@needs_tesseract
@pytest.mark.parametrize("items,expected_cells", [("all", 20), ("techs", 10)])
def test_log_all_items_or_techs_only(cfg, tmp_path, monkeypatch, items, expected_cells):
    """Script the tooltip names: every 4th slot is a tech or a non-tech alternately (10 of the 20 are techs)."""
    names_cycle = ["Core Part Of HOLY DEFLECTION", "WarBot Remains", "Dog Tag Of A, B, 51/ 56", "Hull Part Of LIBERATOR"]
    calls = {"n": 0}

    def fake_capture(*a, **k):
        calls["n"] += 1
        return np.full((20, 50, 3), calls["n"] - 1, np.uint8)             # the crop carries its own index

    monkeypatch.setattr(scanner.tooltip, "capture_live", fake_capture)
    monkeypatch.setattr(scanner.ocr, "read_tooltip_text", lambda crop: names_cycle[int(crop[0, 0, 0]) % 4])
    game = FakeGame([load_theme("01")])
    result = make(cfg, tmp_path, game).scan("cabinet", items=items)[0]
    assert len(result.cells) == expected_cells
    if items == "techs":
        assert all(" Part Of " in c.name for c in result.cells)
        assert any("not logged (techs only)" in w for w in result.warnings)
        assert not any("WarBot" in n or "Dog Tag" in n for n in names.Names(tmp_path / "k.json").data["names"])
    else:
        assert any(c.name == "WarBot Remains" for c in result.cells)


@needs_tesseract
def test_techs_only_never_hovers_non_tech_labels(cfg, tmp_path, monkeypatch):
    """Slots whose label is clearly not a tech (ULT...) are not hovered with techs only; with 'all' they are."""
    hovered = []

    def fake_capture(*a, **k):
        hovered.append(1)
        return None                                           # no tooltip: strong candidates stay as unread items

    monkeypatch.setattr(scanner.tooltip, "capture_live", fake_capture)
    monkeypatch.setattr(scanner.slotmod, "read_label",
                        lambda img, rect: "ULT" if rect[0] % 2 == 0 else "COMP")
    game = FakeGame([load_theme("01")])
    r_all = make(cfg, tmp_path, game).scan("cabinet", items="all")[0]
    n_all = len(hovered)
    hovered.clear()
    r_tech = make(cfg, tmp_path, FakeGame([load_theme("01")])).scan("cabinet", items="techs")[0]
    assert 0 < len(hovered) < n_all
    assert any("not logged (techs only)" in w for w in r_tech.warnings)
