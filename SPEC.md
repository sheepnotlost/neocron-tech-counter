# Neocron Tech Counter — SPEC (source of truth)

## 1. Scope
**In:** count every item in an open cabinet or inventory window, scrolling to the bottom, window, using full item names from tooltips and stack quantities; show results in a small always-on-top window; keep **named lists that accumulate scans across several cabinets and across restarts** (section 13); export them.
**Out (v1):** reading game memory or packets, clicking, moving items, other windows (bank, trade, vendors), a HUD Scale other than the current 2.0 or a resolution other than 2560x1440 (detection scales its pitches with screen height but this is untested), and multi-cell items.

## 2. Environment
- Windows 10, Python 3.14, game borderless fullscreen at **2560x1440**.
- The process calls `SetProcessDpiAwareness(2)` at startup, so all coordinates are physical pixels.
- If the game runs as administrator, the tool must also run as administrator, because Windows blocks synthetic input into elevated windows. The README must say this.
- Dependencies: `mss`, `numpy`, `opencv-python`, `Pillow`, `pytesseract`, and `pytest` for development. UI is `tkinter` (stdlib). Hotkeys and mouse go through `ctypes` (`RegisterHotKey`, `SendInput`, `GetCursorPos`, `GetForegroundWindow`), with no extra packages.
- External: the Tesseract-OCR binary (UB Mannheim Windows installer). The path is set in config, defaulting to `C:\Program Files\Tesseract-OCR\tesseract.exe`. If it's missing, the app shows a clear error with the install link.

## 3. User flow
1. Start the app with `python -m ntc`. A small always-on-top window appears. **There is no calibration step.**
2. In game, open a cabinet and/or the inventory, then press **Ctrl+Alt+S**, or click **Scan** in the app (the app brings the game window to the front first). The **Scan:** dropdown picks `all` (default), `cabinet` or `inventory`.
3. For each window found the app: parks the mouse off the windows, scrolls the window to the top, reads the visible slots, hovers each filled slot to read its tooltip, scrolls down, and repeats until the view stops changing. It then restores the mouse to where it was.
4. Results are added to the active list as one entry per window ("Cabinet N", "Inventory N"), see section 13.

**Abort:** press Ctrl+Alt+X, move the mouse by hand (cursor more than 20px from where the tool put it), let the game lose focus, or close the app (it stops the scan and puts the mouse back before closing). Any of these stops the scan within 100 ms and shows partial results, labelled "ABORTED - partial".

## 4. Config (`config.json`, only values that differ from the defaults are stored)
```
game_window_title_contains: "Neocron Evolution"   # NOT just "Neocron": that also matches this app's own window
tesseract_path, hotkey_scan: "ctrl+alt+s", hotkey_abort: "ctrl+alt+x"
scan_target: "all" | "cabinet" | "inventory"
log_items: "all" | "techs"      # techs = only "<Part> Part Of <weapon>" items are recorded
mouse_mode: "absolute"   # "relative" is inaccurate on this PC (Windows pointer acceleration)
scroll_notches: 2, scroll_settle_ms: 200, scroll_park_ms: 150, max_scroll_frames: 60
hover_settle_ms: 30, tooltip_timeout_ms: 1500, tooltip_probe_ms: 500, tooltip_stable_frames: 2
```
(The old calibration keys and `calib/` templates are gone; nothing about window position or size is stored.)

## 5. Finding and reading windows (no calibration, any HUD color)
The game has 14+ HUD colors (Options > HUD Color) and the windows can be dragged anywhere, so nothing is stored about where a window is or what color it is. Fixed constants (1440p; scaled by screen height / 1440): cabinet slot pitch 144.2 x 72, 5 columns x 10 rows; inventory slot pitch 70 x 72, 8 columns x 6 rows. These windows have a fixed size, so only the alignment of the grid is searched, not its extent.

**5.1 Finding a window (`ntc/detect.py`).** A window is a mesh of thin dark grid lines. Line contrast ranges from strong (mint) to about 5 gray levels (navy), so nothing thresholds a single pixel:
1. Convert to gray and equalise local contrast (CLAHE, clip 3, 16x16 tiles); without it the two navy themes cannot be found.
2. Build soft "dark thin line" evidence maps (thin lines, plus wide bands up to ~8 px: the inventory's row boundaries are 4-6 px thick) at half resolution.
3. Score every position by the evidence that lines up on a lattice of the **full window extent** (5x10 or 8x6), using the minimum of neighbouring lines so a lattice that fits only every other line scores zero (a 72 px lattice laid over a 144 px window). Thin and wide maps are each normalised by their own 99.9th percentile, then added.
4. Refine the 6 best peaks per window type: fit line offsets (median over lines, pitch clamped to nominal +/- 0.4 px), choose the best 1-row/1-column alignment using ALL lines (a lattice shifted by one row has as many real interior lines, but its extra outer line falls on empty space), then slide it +/- 4 px to the centre of the dark bands.
5. Keep a candidate only if its **consistency** (weakest-quartile interior line evidence / median) is >= 0.5. Measured: real windows >= 0.58, background clutter <= 0.43.
6. Drop windows that overlap a better one. A window covered by another window (for example the Options window) is correctly not reported.
Measured on 14 full-resolution captures (one per HUD color): the cabinet is found in 14/14 and the inventory in 12/12 uncovered ones, within 3 px of the true position in all but one navy variant (10 px off; recorded as a known failure in the tests). Detection takes about 1 s.

**5.2 Which slots hold items (`ntc/slots.py`).** A slot is a *candidate* if its label corner (3,3,64x30 inside the slot) contains at least one letter-shaped blob (6-22 px tall, 2-18 wide, not touching the crop edge, found by local contrast so any text color works), or if the slot is visually busy (std/mean of its blurred interior >= 0.18). Measured over 1,226 slots in 12 themes: 0 filled slots missed, 7% of empty slots are extra candidates. The hover resolves them: a **strong** candidate (>= 2 letter blobs) with no tooltip is kept as an unreadable item (`NAME_UNREAD`); a **weak** candidate with no tooltip within `tooltip_probe_ms` is an empty slot and is dropped. (Whole-slot texture alone is unreliable: in the navy themes the window is so see-through that the wall behind it adds texture to empty slots.)

**5.3 Stack numbers.** Every theme draws text with a black drop shadow, and the pixels just up-left of shadow pixels are the text, so the text color is sampled from the slot's own label (a brightness test picks the icon instead in the red theme, where the text is darker than the icon's gray pixels). In the stack area (2,38 / 44x32 inside the slot, narrowed to 28 px wide on a second try because some icons reach toward the text) keep pixels closer to the text color than 0.35 x (text-to-background distance), upscale 4x, run Tesseract `--psm 7` with whitelist `x0123456789`, and accept only `x<1-3 digits>`. The "x" is required: without it 4% of slots with no number read icon edges as digits. No number means a quantity of 1. Measured: 140 of 143 stacks right in 11 themes, 0 phantom numbers.

**5.4 Scrolling.** The mouse wheel scrolls these windows (measured live: 2 rows per notch; the scan uses `scroll_notches` = 2, i.e. 4 rows per step, which fits both windows: the inventory shows 6 rows, the cabinet 10, so consecutive screens always overlap). The scan:
1. Parks the mouse on a spot outside every window.
2. Scrolls up (3 notches at a time) until the view stops changing, so the scan always starts at the top.
3. Reads the visible rows, then scrolls down one notch, and measures how many rows the content moved by comparing a small signature of each row between the two screenshots. 0 = the view did not change (bottom reached). A match that is not good enough = the scan stops with the warning "Lost track of the scrolling". Rows are numbered globally (visible row + rows scrolled), so no row is read twice and none is skipped.
4. Stops after `max_scroll_frames` screens with a warning.
If the first scroll changes nothing and the last visible row has items, the result warns "This window did not scroll" (all items visible, or the wheel is not supported).
Input functions in `ntc/winapi.py` are `move_to` and `wheel`. There are no clicks.

## 6. Tooltips and names
**6.1 Tooltip (per candidate slot):**
- Move the cursor to the cell center, wait `hover_settle_ms`, then poll a **region grab** every 20 ms (a full-screen grab costs about 114 ms, the region about 5 ms).
- Search region: cursor x ±450 px, y from cursor to cursor+100 px.
- Measured on the real game: the tooltip is a pure-black rectangle with a **1 px border of exactly gray (221,221,221)**, about 30 px tall. Detection looks for long horizontal border lines (at least 60 px, tolerance ±4 per channel) and pairs a top line with a bottom line of the same x and width, 18–45 px apart. (Detecting by black pixels fails: the black grid lines merge with the box.)
- **Valid** only if the box's horizontal span contains the current cursor x. The game also hides the old tooltip as soon as the mouse moves and shows the new one after about 120–190 ms, so a stale tooltip is not read.
- **Stable:** the same crop, pixel-identical, for `tooltip_stable_frames` polls in a row.
- OCR (in a background thread while the mouse moves to the next cell): crop the box with only its 1 px border removed (letters with descenders - g, y, comma - reach the bottom edge; a 3 px trim turned "Dog Tag" into "Doa Taa"), invert, upscale 3x, Tesseract `--psm 7`. Collapse whitespace and trim.
- Timeout: nudge the cursor (+6, +3) px and retry once. If it still fails, the name is `"?"` with the flag `NAME_UNREAD`.

**6.2 Name normalization (`known_items.json`):**
1. An exact alias match (case-insensitive) wins.
2. For names shaped "<Part> Part Of <Weapon>", fuzzy-correct the part word against the known part types (Component, Hull, Additional Technology, Technology, Core, Frame) at ratio >= 0.8.
3. Merge into an already-known name **only if the two differ solely by characters the OCR mixes up** (g/a, g/v, y/v, 0/o, 1/l, 1/i, i/l, 5/s, 8/b, u/v, c/e) and have the same length; for "Part Of" names the part word must also be identical. Names that differ in a digit or any other letter never merge: dog tags differ only in their numbers ("51/ 56" vs "51/ 58"), and "II" vs "III" differ in length. (An earlier ratio >= 0.92 rule merged "Frame Part Of HOLY DEFLECTION" into "Core Part Of HOLY DEFLECTION".)
4. Otherwise accept it as a new name, flag it `NEW_NAME`, and add it to the known list. `NEW_NAME` is informational: it is not highlighted and not counted as uncertain.
User corrections (section 8) save an alias mapping the raw OCR text to the corrected name.

**6.3 What gets logged (`log_items`).** `all` records every item. `techs` records only techs: names shaped "<Part> Part Of <weapon>" where the part is Component, Hull, Additional Technology, Technology, Core or Frame (also for names you corrected earlier). Everything else is dropped after its tooltip is read, is not added to `known_items.json`, and is counted in a footer note ("N other item(s) not logged (techs only)"). An item whose name could not be read is kept (flag `NAME_UNREAD`), because it might be a tech.

**Label skip (techs only, `ntc/slots.py`).** With `log_items = techs`, a slot is not hovered at all when its short label says it is not a tech. Techs show one of the labels COMP, HULL, ATP, CORE, FRAM, TECH (same in every HUD color). The label corner is OCRed (letters only, same text-color mask as the stack number) for all new candidate slots of a screen in the background pool before hovering. A slot is skipped only if the text is the known non-tech label **ULT** (built-in list `KNOWN_NON_TECH`; too close to HULL for the distance rule) or is **at least 3 letters long and at edit distance >= 3 from every tech label**. Near-misses ("LUMP", "AIP", "HRAM", "CRE") and every short or empty read are still hovered. Skipped slots count in the "other item(s) not logged" note. Measured over 13 HUD colors (more than 500 tech slots): no tech slot is skipped; the non-tech "ULT" slots are. A label read with a gap inside ("L C") counts as garbled and is hovered. With `log_items = all` nothing is skipped.

## 7. Mouse control
- Moves go through `SendInput`, using absolute coordinates normalized to 0..65535 across the virtual desktop (`mouse_mode` in config; relative mode is inaccurate here).
- **No click or button events, ever.** The only input functions in the codebase are `move_to(x, y)` and `wheel(notches)` (scrolling item windows).
- Before reading a window: save the cursor position, park the mouse on a spot outside every window, wait 250 ms so no tooltip covers the slots, then take the screenshot that section 5 reads.
- Hover order: row-major, candidate slots of newly seen rows only. After the scan, restore the original cursor position.
- Before each move, check the abort conditions in §3.

## 8. UI (tkinter, always on top, 560x700, placed at the right screen edge)
- Status line: Ready / Scanning inventory: screen 2, slot 7 of 18 / Added Cabinet 3 (27 items), Inventory 1 (134 items) to 'Techstorage' in 51 s / error text.
- Buttons: **Scan**, **Undo last scan**, **Export ▾**; a second row with the **Scan:** dropdown (`all`, `cabinet`, `inventory`) and the **Log:** dropdown (`all items`, `techs only`), both remembered; export menu items: Copy to clipboard, Save CSV, Save CSV by cabinet, Save TXT, Save JSON. There is no Calibrate button.
- Table (Treeview) with columns Item and Qty, one row per unique normalized name, sorted by name. **It shows the combined totals of the active list (section 13), not just the last scan.** Rows containing a cell flagged `QTY_UNCERTAIN` or `NAME_UNREAD` are highlighted yellow; new names are reported in the footer only.
- Editing of names and quantities happens in the scan editor of section 13 (double-click a scan).
- If the global hotkeys are already taken (for example the app is open twice), the status line says so and points to the Scan button.
- Footer: `Total: <sum qty> items in <slots> slots across <n> scans · <unique> unique`, plus the warnings of the last scan, for example "This window did not scroll...", "2 cells uncertain", "ABORTED - partial".

## 9. Exports
Files go to `exports/` by default, through a save dialog prefilled with `<list name>_YYYYMMDD_HHMMSS.<ext>`. **Every export says which cabinet(s) hold each item**: just `Cabinet 4` when the item is in one place (the Qty column already gives the number), otherwise the split, `Cabinet 1 (2), Inventory 1 (1)`; the label is the scan's name, so renaming a scan ("Safe house") shows up in the export.
- **Clipboard:** tab-separated `Item<TAB>Qty<TAB>Where` with a header line, plus a `TOTAL` line, so it pastes cleanly into a spreadsheet.
- **CSV:** `scan_time,item,qty,cabinets`, UTF-8 with header.
- **CSV by cabinet:** `list,cabinet,scan_time,item,qty`, one row per item per cabinet.
- **TXT:** aligned columns for Discord or notes (item, qty, where), plus a total line.
- **JSON:** the full result (section 10), per-cell data and flags, a `where` map (`item -> [{cabinet, qty}]`) and the list's entries.
Called without location data, the exporters keep the old three-column format.

## 10. Data model (`ntc/models.py`)
```
CellRead(row, col, name, raw_ocr, qty, flags: list[str])      # row is the global row (visible row + rows scrolled)
ScanResult(started_at, kind: "cabinet"|"inventory", duration_s, aborted: bool, cells: list[CellRead],
           totals: dict[str,int], warnings: list[str])
```
`Scanner.scan(target, progress)` returns one ScanResult per window scanned.

## 11. Acceptance criteria
1. On the 14 full-resolution HUD-color captures: the cabinet is found in all; the inventory in all that are not covered by another window (one navy variant is a known 10 px misalignment); a window covered by another window is not reported; with no window open nothing is reported.
2. No filled slot is missed in any theme; stack numbers read right in at least 97% of cases and a slot without a number never reads as one.
3. On saved tooltip fixtures: the normalized name matches exactly. Names that differ in a digit never merge.
4. Live (default HUD, 2026-10-06): a cabinet of 20 items scans in about 6 s; an inventory of 99 slots over 3+ screens in about 45 s; totals match a manual count.
5. The mouse is never clicked, and is returned to its original position (±2 px) on success and on abort.
6. Moving the mouse by hand during a scan aborts within 100 ms.
7. If no window is open, or the game cannot be brought to the front, the app says so and never moves the mouse.
8. A window that starts scrolled to the middle is scanned from the top to the bottom with no row skipped and none counted twice.
9. All exports produce the documented formats. Lists: see the acceptance criteria in section 13.

## 12. Findings from the real game (measured 2026-10-06)
- Programmatic absolute mouse moves (`SendInput`) make the game show tooltips; relative moves are distorted by pointer acceleration. Tooltips appear 120-190 ms after the mouse stops and disappear as soon as it moves.
- The game ignores a click that is pressed and released instantly; a click needs about 150 ms between press and release (relevant only to testing tools; the app never clicks).
- The mouse wheel scrolls the cabinet and the inventory, 2 rows per notch. Scrolling up 3 notches at a time reaches the top.
- Cabinet slot pitch 144.2 x 72 (5 x 10); inventory slot pitch 70 x 72 (8 x 6) with 4-6 px thick row boundaries. The cabinet window is slightly see-through: the world behind it changes the look of empty slots (more so in the navy themes).
- The tooltip is a black box with a 1 px border of exactly gray (221,221,221), about 30 px tall; descenders reach its bottom edge.
- Stack numbers ("x2") sit at the bottom-left of a slot and, for large counts (x14), overlap the icon. Text is drawn with a black drop shadow in every theme; its color varies (white, cream, green, red, orange).
- HUD Color 0-13+ (Options window, with the - / + buttons). Themes differ in hue, brightness and window transparency; the later ones are variations of green.
- The game window title is "Neocron Evolution"; "Neocron" alone also matches this app's window.
- The results window sits at the right screen edge so it never covers the windows or their tooltips.

## 13. Persistent lists (added 2026-10-06)
**Goal:** scan several cabinets in a row and keep one running list, which survives closing the app.

**Model.** A *list* has a name and an ordered set of *entries*. An entry is one scanned cabinet (`source: "scan"`) or a hand-made entry (`source: "manual"`). An entry holds cells (`row, col, name, raw_ocr, qty, flags`; `row` and `col` are null for manual cells). The list's total for an item is the sum of its quantity over all entries. Stored in `lists.json` in the project folder:
```
{"active": "<list name>",
 "lists": {"<name>": {"created": iso,
                      "entries": [{"id", "label", "source", "time", "partial", "cells": [...]}]}}}
```
**Behaviour.**
1. The app always has an active list. On first run it creates one named "Default".
2. **Lists:** New (asks for a name, becomes active), Rename, Delete (asks for confirmation; deleting the last list creates a new empty "Default"). Names are trimmed, 1–40 characters, unique ignoring case. A selector switches the active list.
3. **Scans are added automatically** to the list that was active when the scan started, as a new entry labelled "Cabinet N", where N is one more than the highest "Cabinet N" already in that list (1 if there is none). Deleting the latest scan therefore frees its number, deleting one in the middle renumbers nothing, and entries you renamed or made by hand are ignored. A partial scan counts as its number. An aborted scan is added too and marked "(partial)". A scan that finds no cells (for example "Cabinet window not found") adds nothing.
4. **Undo last scan** removes the entry added by the most recent scan of this session. It is disabled when there is nothing to undo, and after it is used once.
5. **Scans in this list:** a table of the active list's entries (label, item count, slots, time). Per entry: Rename, Delete (asks for confirmation), Edit. **Add manual entry** creates an empty entry and opens its editor.
6. **Entry editor:** each cell's name and quantity can be changed, a cell can be removed, and a row can be added. Applying recomputes the totals, clears the cell's flags, and teaches `known_items.json` (raw OCR text to corrected name) as in section 8. Quantity must be a whole number of at least 1.
7. **Double-clicking an item** in the totals table shows which entries contain it and how many in each.
8. **Every change is saved immediately** (write to a temporary file, then replace). If `lists.json` is unreadable, it is renamed to `lists.json.bad` and the app starts with a new "Default" list.
9. **Exports** (clipboard, CSV, TXT, JSON) use the active list's combined totals, with the list name in the file name. Two additions: **CSV by cabinet** (`list,cabinet,scan_time,item,qty`, one row per item per entry) and the JSON export includes the list's entries.
10. The results window shows the list name and a footer `Total: <qty> items in <slots> slots across <n> scans · <unique> unique`.

**Acceptance criteria.**
- L1. After scanning two cabinets into one list, the totals equal the sum of both scans.
- L2. Closing and reopening the app restores all lists, entries, and the active list.
- L3. Undo removes exactly the last scan's entry and the totals drop by that scan.
- L4. Deleting or editing an entry updates the totals and survives a restart.
- L5. Deleting a list never touches other lists; deleting the last list leaves an empty "Default".
- L6. A corrupt `lists.json` never crashes the app and is preserved as `lists.json.bad`.
- L7. Clipboard, CSV, TXT, JSON and CSV-by-cabinet exports match the list totals.


## 14. Reference data: tech set requirements (added 2026-10-06)
`data/tech_sets.json` (and the readable `data/tech_sets.md`) hold which parts complete each Neocron rare, taken from https://rares.techhaven.org/en/list-rares on 2026-10-06: 86 items in 14 categories. Each record has `name`, `key`, `group`, `requirements`, `part_kind` (L/T/E-Part), `parts_needed`, `tech_level`, `needs` (a subset of Technology, Hull, Frame, Core, Component, Additional Technology) and `info_url`. 67 items need all six parts, 19 need five (no Additional Technology).
- An in-game tech name `<Part> Part Of <item>` matches a record when `key(item) == record.key`, where `key` lowercases, deletes dots and apostrophes and turns other punctuation into a space ("STEINER FP 1.0" = "Steiner F.P 1.0"). All 71 weapon names in the user's list matched.
- The data is for a future "which sets can I complete" feature; nothing in the app reads it yet. Refresh by re-fetching the source page.

## 15. Sets: which rares can I complete (added 2026-10-06)
Uses the data of section 14 and the **active list** (all its scans together).
- **Matching.** A tech named `<Part> Part Of <item>` counts toward the rare whose `key` equals `key(item)`. Parts the list holds that no rare matches are reported as "not in the database" (never silently dropped).
- **Status per rare.** *Needs* = the part types of its record (5 or 6). *Have* = the needed parts the list holds (at least 1 each). *Missing* = needed parts it does not hold. *Complete sets* = the smallest quantity among the needed parts (0 if any is missing). A part type the rare does not need (for example Additional Technology on a five-part rare) is ignored.
- **Sets window** (button **Sets...** in the main window). Table columns: Item, Category, Status ("COMPLETE x2", "missing 1", ...), Have (n/N), Missing (the part names), sorted closest-to-complete first. A **Show** dropdown filters: `in progress` (default: at least one part held), `complete`, `missing 1`, `missing 2 or fewer`, `all`; a search box filters by name. Double-click a row for the part-by-part view: each needed part with a check or cross and, where held, the cabinets that hold it (`Cabinet 3 (2), Inventory 1`). **Copy** and **Save CSV** export the rows currently shown (`Item, Category, Status, Have, Missing, Where`).
- Pure logic lives in `ntc/sets.py` (no UI); the window only displays it.
- **Acceptance.** A rare with all needed parts is complete; one part short is "missing 1" naming that part; two copies of each part give "COMPLETE x2"; an unneeded part type is ignored; "STEINER FP 1.0" matches "Steiner F.P 1.0"; the bundled data has 86 rares with unique keys.


## 16. Look and window frame (added 2026-10-06)
Purely cosmetic; no behaviour of sections 1-15 changes. Code in `ntc/skin.py`.
- **Palette.** The game's mint-green HUD palette (sampled from HUD Color 0), pushed to brighter, more saturated "gem" tones, then brought down in brightness and covered with a light **matte film** (a faint haze plus fine grain over the bright colour), so surfaces read like candy or jewel colour seen through frosted glass: saturated but soft, no hard glare. Buttons, headings and the header are gradient plates with a soft top gloss; glows are subtle.
- **Font.** Blinker (the game's HUD font) from `assets/fonts`, loaded privately for the process (no install). Falls back to the system font if missing.
- **Icon.** `assets/icon.ico` (the real tech sprite) as window and taskbar icon.
- **Window frame.** The main, Sets, Scan editor and Parts windows have no native title bar: a cut-corner (chamfered top-left and bottom-right) shape with a 1 px neon edge, a custom title bar (icon, title, minimise and close buttons), drag by the title bar, resize by the edges and the bottom-right grip, minimum size so nothing is cut off. The window still has a taskbar entry and is still always-on-top. Closing goes through the same close handler as before (stops a running scan first). If the frame cannot be installed (non-Windows API failure) the native frame is kept.
- The "Add manual entry" button and all other buttons must show their full text at the default size.

## 17. Speed (added 2026-10-06)
Techs-only label skip (section 6.3), 2-notch scrolling and shorter scroll waits (`scroll_settle_ms` 200, `scroll_park_ms` 150, wheel pre-wait 80 ms). Live target (NOT yet measured on the real game): an inventory of 99 slots over 3+ screens clearly faster than the 45 s measured with every item hovered; the 2-notch scroll and the shorter waits must be confirmed live (no skipped or doubled rows, no "Lost track of the scrolling").

## 18. Packaged .exe (added 2026-10-07)
`run_ntc.py` is the entry point and `python tools/build_exe.py` builds the one-file windowed `Neocron Tech Counter.exe` (about 83 MB, committed to the repository root so the repo is the whole package; GitHub's limit is 100 MB per file). It **bundles Tesseract**: only `tesseract.exe`, the DLLs it really loads (found by walking its imports: 26 of 51), with the DWARF debug sections removed (libtesseract 101 MB to 3 MB), and `eng.traineddata`. OpenCV's unused video library is left out. When frozen, `ocr.configure` prefers the bundled `tesseract/` folder (and sets `TESSDATA_PREFIX`), `config.ROOT` (config.json, lists.json, known_items.json, exports/) is the folder of the .exe, and `config.RES` (assets, data) is the bundle's temporary folder. Verified: the bundled Tesseract reads the labels of a cabinet capture (COMP, HULL, ATP, CORE, HULL), and the built .exe starts. Tesseract is Apache-2.0 licensed (see NOTICE.md).
