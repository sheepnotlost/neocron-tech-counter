# Neocron Tech Counter — Plan + Spec

## Context
In Neocron 2 / Evolution, the user opens a cabinet and wants the contents counted automatically. Each grid cell shows a short label (COMP, HULL, CORE…) and, for stacks, an `xN` count. Only the hover tooltip shows the full name (e.g. "Core Part Of HOLY DEFLECTION"). The tool works only from screen pixels. It never reads game memory and never clicks. It may move the mouse to show tooltips (the user approved this, accepting the game-rules risk).

**Feasible?** Yes. The UI is a fixed grid on a flat background, the tooltip is white text on black, and the game runs borderless at a fixed 2560x1440, so screen capture and OCR are reliable here. The main unknown is whether the game shows tooltips when the mouse is moved programmatically. Phase 0 tests this before anything else is built.

Project folder: the project folder (currently empty). Python 3.14.5 is installed.

**Step 1 of implementation:** copy the "SPEC" section below into `SPEC.md` in the project folder. From then on, SPEC.md is the source of truth. If code and spec disagree, fix the code, or update the spec on purpose and note why.

---

# SPEC (copy to SPEC.md)

## 1. Scope
**In:** count every item in the **visible** grid of an open cabinet window, using full item names from tooltips and stack quantities; show results in a small always-on-top window; export them.
**Out (v1):** scrolling the cabinet, reading game memory or packets, clicking, moving items, other resolutions without recalibration, and multi-cell items.

## 2. Environment
- Windows 10, Python 3.14, game borderless fullscreen at **2560x1440**.
- The process calls `SetProcessDpiAwareness(2)` at startup, so all coordinates are physical pixels.
- If the game runs as administrator, the tool must also run as administrator, because Windows blocks synthetic input into elevated windows. The README must say this.
- Dependencies: `mss`, `numpy`, `opencv-python`, `Pillow`, `pytesseract`, and `pytest` for development. UI is `tkinter` (stdlib). Hotkeys and mouse go through `ctypes` (`RegisterHotKey`, `SendInput`, `GetCursorPos`, `GetForegroundWindow`), with no extra packages.
- External: the Tesseract-OCR binary (UB Mannheim Windows installer). The path is set in config, defaulting to `C:\Program Files\Tesseract-OCR\tesseract.exe`. If it's missing, the app shows a clear error with the install link.

## 3. User flow
1. Start the app with `python -m ntc`. A small always-on-top window appears.
2. **First run only:** calibrate (§5).
3. In game, open a cabinet, then press **Ctrl+Alt+S**, or click **Scan** in the app (the app brings the game window to the front first).
4. The app parks the mouse off the grid, takes a screenshot, finds the filled cells, hovers each one, reads its tooltip, reads its stack count, then puts the mouse back where it was.
5. Results appear in the window. The user can fix any cell flagged as uncertain, then export.

**Abort:** press Ctrl+Alt+X, move the mouse by hand (cursor more than 20px from where the tool put it), or let the game lose focus. Any of these stops the scan within 100 ms and shows partial results, labelled "ABORTED – partial".

## 4. Config (`config.json`, created on first run)
```
game_window_title_contains: "Neocron"
tesseract_path, hotkey_scan: "ctrl+alt+s", hotkey_abort: "ctrl+alt+x"
anchor_template: "calib/anchor.png", anchor_match_threshold: 0.85
grid_offset_from_anchor: [dx, dy], cell_size: [w, h], cell_pitch: [px, py]
rows: 10, cols: 5
empty_cell_template: "calib/empty_cell.png", empty_diff_threshold: <set by calibration>
qty_roi_in_cell: [x, y, w, h]          # bottom-left "x5" area
park_offset_from_anchor: [dx, dy]
hover_settle_ms: 120, tooltip_timeout_ms: 1500, tooltip_stable_frames: 2
```
Rough sizes at 1440p, from the user's screenshot: cell pitch about 145x72 px, grid of 5 columns by 10 rows. Calibration sets the real values.

## 5. Calibration (`python -m ntc calibrate` or the **Calibrate** button)
1. The user opens a cabinet that has at least one empty cell, moves the mouse away, and presses Ctrl+Alt+S (or the app counts down 3 seconds).
2. The app shows the screenshot scaled to fit, and the user drags three boxes in turn: (a) the **whole grid**, from the top-left of the first cell to the bottom-right of the last visible cell; (b) the **anchor**, which is the "Take All | Sort | Stack" button bar; (c) one **empty cell**.
3. Rows and columns default to 10 and 5 and can be edited. The cell pitch is the grid size divided by rows and columns.
4. The app saves `anchor.png`, `empty_cell.png`, and the offsets, and derives `empty_diff_threshold` from the gap between the filled and empty cells it sees.
5. It shows a preview with every cell outlined: green for filled, gray for empty. The user confirms, or redoes the calibration.

## 6. Detection pipeline
**6.1 Find the window:** use `cv2.matchTemplate` (TM_CCOEFF_NORMED) to find the anchor in the full screenshot. If the best score is below the threshold, report "Cabinet window not found". The grid origin is the anchor position plus `grid_offset_from_anchor`, so the cabinet window can be anywhere on screen.

**6.2 Filled vs empty:** for each cell, take the interior crop (2px inset) and compute the mean absolute difference from the empty template. The cell is filled if that is above `empty_diff_threshold`.

**6.3 Stack quantity:** crop `qty_roi_in_cell` and keep only bright pixels (text is near-white, about 200+ on every channel). Upscale 4x, then run Tesseract with `--psm 7` and the whitelist `x0123456789`.
- Result matches `^x(\d{1,3})$`: that number is the quantity.
- No bright text: quantity is 1.
- Anything else: quantity is 1 with the flag `QTY_UNCERTAIN`.

**6.4 Tooltip (per filled cell):**
- Move the cursor to the cell center, wait `hover_settle_ms`, then poll the capture every 50 ms.
- Search region: cursor x ±450 px, y from cursor to cursor+100 px.
- The tooltip is a near-black rectangle (every channel below 30) with white text and a light border. Take the largest such component that is 18–45 px tall and at least 60 px wide.
- **Valid** only if its horizontal span contains the current cursor x. This rejects the stale tooltip from the previous cell.
- **Stable:** the same crop, pixel-identical, for `tooltip_stable_frames` captures in a row.
- OCR: invert, upscale 3x, Tesseract `--psm 7`. Collapse whitespace and trim.
- Timeout: nudge the cursor 6 px and retry once. If it still fails, the name is `"?"` with the flag `NAME_UNREAD`.

**6.5 Name normalization (`known_items.json`):** fuzzy-match the OCR text (`difflib` ratio of at least 0.90) against known names and use the match if found. Otherwise accept it as a new name, flag it `NEW_NAME`, and add it to the known list. User corrections (§8) save an alias mapping the raw OCR text to the corrected name.

## 7. Mouse control
- Moves go through `SendInput`, using absolute coordinates normalized to 0..65535 across the virtual desktop. If Phase 0 shows the game ignores that, fall back to relative `MOUSEEVENTF_MOVE`, selected by `mouse_mode` in config.
- **No click or button events, ever.** This is enforced by a single `move_to(x, y)` function, the only input function in the codebase.
- Before scanning: save the cursor position, park it at `park_offset_from_anchor`, and wait 150 ms so no tooltip covers the grid. Then take the grid screenshot that 6.2 and 6.3 use.
- Hover order: row-major, filled cells only. After the scan, restore the original cursor position.
- Before each move, check the abort conditions in §3.

## 8. UI (tkinter, always on top, about 420x520, resizable)
- Status line: Ready / Scanning 7 of 23… / Done in 6.2 s / error text.
- Buttons: **Scan**, **Calibrate**, **Export ▾** (Copy to clipboard, Save CSV, Save TXT, Save JSON).
- Table (Treeview) with columns Item and Qty, one row per unique normalized name, sorted by name. Rows containing a flagged cell are highlighted yellow.
- Double-clicking a row opens its cells. Each cell's name and quantity can be edited there; edits recompute the totals and teach `known_items.json`.
- Footer: `Total: <sum qty> items in <filled cells> slots · <unique> unique`. Warnings appear here, for example "Last row has items — the cabinet may scroll; items below are not counted", "2 cells uncertain", "ABORTED – partial".

## 9. Exports
Files go to `exports/` by default, through a save dialog prefilled with `cabinet_YYYYMMDD_HHMMSS.<ext>`.
- **Clipboard:** tab-separated `Item<TAB>Qty` lines plus a `TOTAL` line, so it pastes cleanly into a spreadsheet.
- **CSV:** `scan_time,item,qty`, UTF-8 with header.
- **TXT:** aligned columns for Discord or notes, plus a total line.
- **JSON:** the full ScanResult (§10), including per-cell data and flags.

## 10. Data model (`ntc/models.py`)
```
CellRead(row, col, name, raw_ocr, qty, flags: list[str])
ScanResult(started_at, duration_s, aborted: bool, cells: list[CellRead],
           totals: dict[str,int], warnings: list[str])
```

## 11. Acceptance criteria
1. On saved 1440p fixture screenshots: filled/empty is 100% correct and stack quantity is 100% correct.
2. On saved tooltip fixtures: the normalized name matches exactly, after the known-names list is seeded with each name once.
3. Live, a 20-item cabinet scans in 10 s or less, with totals matching a manual count.
4. The mouse is never clicked, and is returned to its original position (±2 px) on success and on abort.
5. Moving the mouse by hand during a scan aborts within 100 ms.
6. If the cabinet isn't open, the app shows "Cabinet window not found" and never moves the mouse.
7. All four exports produce the documented formats.

---

# Implementation plan (for Sonnet)

## Layout
```
SPEC.md  README.md  requirements.txt  config.json(generated)
ntc/__main__.py    # CLI: (default) app | calibrate | capture | scan-image <png>
ntc/winapi.py      # ctypes: DPI awareness, SendInput move_to, GetCursorPos, foreground title, RegisterHotKey thread
ntc/capture.py     # mss full-screen grab -> numpy BGR
ntc/config.py      # load/save/defaults
ntc/calibrate.py   # tk box-drag calibration (§5)
ntc/grid.py        # anchor find, cell rects, filled detection, qty OCR (§6.1–6.3)
ntc/tooltip.py     # tooltip locate/validate/stabilize/OCR (§6.4)
ntc/ocr.py         # pytesseract wrappers + preprocessing
ntc/names.py       # known_items.json fuzzy match + aliases (§6.5)
ntc/scanner.py     # orchestration + abort (§3, §7)
ntc/export.py      # 4 exporters (§9)
ntc/app.py         # tk UI (§8)
ntc/models.py
tests/fixtures/*.png   tests/test_grid.py test_tooltip.py test_names.py test_export.py
```

## Phases
0. **Feasibility spike (gate).** Write `winapi.py` and `capture.py`, plus a `capture` command: a hotkey saves full-screen PNGs to `tests/fixtures/`. Ask the user to save (a) the cabinet open with the mouse away from it, (b) 3–4 shots hovering different items, (c) at least one shot with `x2`/`x5` stacks. Then test whether `move_to` over a cell makes the game show its tooltip, in absolute mode and then in relative mode. **If neither works, stop and report to the user before going further.**
1. Write `config.py`, `calibrate.py`, `models.py`, and SPEC.md.
2. Write `grid.py` and `ocr.py`, and the `scan-image` command for offline runs that also dump debug crops to `debug/`. Make `test_grid.py` pass against the fixtures.
3. Write `tooltip.py` and `names.py`, and make `test_tooltip.py` and `test_names.py` pass.
4. Write `scanner.py`, with the abort logic and the cursor save/restore.
5. Write `app.py` and `export.py`, and make `test_export.py` pass.
6. Write the README (install Tesseract, `pip install -r requirements.txt`, calibrate, scan, the admin note).

## Verification
- `pytest` passes, with grid, quantity, tooltip, and names checked against the real fixtures.
- `python -m ntc scan-image tests/fixtures/<cabinet>.png` prints the filled cells and quantities, which match the screenshot by eye.
- Live: the user opens a cabinet and presses Ctrl+Alt+S. Totals match a manual count, the mouse returns to its start position, a hand-move aborts, and every export opens correctly.
